# -*- coding: utf-8 -*-
"""
SQLite 存储层（阶段 3.1）
- 每张业务表以 kv(name, key, payload) 方式存储，payload 为实体 JSON，
  与既有 JSON 数据结构 1:1 兼容，避免嵌套字段规范化风险。
- 所有写操作走事务；启用 WAL 提升并发读写稳定性。
- 提供 migrate_from_json：把 data/ 下旧 JSON 一次性导入 app.db（JSON 原文件保留作备份）。
"""
import os
import json
import sqlite3
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
  name    TEXT NOT NULL,
  key     TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY (name, key)
);
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT
);
"""

_db_path = None
_lock = threading.Lock()


def _conn():
    if not _db_path:
        raise RuntimeError("db.py 尚未初始化：请先调用 init_db(path)")
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    """初始化数据库文件与表结构（幂等）"""
    global _db_path
    _db_path = path
    with _lock:
        conn = _conn()
        try:
            conn.executescript(_SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()
        finally:
            conn.close()


def load_list(name):
    """读取集合（students/jobs/matches/users/shares），返回 [{...}] 或 []"""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT payload FROM kv WHERE name=? ORDER BY rowid", (name,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["payload"]))
        except Exception:
            continue
    return out


def save_list(name, items):
    """整体替换集合（事务）"""
    with _lock:
        conn = _conn()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM kv WHERE name=?", (name,))
            for it in items:
                key = str(it.get("id", "")) if isinstance(it, dict) else ""
                conn.execute(
                    "INSERT INTO kv(name,key,payload) VALUES(?,?,?)",
                    (name, key, json.dumps(it, ensure_ascii=False)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def load_dict(name):
    """读取单实体（settings），返回 dict"""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT payload FROM kv WHERE name=? AND key='__main__'", (name,)).fetchone()
    finally:
        conn.close()
    if not row:
        return {}
    try:
        return json.loads(row["payload"])
    except Exception:
        return {}


def save_dict(name, d):
    with _lock:
        conn = _conn()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT OR REPLACE INTO kv(name,key,payload) VALUES(?,?,?)",
                (name, "__main__", json.dumps(d, ensure_ascii=False)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def migrate_from_json(data_dir, db_path):
    """把 data_dir 下的 JSON 文件导入 SQLite。返回 {集合名: 条数}"""
    init_db(db_path)
    counts = {}
    with _lock:
        conn = _conn()
        try:
            conn.execute("BEGIN")
            for name in ("students", "jobs", "matches", "users", "shares", "settings"):
                fp = os.path.join(data_dir, name + ".json")
                if not os.path.exists(fp):
                    continue
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if name == "settings":
                    conn.execute(
                        "INSERT OR REPLACE INTO kv(name,key,payload) VALUES(?,?,?)",
                        (name, "__main__", json.dumps(data, ensure_ascii=False)))
                    counts[name] = 1
                else:
                    conn.execute("DELETE FROM kv WHERE name=?", (name,))
                    for it in data:
                        key = str(it.get("id", "")) if isinstance(it, dict) else ""
                        conn.execute(
                            "INSERT INTO kv(name,key,payload) VALUES(?,?,?)",
                            (name, key, json.dumps(it, ensure_ascii=False)))
                    counts[name] = len(data)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return counts
