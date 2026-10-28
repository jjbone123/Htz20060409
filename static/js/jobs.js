/* ===== 岗位管理 ===== */
(function () {
  'use strict';
  const { esc, toast, API, openModal, confirmBox } = window.App;

  const DIMS = ['academic', 'honor', 'practice', 'sci', 'quality'];
  const DIM_NAMES = { academic: '学业', honor: '荣誉', practice: '实践', sci: '科创', quality: '综合素质' };
  const TYPES = ['技术类', '产品类', '运营类', '设计类', '职能类', '其他'];
  const WEIGHT_TEMPLATES = {
    tech: { label: '技术类岗位', w: { academic: 30, honor: 10, practice: 20, sci: 25, quality: 15 } },
    product: { label: '运营类岗位', w: { academic: 20, honor: 15, practice: 25, sci: 10, quality: 30 } },
    design: { label: '设计类岗位', w: { academic: 15, honor: 10, practice: 30, sci: 20, quality: 25 } },
  };

  let jobs = [];

  function weightEditor(weights) {
    const w = Object.assign({ academic: 30, honor: 10, practice: 20, sci: 25, quality: 15 }, weights || {});
    const rows = DIMS.map(k =>
      '<div class="weight-row"><label>' + DIM_NAMES[k] + '</label>' +
      '<input type="range" min="0" max="100" step="5" data-dim="' + k + '" value="' + w[k] + '">' +
      '<input type="number" min="0" max="100" data-num="' + k + '" value="' + w[k] + '"></div>').join('');
    return '<div class="card-title">五大能力维度权重（合计须为 100）</div>' + rows +
      '<div class="weight-sum" id="weight-sum">当前合计：' + (Object.values(w).reduce((a, b) => a + b, 0)) + '</div>';
  }

  function splitList(v) {
    return (v || '').split(/[、，,;；\n]/).map(s => s.trim()).filter(Boolean);
  }

  function jobForm(job) {
    const m = openModal({ lg: true });
    m.setTitle(job ? '编辑岗位' : '新建岗位');
    m.setBody(
      '<div class="form-grid">' +
      '<div class="field"><label>岗位名称 *</label><input id="jf-name" value="' + esc(job ? job.name : '') + '" placeholder="如：后端开发实习生"></div>' +
      '<div class="field"><label>岗位类型</label><select id="jf-type">' + TYPES.map(t => '<option' + (job && job.type === t ? ' selected' : '') + '>' + t + '</option>').join('') + '</select></div>' +
      '<div class="field full"><label>职责简介</label><textarea id="jf-desc" rows="3" placeholder="简要描述岗位工作内容与培养方向">' + esc(job ? job.desc : '') + '</textarea></div>' +
      '<div class="field"><label>专业要求</label><input id="jf-major" value="' + esc(job ? (job.major_req || []).join('、') : '') + '" placeholder="用顿号分隔，如：计算机科学与技术、软件工程"></div>' +
      '<div class="field"><label>技能要求</label><input id="jf-skill" value="' + esc(job ? (job.skill_req || []).join('、') : '') + '" placeholder="用顿号分隔，如：Python、数据库"></div>' +
      '</div>' +
      '<div class="field full" style="margin-top:14px"><label>权重模板（快捷填充）</label>' +
      '<select id="jf-wtemplate"><option value="">自定义（手动填写）</option>' +
      Object.keys(WEIGHT_TEMPLATES).map(k => '<option value="' + k + '">' + WEIGHT_TEMPLATES[k].label + '</option>').join('') +
      '</select></div>' +
      '<div style="margin-top:14px">' + weightEditor(job ? job.weights : null) + '</div>'
    );
    m.setFoot('<button class="btn" id="jf-cancel">取 消</button><button class="btn btn-primary" id="jf-save">保 存</button>');
    m.modal.querySelector('#jf-cancel').onclick = () => m.close();

    // 权重模板：选中后自动填充五大维度权重
    const tmplSel = m.modal.querySelector('#jf-wtemplate');
    tmplSel.onchange = () => {
      const t = WEIGHT_TEMPLATES[tmplSel.value];
      if (!t) return;
      DIMS.forEach(k => {
        const num = m.modal.querySelector('input[data-num="' + k + '"]');
        const range = m.modal.querySelector('input[data-dim="' + k + '"]');
        num.value = t.w[k];
        range.value = t.w[k];
      });
      syncSum();
      toast('已套用「' + t.label + '」权重模板', 'ok');
    };

    // 权重联动
    const sumEl = m.modal.querySelector('#weight-sum');
    function syncSum() {
      let total = 0;
      m.modal.querySelectorAll('.weight-row').forEach(row => {
        const dim = row.querySelector('input[type=range]').dataset.dim;
        const num = row.querySelector('input[type=number]');
        const v = parseInt(num.value, 10) || 0;
        row.querySelector('input[type=range]').value = v;
        total += v;
      });
      sumEl.textContent = '当前合计：' + total;
      sumEl.className = 'weight-sum ' + (total === 100 ? 'ok' : 'err');
      return total;
    }
    m.modal.querySelectorAll('input[type=range]').forEach(r => {
      r.oninput = () => { m.modal.querySelector('input[data-num="' + r.dataset.dim + '"]').value = r.value; syncSum(); };
    });
    m.modal.querySelectorAll('input[type=number]').forEach(n => {
      n.oninput = () => { n.value = Math.max(0, Math.min(100, parseInt(n.value, 10) || 0)); syncSum(); };
    });
    syncSum();

    m.modal.querySelector('#jf-save').onclick = async () => {
      const name = m.modal.querySelector('#jf-name').value.trim();
      if (!name) { toast('请填写岗位名称', 'err'); return; }
      if (syncSum() !== 100) { toast('五大维度权重之和必须为 100', 'err'); return; }
      const weights = {};
      m.modal.querySelectorAll('.weight-row').forEach(row => {
        const dim = row.querySelector('input[type=range]').dataset.dim;
        weights[dim] = parseInt(row.querySelector('input[type=number]').value, 10) || 0;
      });
      const payload = {
        name,
        type: m.modal.querySelector('#jf-type').value,
        desc: m.modal.querySelector('#jf-desc').value.trim(),
        major_req: splitList(m.modal.querySelector('#jf-major').value),
        skill_req: splitList(m.modal.querySelector('#jf-skill').value),
        weights,
      };
      try {
        if (job) {
          await API.put('/api/jobs/' + job.id, payload);
          toast('岗位已更新', 'ok');
        } else {
          await API.post('/api/jobs', payload);
          toast('岗位已创建', 'ok');
        }
        m.close();
        load();
      } catch (e) {
        toast(e.message, 'err');
      }
    };
  }

  async function load() {
    const body = document.getElementById('page-body');
    body.innerHTML = '<div class="loading"><span class="spinner"></span>正在加载岗位…</div>';
    try {
      const r = await API.get('/api/jobs');
      if (!body.isConnected) return;
      jobs = r.data;
      body.innerHTML =
        '<div class="btn-row" style="margin:0 0 14px">' +
        '<button class="btn btn-primary" id="job-new">＋ 新建岗位</button>' +
        '<span class="stat-label">共 ' + jobs.length + ' 个岗位</span></div>' +
        '<div class="card"><div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>岗位名称</th><th>岗位类型</th><th>专业要求</th><th>技能要求</th><th>创建时间</th><th>操作</th>' +
        '</tr></thead><tbody>' +
        (jobs.length ? jobs.map(j =>
          '<tr><td><b>' + esc(j.name) + '</b></td><td>' + esc(j.type) + '</td>' +
          '<td><div class="tag-list">' + (j.major_req && j.major_req.length ? j.major_req.map(m => '<span class="tag">' + esc(m) + '</span>').join('') : '<span style="color:#8a99ab">不限</span>') + '</div></td>' +
          '<td><div class="tag-list">' + (j.skill_req && j.skill_req.length ? j.skill_req.map(s => '<span class="tag">' + esc(s) + '</span>').join('') : '<span style="color:#8a99ab">不限</span>') + '</div></td>' +
          '<td>' + esc(j.created_at) + '</td>' +
          '<td><button class="link-btn j-edit" data-id="' + esc(j.id) + '">编辑</button>　' +
          '<button class="link-btn danger j-del" data-id="' + esc(j.id) + '">删除</button></td></tr>').join('')
          : '<tr><td colspan="6"><div class="empty">暂无岗位，点击「新建岗位」创建第一个岗位</div></td></tr>') +
        '</tbody></table></div></div>';
      body.querySelector('#job-new').onclick = () => jobForm(null);
      body.querySelectorAll('.j-edit').forEach(b => b.onclick = () => {
        const j = jobs.find(x => x.id === b.dataset.id);
        if (j) jobForm(j);
      });
      body.querySelectorAll('.j-del').forEach(b => b.onclick = async () => {
        const j = jobs.find(x => x.id === b.dataset.id);
        let hint = '删除后不可恢复。';
        try {
          const mr = await API.get('/api/matches?job_id=' + j.id);
          if (mr.data.length) {
            hint = '该岗位已有 ' + mr.data.length + ' 条历史匹配记录：删除后岗位不可再匹配，但历史报告与记录仍保留可查看。';
          }
        } catch (e) { /* 查询失败则用默认提示 */ }
        const ok = await confirmBox('删除岗位', '确定删除岗位「' + (j ? j.name : '') + '」吗？' + hint, '删 除');
        if (!ok) return;
        try {
          await API.del('/api/jobs/' + b.dataset.id);
          toast('岗位已删除', 'ok');
          load();
        } catch (e) { toast(e.message, 'err'); }
      });
    } catch (e) {
      body.innerHTML = '<div class="empty">加载失败：' + esc(e.message) + '</div>';
    }
  }

  window.Jobs = {
    render: function () {
      const isNew = location.hash.indexOf('new=1') >= 0;
      load().then(() => { if (isNew) jobForm(null); });
    },
  };
})();
