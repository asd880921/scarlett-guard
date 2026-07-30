/* Scarlett Guard —— 前端邏輯
 *
 * 動態原則：
 *  - 所有按壓回饋走 CSS :active，在 pointer-down 當下就發生，不等 click。
 *  - 視圖與收合區塊用彈簧曲線，不用等長的線性過場。
 *  - 切換驅動模式要十幾秒，所以指示器在按下的當下就移到目標位置，
 *    失敗再滑回真實位置（CSS transition 從目前呈現值開始，不會跳）。
 *
 * 文案一律經過 i18n.js 的 t()；靜態文字用 HTML 上的 data-i18n 標記。
 */
(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const t = (key, params) => window.I18N.t(key, params);

  // ================================================================ 診斷
  // 這一段刻意放在最前面：任何在它之後發生的錯誤都會被接住。

  window.__SG_ERRORS = [];

  function reportError(where, error) {
    const detail = error && error.stack ? error.stack : String(error);
    // 先留在記憶體裡 —— 錯誤很可能發生在橋接就緒之前，那時送不出去
    window.__SG_ERRORS.push(`${where}: ${detail}`);
    try {
      toast('UI error', `${where}: ${detail}`.slice(0, 400), 'error', 15000);
    } catch (_) { /* DOM 還沒好 */ }
  }

  window.addEventListener('error', (event) =>
    reportError('window.onerror', event.error || event.message));
  window.addEventListener('unhandledrejection', (event) =>
    reportError('unhandledrejection', event.reason));

  // 橋接就緒後把累積的錯誤送到後端紀錄。沒有這條路徑的話，UI 的 JS 錯誤
  // 只會讓畫面安靜地半殘，從後端完全看不出任何異常。
  let flushed = 0;
  const flushTimer = setInterval(() => {
    const bridge = (window.pywebview && window.pywebview.api) || null;
    if (!bridge || !bridge.log_js_error) return;
    while (flushed < window.__SG_ERRORS.length) {
      bridge.log_js_error('js', window.__SG_ERRORS[flushed]);
      flushed += 1;
    }
  }, 800);
  window.addEventListener('beforeunload', () => clearInterval(flushTimer));

  const state = {
    config: {},
    device: null,
    driverMode: null,
    update: null,
    modePending: '',
    ghosts: [],
    history: [],
    autostart: false,
    elevated: false,
    busy: false,
    view: 'status',
  };

  // ================================================================ 工具

  function api() {
    return (window.pywebview && window.pywebview.api) || null;
  }

  /* 橋接是否「真的」可用。
   *
   * 不能只檢查 window.pywebview.api 是否存在：pywebview 會先建立一個空物件，
   * 方法是稍後才逐一掛上去的。所以直接檢查要用的方法本身。
   */
  function bridgeReady() {
    const bridge = api();
    return !!(bridge && typeof bridge.bootstrap === 'function');
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function call(method, ...args) {
    // 方法可能還沒掛上來（pywebview 是逐一注入的），短暫等待再放棄，
    // 而不是把一個暫時性的競態當成永久失敗回報給使用者。
    let bridge = api();
    for (let waited = 0; waited < 5000; waited += 100) {
      if (bridge && typeof bridge[method] === 'function') break;
      await sleep(100);
      bridge = api();
    }
    if (!bridge || typeof bridge[method] !== 'function') {
      return { ok: false, message: t('toast.bridge', { method }) };
    }
    try {
      return await bridge[method](...args);
    } catch (err) {
      return { ok: false, message: String(err) };
    }
  }

  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function toast(title, body = '', tone = 'info', ttl = 4200) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.dataset.tone = tone;
    el.innerHTML = `<div class="toast-title"></div>${body ? '<div class="toast-body"></div>' : ''}`;
    el.querySelector('.toast-title').textContent = title;
    if (body) el.querySelector('.toast-body').textContent = body;
    $('#toasts').appendChild(el);

    const remove = () => {
      if (!el.isConnected) return;
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), reduceMotion ? 30 : 240);
    };
    setTimeout(remove, ttl);
    el.addEventListener('click', remove);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ================================================================ 語言

  function applyLanguage(code) {
    window.I18N.setLanguage(code);
    window.I18N.apply();
    // 動態產生的內容不受 data-i18n 影響，必須自己重畫一次
    renderViewHeader();
    if (state.driverMode) renderDriverMode(state.driverMode);
    if (state.update) renderUpdate(state.update);
    renderTech();
    renderResetButton();
    renderHistory(state.history);
    renderGhosts();
    renderPaths(state.paths);
    renderLanguageSelect();
  }

  function renderLanguageSelect() {
    const select = $('#cfg-language');
    if (!select) return;
    const value = state.config.language || 'auto';
    select.innerHTML = '';
    const auto = document.createElement('option');
    auto.value = 'auto';
    auto.textContent = t('lang.auto');
    select.appendChild(auto);
    window.I18N.LANGUAGES.forEach((lang) => {
      const option = document.createElement('option');
      option.value = lang.code;
      option.textContent = lang.label;
      select.appendChild(option);
    });
    select.value = value;
  }

  // ================================================================ 視圖切換

  const VIEWS = ['status', 'settings'];

  function renderViewHeader() {
    $('#view-title').textContent = t(`view.${state.view}.title`);
    $('#view-sub').textContent = t(`view.${state.view}.sub`);
  }

  function switchView(name) {
    if (!VIEWS.includes(name)) return;
    state.view = name;
    $$('.nav-item').forEach((btn) => btn.classList.toggle('is-active', btn.dataset.view === name));
    renderViewHeader();

    $$('.view').forEach((view) => {
      const active = view.dataset.view === name;
      view.classList.toggle('is-active', active);
      if (active && !reduceMotion) {
        // 從目前值開始的短位移，收斂快、不過衝
        view.animate(
          [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }],
          { duration: 360, easing: 'cubic-bezier(0.32, 0.72, 0, 1)' }
        );
      }
    });
    $('#scroll').scrollTop = 0;

    if (name === 'settings') scanGhosts();
  }

  // ================================================================ 開關與收合

  function bindSwitch(sel, getter, setter) {
    const el = $(sel);
    if (!el) return;
    const toggle = () => {
      if (el.classList.contains('is-disabled')) return;
      setter(!el.classList.contains('is-on'));
    };
    el.addEventListener('click', toggle);
    el.addEventListener('keydown', (event) => {
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault();
        toggle();
      }
    });
    el._sync = () => {
      const on = !!getter();
      el.classList.toggle('is-on', on);
      el.setAttribute('aria-checked', String(on));
    };
  }

  function syncSwitches() {
    $$('.switch').forEach((el) => el._sync && el._sync());
  }

  /** 收合區塊。進階內容往下一層，但一按就到，不用換頁。 */
  function bindDisclosures() {
    $$('.disclose').forEach((box) => {
      const head = box.querySelector('.disclose-head');
      head.addEventListener('click', () => {
        const open = box.dataset.open !== 'true';
        box.dataset.open = String(open);
        head.setAttribute('aria-expanded', String(open));
      });
    });
  }

  // ================================================================ 設定寫入

  const pushSettings = debounce(async (values) => {
    const result = await call('update_settings', values);
    if (result && result.config) {
      state.config = result.config;
      syncSwitches();
    }
  }, 260);

  function setConfig(key, value, immediate = false) {
    state.config[key] = value;
    syncSwitches();
    if (immediate) {
      call('update_settings', { [key]: value }).then((result) => {
        if (result && result.config) state.config = result.config;
      });
    } else {
      pushSettings({ [key]: value });
    }
  }

  // ================================================================ 權限

  function applyElevation(elevated) {
    state.elevated = !!elevated;
    const pill = $('#elevation-pill');
    pill.dataset.tone = elevated ? 'ok' : 'error';
    $('#elevation-text').textContent = elevated ? t('elev.admin') : t('elev.none');
    $('#elevation-banner').hidden = !!elevated;
    renderResetButton();
  }

  // ================================================================ 更新提示

  /** 有新版才顯示。沒有更新時側欄不該多出一列東西。 */
  function renderUpdate(info) {
    if (!info) return;
    state.update = info;
    const pill = $('#update-pill');
    const show = !!(info.available && info.latest);
    pill.hidden = !show;
    if (!show) return;
    $('#update-text').textContent = t('update.available', { version: info.latest });
    pill.title = t('update.tip', { version: info.latest });
  }

  // ================================================================ 驅動模式（主功能）

  const modeLabel = (mode) => t(mode === 'asio' ? 'mode.asio.name' : 'mode.daily.name');

  function renderDriverMode(data) {
    if (!data) return;
    state.driverMode = data;

    const sw = $('#modeswitch');
    /* 切換要十幾秒。指示器在切換期間停在「目標」位置而不是原位 ——
     * 按下的當下就要有東西動，不然整個操作讀起來像沒接上。
     * 同時掛上 is-pending 明確表示「還沒確認」，失敗時再滑回真實位置。 */
    const shown = state.modePending || data.mode;
    sw.dataset.selected = shown === 'asio' ? 'asio' : 'daily';
    sw.classList.toggle('is-pending', !!state.modePending);

    const locked = !data.elevated || !data.available || state.busy || !!state.modePending;
    $$('.mode-option').forEach((btn) => {
      btn.setAttribute('aria-checked', String(btn.dataset.mode === shown));
      btn.disabled = locked;
    });

    renderModeStatus(data);
    renderTech();
    // 重置能不能按取決於目前是哪個模式，所以模式一變就要重算
    renderResetButton();
  }

  function renderModeStatus(data) {
    const el = $('#mode-status');
    let tone = 'ok';
    let text = '';

    if (state.modePending) {
      tone = 'busy';
      text = t('mode.status.switching', { mode: modeLabel(state.modePending) });
    } else if (!data.elevated) {
      tone = 'error';
      text = t('mode.status.noadmin');
    } else if (!data.available) {
      tone = 'error';
      text = t('mode.status.nodevice');
    } else if (!data.healthy) {
      tone = 'error';
      text = t('mode.status.unhealthy', { problem: data.root_problem || '—' });
    } else if (data.mode === 'unknown') {
      tone = 'warn';
      text = t('mode.status.unknown', { service: data.root_service || '—' });
    } else if (data.complete === false) {
      // 母節點換綁成功但音訊路徑沒起來。這個狀態最危險 —— 看起來像成功，
      // 實際上沒有可用裝置，所以一定要當成錯誤顯示。
      tone = 'error';
      text = t('mode.status.incomplete', { mode: modeLabel(data.mode) });
    } else {
      text = t('mode.status.ok', { mode: modeLabel(data.mode) });
    }

    el.dataset.tone = tone;
    el.textContent = text;

    // 裝置沒有可用驅動、或音訊路徑沒起來時，救援按鈕是唯一的出路
    const broken =
      !!data.elevated &&
      data.available &&
      (!data.healthy || data.mode === 'unknown' || data.complete === false);
    $('#mode-broken-banner').hidden = !broken;
    if (broken) {
      $('#mode-broken-detail').textContent = t('mode.broken.body', {
        service: data.root_service || '—',
      });
    }
  }

  async function refreshDriverMode(force = false) {
    const result = await call('driver_mode', force);
    if (result && result.driver_mode) renderDriverMode(result.driver_mode);
  }

  /** 套用動作結果裡附帶的驅動模式狀態。
   *
   * 後端在切換／修復收尾時會把自己剛探測到的狀態一起回傳，所以這裡是**權威**的。
   * 就算沒帶（舊路徑或呼叫失敗），也一定要用現有狀態重繪一次 —— modePending
   * 剛被清掉，不重繪的話指示器會停在「暫定」位置、按鈕啟用狀態也不會更新。
   */
  function applyModeResult(result) {
    if (result && result.driver_mode) {
      renderDriverMode(result.driver_mode);
    } else if (state.driverMode) {
      renderDriverMode(state.driverMode);
    }
  }

  async function doSwitchMode(mode) {
    const data = state.driverMode;
    if (!data || state.busy || state.modePending) return;
    if (!data.elevated || !data.available) return;
    if (data.mode === mode && data.complete) return;

    state.modePending = mode;
    renderDriverMode(data);
    toast(t('toast.mode.start', { mode: modeLabel(mode) }), t('toast.mode.start.sub'), 'info', 7000);

    const result = await call('switch_driver_mode', mode);
    state.modePending = '';
    // 後端把切換後的狀態一起帶回來了，立刻套用 —— 不能等背景推送，
    // 那中間有好幾秒會拿舊狀態算出「重置可按」「指示器該回到舊模式」等錯誤結論
    applyModeResult(result);

    if (result && result.ok) {
      toast(t('toast.mode.ok', { mode: modeLabel(mode) }), result.detail || '', 'ok', 6000);
    } else {
      // 切換失敗可能讓 Windows 完全沒有音訊裝置，訊息一定要留久一點
      toast(
        t('toast.mode.fail'),
        [(result && result.message) || '', (result && result.detail) || '']
          .filter(Boolean)
          .join('\n'),
        'error',
        16000
      );
    }
    await afterAction();
  }

  async function doRepairMode() {
    if (state.busy || state.modePending) return;
    state.modePending = 'daily';
    if (state.driverMode) renderDriverMode(state.driverMode);

    const result = await call('repair_driver_binding');
    state.modePending = '';
    applyModeResult(result);

    toast(
      result && result.ok ? t('toast.mode.repaired') : t('toast.mode.repair.fail'),
      [(result && result.message) || '', (result && result.detail) || '']
        .filter(Boolean)
        .join('\n'),
      result && result.ok ? 'ok' : 'error',
      result && result.ok ? 6000 : 16000
    );
    await afterAction();
  }

  // ================================================================ 重置（次要動作）

  function renderResetButton() {
    const btn = $('#btn-reset');
    if (!btn) return;
    const primary = state.device && state.device.primary;
    // 日常模式下重置既沒有意義也一定會失敗（內建驅動沒有那個缺陷，
    // 而且 pnputil 拆不掉被音訊引擎持有的子節點）。直接停用，不要讓人按了才知道。
    const dailyMode = !!state.driverMode && state.driverMode.mode === 'daily';

    btn.disabled =
      !state.elevated || !primary || dailyMode || state.busy || !!state.modePending;

    $('#reset-hint').textContent = !state.elevated
      ? t('reset.sub.noadmin')
      : !primary
        ? t('reset.sub.nodevice')
        : dailyMode
          ? t('reset.sub.dailymode')
          : t('reset.sub');
  }

  async function doReset(source = 'manual') {
    if (state.busy || state.modePending) return;
    // 按鈕在日常模式下本來就是停用的，這裡再擋一次是防呆：
    // 萬一狀態一時不同步而讓它可按，也不該真的送出一個註定失敗的請求。
    if (state.driverMode && state.driverMode.mode === 'daily') return;
    const btn = $('#btn-reset');
    btn.classList.add('is-busy');
    btn.disabled = true;

    const result = await call('reset', source);

    btn.classList.remove('is-busy');
    renderResetButton();
    if (result && result.ok) {
      toast(t('toast.reset.ok'), t('toast.reset.ok.sub'), 'ok');
    } else if (result && result.blocked) {
      // 被閘門擋下不是錯誤，是這個動作此刻不適用
      toast(result.message || '', result.detail || '', 'warn', 6000);
    } else {
      toast(
        t('toast.reset.fail'),
        [(result && result.message) || '', (result && result.detail) || '']
          .filter(Boolean)
          .join('\n'),
        'error',
        7000
      );
    }
    await afterAction();
  }

  // ================================================================ 技術細節

  function renderDevice(data) {
    if (!data) return;
    state.device = data;
    if (typeof data.elevated === 'boolean') applyElevation(data.elevated);
    renderResetButton();
    renderTech();
  }

  /** 判斷依據 + 驅動資訊 + 所有節點，全部收在同一個收合區塊裡。 */
  function renderTech() {
    const mode = state.driverMode || {};
    const dev = state.device || {};
    const driver = dev.driver || {};
    const primary = dev.primary;

    // 摘要行讓人不必展開就知道裝置是什麼、在不在線
    $('#tech-note').textContent = primary
      ? `${primary.friendly_name} · ${primary.is_present ? t('chip.online') : primary.status}`
      : t('status.notfound');

    const rows = [
      // 「音訊路徑」放第一行：它才是「這個模式現在能不能用」的答案，
      // 母節點綁在誰身上只是過程。
      [
        t('mode.kv.complete'),
        mode.complete ? t('mode.complete.yes') : t('mode.complete.no'),
      ],
      [t('mode.kv.parent'), mode.root_service || '—'],
      [t('mode.kv.audio'), mode.audio_service || '—'],
      [t('mode.kv.adapter'), mode.adapter_id || '—'],
      [t('mode.kv.inf'), mode.root_inf || '—'],
      [t('mode.kv.status'), `${mode.root_status || '—'} / ${mode.root_problem || '—'}`],
      [t('mode.kv.endpoints'), (mode.endpoints || []).join('、') || '—'],
      [t('mode.kv.hwid'), mode.hardware_id || '—'],
      [t('mode.kv.focusriteinf'), mode.focusrite_inf || t('mode.kv.focusriteinf.none')],
      [t('driver.version'), driver.driver_version || '—'],
      [t('driver.date'), driver.driver_date || '—'],
    ];
    $('#mode-kv').innerHTML = rows
      .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd class="mono">${escapeHtml(v)}</dd>`)
      .join('');

    renderDeviceTable(dev.devices || []);
  }

  function renderDeviceTable(devices) {
    const tbody = $('#devtable tbody');
    if (!devices.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="empty">${escapeHtml(t('devices.empty'))}</td></tr>`;
      return;
    }
    tbody.innerHTML = devices
      .map((dev) => {
        const tone = dev.is_present ? 'ok' : dev.is_ghost ? 'warn' : 'idle';
        return `<tr>
          <td><span class="chip" data-tone="${tone}">${escapeHtml(dev.status)}</span></td>
          <td>${escapeHtml(dev.friendly_name)}</td>
          <td class="mono">${escapeHtml(dev.instance_id)}</td>
        </tr>`;
      })
      .join('');
  }

  function renderPaths(paths) {
    if (!paths) return;
    state.paths = paths;
    $('#paths-kv').innerHTML = [
      [t('paths.config'), paths.config],
      [t('paths.history'), paths.history],
    ]
      .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd class="mono">${escapeHtml(v)}</dd>`)
      .join('');
  }

  // ================================================================ 事件紀錄

  async function refreshHistory() {
    const result = await call('history', 30);
    state.history = (result && result.history) || [];
    renderHistory(state.history);
  }

  function renderHistory(records) {
    const list = $('#timeline');
    if (!records || !records.length) {
      list.innerHTML = `<li class="empty">${escapeHtml(t('log.empty'))}</li>`;
      return;
    }
    list.innerHTML = records.map(historyItem).join('');
  }

  function historyItem(record) {
    const event = String(record.event || '');
    const label = t(`ev.${event}`) === `ev.${event}` ? event : t(`ev.${event}`);

    let tone = 'idle';
    if (event.startsWith('reset_') || event.startsWith('mode_')) {
      tone = record.ok ? 'ok' : 'error';
    } else if (event === 'ghost_cleanup') tone = 'ok';
    else if (event === 'js_error') tone = 'error';

    const bits = [];
    if (record.message) bits.push(record.message);
    if (record.resulting) bits.push(modeLabel(record.resulting));
    if (record.duration_ms) bits.push(t('hist.duration', { ms: record.duration_ms }));
    if (record.removed != null) {
      bits.push(t('hist.removed', { removed: record.removed, requested: record.requested }));
    }

    const time = (record.iso || '').replace('T', ' ').slice(0, 19);
    return `<li class="tl-item">
      <span class="tl-dot" data-tone="${tone}"></span>
      <div class="tl-body">
        <div class="tl-title">${escapeHtml(label)}</div>
        <div class="tl-detail">${escapeHtml(bits.join(' · '))}</div>
      </div>
      <span class="tl-time">${escapeHtml(time)}</span>
    </li>`;
  }

  // ================================================================ 幽靈裝置

  async function scanGhosts() {
    const result = await call('ghosts');
    state.ghosts = (result && result.ghosts) || [];
    renderGhosts();
  }

  function renderGhosts() {
    const list = $('#ghostlist');
    if (!list) return;
    $('#ghost-count').textContent = t('ghosts.count', { n: state.ghosts.length });
    if (!state.ghosts.length) {
      list.innerHTML = `<li class="empty">${escapeHtml(t('ghosts.empty'))}</li>`;
      $('#btn-remove-ghosts').disabled = true;
      return;
    }
    list.innerHTML = state.ghosts
      .map(
        (ghost, index) => `<li class="ghost-item">
          <input type="checkbox" data-index="${index}" />
          <div class="ghost-body">
            <div class="ghost-name">${escapeHtml(ghost.friendly_name)}
              <span class="chip" data-tone="warn">${escapeHtml(ghost.status)}</span></div>
            <div class="ghost-id">${escapeHtml(ghost.instance_id)}</div>
          </div>
        </li>`
      )
      .join('');

    list.querySelectorAll('.ghost-item').forEach((item) => {
      const box = item.querySelector('input');
      item.addEventListener('click', (event) => {
        if (event.target !== box) box.checked = !box.checked;
        updateGhostButton();
      });
      box.addEventListener('change', updateGhostButton);
    });
    updateGhostButton();
  }

  function selectedGhosts() {
    return $$('#ghostlist input:checked').map((box) => state.ghosts[Number(box.dataset.index)]);
  }

  function updateGhostButton() {
    $('#btn-remove-ghosts').disabled = selectedGhosts().length === 0;
  }

  // 只有真正不可逆的動作才用確認對話框
  function confirmDialog(title, body) {
    return new Promise((resolve) => {
      const scrim = $('#scrim');
      $('#dialog-title').textContent = title;
      $('#dialog-body').textContent = body;
      scrim.hidden = false;

      const finish = (value) => {
        scrim.hidden = true;
        $('#dialog-confirm').removeEventListener('click', onConfirm);
        $('#dialog-cancel').removeEventListener('click', onCancel);
        scrim.removeEventListener('click', onScrim);
        document.removeEventListener('keydown', onKey);
        resolve(value);
      };
      const onConfirm = () => finish(true);
      const onCancel = () => finish(false);
      const onScrim = (event) => { if (event.target === scrim) finish(false); };
      const onKey = (event) => { if (event.key === 'Escape') finish(false); };

      $('#dialog-confirm').addEventListener('click', onConfirm);
      $('#dialog-cancel').addEventListener('click', onCancel);
      scrim.addEventListener('click', onScrim);
      document.addEventListener('keydown', onKey);
    });
  }

  // ================================================================ 共用收尾

  /** 任何會改變裝置狀態的動作結束後都跑這一段。
   *
   * 刻意**不**在這裡查裝置狀態：後端在動作收尾時已經開了背景執行緒去強制查一次，
   * 查完會自己從 device / driver_mode 兩個頻道推過來。前端再查一次只會和它撞在
   * 一起，同時開兩支 PowerShell 互搶 CPU。萬一那次推送掉了，輪詢也會補上。
   */
  async function afterAction() {
    refreshHistory();
  }

  async function refreshDevice(force = false) {
    const result = await call('device_status', force);
    if (result && result.device) renderDevice(result.device);
  }

  // ================================================================ Python → JS 事件

  window.SG = {
    onEvent({ channel, payload }) {
      switch (channel) {
        case 'device':
          renderDevice(payload);
          break;
        case 'driver_mode':
          renderDriverMode(payload);
          break;
        case 'busy':
          state.busy = !!payload.busy;
          $('#btn-reset').classList.toggle('is-busy', state.busy);
          // 重置與切換共用同一把鎖，所以 busy 一變就要同步兩邊的可按狀態
          if (state.driverMode) renderDriverMode(state.driverMode);
          renderResetButton();
          break;
        case 'update':
          renderUpdate(payload);
          break;
        case 'toast':
          // 後端主動要求顯示的提示（例如從系統匣點到此刻不適用的動作）
          toast(payload.title || '', payload.body || '', payload.tone || 'info', 6000);
          break;
        case 'history':
          refreshHistory();
          break;
        case 'settings':
          state.config = payload;
          syncSwitches();
          break;
        default:
          break;
      }
    },
  };

  // ================================================================ 綁定

  function bindEverything() {
    $('#nav').addEventListener('click', (event) => {
      const btn = event.target.closest('.nav-item');
      if (btn) switchView(btn.dataset.view);
    });

    $('#btn-refresh').addEventListener('click', async () => {
      await refreshDriverMode(true);
      await refreshDevice(true);
      toast(t('toast.refreshed'), '', 'ok', 1800);
    });
    $('#btn-minimise').addEventListener('click', () => call('hide_window'));
    $('#btn-elevate').addEventListener('click', () => call('relaunch_elevated'));
    $('#update-pill').addEventListener('click', () =>
      call('open_release_page', (state.update && state.update.url) || ''));

    // --- 驅動模式 ---
    $('#modeswitch').addEventListener('click', (event) => {
      const btn = event.target.closest('.mode-option');
      if (btn && !btn.disabled) doSwitchMode(btn.dataset.mode);
    });
    // 分段控制的既有慣例是左右鍵在段之間移動，照著做才不會讓人重新學
    $('#modeswitch').addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const target = event.key === 'ArrowLeft' ? 'daily' : 'asio';
      const btn = $(`.mode-option[data-mode="${target}"]`);
      if (btn && !btn.disabled) {
        btn.focus();
        doSwitchMode(target);
      }
    });
    $('#btn-repair-mode').addEventListener('click', doRepairMode);
    $('#btn-reset').addEventListener('click', () => doReset('manual'));

    bindDisclosures();

    // --- 設定 ---
    $('#cfg-language').addEventListener('change', (event) => {
      const code = event.target.value;
      state.config.language = code;
      applyLanguage(code);
      call('update_settings', { language: code });
    });

    bindSwitch('#sw-hotkey', () => state.config.hotkey_enabled, (on) => setConfig('hotkey_enabled', on, true));
    bindSwitch('#sw-closetray', () => state.config.close_to_tray, (on) => setConfig('close_to_tray', on));
    bindSwitch('#sw-notify', () => state.config.notify_on_reset, (on) => setConfig('notify_on_reset', on));
    bindSwitch('#sw-autostart', () => state.autostart, async (on) => {
      const result = await call('set_autostart', on);
      state.autostart = !!(result && result.enabled);
      syncSwitches();
      toast(
        result && result.ok ? t('toast.autostart.ok') : t('toast.autostart.fail'),
        (result && result.message) || '',
        result && result.ok ? 'ok' : 'error',
        5000
      );
    });

    const hotkeyInput = $('#cfg-hotkey');
    const validateHotkey = debounce(async () => {
      const combo = hotkeyInput.value.trim();
      const note = $('#hotkey-note');
      if (!combo) {
        note.textContent = '';
        return;
      }
      const result = await call('validate_hotkey', combo);
      note.textContent = result.message || '';
      note.dataset.tone = result.ok ? 'ok' : 'error';
      if (result.ok) setConfig('hotkey', combo, true);
    }, 500);
    hotkeyInput.addEventListener('input', validateHotkey);

    // --- 資料 ---
    $('#btn-open-data').addEventListener('click', () => call('open_data_folder'));
    $('#btn-reset-settings').addEventListener('click', async () => {
      const ok = await confirmDialog(t('dlg.resetsettings.title'), t('dlg.resetsettings.body'));
      if (!ok) return;
      const result = await call('reset_settings');
      if (result && result.config) {
        state.config = result.config;
        applyLanguage(state.config.language || 'auto');
        syncSwitches();
      }
      toast(t('toast.settings.reset'), '', 'ok');
    });
    $('#btn-clear-history').addEventListener('click', async () => {
      const ok = await confirmDialog(t('dlg.clearhistory.title'), t('dlg.clearhistory.body'));
      if (!ok) return;
      await call('clear_history');
      refreshHistory();
      toast(t('toast.history.cleared'), '', 'ok');
    });

    // --- 幽靈裝置 ---
    $('#btn-scan-ghosts').addEventListener('click', async () => {
      await scanGhosts();
      toast(t('toast.scan.done'), t('toast.scan.found', { n: state.ghosts.length }), 'ok', 2400);
    });
    $('#btn-remove-ghosts').addEventListener('click', async () => {
      const targets = selectedGhosts();
      if (!targets.length) return;
      const ok = await confirmDialog(
        t('dlg.removeghosts.title'),
        t('dlg.removeghosts.body', { n: targets.length })
      );
      if (!ok) return;
      const result = await call('remove_ghosts', targets.map((g) => g.instance_id));
      toast(
        result.ok ? t('toast.ghosts.removed', { n: result.removed }) : t('toast.ghosts.fail'),
        (result.results || []).filter((r) => !r.ok).map((r) => r.message).join('\n'),
        result.ok ? 'ok' : 'error',
        6000
      );
      await scanGhosts();
      await refreshDevice(true);
    });
  }

  // ================================================================ 啟動

  async function boot() {
    try {
      await bootInner();
    } catch (err) {
      reportError('boot', err);
    }
  }

  async function bootInner() {
    const data = await call('bootstrap');
    if (!data || !data.ok) {
      // 記錄下來，否則這種啟動期失敗只會閃一則 toast 就消失，事後查不到
      reportError('bootstrap', (data && data.message) || 'no response');
      toast(t('toast.bootfail'), (data && data.message) || '', 'error', 9000);
      return;
    }

    state.config = data.config || {};
    state.autostart = !!data.autostart;
    state.history = data.history || [];
    // 版本號的單一來源是 VERSION 檔，寫死在 HTML 裡遲早會和 tag 對不上
    if (data.version) $('#brand-version').textContent = `v${data.version}`;
    renderUpdate(data.update);

    applyLanguage(state.config.language || 'auto');
    applyElevation(data.elevated);

    renderHistory(state.history);
    renderPaths(data.paths);
    $('#cfg-hotkey').value = state.config.hotkey || '';
    syncSwitches();

    if (!data.elevated) {
      toast(t('toast.notelevated'), t('toast.notelevated.body'), 'warn', 9000);
    }
    if (data.hotkey_error) {
      toast(t('toast.hotkeyfail'), data.hotkey_error, 'error', 8000);
    }

    // 驅動模式與裝置狀態都要跑 PowerShell（各約兩秒），刻意不 await ——
    // 其餘畫面已經上好了，沒有理由陪它一起等。也刻意串接而非併發：
    // 兩支 PowerShell 同時啟動只會互搶 CPU，讓兩邊都更慢。
    $('#modeswitch').classList.add('is-loading');
    refreshDriverMode(true)
      .finally(() => $('#modeswitch').classList.remove('is-loading'))
      .then(() => refreshDevice(true));
  }

  // 先用系統語言把靜態文字上好，避免 bootstrap 回來前閃過預設語言
  window.I18N.setLanguage('auto');
  window.I18N.apply();
  bindEverything();
  renderViewHeader();

  /* 等待 pywebview 橋接就緒。
   *
   * 只監聽 pywebviewready 是不夠的：如果事件在本腳本執行前就已經觸發，
   * 監聽器就永遠等不到，boot() 不會執行，畫面會停在靜態文字、所有資料都是空的
   * —— 而且完全沒有錯誤訊息。所以事件與輪詢兩條路並行，先到者贏。
   */
  function whenBridgeReady(callback) {
    let fired = false;
    const run = () => {
      if (fired) return;
      fired = true;
      clearInterval(poll);
      clearTimeout(giveUp);
      callback();
    };

    const poll = setInterval(() => {
      if (bridgeReady()) run();
    }, 50);
    const giveUp = setTimeout(() => {
      clearInterval(poll);
      if (!fired) {
        fired = true;
        toast('Bridge timeout', 'pywebview API 在 20 秒內未就緒。', 'error', 20000);
      }
    }, 20000);

    // 事件本身也可能早於方法掛載，所以一律回到 bridgeReady() 判斷
    window.addEventListener('pywebviewready', () => {
      if (bridgeReady()) run();
    });
    if (bridgeReady()) run();
  }

  whenBridgeReady(boot);
})();
