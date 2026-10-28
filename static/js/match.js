/* ===== AI 智能匹配（核心模块） ===== */
(function () {
  'use strict';
  const { esc, toast, API, openModal, badgeHtml } = window.App;

  const DIM_NAMES = { academic: '学业', honor: '荣誉', practice: '实践', sci: '科创', quality: '综合素质' };
  const DIMS = ['academic', 'honor', 'practice', 'sci', 'quality'];

  function detailModal(res) {
    const m = openModal({ lg: true });
    m.setTitle('匹配详情：' + res.name_masked + '（适配分 ' + res.fit + '）');
    m.setBody(
      '<div class="profile-head">' +
      '<div class="profile-info">' +
      '<p class="pi-row"><b style="font-size:16px">' + esc(res.name_masked) + '</b>　' + badgeHtml(res.rating) + '</p>' +
      '<p class="pi-row">专业：' + esc(res.major) + '　|　年级：' + esc(res.grade) + '</p>' +
      '<p class="pi-row">学号：' + esc(res.student_no_masked) + '</p>' +
      '<p class="pi-row">五维加权得分：<b>' + esc(res.weighted) + '</b>　专业匹配：<b>' + esc(res.major_match) + '</b>　技能匹配：<b>' + esc(res.skill_match) + '</b></p>' +
      '<p class="pi-row">技能：</p><div class="tag-list" style="margin:2px 0 8px">' + ((res.skills || []).map(s => '<span class="tag">' + esc(s) + '</span>').join('') || '<span style="color:#8a99ab">无</span>') + '</div>' +
      '</div>' +
      '<div id="md-radar" style="width:340px;height:280px;flex-shrink:0"></div>' +
      '</div>' +
      '<div class="card-title">五维能力得分</div>' +
      '<div class="score-grid">' +
      DIMS.map(k => '<div class="score-cell"><div class="sc-num">' + esc(res.dims && res.dims[k] != null ? res.dims[k] : '—') + '</div><div class="sc-name">' + esc(DIM_NAMES[k]) + '</div></div>').join('') +
      '</div>' +
      '<div class="card-title" style="margin-top:14px">' + (res.reason_source === 'ai' ? 'AI 推荐理由（DeepSeek 大模型生成）' : '匹配推荐理由（本地规则生成）') + '</div>' +
      '<div class="result-row" style="border-left:3px solid ' + (res.reason_source === 'ai' ? '#00b4d8' : '#94a3b8') + '"><p style="font-size:13px;color:#33475b;margin:0">' + esc(res.reason) + '</p></div>' +
      '<div style="margin-top:12px">' +
      '<div class="card-title">获奖情况</div><div class="tag-list">' + ((res.awards || []).filter(a => a !== '无').map(a => '<span class="tag">' + esc(a) + '</span>').join('') || '<span style="color:#8a99ab">暂无</span>') + '</div>' +
      '<div class="card-title" style="margin-top:10px">科创经历</div><div class="tag-list">' + ((res.sci_exp || []).filter(x => x !== '无').map(x => '<span class="tag">' + esc(x) + '</span>').join('') || '<span style="color:#8a99ab">暂无</span>') + '</div>' +
      '</div>'
    );
    m.setFoot('<button class="btn" id="md-close">关 闭</button>');
    m.modal.querySelector('#md-close').onclick = () => m.close();
    const el = document.getElementById('md-radar');
    if (el && typeof echarts !== 'undefined') {
      const chart = echarts.init(el);
      chart.setOption({
        tooltip: {},
        radar: {
          indicator: DIMS.map(k => ({ name: DIM_NAMES[k], max: 100 })),
          radius: '65%',
          splitArea: { areaStyle: { color: ['#f4f8fe', '#eef3fb'] } },
          axisName: { color: '#33527f' },
        },
        series: [{
          type: 'radar',
          data: [{ value: DIMS.map(k => res.dims && res.dims[k] != null ? res.dims[k] : 0), name: '能力得分', areaStyle: { color: 'rgba(23,105,224,.22)' }, lineStyle: { color: '#1769e0', width: 2 }, itemStyle: { color: '#1769e0' } }],
        }],
      });
      window.__charts.push(chart);
    }
  }

  async function runMatch() {
    const jobId = document.getElementById('m-job').value;
    const threshold = parseInt(document.getElementById('m-threshold').value, 10) || 60;
    if (!jobId) { toast('请先选择岗位', 'err'); return; }
    const btn = document.getElementById('m-run');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>AI 匹配中…（大模型生成推荐理由约需 10-60 秒）';
    try {
      const r = await API.post('/api/match', { job_id: jobId, threshold });
      renderResults(r.data);
      toast('匹配完成：' + r.data.matched_count + ' 人达到阈值', 'ok');
    } catch (e) {
      toast(e.message, 'err');
    } finally {
      btn.disabled = false;
      btn.textContent = '开始 AI 匹配';
    }
  }

  function renderResults(record) {
    const box = document.getElementById('m-results');
    const res = record.results || [];
    box.innerHTML =
      (record.ai_enabled
        ? '<div class="match-tip ok-tip">已接入 DeepSeek 大模型，推荐理由由 AI 实时生成</div>'
        : '<div class="match-tip warn">当前未配置 DeepSeek API Key，推荐理由使用本地规则生成。配置方式：系统设置 → AI 配置。</div>') +
      '<div class="match-tip">岗位「' + esc(record.job_name) + '」· 适配分阈值 ≥ ' + esc(record.threshold) + ' · 候选 ' + esc(record.total_candidates) + ' 人 · 匹配 ' + esc(record.matched_count) + ' 人 · ' + esc(record.created_at) + '</div>' +
      (res.length ? res.map((r, i) =>
        '<div class="result-row">' +
        '<div class="rr-top">' +
        '<span class="stat-label">No.' + (i + 1) + '</span>' +
        '<span class="rr-name">' + esc(r.name_masked) + '</span>' +
        badgeHtml(r.rating) +
        '<span class="tag">' + esc(r.major) + ' · ' + esc(r.grade) + '</span>' +
        '<span class="stat-label" style="margin-left:auto">适配分</span>' +
        '<div class="fit-bar" style="margin:auto 0"><i style="width:' + Math.max(2, r.fit) + '%"></i></div>' +
        '<b class="num" style="color:#1769e0;font-size:18px">' + esc(r.fit) + '</b>' +
        '<button class="btn btn-primary" style="padding:5px 12px;font-size:13px" data-id="' + i + '">查看详情</button>' +
        '</div>' +
        '<div class="rr-reason"><span class="ai-src">' + (r.reason_source === 'ai' ? 'AI 推荐 · ' : '本地规则 · ') + '</span>' + esc(r.reason) + '</div>' +
        '</div>').join('')
        : '<div class="empty">没有学生达到该适配分阈值，可降低阈值后重试</div>');
    box.querySelectorAll('button[data-id]').forEach(b => b.onclick = () => detailModal(res[parseInt(b.dataset.id, 10)]));
    const link = document.getElementById('m-goto-report');
    if (link) { link.classList.remove('hidden'); link.onclick = () => { location.hash = '#/reports'; }; }
  }

  window.Match = {
    render: async function () {
      const body = document.getElementById('page-body');
      body.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载岗位…</div>';
      let jobs = [];
      try {
        const r = await API.get('/api/jobs');
        jobs = r.data;
      } catch (e) {
        if (!body.isConnected) return;
        body.innerHTML = '<div class="empty">加载失败：' + esc(e.message) + '</div>';
        return;
      }
      if (!body.isConnected) return;
      body.innerHTML =
        '<div class="card">' +
        '<div class="card-title">匹配参数设置</div>' +
        '<div class="form-grid">' +
        '<div class="field"><label>选择岗位 *</label><select id="m-job">' +
        '<option value="">—— 请选择岗位 ——</option>' +
        jobs.map(j => '<option value="' + esc(j.id) + '">' + esc(j.name) + '（' + esc(j.type) + '）</option>').join('') +
        '</select></div>' +
        '<div class="field"><label>适配分阈值（仅展示 ≥ 该分数）</label>' +
        '<div style="display:flex;align-items:center;gap:12px"><input type="range" id="m-threshold-range" min="0" max="100" step="5" value="60" style="flex:1">' +
        '<input type="number" id="m-threshold" min="0" max="100" value="60" style="width:76px;text-align:center"></div></div>' +
        '</div>' +
        '<div class="btn-row"><button class="btn btn-primary" id="m-run">开始 AI 匹配</button>' +
        '<button class="btn hidden" id="m-goto-report">前往报告中心查看记录</button></div>' +
        '</div>' +
        '<div id="m-results"></div>';
      if (!jobs.length) {
        body.querySelector('#m-results').innerHTML = '<div class="match-tip warn">暂无岗位，请先到「岗位管理」创建岗位，再进行匹配。</div>';
      }
      const range = body.querySelector('#m-threshold-range');
      const num = body.querySelector('#m-threshold');
      range.oninput = () => { num.value = range.value; };
      num.oninput = () => { range.value = Math.max(0, Math.min(100, parseInt(num.value, 10) || 0)); };
      body.querySelector('#m-run').onclick = runMatch;
    },
  };
})();
