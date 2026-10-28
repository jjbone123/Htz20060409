# -*- coding: utf-8 -*-
"""
轻量化 AI 驱动校园人才快速筛选系统 —— 本地服务端
运行方式：双击「启动系统.bat」，或命令行执行 python server.py
数据全部保存在本机 data/ 目录，重启不丢失。
"""
import sys, os, io, json, time, uuid, hashlib, secrets, random, csv, threading, webbrowser

# Windows 控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 支持环境变量指定数据目录（测试/多实例用），默认仍为应用目录下的 data/
DATA_DIR = os.environ.get("TALENT_DATA_DIR") or os.path.join(BASE_DIR, "data")
EXPORT_DIR = os.path.join(BASE_DIR, "export")
STATIC_DIR = os.path.join(BASE_DIR, "static")
for d in (DATA_DIR, EXPORT_DIR, STATIC_DIR):
    os.makedirs(d, exist_ok=True)

DIMS = ["academic", "honor", "practice", "sci", "quality"]
DIM_NAMES = {"academic": "学业", "honor": "荣誉", "practice": "实践", "sci": "科创", "quality": "综合素质"}

RATING_RULES = [  # (最低分, 等级, 中文)
    (85, "S", "S"),
    (70, "A", "A"),
    (55, "B", "B"),
    (0, "C", "C"),
]

# 相关专业分组（用于专业匹配度的“相关专业”判断）
MAJOR_GROUPS = {
    "计算机类": ["计算机科学与技术", "软件工程", "人工智能", "数据科学与大数据技术", "物联网工程", "网络工程", "信息安全", "智能科学与技术"],
    "电子信息类": ["电子信息工程", "通信工程", "电子科学与技术", "微电子科学与工程", "集成电路设计与集成系统"],
    "机械自动化类": ["机械设计制造及其自动化", "自动化", "电气工程及其自动化", "机器人工程", "智能制造工程"],
    "经管类": ["工商管理", "市场营销", "人力资源管理", "会计学", "国际经济与贸易", "电子商务"],
    "艺术设计类": ["视觉传达设计", "环境设计", "数字媒体艺术", "产品设计"],
}
def _major_group(major):
    for g, ms in MAJOR_GROUPS.items():
        if major in ms:
            return g
    return None

# ============================================================
# 数据存储（SQLite 持久化，阶段 3.1；JSON 迁移后保留作备份）
# ============================================================
import db as _db
DB_PATH = os.path.join(DATA_DIR, "app.db")
_db.init_db(DB_PATH)

# ---------- 敏感字段加密（阶段 3.2：Fernet） ----------
KEY_FILE = os.path.join(DATA_DIR, "secret.key")
_fernet = None

def _get_fernet():
    global _fernet
    if _fernet is None:
        from cryptography.fernet import Fernet
        if not os.path.exists(KEY_FILE):
            with open(KEY_FILE, "wb") as f:
                f.write(Fernet.generate_key())
        with open(KEY_FILE, "rb") as f:
            _fernet = Fernet(f.read())
    return _fernet

def _enc_secret(v):
    return "enc:" + _get_fernet().encrypt(v.encode("utf-8")).decode("utf-8")

def _dec_secret(v):
    if isinstance(v, str) and v.startswith("enc:"):
        return _get_fernet().decrypt(v[4:].encode("utf-8")).decode("utf-8")
    return v  # 兼容未加密的旧数据

def get_users(): return _db.load_list("users")
def save_users(v): _db.save_list("users", v)
def get_students(): return _db.load_list("students")
def save_students(v): _db.save_list("students", v)
def get_jobs(): return _db.load_list("jobs")
def save_jobs(v): _db.save_list("jobs", v)
def get_matches(): return _db.load_list("matches")
def save_matches(v): _db.save_list("matches", v)
def get_settings():
    s = _db.load_dict("settings")
    # API Key 解密（迁移后的明文旧值在此自动转加密）
    ds = s.setdefault("deepseek", {})
    if ds.get("api_key") and not str(ds["api_key"]).startswith("enc:"):
        ds["api_key"] = _enc_secret(ds["api_key"])
        _db.save_dict("settings", s)
    ds["api_key"] = _dec_secret(ds.get("api_key"))
    return s
def save_settings(v):
    ds = v.get("deepseek")
    if isinstance(ds, dict) and ds.get("api_key"):
        plain = _dec_secret(ds["api_key"])
        if plain:
            ds["api_key"] = _enc_secret(plain)
    _db.save_dict("settings", v)
def get_shares(): return _db.load_list("shares")
def save_shares(v): _db.save_list("shares", v)

DEFAULT_SETTINGS = {
    "dim_weights": {"academic": 30, "honor": 10, "practice": 20, "sci": 25, "quality": 15},
    "deepseek": {"api_key": "", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
}

def _hash_pwd(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

# ============================================================
# 演示数据（首次启动自动生成）
# ============================================================
SURNAMES = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "高", "郑", "梁", "谢", "宋", "唐", "许", "邓", "冯", "曹", "彭"]
GIVEN = ["伟", "芳", "娜", "敏", "静", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀兰", "霞", "平", "刚", "桂英", "文", "辉", "丽", "强", "玉兰", "鑫", "浩然", "子涵", "宇轩", "欣怡", "思远", "嘉豪", "雨桐", "俊杰", "雅琪", "博文", "梦瑶", "志强", "佳琪", "瑞霖"]
MAJORS = ["计算机科学与技术", "软件工程", "通信工程", "电子信息工程", "人工智能", "数据科学与大数据技术", "物联网工程", "网络工程", "自动化", "机械设计制造及其自动化", "电子商务", "市场营销", "视觉传达设计"]
GRADES = ["2023级", "2024级", "2025级"]
AWARDS_POOL = [
    "国家级大学生创新创业训练计划项目", "全国大学生数学建模竞赛省级一等奖", "全国大学生数学建模竞赛省级二等奖",
    "蓝桥杯全国软件和信息技术专业人才大赛省赛一等奖", "蓝桥杯省赛二等奖", "中国国际大学生创新大赛省级银奖",
    "挑战杯课外学术科技作品竞赛省级三等奖", "校级三好学生", "校级优秀学生干部", "校级一等奖学金", "校级二等奖学金",
    "全国大学生英语竞赛C类二等奖", "TI杯大学生电子设计竞赛省级二等奖", "无",
]
SCI_POOL = [
    "主持大创项目：基于深度学习的校园垃圾分类识别系统", "参与大创项目：校园二手交易平台开发",
    "参与导师课题：基于LoRa的智慧大棚监测系统", "参与互联网+大赛：AI简历解析工具", "参与挑战杯：社区养老服务平台",
    "参与省级科研训练：光纤传感温度监测", "无",
]
SKILL_POOL = {
    "计算机科学与技术": ["Python", "Java", "C++", "机器学习", "数据结构与算法", "数据库", "Web开发", "Linux"],
    "软件工程": ["Python", "Java", "Spring", "前端开发", "数据库", "软件测试", "Git", "C++"],
    "通信工程": ["C语言", "信号处理", "通信原理", "电路设计", "嵌入式", "Python", "FPGA"],
    "电子信息工程": ["C语言", "电路设计", "嵌入式", "信号处理", "PCB设计", "Python"],
    "人工智能": ["Python", "机器学习", "深度学习", "PyTorch", "数据分析", "NLP", "计算机视觉"],
    "数据科学与大数据技术": ["Python", "数据分析", "SQL", "机器学习", "数据可视化", "Hadoop", "统计学"],
    "物联网工程": ["C语言", "嵌入式", "传感器", "无线通信", "Python", "物联网平台"],
    "网络工程": ["计算机网络", "Linux", "网络安全", "Python", "路由交换", "云计算"],
    "自动化": ["C语言", "PLC", "嵌入式", "自动控制", "电路设计", "Python"],
    "机械设计制造及其自动化": ["SolidWorks", "CAD", "机械设计", "Python", "3D打印"],
    "电子商务": ["数据分析", "运营", "Excel", "短视频运营", "文案策划"],
    "市场营销": ["数据分析", "市场调研", "文案策划", "PPT", "商务沟通"],
    "视觉传达设计": ["Photoshop", "Illustrator", "UI设计", "平面设计", "AE动效"],
}

def _make_demo_students():
    random.seed(20260512)
    used_names = set()
    students = []
    for i in range(48):
        major = random.choice(MAJORS)
        # 姓名不重复
        while True:
            name = random.choice(SURNAMES) + random.choice(GIVEN)
            if name not in used_names:
                used_names.add(name)
                break
        grade = random.choice(GRADES)
        student_no = "24" + str(random.randint(10, 99)) + "0" + str(random.randint(1000, 9999))
        n_awards = random.choices([0, 1, 2, 3], weights=[30, 40, 22, 8])[0]
        awards = [a for a in random.sample(AWARDS_POOL, min(n_awards, 3)) if a != "无"] or ([] if random.random() > 0.25 else ["无"])
        n_sci = random.choices([0, 1], weights=[55, 45])[0]
        sci_exp = random.sample([s for s in SCI_POOL if s != "无"], n_sci) or ([] if random.random() > 0.2 else ["无"])
        skills = random.sample(SKILL_POOL[major], k=min(6, len(SKILL_POOL[major])))
        # 制造有区分度的得分分布：约 15% S / 30% A / 35% B / 20% C
        r = random.random()
        if r < 0.15:
            base = (86, 96)
        elif r < 0.45:
            base = (74, 86)
        elif r < 0.80:
            base = (58, 74)
        else:
            base = (40, 58)
        def sc():
            return max(0, min(100, int(random.gauss((base[0] + base[1]) / 2, 8))))
        scores = {d: sc() for d in DIMS}
        students.append({
            "id": "S%03d" % (i + 1),
            "name": name,
            "student_no": student_no,
            "major": major,
            "grade": grade,
            "awards": awards,
            "sci_exp": sci_exp,
            "skills": skills,
            "scores": scores,
            "source": "demo",
            "created_at": time.strftime("%Y-%m-%d"),
        })
    return students

DEMO_JOBS = [
    {"name": "后端开发实习生", "type": "技术类", "major_req": ["计算机科学与技术", "软件工程", "人工智能", "网络工程"],
     "skill_req": ["Python", "Java", "数据库"], "weights": {"academic": 30, "honor": 5, "practice": 20, "sci": 25, "quality": 20},
     "desc": "参与企业级后端系统开发，负责接口设计与数据库维护，要求扎实的编程基础与数据结构能力。"},
    {"name": "AI 算法实习生", "type": "技术类", "major_req": ["人工智能", "数据科学与大数据技术", "计算机科学与技术"],
     "skill_req": ["Python", "机器学习", "深度学习"], "weights": {"academic": 25, "honor": 5, "practice": 15, "sci": 35, "quality": 20},
     "desc": "协助算法工程师完成模型训练与调优，参与数据分析与特征工程，要求熟悉主流机器学习框架。"},
    {"name": "数据分析实习生", "type": "技术类", "major_req": ["数据科学与大数据技术", "计算机科学与技术", "电子商务", "市场营销"],
     "skill_req": ["数据分析", "SQL", "Python"], "weights": {"academic": 30, "honor": 5, "practice": 25, "sci": 20, "quality": 20},
     "desc": "负责业务数据清洗、分析与可视化，输出数据洞察报告，要求熟练使用 Excel 与 SQL。"},
    {"name": "嵌入式开发实习生", "type": "技术类", "major_req": ["电子信息工程", "通信工程", "物联网工程", "自动化"],
     "skill_req": ["C语言", "嵌入式", "电路设计"], "weights": {"academic": 25, "honor": 5, "practice": 30, "sci": 25, "quality": 15},
     "desc": "参与嵌入式产品软硬件调试，编写驱动与通信协议代码，要求熟悉单片机与硬件调试。"},
    {"name": "产品运营实习生", "type": "运营类", "major_req": ["电子商务", "市场营销", "工商管理"],
     "skill_req": ["数据分析", "运营", "文案策划"], "weights": {"academic": 20, "honor": 10, "practice": 35, "sci": 10, "quality": 25},
     "desc": "协助产品运营与用户增长，参与活动策划与内容运营，要求具备数据敏感度和沟通能力。"},
    {"name": "视觉设计实习生", "type": "设计类", "major_req": ["视觉传达设计", "数字媒体艺术"],
     "skill_req": ["Photoshop", "Illustrator", "UI设计"], "weights": {"academic": 15, "honor": 10, "practice": 35, "sci": 5, "quality": 35},
     "desc": "负责产品界面设计与品牌物料制作，要求有成熟的设计作品与审美能力。"},
]

def _seed_if_needed():
    if not get_users():
        salt = secrets.token_hex(8)
        save_users([{
            "id": "u_admin", "username": "admin", "salt": salt,
            "password_hash": _hash_pwd("admin123", salt),
            "role": "admin", "name": "系统管理员", "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }])
    if not get_settings().get("dim_weights"):
        save_settings(DEFAULT_SETTINGS)
    if not get_jobs():
        jobs = []
        for i, j in enumerate(DEMO_JOBS, 1):
            jobs.append({"id": "J%d" % i, **j, "created_at": time.strftime("%Y-%m-%d %H:%M")})
        save_jobs(jobs)
    if not get_students():
        save_students(_make_demo_students())
    if not get_matches():
        save_matches([])

# ============================================================
# 业务逻辑：评分 / 评级 / 匹配
# ============================================================
def rating_of(weighted):
    for low, code, _cn in RATING_RULES:
        if weighted >= low:
            return code
    return "C"

def student_weighted(s, weights):
    w = weights or DEFAULT_SETTINGS["dim_weights"]
    total_w = sum(w.get(d, 0) for d in DIMS)
    if total_w <= 0:
        return 0.0
    v = sum((s["scores"].get(d, 0) or 0) * w.get(d, 0) for d in DIMS) / total_w
    return round(v, 1)

def major_match_score(major, major_req):
    if not major_req:
        return 60.0
    if major in major_req:
        return 100.0
    mg = _major_group(major)
    if mg and any(m in major_req for m in MAJOR_GROUPS.get(mg, [])):
        return 70.0
    return 30.0

def skill_match_score(skills, skill_req):
    if not skill_req:
        return 50.0
    if not skills:
        return 0.0
    ss = {s.strip().lower() for s in skills if s and s.strip()}
    hit = sum(1 for r in skill_req if r.strip().lower() in ss)
    return round(hit / len(skill_req) * 100, 1)

def fit_score(s, job):
    """适配分 = 0.8×五维加权 + 0.12×专业匹配 + 0.08×技能匹配"""
    w = job.get("weights") or get_settings().get("dim_weights")
    weighted = student_weighted(s, w)
    major = major_match_score(s["major"], job.get("major_req", []))
    skill = skill_match_score(s.get("skills", []), job.get("skill_req", []))
    fit = round(0.80 * weighted + 0.12 * major + 0.08 * skill, 1)
    return {"fit": fit, "weighted": weighted, "major": major, "skill": skill}

def _mask_name(name):
    if not name:
        return ""
    if len(name) <= 1:
        return name[0] + "*"
    return name[0] + "*" + name[-1]

def _mask_no(no):
    if not no:
        return ""
    if len(no) <= 4:
        return "***"
    return no[:2] + "***" + no[-2:]

def _local_reason(s, job, fs, rating):
    best = max(DIMS, key=lambda d: s["scores"].get(d, 0))
    worst = min(DIMS, key=lambda d: s["scores"].get(d, 0))
    return ("该生综合评级 %s，五维加权得分 %.1f 分，其中「%s」维度表现突出，与岗位「%s」的匹配适配分为 %.1f；"
            "专业与技能要求匹配度良好，建议重点关注「%s」维度的进一步提升。"
            % (rating, fs["weighted"], DIM_NAMES[best], job.get("name", ""), fs["fit"], DIM_NAMES[worst]))

# ============================================================
# DeepSeek AI 推荐理由
# ============================================================
def _deepseek_reasons(job, candidates, settings):
    """一次调用生成前 N 名候选的推荐理由，返回 {student_id: reason}"""
    key = (settings.get("deepseek") or {}).get("api_key", "")
    if not key:
        return None
    base = (settings.get("deepseek") or {}).get("base_url", "https://api.deepseek.com").rstrip("/")
    model = (settings.get("deepseek") or {}).get("model", "deepseek-chat")
    cand_lines = []
    for c in candidates:
        cand_lines.append(
            "{\"id\":\"%s\",\"姓名(脱敏)\":\"%s\",\"专业\":\"%s\",\"年级\":\"%s\",\"五维得分\":%s,"
            "\"综合评级\":\"%s\",\"获奖\":%s,\"科创\":%s,\"技能\":%s}"
            % (c["id"], _mask_name(c["name"]), c["major"], c["grade"],
               json.dumps({DIM_NAMES[d]: c["scores"].get(d) for d in DIMS}, ensure_ascii=False),
               c["rating"], json.dumps(c.get("awards", []), ensure_ascii=False),
               json.dumps(c.get("sci_exp", []), ensure_ascii=False),
               json.dumps(c.get("skills", []), ensure_ascii=False)))
    sys_prompt = ("你是资深校园招聘人才顾问，善于基于学生在校真实数据给出客观、简洁的岗位匹配推荐意见。"
                  "对每个候选人写一段不超过60字的中文推荐理由：先说匹配亮点（数据依据），再说1条不足或建议，语气专业、克制、不夸张。")
    user_prompt = ("岗位信息：名称「%s」，类型「%s」，职责简介：%s，专业要求：%s，技能要求：%s，五维权重：%s。\n"
                   "候选人列表：\n%s\n请为每位候选人输出推荐理由，严格只输出 JSON：{\"reasons\":[{\"id\":\"...\",\"reason\":\"...\"}]}"
                   % (job.get("name", ""), job.get("type", ""), job.get("desc", ""),
                      "、".join(job.get("major_req", [])) or "不限", "、".join(job.get("skill_req", [])) or "不限",
                      json.dumps({DIM_NAMES[d]: job.get("weights", {}).get(d) for d in DIMS}, ensure_ascii=False),
                      "\n".join(cand_lines)))
    import requests as _req
    try:
        resp = _req.post(base + "/chat/completions", headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        }, json={
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }, timeout=60)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        reasons = parsed.get("reasons", [])
        return {r["id"]: r["reason"] for r in reasons if r.get("id")}
    except Exception as e:
        print("[DeepSeek] 调用失败：%s" % e)
        return None

def run_match(job_id, threshold, operator="admin"):
    settings = get_settings()
    jobs = get_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        return None
    threshold = max(0, min(100, float(threshold)))
    students = get_students()
    w = job.get("weights") or settings.get("dim_weights")
    rows = []
    for s in students:
        fs = fit_score(s, job)
        if fs["fit"] < threshold:
            continue
        weighted = student_weighted(s, w)
        rows.append({"student": s, "fs": fs, "rating": rating_of(weighted), "weighted": weighted})
    rows.sort(key=lambda r: r["fs"]["fit"], reverse=True)
    # AI 推荐理由：配置了 Key 时对全部候选人分批调用（每批 10 人），单批失败回退本地规则
    top = rows[:10]
    ai_map = {}
    if settings.get("deepseek", {}).get("api_key"):
        for i in range(0, len(top), 10):
            batch = top[i:i + 10]
            cands = [{
                "id": r["student"]["id"], "name": r["student"]["name"], "major": r["student"]["major"],
                "grade": r["student"]["grade"], "scores": r["student"]["scores"],
                "rating": r["rating"], "awards": r["student"].get("awards", []),
                "sci_exp": r["student"].get("sci_exp", []), "skills": r["student"].get("skills", []),
            } for r in batch]
            got = _deepseek_reasons(job, cands, settings)
            if got:
                ai_map.update(got)
            if i + 10 < len(top):
                time.sleep(0.5)

    results = []
    for r in rows:
        s = r["student"]
        if r in top and ai_map and r["student"]["id"] in ai_map:
            reason, source = ai_map[r["student"]["id"]], "ai"
        else:
            reason, source = _local_reason(s, job, r["fs"], r["rating"]), "local"
        results.append({
            "student_id": s["id"], "name_masked": _mask_name(s["name"]),
            "student_no_masked": _mask_no(s.get("student_no", "")),
            "major": s["major"], "grade": s["grade"], "rating": r["rating"],
            "fit": r["fs"]["fit"], "weighted": r["fs"]["weighted"],
            "major_match": r["fs"]["major"], "skill_match": r["fs"]["skill"],
            "dims": s["scores"], "awards": s.get("awards", []), "sci_exp": s.get("sci_exp", []),
            "skills": s.get("skills", []), "reason": reason, "reason_source": source,
        })
    record = {
        "id": "M" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(2).upper(),
        "job_id": job["id"], "job_name": job["name"], "job_type": job.get("type", ""),
        "threshold": threshold, "operator": operator,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_candidates": len(students), "matched_count": len(results),
        "ai_enabled": bool(settings.get("deepseek", {}).get("api_key")),
        "ai_covered": sum(1 for r in top if r["student"]["id"] in ai_map),
        "results": results,
    }
    matches = get_matches()
    matches.insert(0, record)
    save_matches(matches)
    return record

# ============================================================
# Flask 应用
# ============================================================
from flask import Flask, request, jsonify, send_file, Response
import io as _io

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.json.ensure_ascii = False

SESSIONS = {}  # token -> {"user": username, "exp": epoch}
SESSION_TTL = 8 * 3600  # 登录态有效期：8 小时（阶段 3.2）

def _current_user():
    token = request.headers.get("X-Token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    sess = SESSIONS.get(token)
    if not sess:
        return None
    if time.time() > sess.get("exp", 0):
        SESSIONS.pop(token, None)
        return None
    for u in get_users():
        if u["username"] == sess["user"]:
            return u
    return None

def _need_auth(fn):
    def wrapper(*a, **kw):
        u = _current_user()
        if not u:
            return jsonify({"ok": False, "msg": "未登录或登录已失效"}), 401
        return fn(u, *a, **kw)
    wrapper.__name__ = fn.__name__
    return wrapper

def _need_admin(fn):
    def wrapper(u, *a, **kw):
        if u["role"] != "admin":
            return jsonify({"ok": False, "msg": "该功能仅管理员可用"}), 403
        return fn(u, *a, **kw)
    wrapper.__name__ = fn.__name__
    return wrapper

@app.get("/")
def index():
    return send_file(os.path.join(STATIC_DIR, "index.html"))

@app.get("/view.html")
def view_page():
    """学生端扫码查看画像的独立单页（无需登录）"""
    return send_file(os.path.join(STATIC_DIR, "view.html"))

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    users = get_users()
    target = next((x for x in users if x["username"] == username), None)
    if not target:
        time.sleep(0.3)
        return jsonify({"ok": False, "msg": "账号或密码错误"}), 401
    # 失败锁定（阶段 3.2：连续 5 次错误锁定 5 分钟）
    locked_until = target.get("locked_until") or 0
    if time.time() < locked_until:
        remain = int(locked_until - time.time())
        return jsonify({"ok": False, "msg": "账号已锁定，请 %d 分钟 %d 秒后再试" % (remain // 60, remain % 60)}), 423
    if target["password_hash"] != _hash_pwd(password, target["salt"]):
        target["failed"] = target.get("failed", 0) + 1
        if target["failed"] >= 5:
            target["locked_until"] = time.time() + 300
            target["failed"] = 0
            save_users(users)
            return jsonify({"ok": False, "msg": "连续 5 次密码错误，账号已锁定 5 分钟"}), 423
        save_users(users)
        remain = 5 - target["failed"]
        return jsonify({"ok": False, "msg": "账号或密码错误（还可尝试 %d 次）" % remain}), 401
    target["failed"] = 0
    target["locked_until"] = None
    save_users(users)
    token = secrets.token_hex(16)
    SESSIONS[token] = {"user": username, "exp": time.time() + SESSION_TTL}
    return jsonify({"ok": True, "token": token, "user": {
        "username": target["username"], "name": target["name"], "role": target["role"]}})

@app.post("/api/logout")
@_need_auth
def logout(u):
    token = request.headers.get("X-Token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    SESSIONS.pop(token, None)
    return jsonify({"ok": True})

# ---------- 首页看板 ----------
@app.get("/api/dashboard")
@_need_auth
def dashboard(u):
    students = get_students()
    jobs = get_jobs()
    matches = get_matches()
    settings = get_settings()
    w = settings.get("dim_weights")
    profile_total = sum(1 for s in students if all(s.get("scores", {}).get(d) is not None for d in DIMS))
    rating_dist = {"S": 0, "A": 0, "B": 0, "C": 0}
    dim_sum = {d: 0.0 for d in DIMS}
    cnt = 0
    for s in students:
        sc = s.get("scores", {})
        if all(sc.get(d) is not None for d in DIMS):
            cnt += 1
            rating_dist[rating_of(student_weighted(s, w))] += 1
            for d in DIMS:
                dim_sum[d] += sc.get(d, 0)
    dim_avg = {d: (round(dim_sum[d] / cnt, 1) if cnt else 0) for d in DIMS}
    return jsonify({"ok": True, "data": {
        "student_total": len(students),
        "job_total": len(jobs),
        "profile_total": profile_total,
        "match_total": len(matches),
        "rating_dist": rating_dist,
        "dim_avg": dim_avg,
        "recent_matches": [{"id": m["id"], "job_name": m["job_name"], "matched_count": m["matched_count"],
                            "created_at": m["created_at"], "threshold": m["threshold"]} for m in matches[:6]],
    }})

# ---------- 学生人才库 ----------
@app.get("/api/students")
@_need_auth
def students_list(u):
    students = get_students()
    settings = get_settings()
    w = settings.get("dim_weights")
    major = request.args.get("major", "").strip()
    grade = request.args.get("grade", "").strip()
    award = request.args.get("award", "").strip()     # 有/无
    sci = request.args.get("sci", "").strip()         # 有/无
    rating = request.args.get("rating", "").strip()
    q = request.args.get("q", "").strip().lower()
    items = []
    for s in students:
        sc = s.get("scores", {})
        complete = all(sc.get(d) is not None for d in DIMS)
        weighted = student_weighted(s, w) if complete else None
        r = rating_of(weighted) if weighted is not None else "-"
        if major and s["major"] != major:
            continue
        if grade and s["grade"] != grade:
            continue
        has_award = any(a != "无" for a in s.get("awards", []))
        has_sci = any(x != "无" for x in s.get("sci_exp", []))
        if award == "有" and not has_award:
            continue
        if award == "无" and has_award:
            continue
        if sci == "有" and not has_sci:
            continue
        if sci == "无" and has_sci:
            continue
        if rating and r != rating:
            continue
        if q:
            hay = (s["name"] + s["major"] + s["grade"] + " ".join(s.get("skills", []))).lower()
            if q not in hay:
                continue
        items.append({
            "id": s["id"], "name_masked": _mask_name(s["name"]), "student_no_masked": _mask_no(s.get("student_no", "")),
            "major": s["major"], "grade": s["grade"], "award_count": sum(1 for a in s.get("awards", []) if a != "无"),
            "sci_count": sum(1 for x in s.get("sci_exp", []) if x != "无"),
            "weighted": weighted, "rating": r, "complete": complete,
        })
    items.sort(key=lambda x: (x["weighted"] if x["weighted"] is not None else -1), reverse=True)
    return jsonify({"ok": True, "data": items})

@app.get("/api/students/export.csv")
@_need_auth
def students_export_csv(u):
    """导出当前筛选条件下的学生列表为 CSV（UTF-8 BOM，Excel 打开不乱码，默认脱敏）"""
    students = get_students()
    settings = get_settings()
    w = settings.get("dim_weights")
    major = request.args.get("major", "").strip()
    grade = request.args.get("grade", "").strip()
    award = request.args.get("award", "").strip()
    sci = request.args.get("sci", "").strip()
    rating = request.args.get("rating", "").strip()
    q = request.args.get("q", "").strip().lower()
    rows = []
    for s in students:
        sc = s.get("scores", {})
        complete = all(sc.get(d) is not None for d in DIMS)
        weighted = student_weighted(s, w) if complete else None
        r = rating_of(weighted) if weighted is not None else "-"
        if major and s["major"] != major:
            continue
        if grade and s["grade"] != grade:
            continue
        has_award = any(a != "无" for a in s.get("awards", []))
        has_sci = any(x != "无" for x in s.get("sci_exp", []))
        if award == "有" and not has_award:
            continue
        if award == "无" and has_award:
            continue
        if sci == "有" and not has_sci:
            continue
        if sci == "无" and has_sci:
            continue
        if rating and r != rating:
            continue
        if q:
            hay = (s["name"] + s["major"] + s["grade"] + " ".join(s.get("skills", []))).lower()
            if q not in hay:
                continue
        rows.append([
            _mask_name(s["name"]), _mask_no(s.get("student_no", "")),
            s["major"], s["grade"],
            weighted if weighted is not None else "", r,
            sc.get("academic", ""), sc.get("honor", ""), sc.get("practice", ""), sc.get("sci", ""), sc.get("quality", ""),
            "、".join(a for a in s.get("awards", []) if a != "无") or "无",
            "、".join(x for x in s.get("sci_exp", []) if x != "无") or "无",
            "、".join(s.get("skills", [])) or "无",
        ])
    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM：Excel 识别为 UTF-8
    wcsv = csv.writer(buf)
    wcsv.writerow(["姓名(脱敏)", "学号(脱敏)", "专业", "年级", "综合得分", "综合评级",
                   "学业", "荣誉", "实践", "科创", "综合素质", "获奖情况", "科创经历", "技能标签"])
    wcsv.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=student_export.csv"})

@app.get("/api/students/meta")
@_need_auth
def students_meta(u):
    students = get_students()
    majors = sorted({s["major"] for s in students})
    grades = sorted({s["grade"] for s in students}, reverse=True)
    return jsonify({"ok": True, "majors": majors, "grades": grades})

@app.get("/api/students/<sid>")
@_need_auth
def student_detail(u, sid):
    s = next((x for x in get_students() if x["id"] == sid), None)
    if not s:
        return jsonify({"ok": False, "msg": "学生不存在"}), 404
    settings = get_settings()
    w = settings.get("dim_weights")
    sc = s.get("scores", {})
    complete = all(sc.get(d) is not None for d in DIMS)
    weighted = student_weighted(s, w) if complete else None
    rating = rating_of(weighted) if weighted is not None else "-"
    if complete:
        best = max(DIMS, key=lambda d: sc.get(d, 0))
        worst = min(DIMS, key=lambda d: sc.get(d, 0))
    else:
        best, worst = None, None
    advice_map = {
        "academic": "制定学期学习计划，重点突破专业核心课程，可参加学业帮扶与专业竞赛集训。",
        "honor": "积极参与评优评奖与文体活动，积累荣誉证明，提升综合素质竞争力。",
        "practice": "多参加实习、实训与企业项目，将理论转化为可展示的实践成果。",
        "sci": "主动申请大学生创新创业训练计划项目，尽早接触科研与学科竞赛。",
        "quality": "参与团队协作、学生组织与社会服务，锻炼沟通与组织协调能力。",
    }
    return jsonify({"ok": True, "data": {
        "id": s["id"], "name_masked": _mask_name(s["name"]), "student_no_masked": _mask_no(s.get("student_no", "")),
        "major": s["major"], "grade": s["grade"], "awards": s.get("awards", []), "sci_exp": s.get("sci_exp", []),
        "skills": s.get("skills", []), "scores": sc, "weighted": weighted, "rating": rating,
        "source": s.get("source", ""), "best_dim": best, "worst_dim": worst,
        "advice": advice_map.get(worst) if worst else "",
        "dim_names": DIM_NAMES,
        "share": _share_state(sid),
    }})

# ---------- 学生画像分享（扫码自助查看） ----------
SHARE_TTL_HOURS = 24

def _share_state(sid):
    sh = next((x for x in get_shares() if x["sid"] == sid), None)
    if not sh:
        return {"active": False, "share_url": None, "expires_at": None}
    if time.strftime("%Y-%m-%d %H:%M:%S") > sh["expires_at"]:
        return {"active": False, "share_url": None, "expires_at": sh["expires_at"]}
    return {"active": True, "share_url": "/view.html?t=" + sh["token"], "expires_at": sh["expires_at"]}

@app.post("/api/students/<sid>/share")
@_need_auth
def student_share(u, sid):
    s = next((x for x in get_students() if x["id"] == sid), None)
    if not s:
        return jsonify({"ok": False, "msg": "学生不存在"}), 404
    shares = [x for x in get_shares() if x["sid"] != sid]  # 生成新链接时撤销旧链接
    token = secrets.token_urlsafe(16)
    expires = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + SHARE_TTL_HOURS * 3600))
    shares.append({"sid": sid, "token": token, "expires_at": expires,
                   "created_by": u["username"], "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    save_shares(shares)
    return jsonify({"ok": True, "data": {
        "token": token, "share_url": "/view.html?t=" + token, "expires_at": expires,
    }})

@app.delete("/api/students/<sid>/share")
@_need_auth
def student_unshare(u, sid):
    save_shares([x for x in get_shares() if x["sid"] != sid])
    return jsonify({"ok": True})

@app.get("/api/share/<token>")
def share_view(token):
    """公开只读接口：凭一次性分享 token 获取学生脱敏画像（24h 有效）"""
    sh = next((x for x in get_shares() if x["token"] == token), None)
    if not sh:
        return jsonify({"ok": False, "msg": "链接无效或已过期"}), 404
    if time.strftime("%Y-%m-%d %H:%M:%S") > sh["expires_at"]:
        return jsonify({"ok": False, "msg": "链接已过期，请联系管理员重新生成"}), 404
    s = next((x for x in get_students() if x["id"] == sh["sid"]), None)
    if not s:
        return jsonify({"ok": False, "msg": "学生数据不存在"}), 404
    sc = s.get("scores", {})
    complete = all(sc.get(d) is not None for d in DIMS)
    weighted = student_weighted(s, get_settings().get("dim_weights")) if complete else None
    rating = rating_of(weighted) if weighted is not None else "-"
    return jsonify({"ok": True, "data": {
        "name_masked": _mask_name(s["name"]), "major": s["major"], "grade": s["grade"],
        "awards": s.get("awards", []), "sci_exp": s.get("sci_exp", []), "skills": s.get("skills", []),
        "scores": sc, "weighted": weighted, "rating": rating, "dim_names": DIM_NAMES,
    }})

# ---------- 批量导出画像摘要 ----------
def _summary_html(students):
    settings = get_settings()
    w = settings.get("dim_weights")
    rows_html = []
    for s in students:
        sc = s.get("scores", {})
        complete = all(sc.get(d) is not None for d in DIMS)
        weighted = student_weighted(s, w) if complete else None
        rating = rating_of(weighted) if weighted is not None else "-"
        dims = " | ".join("%s %s分" % (DIM_NAMES[d], sc.get(d, "-")) for d in DIMS)
        awards = "、".join(a for a in s.get("awards", []) if a != "无") or "无"
        sci = "、".join(x for x in s.get("sci_exp", []) if x != "无") or "无"
        skills = "、".join(s.get("skills", [])) or "无"
        rows_html.append(
            "<div class='stu-block'><h4>%s（%s · %s）综合评级：%s　综合得分：%s</h4>"
            "<p><b>五维得分：</b>%s</p><p><b>获奖情况：</b>%s</p><p><b>科创经历：</b>%s</p><p><b>技能标签：</b>%s</p></div>"
            % (_mask_name(s["name"]), s["major"], s["grade"], rating,
               weighted if weighted is not None else "未生成", dims, awards, sci, skills))
    html = (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>学生画像摘要导出</title><style>"
        "body{font-family:'Microsoft YaHei',sans-serif;color:#1f2d3d;margin:24px;}"
        "h2{color:#1769e0;border-bottom:2px solid #1769e0;padding-bottom:8px;}"
        ".stu-block{border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;margin:10px 0;page-break-inside:avoid;}"
        "h4{margin:0 0 8px;color:#0f2557;}p{margin:4px 0;font-size:14px;color:#33475b;}"
        ".tools{margin-bottom:14px;}.tools button{padding:8px 16px;border:none;border-radius:6px;background:#1769e0;color:#fff;cursor:pointer;margin-right:8px;}"
        "@media print{.tools{display:none;}}</style></head><body>"
        "<h2>学生人才画像摘要（共 %d 人）</h2><p>生成时间：%s</p>%s</body></html>"
    ) % (len(students), time.strftime("%Y-%m-%d %H:%M:%S"), "".join(rows_html))
    return html

@app.post("/api/students/export-summary")
@_need_auth
def export_summary(u):
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    students = [s for s in get_students() if s["id"] in ids]
    if not students:
        return jsonify({"ok": False, "msg": "未选择任何学生"}), 400
    lines = []
    settings = get_settings()
    w = settings.get("dim_weights")
    for s in students:
        sc = s.get("scores", {})
        complete = all(sc.get(d) is not None for d in DIMS)
        weighted = student_weighted(s, w) if complete else None
        rating = rating_of(weighted) if weighted is not None else "-"
        lines.append("【%s】%s | %s | %s | 综合评级：%s | 综合得分：%s" % (
            s["id"], _mask_name(s["name"]), s["major"], s["grade"], rating,
            weighted if weighted is not None else "未生成"))
        lines.append("  五维得分：" + "，".join("%s %s" % (DIM_NAMES[d], sc.get(d, "-")) for d in DIMS))
        lines.append("  获奖情况：" + ("、".join(a for a in s.get("awards", []) if a != "无") or "无"))
        lines.append("  科创经历：" + ("、".join(x for x in s.get("sci_exp", []) if x != "无") or "无"))
        lines.append("  技能标签：" + ("、".join(s.get("skills", [])) or "无"))
        lines.append("")
    txt = "学生人才画像摘要（共 %d 人）\n生成时间：%s\n\n%s" % (len(students), time.strftime("%Y-%m-%d %H:%M:%S"), "\n".join(lines))
    return jsonify({"ok": True, "html": _summary_html(students), "txt": txt})

# ---------- Excel / CSV 导入 ----------
IMPORT_COL_ALIASES = {
    "name": ["姓名", "学生姓名"], "student_no": ["学号", "学生学号"], "major": ["专业", "学院专业"],
    "grade": ["年级", "入学年份"], "awards": ["获奖情况", "获奖", "荣誉"], "sci_exp": ["科创经历", "科创", "科研经历"],
    "skills": ["技能标签", "技能", "技能特长"], "academic": ["学业得分", "学业成绩", "学业"], "honor": ["荣誉得分", "荣誉"],
    "practice": ["实践得分", "实践", "实践能力"], "sci": ["科创得分", "科创"], "quality": ["综合素质得分", "综合素质", "素质"],
}
def _split_tags(v):
    if v is None:
        return []
    return [x.strip() for x in str(v).replace("、", ",").replace("；", ",").replace(";", ",").replace("，", ",").split(",") if x.strip()]

def _to_score(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip().replace("分", "").replace("%", "")
        if not v:
            return None
        try:
            v = float(v)
        except ValueError:
            return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v < 0 or v > 100:
        return round(max(0, min(100, v)), 1), True  # (值, 是否越界修正)
    return round(v, 1), False

@app.post("/api/students/import")
@_need_auth
def import_students(u):
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "msg": "未接收到文件"}), 400
    filename = file.filename or ""
    fname_l = filename.lower()
    raw = file.read()
    if fname_l.endswith(".csv"):
        text = None
        for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            return jsonify({"ok": False, "msg": "CSV 编码无法识别，请另存为 UTF-8 后重试"}), 400
        rows = list(csv.reader(io.StringIO(text)))
        headers = [h.strip() for h in rows[0]]
        data_rows = rows[1:]
    elif fname_l.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        data_rows = rows[1:]
    else:
        return jsonify({"ok": False, "msg": "仅支持 .xlsx / .csv 文件"}), 400

    col_map = {}
    for field, aliases in IMPORT_COL_ALIASES.items():
        for i, h in enumerate(headers):
            if h and (h == field or any(a in h for a in aliases)):
                col_map[field] = i
                break
    missing = [DIM_NAMES[d] for d in DIMS if d not in col_map] or []
    if "name" not in col_map or "student_no" not in col_map or "major" not in col_map:
        return jsonify({"ok": False, "msg": "表头缺少必填列：姓名 / 学号 / 专业（得分列名示例：学业得分、科创得分等）"}), 400

    students = get_students()
    existing_no = {s["student_no"] for s in students}
    added, duplicates, invalid, warns = [], [], [], []
    max_seq = max((int(s["id"][1:]) for s in students if s["id"].startswith("S")), default=0)
    now = time.strftime("%Y-%m-%d")
    for row in data_rows:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        def gv(field):
            i = col_map.get(field)
            return row[i].strip() if (i is not None and i < len(row) and row[i] is not None) else ""
        name = gv("name")
        no = gv("student_no")
        major = gv("major")
        if not name or not no or not major:
            invalid.append("第 %d 行：姓名/学号/专业不完整" % (data_rows.index(row) + 2))
            continue
        if no in existing_no:
            duplicates.append("学号 %s（%s）已存在" % (no, name))
            continue
        scores = {}
        row_invalid = False
        for d in DIMS:
            v = _to_score(gv(d))
            if v is None:
                row_invalid = True
                invalid.append("学号 %s：缺少「%s」得分" % (no, DIM_NAMES[d]))
                break
            val, flag = v
            scores[d] = val
            if flag:
                warns.append("学号 %s：%s 得分超出 0-100，已自动修正为 %s" % (no, DIM_NAMES[d], val))
        if row_invalid:
            continue
        max_seq += 1
        students.append({
            "id": "S%03d" % max_seq,
            "name": name, "student_no": no, "major": major,
            "grade": gv("grade") or "未填写", "awards": _split_tags(gv("awards")),
            "sci_exp": _split_tags(gv("sci_exp")), "skills": _split_tags(gv("skills")),
            "scores": scores, "source": "import", "created_at": now,
        })
        existing_no.add(no)
        added.append(name)
    save_students(students)
    return jsonify({"ok": True, "data": {
        "added_count": len(added), "duplicate_count": len(duplicates),
        "invalid_count": len(invalid), "warn_count": len(warns),
        "added": added[:50], "duplicates": duplicates[:20], "invalid": invalid[:20],
        "warns": warns[:20], "student_total": len(students),
    }})

@app.get("/api/students/template")
@_need_auth
def template_download(u):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "学生数据导入模板"
    headers = ["姓名", "学号", "专业", "年级", "获奖情况", "科创经历", "技能标签",
               "学业得分", "荣誉得分", "实践得分", "科创得分", "综合素质得分"]
    ws.append(headers)
    ws.append(["张三", "2410703101", "计算机科学与技术", "2024级",
               "全国大学生数学建模竞赛省级二等奖", "参与大创项目：校园垃圾分类识别系统", "Python;机器学习;数据库",
               88, 75, 82, 90, 86])
    ws.append(["李四", "2410703102", "软件工程", "2024级",
               "校级三好学生", "无", "Java;Spring;数据库",
               76, 80, 70, 62, 78])
    for c in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + c)].width = 20
    bio = _io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name="学生数据导入模板.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- 岗位管理 ----------
@app.get("/api/jobs")
@_need_auth
def jobs_list(u):
    return jsonify({"ok": True, "data": get_jobs()})

@app.post("/api/jobs")
@_need_auth
def job_create(u):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "岗位名称不能为空"}), 400
    jobs = get_jobs()
    nid = "J%d" % (max((int(j["id"][1:]) for j in jobs if j["id"].startswith("J")), default=0) + 1)
    job = {
        "id": nid, "name": name, "type": (data.get("type") or "技术类").strip(),
        "major_req": [x.strip() for x in (data.get("major_req") or "") if x and x.strip()],
        "skill_req": [x.strip() for x in (data.get("skill_req") or "") if x and x.strip()],
        "weights": {d: max(0, min(100, int(data.get("weights", {}).get(d, 0)))) for d in DIMS},
        "desc": (data.get("desc") or "").strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    if sum(job["weights"].values()) != 100:
        return jsonify({"ok": False, "msg": "五大维度权重之和必须为 100"}), 400
    jobs.append(job)
    save_jobs(jobs)
    return jsonify({"ok": True, "data": job})

@app.put("/api/jobs/<jid>")
@_need_auth
def job_update(u, jid):
    jobs = get_jobs()
    job = next((j for j in jobs if j["id"] == jid), None)
    if not job:
        return jsonify({"ok": False, "msg": "岗位不存在"}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "岗位名称不能为空"}), 400
    job["name"] = name
    job["type"] = (data.get("type") or job.get("type", "技术类")).strip()
    job["major_req"] = [x.strip() for x in (data.get("major_req") or []) if x and x.strip()]
    job["skill_req"] = [x.strip() for x in (data.get("skill_req") or []) if x and x.strip()]
    job["weights"] = {d: max(0, min(100, int(data.get("weights", {}).get(d, 0)))) for d in DIMS}
    job["desc"] = (data.get("desc") or "").strip()
    if sum(job["weights"].values()) != 100:
        return jsonify({"ok": False, "msg": "五大维度权重之和必须为 100"}), 400
    save_jobs(jobs)
    return jsonify({"ok": True, "data": job})

@app.delete("/api/jobs/<jid>")
@_need_auth
def job_delete(u, jid):
    jobs = get_jobs()
    jobs = [j for j in jobs if j["id"] != jid]
    save_jobs(jobs)
    return jsonify({"ok": True})

# ---------- AI 智能匹配 ----------
@app.post("/api/match")
@_need_auth
def do_match(u):
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    threshold = data.get("threshold", 60)
    if not job_id:
        return jsonify({"ok": False, "msg": "请选择岗位"}), 400
    record = run_match(job_id, threshold, operator=u["username"])
    if not record:
        return jsonify({"ok": False, "msg": "岗位不存在"}), 404
    return jsonify({"ok": True, "data": record})

# ---------- 报告中心 ----------
@app.get("/api/matches")
@_need_auth
def matches_list(u):
    ms = get_matches()
    job_filter = (request.args.get("job_id") or "").strip()
    if job_filter:
        ms = [m for m in ms if m.get("job_id") == job_filter]
    return jsonify({"ok": True, "data": [{
        "id": m["id"], "job_id": m.get("job_id", ""), "job_name": m["job_name"], "job_type": m.get("job_type", ""),
        "threshold": m["threshold"], "created_at": m["created_at"], "operator": m["operator"],
        "matched_count": m["matched_count"], "total_candidates": m.get("total_candidates", 0),
        "ai_enabled": m.get("ai_enabled", False),
    } for m in ms]})

@app.get("/api/matches/<mid>")
@_need_auth
def match_detail(u, mid):
    m = next((x for x in get_matches() if x["id"] == mid), None)
    if not m:
        return jsonify({"ok": False, "msg": "记录不存在"}), 404
    return jsonify({"ok": True, "data": m})

@app.delete("/api/matches/<mid>")
@_need_auth
def match_delete(u, mid):
    ms = [m for m in get_matches() if m["id"] != mid]
    save_matches(ms)
    return jsonify({"ok": True})

# ---------- 报告 PDF 导出（真实 PDF 文件） ----------
def _pdf_font_name():
    """注册系统中文字体，返回可用的字体名；全部失败返回 None"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    candidates = [
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),      # 微软雅黑
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),  # 黑体
        ("C:/Windows/Fonts/simsun.ttc", "SimSun"),  # 宋体
    ]
    for path, name in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
                return name
            except Exception:
                continue
    return None

def build_match_pdf(m):
    """用 ReportLab 将一条匹配记录渲染为 PDF（BytesIO）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    font = _pdf_font_name() or "Helvetica"
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="岗位智能匹配报告")
    styles = getSampleStyleSheet()
    st_title = ParagraphStyle("ct", parent=styles["Title"], fontName=font,
                              fontSize=17, leading=22, spaceAfter=12)
    st_h = ParagraphStyle("h", parent=styles["Heading2"], fontName=font,
                          fontSize=12, leading=16, spaceBefore=10, spaceAfter=6)
    st_body = ParagraphStyle("body", parent=styles["BodyText"], fontName=font,
                             fontSize=10, leading=14)
    st_cell = ParagraphStyle("cell", parent=styles["BodyText"], fontName=font,
                             fontSize=9, leading=12)

    story = []
    story.append(Paragraph("岗位智能匹配报告", st_title))
    story.append(Paragraph("岗位：<b>%s</b>（%s）" % (m.get("job_name", ""), m.get("job_type", "")), st_h))
    meta_lines = [
        "适配分阈值：≥ %s 分" % m["threshold"],
        "候选学生：%s 人　|　匹配人数：%s 人" % (m.get("total_candidates", 0), m["matched_count"]),
        "执行人：%s　|　生成时间：%s" % (m.get("operator", "-"), m["created_at"]),
        "推荐理由来源：%s" % ("DeepSeek 大模型（AI 生成）" if m.get("ai_enabled") else "本地规则（未配置 API Key）"),
    ]
    for line in meta_lines:
        story.append(Paragraph(line, st_body))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("匹配结果明细（按适配分降序）", st_h))

    header = ["排名", "学生（脱敏）", "专业 / 年级", "评级", "适配分", "推荐理由"]
    rows = [header]
    for i, r in enumerate(m.get("results", [])):
        rows.append([
            str(i + 1),
            r.get("name_masked", ""),
            "%s / %s" % (r.get("major", ""), r.get("grade", "")),
            r.get("rating", ""),
            str(r.get("fit", "")),
            Paragraph(r.get("reason", ""), st_cell),
        ])
    tbl = Table(rows, colWidths=[12 * mm, 26 * mm, 38 * mm, 14 * mm, 16 * mm, 84 * mm],
                repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1769e0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, -1), font, 9),
        ("FONT", (0, 0), (-1, 0), font, 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d4e4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("—— 本报告由「轻量化 AI 驱动校园人才快速筛选系统」生成 ——",
                           ParagraphStyle("foot", parent=st_body, fontSize=9,
                                          textColor=colors.HexColor("#8a99ab"))))
    doc.build(story)
    buf.seek(0)
    return buf

@app.get("/api/matches/<mid>/pdf")
@_need_auth
def match_pdf(u, mid):
    m = next((x for x in get_matches() if x["id"] == mid), None)
    if not m:
        return jsonify({"ok": False, "msg": "记录不存在"}), 404
    try:
        buf = build_match_pdf(m)
    except Exception as e:
        print("[PDF] 生成失败：%s" % e)
        return jsonify({"ok": False, "msg": "PDF 生成失败：" + str(e)}), 500
    safe = "".join(c if c not in '\\/:*?"<>|' else "_" for c in m.get("job_name", "报告"))
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name="岗位匹配报告_%s_%s.pdf" % (safe, m["id"]))

# ---------- 系统设置（管理员） ----------
@app.get("/api/settings")
@_need_auth
@_need_admin
def settings_get(u):
    s = get_settings()
    return jsonify({"ok": True, "data": s})

@app.put("/api/settings")
@_need_auth
@_need_admin
def settings_put(u):
    data = request.get_json(silent=True) or {}
    s = get_settings()
    if "dim_weights" in data:
        w = {d: max(0, min(100, int(data["dim_weights"].get(d, 0)))) for d in DIMS}
        if sum(w.values()) != 100:
            return jsonify({"ok": False, "msg": "五大维度权重之和必须为 100"}), 400
        s["dim_weights"] = w
    if "deepseek" in data:
        ds = s.get("deepseek", {})
        for k in ("api_key", "base_url", "model"):
            if k in data["deepseek"]:
                ds[k] = (data["deepseek"][k] or "").strip()
        s["deepseek"] = ds
    save_settings(s)
    return jsonify({"ok": True, "data": s})

@app.post("/api/settings/test-ai")
@_need_auth
@_need_admin
def settings_test_ai(u):
    s = get_settings()
    ds = s.get("deepseek", {})
    key = ds.get("api_key", "")
    if not key:
        return jsonify({"ok": False, "msg": "尚未配置 API Key"}), 400
    import requests as _req
    try:
        resp = _req.post(ds.get("base_url", "https://api.deepseek.com").rstrip("/") + "/chat/completions",
                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                         json={"model": ds.get("model", "deepseek-chat"),
                               "messages": [{"role": "user", "content": "请回复：连接成功"}],
                               "max_tokens": 16}, timeout=30)
        if resp.status_code == 200:
            return jsonify({"ok": True, "msg": "连接成功：" + resp.json()["choices"][0]["message"]["content"][:30]})
        return jsonify({"ok": False, "msg": "调用失败（HTTP %s）：%s" % (resp.status_code, resp.text[:200])})
    except Exception as e:
        return jsonify({"ok": False, "msg": "网络异常：%s" % e})

@app.get("/api/users")
@_need_auth
@_need_admin
def users_list(u):
    return jsonify({"ok": True, "data": [{
        "id": x["id"], "username": x["username"], "name": x["name"],
        "role": x["role"], "created_at": x["created_at"],
    } for x in get_users()]})

@app.post("/api/users")
@_need_auth
@_need_admin
def user_create(u):
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "msg": "账号与密码不能为空"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "msg": "密码至少 6 位"}), 400
    users = get_users()
    if any(x["username"] == username for x in users):
        return jsonify({"ok": False, "msg": "账号已存在"}), 400
    salt = secrets.token_hex(8)
    users.append({
        "id": "u_" + secrets.token_hex(4),
        "username": username, "salt": salt,
        "password_hash": _hash_pwd(password, salt),
        "role": "hr" if data.get("role") != "admin" else "admin",
        "name": (data.get("name") or username).strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
    })
    save_users(users)
    return jsonify({"ok": True})

@app.put("/api/users/<uid>")
@_need_auth
@_need_admin
def user_update(u, uid):
    users = get_users()
    target = next((x for x in users if x["id"] == uid), None)
    if not target:
        return jsonify({"ok": False, "msg": "账号不存在"}), 404
    data = request.get_json(silent=True) or {}
    if data.get("name"):
        target["name"] = (data["name"] or "").strip()
    if data.get("role"):
        if target["id"] == u["id"] and data["role"] != "admin":
            return jsonify({"ok": False, "msg": "不能修改自己的管理员角色"}), 400
        target["role"] = "admin" if data["role"] == "admin" else "hr"
    if data.get("password"):
        if len(data["password"]) < 6:
            return jsonify({"ok": False, "msg": "密码至少 6 位"}), 400
        target["salt"] = secrets.token_hex(8)
        target["password_hash"] = _hash_pwd(data["password"], target["salt"])
    save_users(users)
    return jsonify({"ok": True})

@app.delete("/api/users/<uid>")
@_need_auth
@_need_admin
def user_delete(u, uid):
    users = get_users()
    target = next((x for x in users if x["id"] == uid), None)
    if not target:
        return jsonify({"ok": False, "msg": "账号不存在"}), 404
    if target["id"] == u["id"]:
        return jsonify({"ok": False, "msg": "不能删除当前登录账号"}), 400
    if target["role"] == "admin" and sum(1 for x in users if x["role"] == "admin") <= 1:
        return jsonify({"ok": False, "msg": "至少保留一个管理员账号"}), 400
    save_users([x for x in users if x["id"] != uid])
    return jsonify({"ok": True})

# ============================================================
# 启动
# ============================================================
def _lan_ip():
    """探测本机局域网 IP（用于 0.0.0.0 模式提示访问地址）"""
    import socket as _sk
    try:
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _migrate_json_if_needed():
    """首次启动自动迁移：旧 JSON 存在且 SQLite 尚无数据时导入（JSON 保留作备份）"""
    legacy = any(os.path.exists(os.path.join(DATA_DIR, n + ".json")) for n in
                 ("students", "jobs", "matches", "users", "settings"))
    if not legacy:
        return
    if _db.load_list("students"):
        return  # 已迁移过，跳过
    counts = _db.migrate_from_json(DATA_DIR, DB_PATH)
    print("[迁移] 旧 JSON 数据已导入 SQLite（原 JSON 保留备份）：%s" % counts)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="轻量化 AI 驱动校园人才快速筛选系统")
    parser.add_argument("--host", default="127.0.0.1",
                        help="监听地址，默认 127.0.0.1（仅本机）；填 0.0.0.0 可让同局域网设备访问")
    parser.add_argument("--port", type=int, default=0,
                        help="起始端口，默认 8501（被占用时自动顺延）")
    args = parser.parse_args()

    _migrate_json_if_needed()
    _seed_if_needed()
    host = args.host
    start = args.port or 8501
    port = start
    import socket
    for p in range(start, start + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                port = p
                break
            except OSError:
                continue
    url = "http://127.0.0.1:%d" % port
    print("=" * 60)
    print("  轻量化 AI 驱动校园人才快速筛选系统")
    print("  服务地址：%s" % url)
    if host == "0.0.0.0":
        print("  局域网访问地址：http://%s:%d（同一 WiFi 下的设备可打开）" % (_lan_ip(), port))
    print("  数据目录：%s" % DATA_DIR)
    print("  默认管理员：admin / admin123（登录后请及时修改）")
    print("  关闭本窗口即停止服务。")
    print("=" * 60)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == "__main__":
    main()
