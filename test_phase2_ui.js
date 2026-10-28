// 阶段 2 UI 测试（jsdom + 真实本地服务 8501）
// 覆盖：2.1 权重模板填充+保存 / 2.2 报告中心多选对比 / 2.4 删除岗位二次确认 / 2.3 导出CSV按钮
const { JSDOM, VirtualConsole } = require("jsdom");
const BASE = "http://127.0.0.1:8501";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let failures = 0;
function check(name, cond, extra) {
  if (cond) console.log("PASS " + name);
  else { console.log("FAIL " + name + (extra ? " | " + extra : "")); failures++; }
}

async function waitFor(fn, timeoutMs = 20000, interval = 150) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try { const v = fn(); if (v) return v; } catch (e) { }
    await sleep(interval);
  }
  throw new Error("waitFor timeout: " + fn.toString().slice(0, 140));
}

function makeDom(html, seedStorage, errors) {
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
  return new JSDOM(html, {
    url: BASE + "/",
    runScripts: "dangerously",
    resources: "usable",
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      window.fetch = (url, opts) => fetch(new URL(url, BASE + "/"), opts);
      window.open = () => null;
      if (seedStorage) {
        window.localStorage.setItem("token", seedStorage.token);
        window.localStorage.setItem("user", JSON.stringify(seedStorage.user));
      }
    },
  });
}

async function loadHtml() {
  const html = await (await fetch(BASE + "/")).text();
  return html.replace(/<script src="[^"]*echarts[^"]*"><\/script>/, "");
}

(async () => {
  const errs = [];
  const dom = makeDom(await loadHtml(), null, errs);
  const win = dom.window;

  // 登录
  await waitFor(() => win.App !== undefined, 20000);
  await sleep(500);
  win.document.getElementById("login-username").value = "admin";
  win.document.getElementById("login-password").value = "admin123";
  win.document.getElementById("login-btn").click();
  await waitFor(() => {
    const pb = win.document.getElementById("page-body");
    return pb && pb.textContent.includes("学生总数");
  }, 20000);
  console.log("LOGIN_OK");

  // ---------- 2.1 权重模板 ----------
  win.location.hash = "#/jobs";
  await sleep(500);
  await waitFor(() => win.document.getElementById("page-body").textContent.includes("岗位名称"));
  win.document.getElementById("job-new").click();
  await waitFor(() => win.document.getElementById("jf-wtemplate") !== null);
  const tmpl = win.document.getElementById("jf-wtemplate");
  tmpl.value = "tech";
  tmpl.dispatchEvent(new win.Event("change", { bubbles: true }));
  await sleep(200);
  const getDim = (k) => parseInt(win.document.querySelector('input[data-num="' + k + '"]').value, 10);
  const w = { academic: getDim("academic"), honor: getDim("honor"), practice: getDim("practice"), sci: getDim("sci"), quality: getDim("quality") };
  check("2.1 技术类模板填充 academic=30", w.academic === 30, "got " + w.academic);
  check("2.1 技术类模板填充 sci=25", w.sci === 25, "got " + w.sci);
  const sum = Object.values(w).reduce((a, b) => a + b, 0);
  check("2.1 模板权重合计 100", sum === 100, "sum=" + sum);
  const sumText = win.document.getElementById("weight-sum").textContent;
  check("2.1 合计提示显示 100", /当前合计：100/.test(sumText), sumText);
  // 填写名称并保存
  win.document.getElementById("jf-name").value = "测试岗-模板验证";
  win.document.getElementById("jf-save").click();
  await sleep(800);
  await waitFor(() => win.document.getElementById("page-body").textContent.includes("测试岗-模板验证"));
  check("2.1 带模板权重的新岗位保存成功", true);
  // 清理：删除该岗位（点删除 → 确认）
  const jdel = win.document.querySelector('.j-del[data-id]');
  const delBtn = Array.from(win.document.querySelectorAll(".j-del")).find(b => {
    return true; // 无法直接按名称找，按行文本找
  });
  const rows = Array.from(win.document.querySelectorAll("tbody tr"));
  const target = rows.find(r => r.textContent.includes("测试岗-模板验证"));
  if (target) {
    const btn = target.querySelector(".j-del");
    btn.click();
    await waitFor(() => win.document.querySelector(".modal") !== null);
    const modalText = win.document.querySelector(".modal").textContent;
    check("2.4 删除岗位出现确认弹窗", modalText.includes("删除岗位"), modalText.slice(0, 60));
    // 该岗位刚建、无匹配记录 → 文案为默认提示
    const okBtn = win.document.querySelector(".modal .do");
    okBtn.click();
    await sleep(800);
    await waitFor(() => !win.document.getElementById("page-body").textContent.includes("测试岗-模板验证"));
    check("2.4 确认后岗位删除成功", true);
  } else {
    check("2.4 找到新建测试岗位以便删除", false, "未找到");
  }

  // ---------- 2.2 多轮对比 ----------
  win.location.hash = "#/reports";
  await sleep(500);
  await waitFor(() => win.document.getElementById("page-body").textContent.includes("对比所选"));
  const checks = win.document.querySelectorAll(".rp-check");
  check("2.2 报告列表带复选框", checks.length >= 2, "count=" + checks.length);
  if (checks.length >= 2) {
    checks[0].click();
    checks[1].click();
    await sleep(150);
    win.document.getElementById("rp-compare").click();
    await waitFor(() => {
      const md = win.document.querySelector(".modal");
      return md && (md.textContent.includes("适配分阈值") || md.textContent.includes("加载失败") || md.textContent.includes("空"));
    }, 15000);
    const modal = win.document.querySelector(".modal");
    const text = modal.textContent;
    check("2.2 对比表含阈值行", text.includes("适配分阈值"), text.slice(0, 80));
    check("2.2 对比表含 Top1", text.includes("Top 1"), "");
    check("2.2 对比表含重合度", text.includes("重合"), "");
    const close = modal.querySelector("#cmp-close");
    if (close) close.click();
    await sleep(200);
  }

  // ---------- 2.3 导出 CSV 按钮 ----------
  win.location.hash = "#/talent";
  await sleep(500);
  await waitFor(() => win.document.getElementById("page-body").textContent.includes("学生列表"));
  const csvBtn = win.document.getElementById("btn-csv");
  check("2.3 人才库有「导出 CSV」按钮", !!csvBtn && csvBtn.textContent.includes("CSV"), "");

  // 控制台错误检查（排除已知无害项）
  const fatal = errs.filter(e => !/favicon|net::ERR/.test(e));
  check("阶段2 UI 无致命控制台错误", fatal.length === 0, fatal.slice(0, 3).join(" || "));

  console.log(failures === 0 ? "PHASE2_UI_PASS" : "PHASE2_UI_FAIL");
  dom.window.close();
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error("FATAL: " + (e && e.message));
  process.exit(1);
});
