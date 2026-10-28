# -*- coding: utf-8 -*-
"""
阶段 2 测试：功能完善（多轮匹配对比 / CSV 导出 / 删除保护）
- 独立数据目录 + 独立端口实例，不污染正式数据
- 运行：python test_phase2.py
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
TMP_DATA = os.path.join(BASE, ".test_data_phase2")
PORT = 8612
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
         "--host", "127.0.0.1", "--port", str(PORT)],
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
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def login():
    code, raw, _ = http("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert code == 200, "登录失败: %s %s" % (code, raw[:200])
    j = json.loads(raw)
    return j["token"]


class Phase2MatchCompareTest(unittest.TestCase):
    """任务 2.2：多轮匹配对比（同岗位多次匹配 + job_id 过滤）"""

    def setUp(self):
        self.tok = login()
        code, raw, _ = http("GET", "/api/jobs", token=self.tok)
        self.job = json.loads(raw)["data"][0]

    def test_same_job_multiple_matches(self):
        for t in (60, 80):
            code, raw, _ = http("POST", "/api/match", {"job_id": self.job["id"], "threshold": t}, token=self.tok)
            self.assertEqual(code, 200, "匹配应成功")
            rec = json.loads(raw)["data"]
            self.assertEqual(rec["job_id"], self.job["id"], "匹配记录应带 job_id")
            self.assertEqual(rec["threshold"], t)
        # 按岗位过滤
        code, raw, _ = http("GET", "/api/matches?job_id=" + self.job["id"], token=self.tok)
        self.assertEqual(code, 200)
        ms = json.loads(raw)["data"]
        self.assertEqual(len(ms), 2, "同岗位两次匹配应可过滤出 2 条")
        self.assertTrue(all(m["job_id"] == self.job["id"] for m in ms))
        thresholds = sorted(m["threshold"] for m in ms)
        self.assertEqual(thresholds, [60, 80], "两条记录的阈值应为 60 与 80")
        # 阈值不同则匹配人数不同（80 分阈值人数 <= 60 分阈值人数）
        d60 = next(m for m in ms if m["threshold"] == 60)
        d80 = next(m for m in ms if m["threshold"] == 80)
        self.assertGreaterEqual(d60["matched_count"], d80["matched_count"],
                                "阈值越高匹配人数越少或相等")


class Phase2CsvExportTest(unittest.TestCase):
    """任务 2.3：学生列表 CSV 导出（UTF-8 BOM，筛选联动）"""

    def test_csv_full(self):
        tok = login()
        code, raw, headers = http("GET", "/api/students/export.csv", token=tok)
        self.assertEqual(code, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        text = raw.decode("utf-8")
        self.assertTrue(text.startswith("\ufeff"), "CSV 应以 UTF-8 BOM 开头（Excel 不乱码）")
        lines = text.strip("\ufeff").splitlines()
        self.assertEqual(len(lines), 49, "48 名学生 + 1 行表头")
        self.assertEqual(len(lines[0].split(",")), 14, "表头应为 14 列")

    def test_csv_with_filter(self):
        tok = login()
        code, raw, _ = http("GET", "/api/students?rating=S", token=tok)
        s_count = len(json.loads(raw)["data"])
        self.assertGreater(s_count, 0, "测试数据应存在 S 级学生")
        code, raw, _ = http("GET", "/api/students/export.csv?rating=S", token=tok)
        text = raw.decode("utf-8")
        lines = [l for l in text.strip("\ufeff").splitlines() if l.strip()]
        self.assertEqual(len(lines) - 1, s_count, "筛选导出行数应与列表一致")
        # 抽查一行脱敏：第 2 列学号应形如 24***58
        import re
        sample = lines[1]
        no = sample.split(",")[1]
        self.assertRegex(no, r"^\d{2}\*{3}\d{2}$", "学号应脱敏")


class Phase2DeleteProtectTest(unittest.TestCase):
    """任务 2.4：删除岗位后历史匹配记录保留、报告仍可打开"""

    def test_delete_job_keeps_matches(self):
        tok = login()
        code, raw, _ = http("GET", "/api/jobs", token=tok)
        jobs = json.loads(raw)["data"]
        job = jobs[0]
        # 确保该岗位有匹配记录
        code, raw, _ = http("POST", "/api/match", {"job_id": job["id"], "threshold": 60}, token=tok)
        self.assertEqual(code, 200)
        rec = json.loads(raw)["data"]
        mid = rec["id"]
        code, raw, _ = http("GET", "/api/matches?job_id=" + job["id"], token=tok)
        n_before = len(json.loads(raw)["data"])
        # 删除岗位
        code, raw, _ = http("DELETE", "/api/jobs/" + job["id"], token=tok)
        self.assertEqual(code, 200, "岗位应可删除")
        # 历史记录保留且报告详情可打开
        code, raw, _ = http("GET", "/api/matches?job_id=" + job["id"], token=tok)
        self.assertEqual(len(json.loads(raw)["data"]), n_before, "删除岗位不影响历史记录")
        code, raw, _ = http("GET", "/api/matches/" + mid, token=tok)
        self.assertEqual(code, 200, "历史报告详情仍可打开")
        self.assertEqual(json.loads(raw)["data"]["job_name"], job["name"], "报告保留岗位名快照")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Phase2MatchCompareTest)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase2CsvExportTest))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase2DeleteProtectTest))
    start_server()
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        stop_server()
    sys.exit(0 if result.wasSuccessful() else 1)
