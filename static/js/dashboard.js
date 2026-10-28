/* ===== 首页总看板 ===== */
(function () {
  'use strict';
  const { esc, toast, API, badgeHtml } = window.App;

  const ICON = {
    people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="17" cy="9" r="2.6"/><path d="M15.6 14.1c2.3.5 4.1 1.9 4.7 4.9"/></svg>',
    briefcase: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="7" width="18" height="12" rx="2"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7"/><path d="M3 12h18"/></svg>',
    card: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M6 15c.4-1.6 1.6-2.4 3-2.4s2.6.8 3 2.4"/><path d="M14.5 9h4M14.5 12.5h4M14.5 16h3"/></svg>',
    bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M13 3 5 13h5l-1 8 8-10h-5z"/></svg>',
  };

  function statCard(cls, icon, num, label) {
    return '<div class="stat-card"><div class="stat-icon ' + cls + '">' + icon + '</div>' +
      '<div><div class="stat-num">' + esc(num) + '</div><div class="stat-label">' + esc(label) + '</div></div></div>';
  }

  function makeChart(id, option) {
    const el = document.getElementById(id);
    if (!el || typeof echarts === 'undefined') return;
    const chart = echarts.init(el);
    chart.setOption(option);
    window.__charts.push(chart);
  }

  window.Dashboard = {
    render: async function () {
      const body = document.getElementById('page-body');
      body.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载看板数据…</div>';
      let d;
      try {
        const r = await API.get('/api/dashboard');
        d = r.data;
      } catch (e) {
        if (!body.isConnected) return;
        body.innerHTML = '<div class="empty">' + esc(e.message) + '</div>';
        return;
      }
      if (!body.isConnected) return; // 路由已切换，放弃写入旧节点
      const dist = d.rating_dist || { S: 0, A: 0, B: 0, C: 0 };
      const avg = d.dim_avg || {};
      const recent = (d.recent_matches || []);
      body.innerHTML =
        '<div class="stat-grid">' +
        statCard('i1', ICON.people, d.student_total, '学生总数') +
        statCard('i2', ICON.briefcase, d.job_total, '岗位数量') +
        statCard('i3', ICON.card, d.profile_total, '已生成画像数') +
        statCard('i4', ICON.bolt, d.match_total, '匹配记录') +
        '</div>' +
        '<div class="chart-grid">' +
        '<div class="chart-half"><div class="card-title">人才等级分布</div><div id="chart-pie" class="chart-box"></div></div>' +
        '<div class="chart-half"><div class="card-title">各维度平均得分</div><div id="chart-bar" class="chart-box"></div></div>' +
        '</div>' +
        '<div class="card"><div class="card-title">快捷操作</div><div class="quick-grid">' +
        '<div class="quick-btn" id="qb-job"><div class="qb-icon">' + ICON.briefcase + '</div><div class="qb-title">新建岗位</div><div class="qb-desc">录入岗位要求与能力权重</div></div>' +
        '<div class="quick-btn" id="qb-import"><div class="qb-icon">' + ICON.card + '</div><div class="qb-title">批量导入学生数据</div><div class="qb-desc">Excel 上传 · 自动清洗提示</div></div>' +
        '<div class="quick-btn" id="qb-match"><div class="qb-icon">' + ICON.bolt + '</div><div class="qb-title">一键 AI 匹配</div><div class="qb-desc">智能生成推荐理由</div></div>' +
        '</div></div>' +
        '<div class="card"><div class="card-title">最近匹配记录 <span class="tag">' + recent.length + ' 条</span></div>' +
        (recent.length
          ? '<table class="tbl"><thead><tr><th>岗位</th><th>阈值</th><th>匹配人数</th><th>时间</th><th></th></tr></thead><tbody>' +
            recent.map(m => '<tr><td>' + esc(m.job_name) + '</td><td>≥ ' + esc(m.threshold) + ' 分</td><td class="num">' + esc(m.matched_count) + '</td><td>' + esc(m.created_at) + '</td>' +
              '<td><a href="#/reports">查看报告</a></td></tr>').join('') + '</tbody></table>'
          : '<div class="empty">暂无匹配记录，点击上方「一键 AI 匹配」开始第一次匹配</div>') +
        '</div>';

      document.getElementById('qb-job').onclick = () => { location.hash = '#/jobs?new=1'; };
      document.getElementById('qb-import').onclick = () => { location.hash = '#/settings?tab=import'; };
      document.getElementById('qb-match').onclick = () => { location.hash = '#/match'; };

      makeChart('chart-pie', {
        tooltip: { trigger: 'item', formatter: '{b} 级：{c} 人（{d}%）' },
        legend: { bottom: 0, data: ['S', 'A', 'B', 'C'] },
        series: [{
          type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { formatter: '{b} 级 {c} 人' },
          data: [
            { value: dist.S, name: 'S', itemStyle: { color: '#e8b339' } },
            { value: dist.A, name: 'A', itemStyle: { color: '#22a06b' } },
            { value: dist.B, name: 'B', itemStyle: { color: '#3b82c4' } },
            { value: dist.C, name: 'C', itemStyle: { color: '#94a3b8' } },
          ],
        }],
      });

      makeChart('chart-bar', {
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 16, top: 24, bottom: 28 },
        xAxis: { type: 'category', data: ['学业', '荣誉', '实践', '科创', '综合素质'], axisLine: { lineStyle: { color: '#d6deea' } } },
        yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#eef2f8' } } },
        series: [{
          type: 'bar', barWidth: 34,
          data: [avg.academic, avg.honor, avg.practice, avg.sci, avg.quality].map(v => {
            const color = (typeof echarts !== 'undefined' && echarts.graphic && echarts.graphic.LinearGradient)
              ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: '#1769e0' }, { offset: 1, color: '#00b4d8' }])
              : '#1769e0';
            return { value: v == null ? 0 : v, itemStyle: { color } };
          }),
          label: { show: true, position: 'top', formatter: '{c}' },
        }],
      });
    },
  };
})();
