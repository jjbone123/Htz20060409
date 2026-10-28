# -*- coding: utf-8 -*-
"""
阶段 1 测试：答辩增强（PDF 导出 / AI 全量理由 / 学生端扫码分享 / 局域网启动参数）
- 使用独立数据目录 + 独立端口启动服务实例，不污染正式数据
- 运行：python test_phase1.py
"""
import os
import sys
import json
import time
import shutil
import socket
import unittest
import subprocess
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
TMP_DATA = os.path.join(BASE, ".test_data_phase1")
PORT = 8611
URL = "http://127.0.0.1:%d" % PORT
SERVER_PROC = None


def _wait_port(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def start_server():
    global SERVER_PROC
    if os.path.exists(TMP_DATA):
        shutil.rmtree(TMP_DATA)
    os.makedirs(TMP_DATA)
    env = dict(os.environ)
    env["TALENT_DATA_DIR"] = TMP_DATA
    SERVER_PROC = subprocess.Popen(
        [sys.executable, os.path.join(BASE, "server.py"),
         "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=BASE, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_port(PORT):
        SERVER_PROC.kill()
        raise RuntimeError("测试服务未能在 %d 秒内启动" % 30)


def stop_server():
    global SERVER_PROC
    if SERVER_PROC:
        SERVER_PROC.terminate()
        try:
            SERVER_PROC.wait(timeout=5)
        except subprocess.TimeoutExpired:
            SERVER_PROC.kill()
        SERVER_PROC = None


def http(method, path, data=None, token=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(URL + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def login():
    code, raw = http("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert code == 200, "登录失败: %s %s" % (code, raw[:200])
    j = json.loads(raw)
    assert j.get("ok") and j.get("token"), "登录返回缺少 token: %s" % raw[:200]
    return j["token"]


class Phase1PDFTest(unittest.TestCase):
    """任务 1.1：报告中心真实 PDF 导出"""

    def test_pdf_download(self):
        tok = login()
        # 先创建一条真实匹配记录（报告中心依赖匹配记录）
        code, raw = http("GET", "/api/jobs", token=tok)
        jobs = json.loads(raw)["data"]
        self.assertGreater(len(jobs), 0)
        code, raw = http("POST", "/api/match", {"job_id": jobs[0]["id"], "threshold": 60}, token=tok)
        self.assertEqual(code, 200)
        code, raw = http("GET", "/api/matches", token=tok)
        self.assertEqual(code, 200)
        matches = json.loads(raw)["data"]
        self.assertGreater(len(matches), 0, "创建匹配后应至少有一条记录")
        mid = matches[0]["id"]
        code, raw = http("GET", "/api/matches/%s/pdf" % mid, token=tok)
        self.assertEqual(code, 200, "PDF 接口应返回 200")
        self.assertTrue(raw.startswith(b"%PDF"), "响应应为 PDF 文件，实际头: %r" % raw[:8])
        self.assertGreater(len(raw), 1000, "PDF 应包含实际内容")
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("岗位智能匹配报告", text, "PDF 应包含中文标题（中文字体注册失败会丢字）")
        self.assertIn(matches[0]["job_name"], text, "PDF 应包含岗位名称")
        self.assertIn("适配分", text, "PDF 应包含明细表头")

    def test_pdf_404(self):
        tok = login()
        code, _ = http("GET", "/api/matches/not-exist/pdf", token=tok)
        self.assertEqual(code, 404)

    def test_pdf_requires_login(self):
        code, _ = http("GET", "/api/matches/whatever/pdf")
        self.assertEqual(code, 401)


class Phase1AITest(unittest.TestCase):
    """任务 1.2：AI 推荐理由全量覆盖（无 Key 降级 + 分批逻辑）"""

    def test_no_key_local_reasons(self):
        tok = login()
        code, raw = http("GET", "/api/jobs", token=tok)
        jobs = json.loads(raw)["data"]
        self.assertGreater(len(jobs), 0)
        code, raw = http("POST", "/api/match", {"job_id": jobs[0]["id"], "threshold": 60}, token=tok)
        self.assertEqual(code, 200)
        rec = json.loads(raw)["data"]
        self.assertFalse(rec["ai_enabled"], "未配置 Key 时 ai_enabled 应为 False")
        self.assertEqual(rec["ai_covered"], 0, "未配置 Key 时 ai_covered 应为 0")
        self.assertGreater(rec["matched_count"], 0)
        for r in rec["results"]:
            self.assertEqual(r["reason_source"], "local", "未配置 Key 时全部应为本地理由")
            self.assertTrue(r["reason"] and r["reason"].strip(), "理由不得为空")

    def test_batched_ai_reasons(self):
        # 单元级：注入模拟 Key 与模拟 AI 响应，验证分批调用与 ai_covered 统计
        sys.path.insert(0, BASE)
        os.environ["TALENT_DATA_DIR"] = TMP_DATA
        import server as srv
        srv.SESSIONS.clear()
        jobs = srv.get_jobs()
        job = jobs[0]
        settings = srv.get_settings()
        old_key = settings.get("deepseek", {}).get("api_key")
        old_calls = []

        def fake_reasons(job, cands, settings):
            old_calls.append(len(cands))
            return {c["id"]: "AI 模拟推荐理由（测试用）" for c in cands}

        srv.settings_write = settings
        srv.get_settings = lambda: settings
        settings.setdefault("deepseek", {})["api_key"] = "sk-test-fake"
        original = srv._deepseek_reasons
        srv._deepseek_reasons = fake_reasons
        try:
            rec = srv.run_match(job["id"], 60, operator="admin")
        finally:
            srv._deepseek_reasons = original
            if old_key is None:
                settings["deepseek"].pop("api_key", None)
        self.assertTrue(rec["ai_enabled"], "配置 Key 后 ai_enabled 应为 True")
        # 前 10 名候选人都应拿到 AI 理由
        self.assertEqual(rec["ai_covered"], 10, "应覆盖前 10 名候选人")
        self.assertGreater(len(old_calls), 0, "应发生分批 AI 调用")
        ai_reason_count = sum(1 for r in rec["results"][:10] if r["reason_source"] == "ai")
        self.assertEqual(ai_reason_count, 10, "前 10 名应全部是 AI 理由")


class Phase1ShareTest(unittest.TestCase):
    """任务 1.3：学生端扫码看画像（分享链接 / 公开只读 / 撤销 / 过期）"""

    def _create_share(self, tok, sid="S001"):
        code, raw = http("POST", "/api/students/%s/share" % sid, {}, token=tok)
        self.assertEqual(code, 200)
        j = json.loads(raw)
        self.assertTrue(j["ok"])
        d = j["data"]
        self.assertTrue(d["token"] and d["share_url"].endswith("?t=" + d["token"]))
        return d["token"]

    def test_share_flow(self):
        tok = login()
        token = self._create_share(tok)
        # 公开访问（无需登录）
        code, raw = http("GET", "/api/share/" + token)
        self.assertEqual(code, 200)
        d = json.loads(raw)["data"]
        self.assertTrue(d["name_masked"].startswith(d["name_masked"][0]), "姓名应脱敏")
        self.assertNotIn("student_no", d, "公开接口不得返回完整学号")
        self.assertNotIn("id", d, "公开接口不得返回内部学生 ID")
        self.assertIn("rating", d)
        self.assertIn("scores", d)
        # 详情接口应带分享状态
        code, raw = http("GET", "/api/students/S001", token=tok)
        d2 = json.loads(raw)["data"]
        self.assertTrue(d2["share"]["active"])
        self.assertEqual(d2["share"]["share_url"], "/view.html?t=" + token)
        # 撤销
        code, _ = http("DELETE", "/api/students/S001/share", token=tok)
        self.assertEqual(code, 200)
        code, raw = http("GET", "/api/share/" + token)
        self.assertEqual(code, 404, "撤销后链接应失效")

    def test_share_expired(self):
        tok = login()
        token = self._create_share(tok)
        # 把有效期改为过去（直接操作 SQLite 存储）
        sys.path.insert(0, BASE)
        import db as tdb
        tdb.init_db(os.path.join(TMP_DATA, "app.db"))
        shares = tdb.load_list("shares")
        self.assertTrue(shares, "分享记录应已入库")
        for sh in shares:
            sh["expires_at"] = "2000-01-01 00:00:00"
        tdb.save_list("shares", shares)
        code, raw = http("GET", "/api/share/" + token)
        self.assertEqual(code, 404)
        self.assertIn("过期", json.loads(raw)["msg"])

    def test_share_invalid_token(self):
        code, _ = http("GET", "/api/share/nonexistent-token")
        self.assertEqual(code, 404)

    def test_view_page_exists(self):
        code, raw = http("GET", "/view.html")
        self.assertEqual(code, 200)
        self.assertIn("学生能力画像", raw.decode("utf-8", "ignore"))


class Phase1LanTest(unittest.TestCase):
    """任务 1.4：局域网访问配置化（--host/--port 生效，0.0.0.0 可访问）"""

    def test_lan_args_effective(self):
        # 测试实例本身以 --host 0.0.0.0 --port 8611 启动
        code, _ = http("GET", "/")
        self.assertEqual(code, 200, "自定义端口实例应可访问")
        # 0.0.0.0 模式应同时可通过本机回环地址访问
        with urllib.request.urlopen("http://127.0.0.1:%d/" % PORT, timeout=5) as r:
            self.assertEqual(r.status, 200, "0.0.0.0 模式本机应可访问")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Phase1PDFTest)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase1AITest))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase1ShareTest))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase1LanTest))
    start_server()
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        stop_server()
    sys.exit(0 if result.wasSuccessful() else 1)
