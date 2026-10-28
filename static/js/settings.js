/* ===== 系统设置（管理员专属） ===== */
(function () {
  'use strict';
  const { esc, toast, API, openModal, confirmBox } = window.App;

  const DIMS = ['academic', 'honor', 'practice', 'sci', 'quality'];
  const DIM_NAMES = { academic: '学业', honor: '荣誉', practice: '实践', sci: '科创', quality: '综合素质' };

  async function loadSettings() {
    const r = await API.get('/api/settings');
    return r.data;
  }

  // ---------- Tab 1：权重配置 ----------
  async function tabWeights(holder) {
    holder.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    let s;
    try {
      s = await loadSettings();
    } catch (e) {
      if (!holder.isConnected) return;
      holder.innerHTML = '<div class="empty">' + esc(e.message) + '</div>';
      return;
    }
    if (!holder.isConnected) return;
    const w = Object.assign({ academic: 30, honor: 10, practice: 20, sci: 25, quality: 15 }, s.dim_weights || {});
    holder.innerHTML =
      '<div class="card"><div class="card-title">五大能力维度权重配置</div>' +
      '<p class="form-note" style="margin-bottom:12px">权重影响学生综合得分与岗位适配分计算，合计必须为 100。修改后立即对后续匹配生效。</p>' +
      DIMS.map(k =>
        '<div class="weight-row"><label>' + DIM_NAMES[k] + '</label>' +
        '<input type="range" min="0" max="100" step="5" data-dim="' + k + '" value="' + w[k] + '">' +
        '<input type="number" min="0" max="100" data-num="' + k + '" value="' + w[k] + '"></div>').join('') +
      '<div class="weight-sum" id="ws-sum">当前合计：' + (DIMS.reduce((a, k) => a + w[k], 0)) + '</div>' +
      '<div class="btn-row"><button class="btn btn-primary" id="ws-save">保存权重</button></div></div>';

    const sumEl = holder.querySelector('#ws-sum');
    function sync() {
      let total = 0;
      holder.querySelectorAll('.weight-row').forEach(row => {
        const dim = row.querySelector('input[type=range]').dataset.dim;
        const num = row.querySelector('input[type=number]');
        const v = Math.max(0, Math.min(100, parseInt(num.value, 10) || 0));
        num.value = v;
        row.querySelector('input[type=range]').value = v;
        total += v;
      });
      sumEl.textContent = '当前合计：' + total;
      sumEl.className = 'weight-sum ' + (total === 100 ? 'ok' : 'err');
      return total;
    }
    holder.querySelectorAll('input[type=range]').forEach(r => r.oninput = () => {
      holder.querySelector('input[data-num="' + r.dataset.dim + '"]').value = r.value;
      sync();
    });
    holder.querySelectorAll('input[type=number]').forEach(n => n.oninput = () => sync());
    sync();
    holder.querySelector('#ws-save').onclick = async () => {
      if (sync() !== 100) { toast('权重之和必须为 100', 'err'); return; }
      const dim_weights = {};
      holder.querySelectorAll('.weight-row').forEach(row => {
        const dim = row.querySelector('input[type=range]').dataset.dim;
        dim_weights[dim] = parseInt(row.querySelector('input[type=number]').value, 10) || 0;
      });
      try {
        await API.put('/api/settings', { dim_weights });
        toast('权重已保存', 'ok');
      } catch (e) { toast(e.message, 'err'); }
    };
  }

  // ---------- Tab 2：用户权限 ----------
  async function tabUsers(holder) {
    holder.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    let users;
    try {
      const r = await API.get('/api/users');
      users = r.data;
    } catch (e) {
      holder.innerHTML = '<div class="empty">' + esc(e.message) + '</div>';
      return;
    }
    holder.innerHTML =
      '<div class="btn-row" style="margin:0 0 14px"><button class="btn btn-primary" id="u-add">＋ 新增 HR 账号</button>' +
      '<span class="stat-label">共 ' + users.length + ' 个账号（管理员 ' + users.filter(x => x.role === 'admin').length + ' 个）</span></div>' +
      '<div class="card"><div class="table-wrap"><table class="tbl"><thead><tr>' +
      '<th>账号</th><th>姓名</th><th>角色</th><th>创建时间</th><th>操作</th></tr></thead><tbody>' +
      users.map(x =>
        '<tr><td><b>' + esc(x.username) + '</b></td><td>' + esc(x.name) + '</td>' +
        '<td>' + (x.role === 'admin' ? '<span class="tag" style="background:#fff1e6;color:#b25e00">管理员</span>' : '<span class="tag" style="background:#e6f5ee;color:#17674a">HR 专员</span>') + '</td>' +
        '<td>' + esc(x.created_at) + '</td>' +
        '<td><button class="link-btn u-edit" data-id="' + esc(x.id) + '">编辑</button>　' +
        '<button class="link-btn danger u-del" data-id="' + esc(x.id) + '">删除</button></td></tr>').join('') +
      '</tbody></table></div>' +
      '<p class="form-note" style="margin-top:10px">权限说明：HR 专员可使用除「系统设置」外的全部模块；管理员拥有全部权限。</p></div>';

    function userModal(user) {
      const m = openModal();
      m.setTitle(user ? '编辑账号' : '新增 HR 账号');
      m.setBody(
        '<div class="field"><label>账号 *</label><input id="um-username" value="' + esc(user ? user.username : '') + '" ' + (user ? 'disabled style="background:#f4f7fc"' : '') + '></div>' +
        '<div class="field"><label>姓名</label><input id="um-name" value="' + esc(user ? user.name : '') + '"></div>' +
        '<div class="field"><label>角色</label><select id="um-role"><option value="hr"' + (user && user.role === 'hr' ? ' selected' : '') + '>HR 专员</option><option value="admin"' + (user && user.role === 'admin' ? ' selected' : '') + '>管理员</option></select></div>' +
        '<div class="field"><label>' + (user ? '重置密码（留空则不修改）' : '密码 *（至少 6 位）') + '</label><input id="um-pwd" type="password" placeholder="' + (user ? '不修改请留空' : '请输入密码') + '"></div>'
      );
      m.setFoot('<button class="btn" id="um-cancel">取 消</button><button class="btn btn-primary" id="um-save">保 存</button>');
      m.modal.querySelector('#um-cancel').onclick = () => m.close();
      m.modal.querySelector('#um-save').onclick = async () => {
        const username = m.modal.querySelector('#um-username').value.trim();
        const name = m.modal.querySelector('#um-name').value.trim();
        const role = m.modal.querySelector('#um-role').value;
        const password = m.modal.querySelector('#um-pwd').value;
        try {
          if (user) {
            const payload = { name: name || user.name, role };
            if (password) payload.password = password;
            await API.put('/api/users/' + user.id, payload);
            toast('账号已更新', 'ok');
          } else {
            if (!username || !password) { toast('账号与密码不能为空', 'err'); return; }
            await API.post('/api/users', { username, name, role, password });
            toast('账号已创建', 'ok');
          }
          m.close();
          tabUsers(holder);
        } catch (e) { toast(e.message, 'err'); }
      };
    }

    holder.querySelector('#u-add').onclick = () => userModal(null);
    holder.querySelectorAll('.u-edit').forEach(b => b.onclick = () => userModal(users.find(x => x.id === b.dataset.id)));
    holder.querySelectorAll('.u-del').forEach(b => b.onclick = async () => {
      const t = users.find(x => x.id === b.dataset.id);
      const ok = await confirmBox('删除账号', '确定删除账号「' + (t ? t.username : '') + '」吗？', '删 除');
      if (!ok) return;
      try {
        await API.del('/api/users/' + b.dataset.id);
        toast('账号已删除', 'ok');
        tabUsers(holder);
      } catch (e) { toast(e.message, 'err'); }
    });
  }

  // ---------- Tab 3：数据导入 ----------
  async function tabImport(holder) {
    let total = 0;
    try {
      const r = await API.get('/api/students');
      total = r.data.length;
    } catch (e) { }
    holder.innerHTML =
      '<div class="card"><div class="card-title">批量导入学生数据</div>' +
      '<p class="form-note">支持 .xlsx / .csv 文件。表头必须包含：姓名、学号、专业，以及五大维度得分（学业得分、荣誉得分、实践得分、科创得分、综合素质得分）。<br>' +
      '当前学生库共 <b>' + total + '</b> 人。建议先下载模板，按模板格式整理数据后上传。</p>' +
      '<div class="btn-row" style="margin:12px 0 0">' +
      '<button class="btn" id="imp-tpl">下载导入模板（.xlsx）</button>' +
      '<label class="btn btn-primary" style="cursor:pointer">选择文件<input type="file" id="imp-file" accept=".xlsx,.xlsm,.csv" style="display:none"></label>' +
      '<button class="btn btn-ok" id="imp-run" disabled>开始导入</button></div>' +
      '<div class="field" style="margin-top:12px"><input id="imp-path" readonly placeholder="未选择文件" style="background:#f4f7fc"></div></div>' +
      '<div id="imp-report"></div>';

    holder.querySelector('#imp-tpl').onclick = async () => {
      try {
        const res = await fetch('/api/students/template', { headers: { 'X-Token': window.App.API.token } });
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = '学生数据导入模板.xlsx';
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      } catch (e) { toast('模板下载失败', 'err'); }
    };
    let file = null;
    const fi = holder.querySelector('#imp-file');
    const pathInput = holder.querySelector('#imp-path');
    fi.onchange = () => {
      file = fi.files[0];
      pathInput.value = file ? file.name : '';
      holder.querySelector('#imp-run').disabled = !file;
    };
    holder.querySelector('#imp-run').onclick = async () => {
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      const btn = holder.querySelector('#imp-run');
      btn.disabled = true; btn.textContent = '清洗导入中…';
      try {
        const r = await API.post('/api/students/import', fd);
        const d = r.data;
        holder.querySelector('#imp-report').innerHTML =
          '<div class="card"><div class="card-title">数据清洗结果</div><div class="clean-report">' +
          '<p class="cr-item">成功导入：<b class="add">' + d.added_count + '</b> 人（当前学生总数 ' + d.student_total + '）</p>' +
          (d.duplicate_count ? '<p class="cr-item">重复跳过：<b class="dup">' + d.duplicate_count + '</b> 条' + (d.duplicates.length ? '<div style="font-size:12px;color:#8a99ab">' + d.duplicates.map(x => '· ' + esc(x)).join('<br>') + '</div>' : '') + '</p>' : '') +
          (d.invalid_count ? '<p class="cr-item">无效行跳过：<b class="bad">' + d.invalid_count + '</b> 条' + (d.invalid.length ? '<div style="font-size:12px;color:#8a99ab">' + d.invalid.map(x => '· ' + esc(x)).join('<br>') + '</div>' : '') + '</p>' : '') +
          (d.warn_count ? '<p class="cr-item">自动修正提示：<b class="dup">' + d.warn_count + '</b> 条' + (d.warns.length ? '<div style="font-size:12px;color:#8a99ab">' + d.warns.map(x => '· ' + esc(x)).join('<br>') + '</div>' : '') + '</p>' : '') +
          '</div></div>';
        toast('导入完成：新增 ' + d.added_count + ' 人', 'ok');
      } catch (e) {
        holder.querySelector('#imp-report').innerHTML = '<div class="match-tip warn">' + esc(e.message) + '</div>';
      } finally {
        btn.disabled = false; btn.textContent = '开始导入';
      }
    };
  }

  // ---------- Tab 4：AI 配置 ----------
  async function tabAI(holder) {
    holder.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    let s;
    try {
      s = await loadSettings();
    } catch (e) {
      if (!holder.isConnected) return;
      holder.innerHTML = '<div class="empty">' + esc(e.message) + '</div>';
      return;
    }
    if (!holder.isConnected) return;
    const ds = s.deepseek || {};
    holder.innerHTML =
      '<div class="card"><div class="card-title">DeepSeek 大模型配置</div>' +
      '<p class="form-note" style="margin-bottom:12px">配置后 AI 智能匹配将调用 DeepSeek 大模型生成每位候选人的推荐理由。API Key 仅保存在本机 data/settings.json 中，不会出现在浏览器。未配置时系统自动使用本地规则生成推荐理由。</p>' +
      '<div class="form-grid">' +
      '<div class="field full"><label>API Key</label><input id="ai-key" type="password" placeholder="' + (ds.api_key ? '已配置（如需更换请填写新 Key）' : '请输入 DeepSeek API Key') + '" style="font-family:monospace"></div>' +
      '<div class="field"><label>接口地址</label><input id="ai-base" value="' + esc(ds.base_url || 'https://api.deepseek.com') + '"></div>' +
      '<div class="field"><label>模型名称</label><input id="ai-model" value="' + esc(ds.model || 'deepseek-chat') + '"></div>' +
      '</div>' +
      '<div class="btn-row"><button class="btn btn-primary" id="ai-save">保存配置</button>' +
      '<button class="btn" id="ai-test">测试连接</button>' +
      '<span id="ai-result" class="stat-label"></span></div></div>';

    holder.querySelector('#ai-save').onclick = async () => {
      const deepseek = {
        api_key: holder.querySelector('#ai-key').value.trim(),
        base_url: holder.querySelector('#ai-base').value.trim() || 'https://api.deepseek.com',
        model: holder.querySelector('#ai-model').value.trim() || 'deepseek-chat',
      };
      if (!deepseek.api_key && !ds.api_key) { toast('请先填写 API Key', 'err'); return; }
      try {
        await API.put('/api/settings', { deepseek });
        toast('配置已保存', 'ok');
        tabAI(holder);
      } catch (e) { toast(e.message, 'err'); }
    };
    holder.querySelector('#ai-test').onclick = async () => {
      const res = holder.querySelector('#ai-result');
      res.textContent = '测试中…';
      try {
        const r = await API.post('/api/settings/test-ai', {});
        res.textContent = r.msg;
        toast(r.ok ? '连接成功' : '连接失败', r.ok ? 'ok' : 'err');
      } catch (e) { res.textContent = e.message; }
    };
  }

  const TABS = [
    { key: 'weights', label: '指标权重配置', fn: tabWeights },
    { key: 'users', label: '用户权限管理', fn: tabUsers },
    { key: 'import', label: '数据导入', fn: tabImport },
    { key: 'ai', label: 'AI 配置', fn: tabAI },
  ];

  window.Settings = {
    render: function () {
      const body = document.getElementById('page-body');
      let active = window.App.tab || 'weights';
      if (!TABS.find(t => t.key === active)) active = 'weights';
      body.innerHTML = '<div class="tabs">' + TABS.map(t =>
        '<button data-key="' + t.key + '" class="' + (t.key === active ? 'active' : '') + '">' + t.label + '</button>').join('') +
        '</div><div id="set-holder"></div>';
      const holder = body.querySelector('#set-holder');
      body.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
        active = b.dataset.key;
        body.querySelectorAll('.tabs button').forEach(x => x.classList.toggle('active', x === b));
        const t = TABS.find(x => x.key === active);
        t.fn(holder);
      });
      TABS.find(t => t.key === active).fn(holder);
    },
  };
})();
