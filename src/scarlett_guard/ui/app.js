/* Scarlett Guard —— 前端邏輯
 *
 * 動態原則：
 *  - 所有按壓回饋走 CSS :active，在 pointer-down 當下就發生，不等 click。
 *  - 視圖切換用彈簧曲線的位移＋淡入，而不是等長的線性過場。
 *  - 儀表每 100ms 由 Python 推送一次，畫布用 requestAnimationFrame 補間，
 *    讓每幀的位移小於感知門檻，不會頻閃。
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
  // 函式宣告會被提升，所以這裡可以安全地引用底下才定義的 api() 與 toast()。

  window.__SG_ERRORS = [];
  // 啟動軌跡。UI 出問題時要能回答「到底走到哪一步」，光看畫面看不出來。
  window.__SG_TRACE = [];
  const trace = (msg) => window.__SG_TRACE.push(msg);

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
    monitor: {},
    stats: {},
    ghosts: [],
    history: [],
    inputDevices: [],
    autostart: false,
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
   * 方法是稍後才逐一掛上去的。只看物件存在就開始呼叫，會拿到
   * 「橋接尚未就緒：bootstrap」。所以直接檢查要用的方法本身。
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

  function fmtSeconds(value) {
    const n = Number(value);
    return `${Number.isInteger(n) ? n : n.toFixed(1)}s`;
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
    if (state.device) renderDevice(state.device);
    if (state.stats) renderStats(state.stats);
    if (state.monitor) renderMonitor(state.monitor);
    renderHistory(state.history);
    renderGhosts();
    renderInputDevices(state.inputDevices);
    renderSliders();
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

  const VIEWS = ['status', 'detect', 'settings', 'history', 'maintenance'];

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

    if (name === 'maintenance') scanGhosts();
    if (name === 'history') refreshHistory();
  }

  // ================================================================ 開關元件

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

  // ================================================================ 設定寫入

  const pushSettings = debounce(async (values) => {
    const result = await call('update_settings', values);
    if (result && result.config) {
      state.config = result.config;
      syncSwitches();
      renderSliders();
    }
  }, 260);

  function setConfig(key, value, immediate = false) {
    state.config[key] = value;
    syncSwitches();
    renderSliders();
    if (immediate) {
      call('update_settings', { [key]: value }).then((result) => {
        if (result && result.config) state.config = result.config;
      });
    } else {
      pushSettings({ [key]: value });
    }
  }

  // ================================================================ 渲染：狀態

  /** 權限狀態不需要等裝置查詢，bootstrap 一回來就能上。 */
  function applyElevation(elevated) {
    state.elevated = !!elevated;
    const pill = $('#elevation-pill');
    pill.dataset.tone = elevated ? 'ok' : 'error';
    $('#elevation-text').textContent = elevated ? t('elev.admin') : t('elev.none');
    $('#elevation-banner').hidden = !!elevated;
    if (!elevated) {
      $('#btn-reset').disabled = true;
      $('#reset-hint').textContent = t('reset.sub.noadmin');
    }
  }

  function renderDevice(data) {
    if (!data) return;
    state.device = data;

    const primary = data.primary;
    const ring = $('#status-ring');
    const chips = $('#device-chips');
    chips.innerHTML = '';

    let tone = 'idle';
    if (state.busy) tone = 'busy';
    else if (primary && primary.is_present) tone = 'ok';
    else if (primary) tone = 'error';
    ring.dataset.tone = tone;

    $('#device-name').textContent = primary ? primary.friendly_name : t('status.notfound');
    $('#device-id').textContent = primary ? primary.instance_id : t('status.notfound.sub');

    const addChip = (text, chipTone) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      if (chipTone) chip.dataset.tone = chipTone;
      chip.textContent = text;
      chips.appendChild(chip);
    };

    if (primary) {
      addChip(
        primary.is_present ? t('chip.online') : t('chip.offline', { status: primary.status }),
        primary.is_present ? 'ok' : 'error'
      );
    }
    addChip(
      data.uses_focusrite_driver ? t('chip.driver.focusrite') : t('chip.driver.uac2'),
      data.uses_focusrite_driver ? 'warn' : 'ok'
    );
    addChip(data.elevated ? t('chip.elevated') : t('chip.notelevated'),
            data.elevated ? 'ok' : 'error');
    if (data.ghost_count > 0) addChip(t('chip.ghosts', { n: data.ghost_count }), 'warn');

    const pill = $('#elevation-pill');
    pill.dataset.tone = data.elevated ? 'ok' : 'error';
    $('#elevation-text').textContent = data.elevated ? t('elev.admin') : t('elev.none');
    $('#elevation-banner').hidden = !!data.elevated;
    $('#suspend-banner').hidden = !data.auto_recover_suspended;

    const resetBtn = $('#btn-reset');
    resetBtn.disabled = !data.elevated || !primary || state.busy;
    $('#reset-hint').textContent = !data.elevated
      ? t('reset.sub.noadmin')
      : primary
        ? t('reset.sub')
        : t('reset.sub.nodevice');

    renderDriver(data);
    renderDeviceTable(data.devices || []);
  }

  function renderDriver(data) {
    const driver = data.driver || {};
    const rows = [
      [t('driver.version'), driver.driver_version || '—'],
      [t('driver.provider'), driver.driver_provider || '—'],
      [t('driver.date'), driver.driver_date || '—'],
      [t('driver.manufacturer'), driver.manufacturer || '—'],
      [t('driver.class'), data.primary ? data.primary.device_class || '—' : '—'],
    ];
    $('#driver-kv').innerHTML = rows
      .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`)
      .join('');

    $('#driver-mode').textContent = data.uses_focusrite_driver
      ? t('chip.driver.focusrite')
      : t('chip.driver.uac2');
    $('#driver-hint').textContent = data.uses_focusrite_driver
      ? t('driver.hint.focusrite')
      : t('driver.hint.uac2');
  }

  function renderDeviceTable(devices) {
    const tbody = $('#devtable tbody');
    if (!devices.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="empty">${escapeHtml(t('devices.empty'))}</td></tr>`;
      return;
    }
    tbody.innerHTML = devices
      .map((dev) => {
        const tone = dev.is_present ? 'ok' : dev.is_ghost ? 'warn' : 'idle';
        return `<tr>
          <td><span class="chip" data-tone="${tone}">${escapeHtml(dev.status)}</span></td>
          <td>${escapeHtml(dev.friendly_name)}</td>
          <td>${escapeHtml(dev.device_class || '—')}</td>
          <td>${escapeHtml(dev.instance_id)}</td>
        </tr>`;
      })
      .join('');
  }

  function renderStats(stats) {
    if (!stats) return;
    state.stats = stats;
    $('#stat-last').textContent = stats.last_reset_ago || '—';
    $('#stat-last-iso').textContent = stats.last_reset_iso || t('stat.none');
    const unit = t('stat.times');
    $('#stat-24h').innerHTML =
      `${stats.resets_24h || 0}${unit ? `<small> ${escapeHtml(unit)}</small>` : ''}`;
    $('#stat-7d').textContent = t('stat.7d', { n: stats.resets_7d || 0 });
    $('#stat-gap').textContent =
      stats.mean_gap_hours != null ? t('unit.hours', { n: stats.mean_gap_hours }) : '—';
  }

  // ================================================================ 渲染：監聽儀表

  const wave = { values: [], target: [] };

  function renderMonitor(data) {
    if (!data) return;
    state.monitor = data;

    const sw = $('#sw-monitor');
    sw.classList.toggle('is-on', !!data.running);
    sw.setAttribute('aria-checked', String(!!data.running));

    $('#monitor-device').textContent = data.running
      ? data.device_name || t('monitor.on')
      : t('monitor.off');

    const err = $('#monitor-error');
    if (data.error) {
      err.hidden = false;
      err.textContent = data.error;
    } else {
      err.hidden = true;
    }

    if (!data.running) {
      $('#monitor-readout').textContent = '—';
      $('#val-rms').textContent = '—';
      $('#val-zcr').textContent = '—';
      $('#bar-rms').style.width = '0%';
      $('#bar-zcr').style.width = '0%';
      wave.target = [];
      return;
    }

    const rms = Number(data.rms_db);
    const zcr = Number(data.zcr);
    const baseline = data.baseline_db;

    $('#monitor-readout').textContent =
      baseline != null
        ? t('monitor.readout.base', { gap: data.callback_gap, base: baseline })
        : t('monitor.readout', { gap: data.callback_gap });
    $('#val-rms').textContent = `${rms.toFixed(1)} dB`;
    $('#val-zcr').textContent = zcr.toFixed(3);

    $('#bar-rms').style.width = `${dbToPercent(rms)}%`;
    $('#bar-baseline').style.left = baseline != null ? `${dbToPercent(baseline)}%` : '0%';
    $('#bar-zcr').style.width = `${Math.min(100, (zcr / 0.6) * 100)}%`;
    $('#bar-zcr-th').style.left =
      `${Math.min(100, (Number(state.config.noise_zcr || 0.3) / 0.6) * 100)}%`;

    wave.target = (data.waveform || []).slice(-140);
    $('#suspend-banner').hidden = !data.auto_recover_suspended;
  }

  function dbToPercent(db) {
    // -100dB → 0%，0dB → 100%
    return Math.max(0, Math.min(100, ((Number(db) + 100) / 100) * 100));
  }

  function drawWave() {
    const canvas = $('#wave-canvas');
    if (canvas && canvas.isConnected) {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w > 0 && h > 0) {
        if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
          canvas.width = w * dpr;
          canvas.height = h * dpr;
        }
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        // 平滑補間，讓每幀位移小於感知門檻
        const target = wave.target;
        if (wave.values.length !== target.length) wave.values = target.slice();
        for (let i = 0; i < target.length; i += 1) {
          const from = wave.values[i] ?? target[i];
          wave.values[i] = from + (target[i] - from) * (reduceMotion ? 1 : 0.35);
        }

        const points = wave.values;
        if (points.length > 1) {
          const step = w / (points.length - 1);
          const accent =
            getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() ||
            '#0a84ff';

          ctx.beginPath();
          points.forEach((db, i) => {
            const y = h - (dbToPercent(db) / 100) * h;
            if (i === 0) ctx.moveTo(0, y);
            else ctx.lineTo(i * step, y);
          });

          const grad = ctx.createLinearGradient(0, 0, 0, h);
          grad.addColorStop(0, accent);
          grad.addColorStop(1, 'rgba(10,132,255,0.15)');
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.8;
          ctx.lineJoin = 'round';
          ctx.lineCap = 'round';
          ctx.stroke();

          ctx.lineTo(w, h);
          ctx.lineTo(0, h);
          ctx.closePath();
          ctx.fillStyle = 'rgba(10,132,255,0.10)';
          ctx.fill();
        }
      }
    }
    requestAnimationFrame(drawWave);
  }

  // ================================================================ 滑桿

  const SLIDERS = [
    ['#cfg-cooldown', '#val-cooldown', 'cooldown_seconds', (v) => fmtSeconds(v)],
    ['#cfg-maxreset', '#val-maxreset', 'max_resets_per_hour', (v) => t('unit.perhour', { n: v })],
    ['#cfg-stall', '#val-stall', 'stall_seconds', (v) => fmtSeconds(v)],
    ['#cfg-silence', '#val-silence', 'silence_seconds', (v) => fmtSeconds(v)],
    ['#cfg-silencefloor', '#val-silencefloor', 'silence_floor_db', (v) => `${v} dB`],
    ['#cfg-noisemargin', '#val-noisemargin', 'noise_margin_db', (v) => `+${v} dB`],
    ['#cfg-noisezcr', '#val-noisezcr', 'noise_zcr', (v) => Number(v).toFixed(2)],
    ['#cfg-noiseseconds', '#val-noiseseconds', 'noise_seconds', (v) => fmtSeconds(v)],
    ['#cfg-settle', '#val-settle', 'post_reset_settle_seconds', (v) => fmtSeconds(v)],
  ];

  function renderSliders() {
    SLIDERS.forEach(([inputSel, valueSel, key, format]) => {
      const input = $(inputSel);
      const label = $(valueSel);
      if (!input) return;
      const value = state.config[key];
      if (value != null && document.activeElement !== input) input.value = value;
      if (label) label.textContent = format(input.value);
    });
  }

  function bindSliders() {
    SLIDERS.forEach(([inputSel, valueSel, key, format]) => {
      const input = $(inputSel);
      const label = $(valueSel);
      if (!input) return;
      input.addEventListener('input', () => {
        if (label) label.textContent = format(input.value);
        setConfig(key, Number(input.value));
      });
    });
  }

  function renderInputDevices(devices) {
    const select = $('#cfg-inputdev');
    state.inputDevices = devices || [];
    const current = state.config.monitor_input_device || '';
    select.innerHTML = '';
    const auto = document.createElement('option');
    auto.value = '';
    auto.textContent = t('dev.input.auto');
    select.appendChild(auto);
    state.inputDevices.forEach((dev) => {
      const option = document.createElement('option');
      option.value = dev.name;
      option.textContent = `${dev.name}${dev.hostapi ? ` — ${dev.hostapi}` : ''}`;
      select.appendChild(option);
    });
    select.value = current;
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

  // ================================================================ 紀錄

  async function refreshHistory() {
    const result = await call('history', 80);
    state.history = (result && result.history) || [];
    renderHistory(state.history);
  }

  function renderHistory(records) {
    const list = $('#timeline');
    if (!records || !records.length) {
      list.innerHTML = `<li class="empty">${escapeHtml(t('history.empty'))}</li>`;
      return;
    }
    list.innerHTML = records.map(historyItem).join('');
  }

  function historyItem(record) {
    const event = String(record.event || '');
    const label = t(`ev.${event}`) === `ev.${event}` ? event : t(`ev.${event}`);

    let tone = 'idle';
    if (event.startsWith('reset_')) tone = record.ok ? 'ok' : 'error';
    else if (event === 'anomaly' || event === 'auto_skipped') tone = 'warn';
    else if (event === 'auto_suspended') tone = 'error';
    else if (event === 'ghost_cleanup') tone = 'ok';

    const bits = [];
    if (record.message) bits.push(record.message);
    if (record.label) bits.push(record.label);
    if (record.detail) bits.push(record.detail);
    if (record.duration_ms) bits.push(t('hist.duration', { ms: record.duration_ms }));
    if (record.method) bits.push(t('hist.method', { method: record.method }));
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

  // ================================================================ 動作

  async function doReset(source = 'manual') {
    if (state.busy) return;
    const btn = $('#btn-reset');
    btn.classList.add('is-busy');
    btn.disabled = true;
    $('#status-ring').dataset.tone = 'busy';

    const result = await call('reset', source);

    btn.classList.remove('is-busy');
    if (result && result.ok) {
      toast(t('toast.reset.ok'), t('toast.reset.ok.sub'), 'ok');
    } else {
      const detail = [(result && result.message) || '', (result && result.detail) || '']
        .filter(Boolean)
        .join('\n');
      toast(t('toast.reset.fail'), detail, 'error', 7000);
    }
    await refreshDevice(true);
    await refreshStats();
    refreshHistory();
  }

  async function refreshDevice(force = false) {
    const result = await call('device_status', force);
    if (result && result.device) renderDevice(result.device);
  }

  async function refreshStats() {
    const result = await call('stats');
    if (result && result.stats) renderStats(result.stats);
  }

  // ================================================================ Python → JS 事件

  window.SG = {
    onEvent({ channel, payload }) {
      switch (channel) {
        case 'device':
          renderDevice(payload);
          break;
        case 'monitor':
          renderMonitor(payload);
          break;
        case 'stats':
          renderStats(payload);
          break;
        case 'busy':
          state.busy = !!payload.busy;
          $('#btn-reset').classList.toggle('is-busy', state.busy);
          if (state.busy) $('#status-ring').dataset.tone = 'busy';
          break;
        case 'anomaly':
          toast(t('toast.anomaly', { label: payload.label || '' }), payload.detail || '', 'warn', 8000);
          refreshHistory();
          break;
        case 'auto_suspended':
          $('#suspend-banner').hidden = false;
          $('#suspend-detail').textContent = payload.detail || t('banner.suspend.body');
          toast(t('toast.suspend'), payload.detail || '', 'error', 9000);
          break;
        case 'history':
          refreshHistory();
          break;
        case 'settings':
          state.config = payload;
          syncSwitches();
          renderSliders();
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

    $('#btn-reset').addEventListener('click', () => doReset('manual'));
    $('#btn-refresh').addEventListener('click', async () => {
      await refreshDevice(true);
      await refreshStats();
      toast(t('toast.refreshed'), '', 'ok', 1800);
    });
    $('#btn-minimise').addEventListener('click', () => call('hide_window'));
    $('#btn-elevate').addEventListener('click', () => call('relaunch_elevated'));
    $('#btn-resume-auto').addEventListener('click', async () => {
      await call('resume_auto_recover');
      $('#suspend-banner').hidden = true;
      toast(t('toast.autoresume'), '', 'ok');
    });

    // --- 語言 ---
    $('#cfg-language').addEventListener('change', (event) => {
      const code = event.target.value;
      state.config.language = code;
      applyLanguage(code);
      call('update_settings', { language: code });
    });

    // --- 開關 ---
    bindSwitch('#sw-monitor', () => state.monitor.running, async (on) => {
      const result = await call('set_monitor_enabled', on);
      if (result && result.state) renderMonitor(result.state);
      if (result && !result.ok) toast(t('toast.monitor.fail'), result.message || '', 'error', 8000);
      else toast(on ? t('toast.monitor.on') : t('toast.monitor.off'), '', 'ok', 2200);
      state.config.monitor_enabled = on;
    });
    bindSwitch('#sw-auto', () => state.config.auto_recover, (on) => setConfig('auto_recover', on, true));
    bindSwitch('#sw-stall', () => state.config.detect_stall, (on) => setConfig('detect_stall', on));
    bindSwitch('#sw-silence', () => state.config.detect_silence, (on) => setConfig('detect_silence', on));
    bindSwitch('#sw-noise', () => state.config.detect_noise, (on) => setConfig('detect_noise', on));
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

    bindSliders();

    // --- 熱鍵輸入 ---
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

    // --- 下拉選單 ---
    $('#cfg-inputdev').addEventListener('change', (event) =>
      setConfig('monitor_input_device', event.target.value, true));
    $('#cfg-samplerate').addEventListener('change', (event) =>
      setConfig('monitor_samplerate', Number(event.target.value), true));
    $('#cfg-blocksize').addEventListener('change', (event) =>
      setConfig('monitor_blocksize', Number(event.target.value), true));

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
      refreshStats();
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

    // 快捷鍵：Ctrl+R 在視窗內直接重置
    document.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'r') {
        event.preventDefault();
        doReset('manual');
      }
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
    trace('boot: calling bootstrap');
    const data = await call('bootstrap');
    trace(`boot: bootstrap returned ok=${data && data.ok}`);
    if (!data || !data.ok) {
      // 記錄下來，否則這種啟動期失敗只會閃一則 toast 就消失，事後查不到
      reportError('bootstrap', (data && data.message) || 'no response');
    }
    if (!data || !data.ok) {
      toast(t('toast.bootfail'), (data && data.message) || '', 'error', 9000);
      return;
    }

    state.config = data.config || {};
    state.autostart = !!data.autostart;
    state.inputDevices = data.input_devices || [];
    state.history = data.history || [];

    applyLanguage(state.config.language || 'auto');
    applyElevation(data.elevated);

    renderStats(data.stats);
    renderMonitor(data.monitor);
    renderHistory(state.history);
    renderInputDevices(state.inputDevices);
    renderPaths(data.paths);

    $('#cfg-hotkey').value = state.config.hotkey || '';
    $('#cfg-samplerate').value = String(state.config.monitor_samplerate || 0);
    $('#cfg-blocksize').value = String(state.config.monitor_blocksize || 1024);

    syncSwitches();
    renderSliders();

    if (!data.elevated) {
      toast(t('toast.notelevated'), t('toast.notelevated.body'), 'warn', 9000);
    }
    if (data.hotkey_error) {
      toast(t('toast.hotkeyfail'), data.hotkey_error, 'error', 8000);
    }
    trace('boot: fast data rendered');

    // 裝置狀態要跑 PowerShell（約 2–3 秒），刻意不 await ——
    // 其餘頁面的資料已經在畫面上了，沒有理由陪它一起等。
    $('#status-ring').classList.add('is-loading');
    refreshDevice(true).finally(() => {
      $('#status-ring').classList.remove('is-loading');
      trace('boot: device rendered');
    });
  }

  // 前端例外若沒有出口，畫面只會安靜地半殘 —— 一律回報到後端紀錄並提示使用者
  // 先用系統語言把靜態文字上好，避免 bootstrap 回來前閃過預設語言
  window.I18N.setLanguage('auto');
  window.I18N.apply();
  bindEverything();
  renderViewHeader();
  requestAnimationFrame(drawWave);

  /* 等待 pywebview 橋接就緒。
   *
   * 只監聽 pywebviewready 是不夠的：如果事件在本腳本執行前就已經觸發
   * （例如多載入一支 script 讓執行時機晚了幾毫秒），監聽器就永遠等不到，
   * boot() 不會執行，畫面會停在靜態文字、所有資料都是空的 —— 而且完全
   * 沒有錯誤訊息。所以事件與輪詢兩條路並行，先到者贏。
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

  trace('script end');
  whenBridgeReady(() => {
    trace('bridge ready');
    boot();
  });
})();
