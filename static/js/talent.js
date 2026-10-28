/* ===== 学生人才库 ===== */
(function () {
  'use strict';
  const { esc, toast, API, openModal, confirmBox, badgeHtml, downloadText, openPrintWindow } = window.App;

  const PAGE_SIZE = 10;
  let state = { list: [], filters: {}, page: 1, selected: new Set(), total: 0 };

  function filterHtml() {
    return '' +
      '<div class="filter-bar">' +
      '<div class="fitem"><label>专业</label><select id="f-major"><option value="">全部专业</option></select></div>' +
      '<div class="fitem"><label>年级</label><select id="f-grade"><option value="">全部年级</option></select></div>' +
      '<div class="fitem"><label>获奖情况</label><select id="f-award"><option value="">全部</option><option value="有">有获奖</option><option value="无">无获奖</option></select></div>' +
      '<div class="fitem"><label>科创经历</label><select id="f-sci"><option value="">全部</option><option value="有">有科创</option><option value="无">无科创</option></select></div>' +
      '<div class="fitem"><label>综合评级</label><select id="f-rating"><option value="">全部</option><option value="S">S 级</option><option value="A">A 级</option><option value="B">B 级</option><option value="C">C 级</option></select></div>' +
      '<div class="fitem"><label>关键词</label><input id="f-q" placeholder="姓名/专业/技能" style="min-width:150px"></div>' +
      '<button class="btn btn-primary" id="f-search">筛 选</button>' +
      '<button class="btn" id="f-reset">重 置</button>' +
      '</div>';
  }

  function renderList() {
    const body = document.getElementById('page-body');
    const start = (state.page - 1) * PAGE_SIZE;
    const rows = state.list.slice(start, start + PAGE_SIZE);
    const tbody = rows.map(s => {
      const checked = state.selected.has(s.id) ? ' checked' : '';
      return '<tr>' +
        '<td><input type="checkbox" class="chk row-chk" data-id="' + esc(s.id) + '"' + checked + '></td>' +
        '<td><b>' + esc(s.name_masked) + '</b></td>' +
        '<td>' + esc(s.student_no_masked) + '</td>' +
        '<td>' + esc(s.major) + '</td>' +
        '<td>' + esc(s.grade) + '</td>' +
        '<td class="num">' + esc(s.award_count) + '</td>' +
        '<td class="num">' + esc(s.sci_count) + '</td>' +
        '<td class="num">' + (s.weighted !== null ? esc(s.weighted) : '—') + '</td>' +
        '<td>' + (s.rating === '-' ? '<span class="badge -">—</span>' : badgeHtml(s.rating)) + '</td>' +
        '<td><button class="link-btn view-btn" data-id="' + esc(s.id) + '">查看画像</button></td>' +
        '</tr>';
    }).join('');
    const pageCount = Math.max(1, Math.ceil(state.list.length / PAGE_SIZE));
    body.innerHTML = filterHtml() +
      '<div class="card">' +
      '<div class="card-title">学生列表 <span class="tag">共 ' + state.total + ' 人</span></div>' +
      '<div class="table-wrap"><table class="tbl"><thead><tr>' +
      '<th><input type="checkbox" class="chk" id="chk-all" ' + (state.list.length && state.selected.size === state.list.length ? 'checked' : '') + '></th>' +
      '<th>姓名（脱敏）</th><th>学号</th><th>专业</th><th>年级</th><th>获奖</th><th>科创</th><th>综合得分</th><th>评级</th><th>操作</th>' +
      '</tr></thead><tbody>' + tbody + '</tbody></table></div>' +
      '<div class="btn-row">' +
      '<span class="stat-label" id="sel-info">已选 ' + state.selected.size + ' 人</span>' +
      '<button class="btn btn-primary" id="btn-export" ' + (state.selected.size ? '' : 'disabled') + '>批量导出画像摘要</button>' +
      '<button class="btn" id="btn-csv">导出 CSV（当前筛选）</button>' +
      '<div class="spacer"></div>' +
      '</div>' +
      (pageCount > 1 ? '<div class="pager">' +
        '<button id="pg-prev" ' + (state.page > 1 ? '' : 'disabled') + '>上一页</button>' +
        '<span>第 ' + state.page + ' / ' + pageCount + ' 页</span>' +
        '<button id="pg-next" ' + (state.page < pageCount ? '' : 'disabled') + '>下一页</button></div>' : '') +
      '</div>';

    // 绑定筛选
    const majors = body.querySelector('#f-major');
    const grades = body.querySelector('#f-grade');
    API.get('/api/students/meta').then(r => {
      majors.innerHTML = '<option value="">全部专业</option>' + r.majors.map(m => '<option>' + esc(m) + '</option>').join('');
      grades.innerHTML = '<option value="">全部年级</option>' + r.grades.map(g => '<option>' + esc(g) + '</option>').join('');
      if (state.filters.major) majors.value = state.filters.major;
      if (state.filters.grade) grades.value = state.filters.grade;
    }).catch(e => toast(e.message, 'err'));
    body.querySelector('#f-major').value = state.filters.major || '';
    body.querySelector('#f-grade').value = state.filters.grade || '';
    body.querySelector('#f-award').value = state.filters.award || '';
    body.querySelector('#f-sci').value = state.filters.sci || '';
    body.querySelector('#f-rating').value = state.filters.rating || '';
    body.querySelector('#f-q').value = state.filters.q || '';

    // 事件
    body.querySelector('#f-search').onclick = () => {
      state.filters = {
        major: body.querySelector('#f-major').value,
        grade: body.querySelector('#f-grade').value,
        award: body.querySelector('#f-award').value,
        sci: body.querySelector('#f-sci').value,
        rating: body.querySelector('#f-rating').value,
        q: body.querySelector('#f-q').value.trim(),
      };
      state.page = 1; state.selected.clear();
      load();
    };
    body.querySelector('#f-reset').onclick = () => { state.filters = {}; state.page = 1; state.selected.clear(); load(); };
    body.querySelector('#chk-all').onchange = (e) => {
      const on = e.target.checked;
      rows.forEach(s => on ? state.selected.add(s.id) : state.selected.delete(s.id));
      body.querySelectorAll('.row-chk').forEach(c => c.checked = on);
      updateSel();
    };
    body.querySelectorAll('.row-chk').forEach(c => c.onchange = (e) => {
      const id = e.target.dataset.id;
      e.target.checked ? state.selected.add(id) : state.selected.delete(id);
      const all = body.querySelector('#chk-all');
      if (all) all.checked = state.list.length && state.selected.size === state.list.length;
      updateSel();
    });
    body.querySelectorAll('.view-btn').forEach(b => b.onclick = () => showProfile(b.dataset.id));
    body.querySelector('#btn-export').onclick = exportSummary;
    body.querySelector('#btn-csv').onclick = exportCsv;
    const prev = body.querySelector('#pg-prev');
    const next = body.querySelector('#pg-next');
    if (prev) prev.onclick = () => { state.page--; renderList(); };
    if (next) next.onclick = () => { state.page++; renderList(); };
  }

  function updateSel() {
    const info = document.getElementById('sel-info');
    const btn = document.getElementById('btn-export');
    if (info) info.textContent = '已选 ' + state.selected.size + ' 人';
    if (btn) btn.disabled = !state.selected.size;
  }

  async function load() {
    const body = document.getElementById('page-body');
    body.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载学生数据…</div>';
    try {
      const params = new URLSearchParams();
      Object.keys(state.filters).forEach(k => { if (state.filters[k]) params.set(k, state.filters[k]); });
      const r = await API.get('/api/students?' + params.toString());
      if (!body.isConnected) return;
      state.list = r.data;
      state.total = r.data.length;
      state.page = 1;
      // 清除已不存在的选中项
      const ids = new Set(r.data.map(s => s.id));
      [...state.selected].forEach(id => { if (!ids.has(id)) state.selected.delete(id); });
      renderList();
    } catch (e) {
      body.innerHTML = '<div class="empty">加载失败：' + esc(e.message) + '</div>';
    }
  }

  async function bindShare(m, id, shareState) {
    const btn = m.modal.querySelector('#pf-share');
    const box = m.modal.querySelector('#share-result');
    const img = m.modal.querySelector('#share-qr');
    const link = m.modal.querySelector('#share-link');
    const expire = m.modal.querySelector('#share-expire');
    const unshare = m.modal.querySelector('#pf-unshare');

    async function show(url, expires) {
      box.style.display = 'block';
      btn.textContent = '重新生成链接';
      link.href = url;
      link.textContent = url;
      expire.textContent = expires;
      try {
        if (typeof window.qrcode === 'function') {
          const qr = window.qrcode(0, 'M');
          qr.addData(url);
          qr.make();
          img.src = qr.createDataURL(4, 6);
        }
      } catch (e) { img.style.display = 'none'; }
    }
    function hide() {
      box.style.display = 'none';
      btn.textContent = '生成分享链接';
      img.style.display = '';
    }

    if (shareState && shareState.active) {
      await show(shareState.share_url, shareState.expires_at);
    }
    btn.onclick = async () => {
      try {
        const r = await API.post('/api/students/' + id + '/share', {});
        toast('分享链接已生成', 'ok');
        await show(r.data.share_url, r.data.expires_at);
      } catch (e) { toast(e.message, 'err'); }
    };
    unshare.onclick = async () => {
      try {
        await API.del('/api/students/' + id + '/share');
        toast('已撤销分享', 'ok');
        hide();
      } catch (e) { toast(e.message, 'err'); }
    };
  }

  async function exportCsv() {
    const params = new URLSearchParams();
    Object.keys(state.filters).forEach(k => { if (state.filters[k]) params.set(k, state.filters[k]); });
    try {
      const res = await fetch('/api/students/export.csv?' + params.toString(), {
        headers: { 'X-Token': API.token },
      });
      if (!res.ok) {
        const j = await res.json().catch(() => null);
        throw new Error(j && j.msg ? j.msg : '导出失败');
      }
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = '学生人才库_当前筛选.csv';
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 3000);
      toast('CSV 已导出（当前筛选 ' + state.total + ' 人）', 'ok');
    } catch (e) {
      toast(e.message, 'err');
    }
  }

  async function showProfile(id) {
    const m = openModal({ lg: true });
    m.setTitle('学生能力画像');
    m.setBody('<div class="loading"><span class="spinner"></span>加载中…</div>');
    try {
      const r = await API.get('/api/students/' + id);
      const d = r.data;
      const sc = d.scores || {};
      const dimNames = d.dim_names || {};
      const order = ['academic', 'honor', 'practice', 'sci', 'quality'];
      m.setBody(
        '<div class="profile-head">' +
        '<div class="profile-info">' +
        '<p class="pi-row"><b style="font-size:16px">' + esc(d.name_masked) + '</b>　' + (d.rating === '-' ? '' : badgeHtml(d.rating)) + '</p>' +
        '<p class="pi-row">专业：' + esc(d.major) + '　|　年级：' + esc(d.grade) + '</p>' +
        '<p class="pi-row">学号：' + esc(d.student_no_masked) + '　|　综合得分：<b>' + esc(d.weighted !== null ? d.weighted : '未生成') + '</b></p>' +
        '<p class="pi-row">技能：</p><div class="tag-list" style="margin:2px 0 8px">' + ((d.skills || []).map(s => '<span class="tag">' + esc(s) + '</span>').join('') || '<span style="color:#8a99ab">无</span>') + '</div>' +
        '</div>' +
        '<div id="radar-box" style="width:340px;height:280px;flex-shrink:0"></div>' +
        '</div>' +
        '<div class="card-title">五维能力得分</div>' +
        '<div class="score-grid">' +
        order.map(k => '<div class="score-cell"><div class="sc-num">' + esc(sc[k] !== undefined && sc[k] !== null ? sc[k] : '—') + '</div><div class="sc-name">' + esc(dimNames[k] || k) + '</div></div>').join('') +
        '</div>' +
        '<div style="margin-top:14px">' +
        '<div class="card-title">获奖情况</div><div class="tag-list">' + (d.awards && d.awards.length ? d.awards.filter(a => a !== '无').map(a => '<span class="tag">' + esc(a) + '</span>').join('') : '<span style="color:#8a99ab">暂无</span>') + '</div>' +
        '<div class="card-title" style="margin-top:12px">科创经历</div><div class="tag-list">' + (d.sci_exp && d.sci_exp.length ? d.sci_exp.filter(x => x !== '无').map(x => '<span class="tag">' + esc(x) + '</span>').join('') : '<span style="color:#8a99ab">暂无</span>') + '</div>' +
        '</div>' +
        (d.worst_dim ? '<div class="match-tip warn" style="margin-top:14px">短板诊断：<b>' + esc(dimNames[d.worst_dim]) + '</b> 维度得分相对最低（' + esc(sc[d.worst_dim]) + ' 分）。提升建议：' + esc(d.advice) + '</div>' : '') +
        '<div class="card-title" style="margin-top:16px">扫码分享画像</div>' +
        '<div id="share-box">' +
        '<button class="btn btn-primary" id="pf-share">生成分享链接</button>' +
        '<span class="stat-label" style="margin-left:10px">学生可用手机扫码查看本人画像（24 小时有效）</span>' +
        '<div id="share-result" style="display:none;margin-top:10px;padding:12px 16px;border:1px dashed #b8c8dd;border-radius:8px;background:#f8fafd">' +
        '<div style="display:flex;gap:16px;align-items:center">' +
        '<img id="share-qr" width="132" height="132" alt="分享二维码" style="border:1px solid #e2e8f0;border-radius:6px">' +
        '<div style="flex:1">' +
        '<p style="margin:0 0 6px">分享链接：<a id="share-link" target="_blank" rel="noopener" style="color:#1769e0"></a></p>' +
        '<p class="stat-label" style="margin:0 0 8px">有效期至：<span id="share-expire"></span></p>' +
        '<button class="btn" id="pf-unshare">撤销分享</button>' +
        '</div></div></div>' +
        '</div>'
      );
      m.setFoot('<button class="btn" id="pf-close">关 闭</button>');
      m.modal.querySelector('#pf-close').onclick = () => m.close();
      bindShare(m, id, d.share);
      const el = document.getElementById('radar-box');
      if (el && typeof echarts !== 'undefined') {
        const chart = echarts.init(el);
        chart.setOption({
          tooltip: {},
          radar: {
            indicator: order.map(k => ({ name: dimNames[k] || k, max: 100 })),
            radius: '65%',
            splitArea: { areaStyle: { color: ['#f4f8fe', '#eef3fb'] } },
            axisName: { color: '#33527f' },
          },
          series: [{
            type: 'radar',
            data: [{ value: order.map(k => sc[k] != null ? sc[k] : 0), name: '能力得分', areaStyle: { color: 'rgba(23,105,224,.22)' }, lineStyle: { color: '#1769e0', width: 2 }, itemStyle: { color: '#1769e0' } }],
          }],
        });
        window.__charts.push(chart);
        window.addEventListener('resize', function rh() { try { chart.resize(); } catch (e) { } }, { once: true });
      }
    } catch (e) {
      m.setBody('<div class="empty">' + esc(e.message) + '</div>');
    }
  }

  async function exportSummary() {
    if (!state.selected.size) { toast('请先勾选学生', 'err'); return; }
    const ids = [...state.selected];
    try {
      const r = await API.post('/api/students/export-summary', { ids });
      const html = r.html.replace('</body>',
        '<div class="tools" style="margin-top:16px"><button onclick="window.print()">导出 PDF / 打印</button>' +
        '<button id="dl-txt">下载 TXT 摘要</button></div>' +
        '<script>document.getElementById("dl-txt").onclick=function(){var b=new Blob([' + JSON.stringify(r.txt) + '],{type:"text/plain;charset=utf-8"});var a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="学生画像摘要.txt";a.click();};<\/script>' +
        '</body>');
      const w = openPrintWindow(html);
      if (!w) return;
      toast('已生成画像摘要（' + ids.length + ' 人）', 'ok');
    } catch (e) {
      toast(e.message, 'err');
    }
  }

  window.Talent = {
    render: function () {
      load();
    },
  };
})();
