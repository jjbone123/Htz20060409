/* ===== 报告中心 ===== */
(function () {
  'use strict';
  const { esc, toast, API, confirmBox, badgeHtml, downloadText, openModal } = window.App;

  function txtReport(m) {
    const lines = [];
    lines.push('岗位智能匹配报告');
    lines.push('岗位：' + m.job_name + '（' + (m.job_type || '') + '）');
    lines.push('适配分阈值：≥ ' + m.threshold + ' 分');
    lines.push('候选学生：' + (m.total_candidates || '-') + ' 人　匹配人数：' + m.matched_count + ' 人');
    lines.push('执行人：' + (m.operator || '-') + '　生成时间：' + m.created_at);
    lines.push('AI 推荐理由：' + (m.ai_enabled ? '已接入 DeepSeek 大模型' : '本地规则生成（未配置 API Key）'));
    lines.push('');
    m.results.forEach((r, i) => {
      lines.push('No.' + (i + 1) + '　' + r.name_masked + '（' + r.major + '·' + r.grade + '）　评级 ' + r.rating + '　适配分 ' + r.fit);
      lines.push('  五维得分：' + ['academic', 'honor', 'practice', 'sci', 'quality'].map(k => (r.dims ? r.dims[k] : '-')).join(' / ') +
        '　专业匹配 ' + r.major_match + '　技能匹配 ' + r.skill_match);
      lines.push('  推荐理由：' + r.reason);
    });
    return lines.join('\n');
  }

  function preview(m) {
    // 全屏报告视图
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:80;background:#eef2f8;overflow:auto;padding:20px';
    overlay.innerHTML = '<div style="max-width:900px;margin:0 auto">' +
      '<div class="no-print" style="display:flex;gap:10px;margin-bottom:12px;align-items:center">' +
      '<button class="btn btn-primary" id="rp-pdf">下载 PDF</button>' +
      '<button class="btn" id="rp-print">打印</button>' +
      '<button class="btn" id="rp-txt">下载 TXT</button>' +
      '<button class="btn" id="rp-close">返回列表</button>' +
      '<span class="stat-label" style="margin-left:auto">PDF 由系统直接生成，可保存到任意位置</span></div>' +
      '<div class="report-paper" id="report-paper">' +
      '<h2>岗位智能匹配报告</h2>' +
      '<div class="report-meta">' +
      '岗位：<b>' + esc(m.job_name) + '</b>（' + esc(m.job_type || '') + '）　|　适配分阈值：≥ ' + esc(m.threshold) + ' 分<br>' +
      '候选学生：' + esc(m.total_candidates || '-') + ' 人　|　匹配人数：<b>' + esc(m.matched_count) + '</b> 人<br>' +
      '执行人：' + esc(m.operator || '-') + '　|　生成时间：' + esc(m.created_at) + '<br>' +
      '推荐理由来源：' + (m.ai_enabled ? 'DeepSeek 大模型（AI 生成）' : '本地规则（未配置 API Key）') +
      '</div>' +
      '<div class="card-title">匹配结果明细（按适配分降序）</div>' +
      '<table class="report-table"><thead><tr><th>排名</th><th>学生（脱敏）</th><th>专业 / 年级</th><th>评级</th><th>适配分</th><th>推荐理由</th></tr></thead><tbody>' +
      (m.results || []).map((r, i) =>
        '<tr><td>' + (i + 1) + '</td><td>' + esc(r.name_masked) + '</td><td>' + esc(r.major) + ' / ' + esc(r.grade) + '</td>' +
        '<td>' + esc(r.rating) + '</td><td><b>' + esc(r.fit) + '</b></td><td style="font-size:12px">' + esc(r.reason) + '</td></tr>').join('') +
      '</tbody></table>' +
      '</div></div>';
    document.body.appendChild(overlay);
    document.body.classList.add('printing');
    overlay.querySelector('#rp-pdf').onclick = () => { window.open('/api/matches/' + m.id + '/pdf'); };
    overlay.querySelector('#rp-print').onclick = () => window.print();
    overlay.querySelector('#rp-txt').onclick = () => downloadText('岗位匹配报告_' + m.job_name + '.txt', txtReport(m));
    overlay.querySelector('#rp-close').onclick = () => { overlay.remove(); document.body.classList.remove('printing'); };
  }

  async function showCompare(ids) {
    const m = openModal({ lg: true });
    m.setTitle('多轮匹配对比');
    m.setBody('<div class="loading"><span class="spinner"></span>正在加载记录…</div>');
    try {
      const recs = [];
      for (const id of ids) {
        const d = await API.get('/api/matches/' + id);
        recs.push(d.data);
      }
      const labels = recs.map((r, i) => '匹配 ' + (i + 1) + '（' + r.created_at.slice(5, 16) + '）');
      const cell = function (v) { return '<td class="num">' + esc(v) + '</td>'; };
      let html = '<div class="table-wrap"><table class="tbl"><thead><tr><th>指标</th>' +
        labels.map(l => '<th>' + esc(l) + '</th>').join('') + '</tr></thead><tbody>';
      html += '<tr><td><b>适配分阈值</b></td>' + recs.map(r => cell('≥ ' + r.threshold)).join('') + '</tr>';
      html += '<tr><td><b>匹配人数</b></td>' + recs.map(r => cell(r.matched_count + ' / ' + r.total_candidates)).join('') + '</tr>';
      html += '<tr><td><b>推荐理由来源</b></td>' + recs.map(r => '<td>' + (r.ai_enabled ? 'AI 生成' : '本地规则') + '</td>').join('') + '</tr>';
      html += '<tr><td><b>执行人</b></td>' + recs.map(r => '<td>' + esc(r.operator) + '</td>').join('') + '</tr>';
      for (let i = 0; i < 5; i++) {
        html += '<tr><td><b>Top ' + (i + 1) + '</b></td>' + recs.map(r => {
          const t = r.results && r.results[i];
          return '<td>' + (t ? esc(t.name_masked) + '　' + esc(t.fit) + ' 分' : '<span style="color:#8a99ab">—</span>') + '</td>';
        }).join('') + '</tr>';
      }
      html += '</tbody></table></div>';
      // Top5 重合度（两两）
      const top5 = recs.map(r => (r.results || []).slice(0, 5).map(x => x.name_masked));
      const overlap = [];
      for (let i = 0; i < recs.length; i++) {
        for (let j = i + 1; j < recs.length; j++) {
          const common = top5[i].filter(n => top5[j].indexOf(n) >= 0).length;
          overlap.push('「' + labels[i] + '」与「' + labels[j] + '」Top5 重合 <b>' + common + '</b> 人');
        }
      }
      html += '<div class="card-title" style="margin-top:14px">Top 5 重合度</div><div class="tag-list">' +
        overlap.map(o => '<span class="tag" style="background:#eef3fb">' + o + '</span>').join('') + '</div>';
      m.setBody(html);
      m.setFoot('<button class="btn" id="cmp-close">关 闭</button>');
      m.modal.querySelector('#cmp-close').onclick = () => m.close();
    } catch (e) {
      m.setBody('<div class="empty">' + esc(e.message) + '</div>');
    }
  }

  async function load() {
    const body = document.getElementById('page-body');
    body.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载匹配记录…</div>';
    const sel = new Set();
    try {
      const [mr, jr] = await Promise.all([API.get('/api/matches'), API.get('/api/jobs')]);
      if (!body.isConnected) return;
      const list = mr.data;
      const jobs = jr.data;
      body.innerHTML =
        '<div class="btn-row" style="margin:0 0 14px;align-items:center">' +
        '<select id="rp-filter" style="max-width:240px"><option value="">全部岗位</option>' +
        jobs.map(j => '<option value="' + esc(j.id) + '">' + esc(j.name) + '</option>').join('') + '</select>' +
        '<button class="btn" id="rp-compare">对比所选（2-4 条）</button>' +
        '<span class="stat-label" id="rp-count">共 ' + list.length + ' 条记录</span></div>' +
        '<div class="card"><div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th style="width:34px"><input type="checkbox" id="rp-all"></th>' +
        '<th>岗位</th><th>类型</th><th>阈值</th><th>匹配人数</th><th>推荐理由来源</th><th>执行人</th><th>时间</th><th>操作</th>' +
        '</tr></thead><tbody>' +
        (list.length ? list.map(m =>
          '<tr data-id="' + esc(m.id) + '"><td><input type="checkbox" class="rp-check" data-id="' + esc(m.id) + '"></td>' +
          '<td><b>' + esc(m.job_name) + '</b></td><td>' + esc(m.job_type) + '</td>' +
          '<td class="num">≥ ' + esc(m.threshold) + '</td><td class="num">' + esc(m.matched_count) + ' / ' + esc(m.total_candidates) + '</td>' +
          '<td>' + (m.ai_enabled ? '<span class="tag" style="background:#e6f5ee;color:#17674a">AI 生成</span>' : '<span class="tag">本地规则</span>') + '</td>' +
          '<td>' + esc(m.operator) + '</td><td>' + esc(m.created_at) + '</td>' +
          '<td><button class="link-btn rp-view" data-id="' + esc(m.id) + '">预览报告</button>　' +
          '<button class="link-btn danger rp-del" data-id="' + esc(m.id) + '">删除</button></td></tr>').join('')
          : '<tr><td colspan="9"><div class="empty">暂无匹配记录，请到「AI 智能匹配」模块执行一次匹配</div></td></tr>') +
        '</tbody></table></div></div>';
      const filter = body.querySelector('#rp-filter');
      const countEl = body.querySelector('#rp-count');
      const refreshRows = function () {
        const f = filter.value;
        body.querySelectorAll('tbody tr[data-id]').forEach(tr => {
          tr.style.display = (f && tr.dataset.jobId !== f) ? 'none' : '';
        });
      };
      // 记录行标记 job_id（用于筛选）
      const jobIdOf = {};
      list.forEach(m => { jobIdOf[m.id] = m.job_id || ''; });
      body.querySelectorAll('tbody tr[data-id]').forEach(tr => {
        tr.dataset.jobId = jobIdOf[tr.dataset.id] || '';
      });
      filter.onchange = () => {
        sel.clear();
        body.querySelectorAll('.rp-check').forEach(c => { c.checked = false; });
        refreshRows();
      };
      body.querySelectorAll('.rp-check').forEach(c => {
        c.onchange = () => {
          if (c.checked) sel.add(c.dataset.id); else sel.delete(c.dataset.id);
          if (sel.size > 4) { sel.delete(c.dataset.id); c.checked = false; toast('最多同时对比 4 条记录', 'err'); }
          countEl.textContent = '已选 ' + sel.size + ' 条';
        };
      });
      body.querySelector('#rp-all').onchange = (e) => {
        sel.clear();
        body.querySelectorAll('.rp-check').forEach(c => {
          c.checked = e.target.checked;
          if (c.checked) sel.add(c.dataset.id);
        });
        if (sel.size > 4) {
          let keep = 0;
          body.querySelectorAll('.rp-check').forEach(c => {
            if (c.checked && keep >= 4) { c.checked = false; sel.delete(c.dataset.id); }
            else if (c.checked) keep++;
          });
          toast('最多同时对比 4 条记录', 'err');
        }
        countEl.textContent = '已选 ' + sel.size + ' 条';
      };
      body.querySelector('#rp-compare').onclick = () => {
        if (sel.size < 2) { toast('请至少勾选 2 条记录进行对比', 'err'); return; }
        showCompare([...sel]);
      };
      body.querySelectorAll('.rp-view').forEach(b => b.onclick = async () => {
        try {
          const d = await API.get('/api/matches/' + b.dataset.id);
          preview(d.data);
        } catch (e) { toast(e.message, 'err'); }
      });
      body.querySelectorAll('.rp-del').forEach(b => b.onclick = async () => {
        const ok = await confirmBox('删除匹配记录', '确定删除该条匹配记录吗？删除后不可恢复。', '删 除');
        if (!ok) return;
        try {
          await API.del('/api/matches/' + b.dataset.id);
          toast('记录已删除', 'ok');
          load();
        } catch (e) { toast(e.message, 'err'); }
      });
    } catch (e) {
      body.innerHTML = '<div class="empty">加载失败：' + esc(e.message) + '</div>';
    }
  }

  window.Reports = {
    render: function () { load(); },
  };
})();
