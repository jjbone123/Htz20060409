/* ===== 核心框架：请求 / 登录态 / 路由 / 弹窗 / Toast ===== */
(function () {
  'use strict';

  // ---------- API ----------
  const API = {
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    async req(path, opts = {}) {
      const headers = Object.assign({}, opts.headers || {});
      if (this.token) headers['X-Token'] = this.token;
      let body = opts.body;
      if (body && typeof body !== 'string' && !(body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(body);
      }
      const res = await fetch(path, Object.assign({}, opts, { headers, body }));
      if (res.status === 401) {
        window.App.logout('登录已失效，请重新登录');
        throw new Error('未登录');
      }
      const ct = res.headers.get('content-type') || '';
      let data = null;
      if (ct.includes('application/json')) {
        data = await res.json();
      } else {
        data = await res.text();
      }
      if (!res.ok && data && data.msg !== undefined && !data.ok) {
        const err = new Error(data.msg || '请求失败');
        err.data = data;
        throw err;
      }
      return data;
    },
    get(path) { return this.req(path); },
    post(path, body) { return this.req(path, { method: 'POST', body }); },
    put(path, body) { return this.req(path, { method: 'PUT', body }); },
    del(path) { return this.req(path, { method: 'DELETE' }); },
  };

  // ---------- 工具 ----------
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function toast(msg, type) {
    const root = document.getElementById('toast-root');
    const t = document.createElement('div');
    t.className = 'toast' + (type === 'err' ? ' err' : type === 'ok' ? ' ok' : '');
    t.textContent = msg;
    root.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 320); }, 3200);
  }
  function openModal(html, { lg } = {}) {
    const root = document.getElementById('modal-root');
    const mask = document.createElement('div');
    mask.className = 'modal-mask';
    mask.innerHTML = '<div class="modal' + (lg ? ' lg' : '') + '">' +
      '<div class="modal-head"><h3></h3><button class="modal-close">&times;</button></div>' +
      '<div class="modal-body"></div><div class="modal-foot"></div></div>';
    mask.querySelector('.modal-close').onclick = () => mask.remove();
    mask.addEventListener('mousedown', (e) => { if (e.target === mask) mask.remove(); });
    root.appendChild(mask);
    const modal = mask.querySelector('.modal');
    return {
      mask, modal,
      setTitle(t) { modal.querySelector('.modal-head h3').textContent = t; },
      setBody(h) { modal.querySelector('.modal-body').innerHTML = h; },
      setFoot(h) { modal.querySelector('.modal-foot').innerHTML = h; },
      close() { mask.remove(); },
      onclose(fn) { mask.addEventListener('click', function handler(e) { if (!mask.contains(e.target)) return; if (e.target === mask || e.target.classList.contains('modal-close')) { fn && fn(); } }); },
    };
  }
  function confirmBox(title, text, okText) {
    return new Promise((resolve) => {
      const m = openModal();
      m.setTitle(title || '确认');
      m.setBody('<p style="font-size:14px;color:#33475b">' + esc(text) + '</p>');
      m.setFoot('<button class="btn btn-ghost cancel">取消</button><button class="btn btn-primary do">' + esc(okText || '确定') + '</button>');
      m.modal.querySelector('.cancel').onclick = () => { m.close(); resolve(false); };
      m.modal.querySelector('.do').onclick = () => { m.close(); resolve(true); };
    });
  }
  function badgeHtml(rating) {
    return '<span class="badge ' + esc(rating) + '">' + esc(rating) + '</span>';
  }

  // ---------- 路由 ----------
  const MENU = [
    { key: 'dashboard', label: '首页看板' },
    { key: 'talent', label: '学生人才库' },
    { key: 'jobs', label: '岗位管理' },
    { key: 'match', label: 'AI 智能匹配' },
    { key: 'reports', label: '报告中心' },
    { key: 'settings', label: '系统设置', adminOnly: true },
  ];
  const ROUTERS = {
    dashboard: () => window.Dashboard.render(),
    talent: () => window.Talent.render(),
    jobs: () => window.Jobs.render(),
    match: () => window.Match.render(),
    reports: () => window.Reports.render(),
    settings: () => window.Settings.render(),
  };
  const TITLES = {
    dashboard: ['首页总看板', '数据统计 · 人才分布 · 快捷操作'],
    talent: ['学生人才库', '多维筛选 · 能力画像 · 批量导出'],
    jobs: ['岗位管理', '维护招聘岗位与能力权重'],
    match: ['AI 智能匹配', 'AI 驱动 · 岗位 × 学生精准匹配'],
    reports: ['报告中心', '历史匹配记录 · 预览 · 导出 PDF'],
    settings: ['系统设置', '指标权重 · 用户权限 · 数据导入 · AI 配置（管理员）'],
  };

  function parseHash() {
    let h = location.hash.replace(/^#\/?/, '') || 'dashboard';
    let tab = null;
    const qi = h.indexOf('?');
    if (qi >= 0) {
      const qs = h.slice(qi + 1);
      h = h.slice(0, qi);
      const m = qs.match(/tab=([^&]+)/);
      if (m) tab = decodeURIComponent(m[1]);
    }
    return { page: h, tab };
  }

  function renderNav(active) {
    const nav = document.getElementById('main-nav');
    const role = window.App.user ? window.App.user.role : 'hr';
    nav.innerHTML = MENU.filter(m => !m.adminOnly || role === 'admin').map(m =>
      '<a href="#/' + m.key + '" class="' + (m.key === active ? 'active' : '') + '">' + m.label + '</a>').join('');
  }

  function route() {
    if (!window.App.user) return;
    const { page, tab } = parseHash();
    const role = window.App.user.role;
    const menu = MENU.find(m => m.key === page);
    if (!menu || (menu.adminOnly && role !== 'admin')) {
      location.hash = '#/dashboard';
      return;
    }
    renderNav(page);
    const t = TITLES[page] || ['', ''];
    const content = document.getElementById('content');
    content.innerHTML = '<h1 class="page-title">' + esc(t[0]) + '</h1><p class="page-sub">' + esc(t[1]) + '</p><div id="page-body"></div>';
    window.App.page = page;
    window.App.tab = tab;
    if (window.__charts) {
      window.__charts.forEach(c => { try { c.dispose(); } catch (e) { } });
      window.__charts = [];
    }
    try {
      ROUTERS[page]();
    } catch (e) {
      content.querySelector('#page-body').innerHTML = '<div class="empty">页面加载出错：' + esc(e.message) + '</div>';
    }
  }

  // ---------- 登录 / 退出 ----------
  async function doLogin() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    if (!username || !password) { toast('请输入账号和密码', 'err'); return; }
    const btn = document.getElementById('login-btn');
    btn.disabled = true; btn.textContent = '登录中…';
    try {
      const r = await API.post('/api/login', { username, password });
      API.token = r.token; API.user = r.user;
      window.App.user = r.user;
      localStorage.setItem('token', r.token);
      localStorage.setItem('user', JSON.stringify(r.user));
      showApp();
      toast('欢迎回来，' + r.user.name, 'ok');
    } catch (e) {
      toast(e.message || '登录失败', 'err');
    } finally {
      btn.disabled = false; btn.textContent = '登 录';
    }
  }

  function logout(msg) {
    API.token = ''; API.user = null;
    window.App.user = null;
    localStorage.removeItem('token'); localStorage.removeItem('user');
    if (msg) toast(msg);
    showLogin();
  }

  function showApp() {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('app-view').classList.remove('hidden');
    document.getElementById('user-name').textContent = (API.user.name || API.user.username);
    const badge = document.getElementById('role-badge');
    badge.textContent = API.user.role === 'admin' ? '管理员' : 'HR 专员';
    badge.classList.toggle('admin', API.user.role === 'admin');
    if (!location.hash || location.hash === '#/') {
      location.hash = '#/dashboard';  // 触发 hashchange → route()，避免重复渲染
    } else {
      route();
    }
  }

  function showLogin() {
    document.getElementById('app-view').classList.add('hidden');
    document.getElementById('login-view').classList.remove('hidden');
  }

  // ---------- 导出帮助 ----------
  function downloadText(filename, text) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }
  function openPrintWindow(html) {
    const w = window.open('', '_blank');
    if (!w) { toast('浏览器拦截了新窗口，请允许弹出窗口', 'err'); return null; }
    w.document.write(html);
    w.document.close();
    return w;
  }

  window.App = {
    API, esc, toast, openModal, confirmBox, badgeHtml, downloadText, openPrintWindow,
    route, logout, user: API.user, page: 'dashboard', tab: null,
  };

  // ---------- 事件绑定 ----------
  document.getElementById('login-btn').onclick = doLogin;
  document.getElementById('login-password').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
  document.getElementById('login-username').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
  document.getElementById('logout-btn').onclick = () => logout('已退出登录');
  window.addEventListener('hashchange', route);

  window.__charts = [];
  window.addEventListener('resize', () => {
    (window.__charts || []).forEach(c => { try { c.resize(); } catch (e) { } });
  });

  if (API.user && API.token) {
    showApp();
  } else {
    showLogin();
  }
})();
