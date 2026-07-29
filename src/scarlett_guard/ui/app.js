/* Scarlett Guard —— 前端邏輯
 *
 * 動態原則：
 *  - 所有按壓回饋走 CSS :active，在 pointer-down 當下就發生，不等 click。
 *  - 視圖切換用彈簧曲線的位移＋淡入，而不是等長的線性過場。
 *  - 儀表每 100ms 由 Python 推送一次，畫布用 requestAnimationFrame 補間，
 *    讓每幀的位移小於感知門檻，不會頻閃。
 */
(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = {
    config: {},
    device: null,
    monitor: {},
    stats: {},
    ghosts: [],
    busy: false,
    ready: false,
  };

  // ================================================================ 工具

  function api() {
    return (window.pywebview && window.pywebview.api) || null;
  }

  async function call(method, ...args) {
    const bridge = api();
    if (!bridge || typeof bridge[method] !== 'function') {
      return { ok: false, message: `橋接尚未就緒：${method}` };
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
    return Number.isInteger(n) ? `${n} 秒` : `${n.toFixed(1)} 秒`;
  }

  // ================================================================ 視圖切換

  const VIEW_META = {
    status: ['狀態', 'Focusrite 裝置的即時狀況與一鍵重置'],
    detect: ['自動偵測', '監聽音訊串流，異常時自動復原'],
    settings: ['設定', '熱鍵、監聽裝置與常駐行為'],
    history: ['紀錄', '每一次異常與重置的完整軌跡'],
    maintenance: ['維護', '幽靈裝置清理與節點總覽'],
  };

  function switchView(name) {
    $$('.nav-item').forEach((btn) => btn.classList.toggle('is-active', btn.dataset.view === name));

    const [title, sub] = VIEW_META[name] || ['', ''];
    $('#view-title').textContent = title;
    $('#view-sub').textContent = sub;

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
    (result?.messages || []).forEach((msg) => msg && toast(msg, '', 'info', 2600));
  }, 260);

  function setConfig(key, value, immediate = false) {
    state.config[key] = value;
    syncSwitches();
    renderSliders();
    if (immediate) {
      call('update_settings', { [key]: value }).then((result) => {
        if (result && result.config) state.config = result.config;
        (result?.messages || []).forEach((msg) => msg && toast(msg, '', 'info', 2600));
      });
    } else {
      pushSettings({ [key]: value });
    }
  }

  // ================================================================ 渲染：狀態

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

    $('#device-name').textContent = primary ? primary.friendly_name : '找不到 Focusrite 裝置';
    $('#device-id').textContent = primary ? primary.instance_id : '請確認 USB 已連接';

    const addChip = (text, chipTone) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      if (chipTone) chip.dataset.tone = chipTone;
      chip.textContent = text;
      chips.appendChild(chip);
    };

    if (primary) addChip(primary.is_present ? '裝置在線' : `離線（${primary.status}）`,
                         primary.is_present ? 'ok' : 'error');
    addChip(data.uses_focusrite_driver ? 'Focusrite 專屬驅動' : 'Windows 內建 UAC2 驅動',
            data.uses_focusrite_driver ? 'warn' : 'ok');
    addChip(data.elevated ? '已提權' : '未提權', data.elevated ? 'ok' : 'error');
    if (data.ghost_count > 0) addChip(`${data.ghost_count} 個幽靈裝置`, 'warn');

    // 權限狀態同步到側欄與橫幅
    const pill = $('#elevation-pill');
    pill.dataset.tone = data.elevated ? 'ok' : 'error';
    $('#elevation-text').textContent = data.elevated ? '系統管理員' : '權限不足';
    $('#elevation-banner').hidden = !!data.elevated;
    $('#suspend-banner').hidden = !data.auto_recover_suspended;

    const resetBtn = $('#btn-reset');
    resetBtn.disabled = !data.elevated || !primary || state.busy;
    $('#reset-hint').textContent = !data.elevated
      ? '需要系統管理員權限才能執行'
      : primary
        ? '等同於拔掉再插回 USB'
        : '找不到可重置的裝置';

    renderDriver(data);
    renderDeviceTable(data.devices || []);
  }

  function renderDriver(data) {
    const kv = $('#driver-kv');
    const driver = data.driver || {};
    const rows = [
      ['驅動版本', driver.driver_version || '—'],
      ['驅動供應商', driver.driver_provider || '—'],
      ['驅動日期', driver.driver_date || '—'],
      ['製造商', driver.manufacturer || '—'],
      ['裝置類別', data.primary ? data.primary.device_class || '—' : '—'],
    ];
    kv.innerHTML = rows
      .map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`)
      .join('');

    $('#driver-mode').textContent = data.uses_focusrite_driver
      ? 'Focusrite 專屬驅動'
      : 'Windows 內建類別驅動';

    $('#driver-hint').textContent = data.uses_focusrite_driver
      ? '目前走的是 Focusrite 專屬驅動 —— 也就是本工具要對付的那一套。若改用 Windows 內建的 UAC2 類別驅動並搭配 FlexASIO，問題通常會直接消失，代價是失去 Focusrite Control 2 的軟體功能。'
      : '目前走的是 Windows 內建的 UAC2 類別驅動，理論上不會遇到 Focusrite 驅動的復原缺陷。此時本工具主要作為保險。';
  }

  function renderDeviceTable(devices) {
    const tbody = $('#devtable tbody');
    if (!devices.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty">沒有找到任何 Focusrite 裝置節點</td></tr>';
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
    $('#stat-last-iso').textContent = stats.last_reset_iso || '尚無紀錄';
    $('#stat-24h').innerHTML = `${stats.resets_24h || 0}<small> 次</small>`;
    $('#stat-7d').textContent = `7 天內 ${stats.resets_7d || 0} 次`;
    $('#stat-gap').textContent =
      stats.mean_gap_hours != null ? `${stats.mean_gap_hours} 小時` : '—';
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
      ? data.device_name || '監聽中'
      : '未啟用';

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
      `gap ${data.callback_gap}s${baseline != null ? ` · 噪音底 ${baseline} dB` : ''}`;
    $('#val-rms').textContent = `${rms.toFixed(1)} dB`;
    $('#val-zcr').textContent = zcr.toFixed(3);

    $('#bar-rms').style.width = `${dbToPercent(rms)}%`;
    $('#bar-baseline').style.left =
      baseline != null ? `${dbToPercent(baseline)}%` : '0%';
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
          const styles = getComputedStyle(document.documentElement);
          const accent = styles.getPropertyValue('--accent').trim() || '#0a84ff';

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

  // ================================================================ 渲染：滑桿與設定

  const SLIDERS = [
    ['#cfg-cooldown', '#val-cooldown', 'cooldown_seconds', (v) => fmtSeconds(v)],
    ['#cfg-maxreset', '#val-maxreset', 'max_resets_per_hour', (v) => `${v} 次/時`],
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
    const current = state.config.monitor_input_device || '';
    select.innerHTML = '<option value="">自動選擇 Focusrite</option>';
    (devices || []).forEach((dev) => {
      const option = document.createElement('option');
      option.value = dev.name;
      option.textContent = `${dev.name}${dev.hostapi ? ` — ${dev.hostapi}` : ''}`;
      select.appendChild(option);
    });
    select.value = current;
  }

  function renderPaths(paths) {
    if (!paths) return;
    $('#paths-kv').innerHTML = [
      ['設定檔', paths.config],
      ['紀錄檔', paths.history],
    ]
      .map(([k, v]) => `<dt>${k}</dt><dd class="mono">${escapeHtml(v)}</dd>`)
      .join('');
  }

  // ================================================================ 渲染：紀錄

  const EVENT_LABELS = {
    reset_manual: ['手動重置', 'ok'],
    reset_hotkey: ['熱鍵重置', 'ok'],
    reset_tray: ['系統匣重置', 'ok'],
    reset_auto: ['自動重置', 'ok'],
    anomaly: ['偵測到異常', 'warn'],
    auto_skipped: ['略過自動重置', 'warn'],
    auto_suspended: ['自動復原已暫停', 'error'],
    ghost_cleanup: ['清理幽靈裝置', 'ok'],
    app_start: ['程式啟動', 'idle'],
    app_stop: ['程式結束', 'idle'],
  };

  async function refreshHistory() {
    const result = await call('history', 80);
    renderHistory(result && result.history);
  }

  function renderHistory(records) {
    const list = $('#timeline');
    if (!records || !records.length) {
      list.innerHTML = '<li class="empty">尚無紀錄</li>';
      return;
    }
    list.innerHTML = records.map(historyItem).join('');
  }

  function historyItem(record) {
    const [label, defaultTone] = EVENT_LABELS[record.event] || [record.event, 'idle'];
    let tone = defaultTone;
    if (record.event && record.event.startsWith('reset_')) tone = record.ok ? 'ok' : 'error';

    const bits = [];
    if (record.message) bits.push(record.message);
    if (record.label) bits.push(record.label);
    if (record.detail) bits.push(record.detail);
    if (record.duration_ms) bits.push(`耗時 ${record.duration_ms} ms`);
    if (record.method) bits.push(`方式：${record.method}`);
    if (record.removed != null) bits.push(`移除 ${record.removed} / ${record.requested} 個`);

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
    $('#ghost-count').textContent = `${state.ghosts.length} 個`;
    if (!state.ghosts.length) {
      list.innerHTML = '<li class="empty">沒有殘留的幽靈裝置</li>';
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
      toast('裝置已重置', result.detail ? '' : '串流已重建', 'ok');
    } else {
      toast('重置失敗', (result && (result.message || '')) + '\n' + (result?.detail || ''), 'error', 7000);
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
          toast(`偵測到異常：${payload.label || ''}`, payload.detail || '', 'warn', 8000);
          refreshHistory();
          break;
        case 'auto_suspended':
          $('#suspend-banner').hidden = false;
          $('#suspend-detail').textContent = payload.detail || '';
          toast('自動復原已暫停', payload.detail || '', 'error', 9000);
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
      toast('已重新整理', '', 'ok', 1800);
    });
    $('#btn-minimise').addEventListener('click', () => call('hide_window'));
    $('#btn-elevate').addEventListener('click', () => call('relaunch_elevated'));
    $('#btn-resume-auto').addEventListener('click', async () => {
      await call('resume_auto_recover');
      $('#suspend-banner').hidden = true;
      toast('自動復原已重新啟用', '', 'ok');
    });

    // --- 開關 ---
    bindSwitch('#sw-monitor', () => state.monitor.running, async (on) => {
      const result = await call('set_monitor_enabled', on);
      if (result && result.state) renderMonitor(result.state);
      if (result && !result.ok) toast('無法啟動監聽', result.message || '', 'error', 8000);
      else toast(on ? '已開始監聽' : '已停止監聽', '', 'ok', 2200);
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
      toast(result?.ok ? '已更新開機設定' : '設定失敗', result?.message || '', result?.ok ? 'ok' : 'error', 5000);
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
      const ok = await confirmDialog('回復預設設定', '所有設定將回到出廠值，紀錄不受影響。');
      if (!ok) return;
      const result = await call('reset_settings');
      if (result && result.config) {
        state.config = result.config;
        syncSwitches();
        renderSliders();
        renderInputDevices(state.inputDevices);
      }
      toast('已回復預設設定', '', 'ok');
    });
    $('#btn-clear-history').addEventListener('click', async () => {
      const ok = await confirmDialog('清空紀錄', '所有事件紀錄將被永久刪除，此動作無法復原。');
      if (!ok) return;
      await call('clear_history');
      refreshHistory();
      refreshStats();
      toast('紀錄已清空', '', 'ok');
    });

    // --- 幽靈裝置 ---
    $('#btn-scan-ghosts').addEventListener('click', async () => {
      await scanGhosts();
      toast('已重新掃描', `找到 ${state.ghosts.length} 個幽靈裝置`, 'ok', 2400);
    });
    $('#btn-remove-ghosts').addEventListener('click', async () => {
      const targets = selectedGhosts();
      if (!targets.length) return;
      const ok = await confirmDialog(
        '移除幽靈裝置',
        `即將移除 ${targets.length} 個裝置節點。這些節點目前不在線上，移除後若重新插入裝置 ` +
        'Windows 會重新建立。此動作無法復原。'
      );
      if (!ok) return;
      const result = await call('remove_ghosts', targets.map((g) => g.instance_id));
      toast(
        result.ok ? `已移除 ${result.removed} 個` : '移除失敗',
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

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ================================================================ 啟動

  async function boot() {
    const data = await call('bootstrap');
    if (!data || !data.ok) {
      toast('初始化失敗', (data && data.message) || '', 'error', 9000);
      return;
    }

    state.config = data.config || {};
    state.autostart = !!data.autostart;
    state.inputDevices = data.input_devices || [];
    state.ready = true;

    renderDevice(data.device);
    renderStats(data.stats);
    renderMonitor(data.monitor);
    renderHistory(data.history);
    renderInputDevices(state.inputDevices);
    renderPaths(data.paths);

    $('#cfg-hotkey').value = state.config.hotkey || '';
    $('#cfg-samplerate').value = String(state.config.monitor_samplerate || 48000);
    $('#cfg-blocksize').value = String(state.config.monitor_blocksize || 1024);

    syncSwitches();
    renderSliders();

    if (!data.elevated) {
      toast('未以系統管理員執行', '重置功能需要提權，可在上方橫幅一鍵重新啟動。', 'warn', 9000);
    }
    if (data.hotkey_error) {
      toast('熱鍵註冊失敗', data.hotkey_error, 'error', 8000);
    }
  }

  bindEverything();
  requestAnimationFrame(drawWave);

  if (window.pywebview && window.pywebview.api) boot();
  else window.addEventListener('pywebviewready', boot);
})();
