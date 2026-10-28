# -*- coding: utf-8 -*-
"""
阶段 3 测试：架构升级（SQLite 迁移与持久化 / 数据安全加固）
- 独立数据目录：预置旧 JSON → 验证自动迁移 → 并发写 → 重启不丢
- 单测部分（Flask test_client）：api_key 加密、登录失败锁定、token 过期
- 运行：python test_phase3.py
"""
import os
import sys
import io
import json
import time
import shutil
import socket
import sqlite3
import threading
import unittest
import subprocess
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DATA = os.path.join(BASE, "data")  # 正式数据（迁移前为 JSON，用作迁移来源）
TMP_DATA = os.path.join(BASE, ".test_data_phase3")
PORT = 8613
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


def start_server(data_dir):
    global SERVER_PROC
    env = dict(os.environ)
    env["TALENT_DATA_DIR"] = data_dir
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
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def login():
    code, raw = http("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert code == 200, "登录失败: %s %s" % (code, raw[:200])
    return json.loads(raw)["token"]


def setup_legacy_json():
    """把正式 JSON 数据复制到独立目录，模拟『旧版本 JSON 数据』"""
    if os.path.exists(TMP_DATA):
        shutil.rmtree(TMP_DATA)
    os.makedirs(TMP_DATA)
    for n in ("students", "jobs", "matches", "users", "settings"):
        src = os.path.join(SRC_DATA, n + ".json")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(TMP_DATA, n + ".json"))


class Phase3MigrateTest(unittest.TestCase):
    """任务 3.1：JSON → SQLite 自动迁移 + 功能全同 + 重启不丢 + 并发写"""

    @classmethod
    def setUpClass(cls):
        setup_legacy_json()
        start_server(TMP_DATA)

    @classmethod
    def tearDownClass(cls):
        stop_server()

    def test_auto_migrate(self):
        db_path = os.path.join(TMP_DATA, "app.db")
        self.assertTrue(os.path.exists(db_path), "应生成 app.db")
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM kv WHERE name='students'").fetchone()
            self.assertEqual(row[0], 48, "迁移学生数应为 48，实际 %s" % row[0])
        finally:
            conn.close()
        # 旧 JSON 保留作备份
        self.assertTrue(os.path.exists(os.path.join(TMP_DATA, "students.json")),
                        "迁移后原 JSON 应保留作备份")

    def test_api_after_migrate(self):
        tok = login()
        code, raw = http("GET", "/api/students", token=tok)
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(raw)["data"]), 48)
        code, raw = http("GET", "/api/jobs", token=tok)
        jobs = json.loads(raw)["data"]
        self.assertGreaterEqual(len(jobs), 6)
        code, raw = http("GET", "/api/dashboard", token=tok)
        self.assertEqual(code, 200)

    def test_concurrent_writes(self):
        tok = login()
        errors = []
        def worker(i):
            try:
                code, raw = http("POST", "/api/jobs", {
                    "name": "并发岗位-%d" % i, "type": "技术类", "desc": "", "major_req": [], "skill_req": [],
                    "weights": {"academic": 30, "honor": 10, "practice": 20, "sci": 25, "quality": 15},
                }, token=tok)
                if code != 200:
                    errors.append("job%s -> %s %s" % (i, code, raw[:120]))
            except Exception as e:
                errors.append("job%s -> %s" % (i, e))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], "并发写不应出错: %s" % errors[:3])
        code, raw = http("GET", "/api/jobs", token=tok)
        self.assertEqual(code, 200)

    def test_restart_keeps_data(self):
        stop_server()
        start_server(TMP_DATA)  # 用同一数据目录重启
        tok = login()
        code, raw = http("GET", "/api/students", token=tok)
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(raw)["data"]), 48, "重启后数据不丢")
        code, raw = http("GET", "/api/jobs", token=tok)
        names = [j["name"] for j in json.loads(raw)["data"]]
        self.assertTrue(any("并发岗位" in n for n in names), "并发写入的数据重启后仍在")


class Phase3SecurityTest(unittest.TestCase):
    """任务 3.2：API Key 加密 / 登录失败锁定 / token 过期（Flask test_client 单测）"""

    @classmethod
    def setUpClass(cls):
        os.environ["TALENT_DATA_DIR"] = TMP_DATA
        sys.path.insert(0, BASE)
        import server as srv
        cls.srv = srv
        cls.client = srv.app.test_client()

    def setUp(self):
        # 每个用例前清理会话与锁定状态
        self.srv.SESSIONS.clear()
        users = self.srv.get_users()
        for u in users:
            u["failed"] = 0
            u["locked_until"] = None
        self.srv.save_users(users)

    def test_api_key_encrypted_at_rest(self):
        srv = self.srv
        srv.save_settings({"dim_weights": srv.DEFAULT_SETTINGS["dim_weights"],
                           "deepseek": {"api_key": "sk-SECRET-123456", "base_url": "https://api.deepseek.com",
                                        "model": "deepseek-chat"}})
        conn = sqlite3.connect(srv.DB_PATH)
        try:
            row = conn.execute("SELECT payload FROM kv WHERE name='settings' AND key='__main__'").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertNotIn("sk-SECRET-123456", row[0], "SQLite 中不得出现 API Key 明文")
        # 读取时解密返回
        s = srv.get_settings()
        self.assertEqual(s["deepseek"]["api_key"], "sk-SECRET-123456", "读取时应解密出真实 Key")
        # 恢复
        srv.save_settings(srv.DEFAULT_SETTINGS)

    def test_login_lock_after_5_failures(self):
        c = self.client
        for i in range(5):
            r = c.post("/api/login", json={"username": "admin", "password": "wrong-pwd"})
            self.assertIn(r.status_code, (401, 423))
        # 第 6 次：即使密码正确也被锁定
        r = c.post("/api/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(r.status_code, 423, "锁定后正确密码也应拒绝")
        self.assertIn("锁定", r.get_json()["msg"])

    def test_token_expired(self):
        srv, c = self.srv, self.client
        expired = "deadbeef" * 4
        srv.SESSIONS[expired] = {"user": "admin", "exp": time.time() - 60}
        r = c.get("/api/jobs", headers={"X-Token": expired})
        self.assertEqual(r.status_code, 401, "过期 token 应返回未登录")
        self.assertNotIn(expired, srv.SESSIONS, "过期 token 应被清除")

    def test_fresh_token_works(self):
        c = self.client
        r = c.post("/api/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(r.status_code, 200)
        tok = r.get_json()["token"]
        r2 = c.get("/api/jobs", headers={"X-Token": tok})
        self.assertEqual(r2.status_code, 200, "有效 token 正常访问")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Phase3MigrateTest)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Phase3SecurityTest))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    stop_server()
    sys.exit(0 if result.wasSuccessful() else 1)
