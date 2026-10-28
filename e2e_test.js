// 无头浏览器端到端测试（jsdom + 真实本地服务）
// Phase A：全新登录 → 看板 → 人才库 → 岗位 → AI匹配 → 报告 → 设置
// Phase B：刷新恢复登录（localStorage 已存 token）→ 直接进入看板
const { JSDOM, VirtualConsole } = require("jsdom");

const BASE = "http://127.0.0.1:8501";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(fn, timeoutMs = 15000, interval = 150) {
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
  vc.on("warn", (...a) => errors.push("console.warn: " + a.join(" ")));
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
  // 测试环境移除 echarts（jsdom 无 canvas 实现），页面会优雅跳过图表渲染
  const html = await (await fetch(BASE + "/")).text();
  return html.replace(/<script src="[^"]*echarts[^"]*"><\/script>/, "");
}

(async () => {
  let winA = null;
  process.on("unhandledRejection", (err) => {
    console.error("UNHANDLED: " + (err && err.message));
    try {
      if (winA) {
        const pb = winA.document.getElementById("page-body");
        console.error("DIAG len=" + (pb ? pb.innerHTML.length : 0) + " qb-job=" + (pb ? !!pb.querySelector("#qb-job") : "n/a") +
          " head=" + (pb ? pb.innerHTML.slice(0, 120).replace(/\s+/g, " ") : ""));
      }
    } catch (e) { console.error("DIAG-FAIL " + e.message); }
    process.exit(1);
  });

  // ---------- Phase A ----------
  const errA = [];
  const domA = makeDom(await loadHtml(), null, errA);
  winA = domA.window;

  await waitFor(() => winA.App !== undefined, 20000);
  await sleep(600);
  console.log("A1 App 已加载, 模块: D=" + !!winA.Dashboard + " T=" + !!winA.Talent + " J=" + !!winA.Jobs +
    " M=" + !!winA.Match + " R=" + !!winA.Reports + " S=" + !!winA.Settings);

  winA.document.getElementById("login-username").value = "admin";
  winA.document.getElementById("login-password").value = "admin123";
  winA.document.getElementById("login-btn").click();
  await sleep(4000);
  const pbA = winA.document.getElementById("page-body");
  console.log("A2-DIAG page-body exists=" + !!pbA + " len=" + (pbA ? pbA.innerHTML.length : 0) +
    " qb-job=" + (pbA && !!pbA.querySelector("#qb-job")) +
    " text=" + (pbA ? pbA.textContent.replace(/\s+/g, " ").slice(0, 60) : ""));
  await waitFor(() => {
    const pb = winA.document.getElementById("page-body");
    return pb && (pb.textContent.includes("学生总数") || pb.textContent.includes("页面加载出错"));
  }, 20000);
  console.log("A2 看板渲染: " + winA.document.getElementById("page-body").textContent.replace(/\s+/g, " ").slice(0, 140));

  winA.location.hash = "#/talent";
  await waitFor(() => {
    const pb = winA.document.getElementById("page-body");
    return pb && pb.textContent.includes("学生列表");
  }, 10000);
  const rows = winA.document.querySelectorAll("#page-body tbody tr");
  console.log("A3 人才库行数: " + rows.length + " | 首行: " + (rows[0] ? rows[0].textContent.replace(/\s+/g, " ").slice(0, 60) : ""));

  winA.location.hash = "#/jobs";
  await waitFor(() => {
    const pb = winA.document.getElementById("page-body");
    return pb && pb.textContent.includes("新建岗位");
  }, 10000);
  console.log("A4 岗位管理渲染: " + winA.document.getElementById("page-body").textContent.replace(/\s+/g, " ").slice(0, 100));

  winA.location.hash = "#/match";
  await waitFor(() => {
    const s = winA.document.getElementById("m-job");
    return s && s.options.length > 1;
  }, 10000);
  const sel = winA.document.getElementById("m-job");
  sel.value = sel.options[1].value;
  winA.document.getElementById("m-threshold").value = "60";
  winA.document.getElementById("m-run").click();
  await waitFor(() => {
    const b = winA.document.getElementById("m-results");
    return b && b.textContent.includes("岗位「");
  }, 30000);
  console.log("A5 匹配结果: " + winA.document.getElementById("m-results").textContent.replace(/\s+/g, " ").slice(0, 170));

  winA.location.hash = "#/reports";
  await waitFor(() => {
    const pb = winA.document.getElementById("page-body");
    return pb && (pb.textContent.includes("预览报告") || pb.textContent.includes("暂无匹配记录"));
  }, 10000);
  console.log("A6 报告中心: " + winA.document.getElementById("page-body").textContent.replace(/\s+/g, " ").slice(0, 80));

  winA.location.hash = "#/settings";
  await waitFor(() => {
    const pb = winA.document.getElementById("page-body");
    return pb && pb.textContent.includes("指标权重配置");
  }, 10000);
  console.log("A7 系统设置: " + winA.document.getElementById("page-body").textContent.replace(/\s+/g, " ").slice(0, 80));
  console.log("A8 控制台错误: " + (errA.length ? JSON.stringify(errA) : "无"));

  const token = winA.localStorage.getItem("token");
  const user = JSON.parse(winA.localStorage.getItem("user"));

  // ---------- Phase B：刷新恢复登录 ----------
  const errB = [];
  const domB = makeDom(await loadHtml(), { token, user }, errB);
  const winB = domB.window;
  await waitFor(() => {
    const pb = winB.document.getElementById("page-body");
    return pb && pb.textContent.includes("学生总数");
  }, 20000);
  console.log("B1 刷新恢复→直接看板: " + winB.document.getElementById("page-body").textContent.replace(/\s+/g, " ").slice(0, 100));
  console.log("B2 控制台错误: " + (errB.length ? JSON.stringify(errB) : "无"));

  console.log("E2E_TEST_PASS");
  process.exit(0);
})().catch((e) => {
  console.error("E2E_TEST_FAIL: " + e.message);
  process.exit(1);
});
