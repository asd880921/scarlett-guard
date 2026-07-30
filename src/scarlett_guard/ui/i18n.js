/* 介面文案。三種語言共用同一組 key。
 *
 * 用法：
 *   HTML 上標 data-i18n="key" 由 applyI18n() 套用；
 *   動態產生的字串在 JS 裡呼叫 t('key', { name: 'x' })。
 *   佔位符格式為 {name}。
 */
window.I18N = (() => {
  const CATALOG = {
    'zh-Hant': {
      'app.title': 'Scarlett Guard',

      'nav.status': '狀態',
      'nav.mode': '驅動模式',
      'nav.detect': '自動偵測',
      'nav.settings': '設定',
      'nav.history': '紀錄',
      'nav.maintenance': '維護',

      'view.status.title': '狀態',
      'view.status.sub': 'Focusrite 裝置的即時狀況與一鍵重置',
      'view.mode.title': '驅動模式',
      'view.mode.sub': '依情境在穩定與低延遲之間切換',
      'view.detect.title': '自動偵測',
      'view.detect.sub': '監聽音訊串流，異常時自動復原',
      'view.settings.title': '設定',
      'view.settings.sub': '熱鍵、監聽裝置與常駐行為',
      'view.history.title': '紀錄',
      'view.history.sub': '每一次異常與重置的完整軌跡',
      'view.maintenance.title': '維護',
      'view.maintenance.sub': '幽靈裝置清理與節點總覽',

      'top.refresh': '重新整理',
      'top.refresh.tip': '重新整理裝置狀態',
      'top.minimise': '收進系統匣',
      'top.minimise.tip': '收進系統匣',

      'elev.checking': '檢查權限中…',
      'elev.admin': '系統管理員',
      'elev.none': '權限不足',
      'banner.elev.title': '需要系統管理員權限',
      'banner.elev.body': '重置 PnP 裝置必須提權執行，否則重置按鈕無法運作。',
      'banner.elev.action': '以管理員重新啟動',
      'banner.suspend.title': '自動復原已暫停',
      'banner.suspend.body': '短時間內重置次數過多，已暫停以避免無限迴圈。',
      'banner.suspend.action': '重新啟用',

      'status.detecting': '正在偵測裝置…',
      'status.notfound': '找不到 Focusrite 裝置',
      'status.notfound.sub': '請確認 USB 已連接',
      'reset.label': '立即重置裝置',
      'reset.sub': '等同於拔掉再插回 USB',
      'reset.sub.noadmin': '需要系統管理員權限才能執行',
      'reset.sub.nodevice': '找不到可重置的裝置',

      'chip.online': '裝置在線',
      'chip.offline': '離線（{status}）',
      'chip.driver.focusrite': 'Focusrite 專屬驅動',
      'chip.driver.uac2': 'Windows 內建 UAC2 驅動',
      'chip.elevated': '已提權',
      'chip.notelevated': '未提權',
      'chip.ghosts': '{n} 個幽靈裝置',

      'stat.last': '上次重置',
      'stat.none': '尚無紀錄',
      'stat.24h': '24 小時內',
      'stat.times': '次',
      'stat.7d': '7 天內 {n} 次',
      'stat.gap': '平均間隔',
      'stat.gap.foot': '兩次重置之間',
      'unit.hours': '{n} 小時',

      'card.driver': '驅動資訊',
      'driver.version': '驅動版本',
      'driver.provider': '驅動供應商',
      'driver.date': '驅動日期',
      'driver.manufacturer': '製造商',
      'driver.class': '裝置類別',
      'driver.hint.focusrite':
        '目前使用 Focusrite 專屬驅動。本工具的重置功能正是針對這套驅動的音訊串流問題設計的。',
      'driver.hint.uac2':
        '目前走的是 Windows 內建的 UAC2 類別驅動，理論上不會遇到 Focusrite 驅動的復原缺陷。此時本工具主要作為保險。',

      'card.monitor': '音訊監聽',
      'monitor.hint':
        '監聽 Scarlett 的<strong>錄音端點</strong>而非播放 loopback —— 錄音端拿到的是 ADC 的真實取樣，才能反映硬體那一側是否還活著。',
      'monitor.off': '未啟用',
      'monitor.on': '監聽中',
      'monitor.volume': '音量',
      'monitor.zcr': '過零率',
      'monitor.readout': 'gap {gap}s',
      'monitor.readout.base': 'gap {gap}s · 噪音底 {base} dB',

      'card.autorecover': '自動復原',
      'autorecover.hint':
        '偵測到異常時自動執行重置。這些偵測是<strong>啟發式規則，不是保證</strong> —— 建議先只開監聽、觀察幾天儀表與紀錄，確認不會誤判之後再打開自動復原。',
      'row.cooldown': '冷卻時間',
      'row.cooldown.sub': '兩次自動重置之間的最短間隔',
      'row.maxreset': '每小時上限',
      'row.maxreset.sub': '超過就暫停自動復原，避免無限迴圈',
      'unit.perhour': '{n} 次/時',

      'card.detectors': '偵測器',
      'det.stall.title': '串流凍結（stall）',
      'det.stall.sub': '音訊回呼停止進來，代表 driver 的 stream 時鐘已停。最可靠的訊號。',
      'det.time': '判定時間',
      'det.silence.title': '訊號消失（silence）',
      'det.silence.sub':
        '連續位元級全零。類比 ADC 正常時永遠有噪音底，不可能長時間輸出精確的零。',
      'det.duration': '持續時間',
      'det.silence.floor': '靜音門檻',
      'det.silence.note':
        '門檻必須遠低於實際噪音底（本機實測約 −104 dB），否則正常待機就會誤判。另外若你在 Windows 中將此輸入靜音，也會產生全零而被判定為異常。',
      'det.noise.title': '電流音（noise）',
      'det.noise.sub':
        '音量高出噪音底一大截且過零率極高。人聲與樂器的過零率遠低於此。',
      'det.noise.margin': '高出噪音底',
      'det.noise.zcr': '過零率門檻',
      'det.noise.note':
        '最容易誤判的一個。錄製 hi-hat、破音吉他或白噪素材時可能觸發，請依實測調整。',

      'card.hotkey': '全域熱鍵',
      'hotkey.hint': '在任何前景視窗（含全螢幕 DAW）按下即可重置，不必切回本程式。',
      'hotkey.combo': '組合鍵',
      'hotkey.combo.sub': 'pynput 格式，例如 <ctrl>+<alt>+r',

      'card.monitordev': '監聽裝置',
      'dev.input': '錄音端點',
      'dev.input.sub': '留空為自動選擇 Focusrite',
      'dev.input.auto': '自動選擇 Focusrite',
      'dev.samplerate': '取樣率',
      'dev.samplerate.sub': '需與裝置目前設定相符',
      'dev.samplerate.auto': '自動（跟隨裝置）',
      'dev.blocksize': '監聽區塊大小',
      'dev.blocksize.sub':
        '越小偵測反應越快，CPU 負擔略高。這是<strong>本程式擷取音訊</strong>的區塊，不是 Focusrite 的 ASIO Buffer Size',
      'dev.blocksize.note':
        'Focusrite 自己的 ASIO Buffer Size 只能在 Focusrite Control 2 的 Device Settings 裡改，沒有公開 API 可供外部程式設定 —— 本程式改用 <code>pnputil</code> 重置裝置達成同樣的「重建 stream」效果，不需要去動那個設定。',

      'card.behaviour': '行為',
      'beh.autostart': '開機自動啟動',
      'beh.autostart.sub': '以工作排程器建立高權限登入工作，不會跳 UAC',
      'beh.closetray': '關閉視窗時收進系統匣',
      'beh.closetray.sub': '保持常駐，熱鍵才會持續有效',
      'beh.notify': '重置後顯示系統通知',
      'beh.notify.sub': '由系統匣圖示發出',
      'beh.settle': '重置後緩衝時間',
      'beh.settle.sub': '等待裝置與驅動穩定再恢復監聽',

      'card.language': '語言',
      'lang.label': '介面語言',
      'lang.sub': '變更後立即套用，系統匣選單需重新啟動程式',
      'lang.auto': '自動（跟隨系統）',

      'card.paths': '資料位置',
      'paths.config': '設定檔',
      'paths.history': '紀錄檔',
      'btn.opendata': '開啟資料夾',
      'btn.resetsettings': '回復預設設定',

      'card.history': '事件紀錄',
      'btn.clear': '清空',
      'history.hint':
        '以 JSON Lines 保存，可直接用文字工具或 pandas 分析「到底多久壞一次、是否真的和 CPU 負載相關」。',
      'history.empty': '尚無紀錄',
      'hist.duration': '耗時 {ms} ms',
      'hist.method': '方式：{method}',
      'hist.removed': '移除 {removed} / {requested} 個',

      'card.ghosts': '幽靈裝置',
      'ghosts.hint':
        '反覆插拔與重裝驅動累積下來的殘留節點（狀態為 Unknown）。<strong>尚未證實與斷音問題有因果關係</strong>，但清乾淨可以排除干擾變因，讓後續測試的結論更可信。',
      'ghosts.empty': '沒有殘留的幽靈裝置',
      'ghosts.count': '{n} 個',
      'btn.scan': '重新掃描',
      'btn.removesel': '移除選取項目',

      'card.alldevices': '所有 Focusrite 裝置節點',
      'table.status': '狀態',
      'table.name': '名稱',
      'table.class': '類別',
      'table.id': 'Instance ID',
      'devices.empty': '沒有找到任何 Focusrite 裝置節點',

      'dialog.title': '確認',
      'dialog.cancel': '取消',
      'dialog.confirm': '確認移除',
      'dlg.resetsettings.title': '回復預設設定',
      'dlg.resetsettings.body': '所有設定將回到出廠值，紀錄不受影響。',
      'dlg.clearhistory.title': '清空紀錄',
      'dlg.clearhistory.body': '所有事件紀錄將被永久刪除，此動作無法復原。',
      'dlg.removeghosts.title': '移除幽靈裝置',
      'dlg.removeghosts.body':
        '即將移除 {n} 個裝置節點。這些節點目前不在線上，移除後若重新插入裝置 Windows 會重新建立。此動作無法復原。',

      'toast.refreshed': '已重新整理',
      'toast.reset.ok': '裝置已重置',
      'toast.reset.ok.sub': '串流已重建',
      'toast.reset.fail': '重置失敗',
      'toast.monitor.on': '已開始監聽',
      'toast.monitor.off': '已停止監聽',
      'toast.monitor.fail': '無法啟動監聽',
      'toast.autostart.ok': '已更新開機設定',
      'toast.autostart.fail': '設定失敗',
      'toast.settings.reset': '已回復預設設定',
      'toast.history.cleared': '紀錄已清空',
      'toast.scan.done': '已重新掃描',
      'toast.scan.found': '找到 {n} 個幽靈裝置',
      'toast.ghosts.removed': '已移除 {n} 個',
      'toast.ghosts.fail': '移除失敗',
      'toast.anomaly': '偵測到異常：{label}',
      'toast.suspend': '自動復原已暫停',
      'toast.autoresume': '自動復原已重新啟用',
      'toast.notelevated': '未以系統管理員執行',
      'toast.notelevated.body': '重置功能需要提權，可在上方橫幅一鍵重新啟動。',
      'toast.hotkeyfail': '熱鍵註冊失敗',
      'toast.bootfail': '初始化失敗',
      'toast.bridge': '橋接尚未就緒：{method}',

      // --- 驅動模式 ---
      'mode.switch.aria': '驅動模式',
      'mode.daily.name': '日常模式',
      'mode.daily.for': '聽音樂、看影片、遊戲',
      'mode.daily.trade': 'Windows 內建驅動 · 穩定 · 全雙工約 46 ms',
      'mode.asio.name': '錄音模式',
      'mode.asio.for': '練琴、錄音、軟體監聽',
      'mode.asio.trade': '原廠驅動 + ASIO · 低延遲 · 可能需要重置',
      'mode.detecting': '正在讀取驅動綁定…',
      'mode.hint':
        '切換會讓裝置重新列舉，音訊中斷約 <strong>10 秒</strong>，' +
        '正在錄音或播放的程式需要重新選擇裝置。切換完全可逆，兩個驅動都留在系統裡。',
      'mode.status.ok': '目前是{mode}，裝置運作正常',
      'mode.status.switching': '正在切換到{mode}，請稍候…',
      'mode.status.noadmin': '需要系統管理員權限才能切換驅動綁定',
      'mode.status.nodevice': '找不到 Focusrite 裝置，請確認 USB 已連接',
      'mode.status.unhealthy': '裝置狀態異常（問題碼 {problem}）',
      'mode.status.unknown': '無法判定模式：裝置綁在「{service}」上',
      'mode.status.incomplete': '{mode}的驅動已換綁，但音訊路徑沒有起來 —— 目前實際上沒有可用裝置',

      'mode.kv.complete': '音訊路徑',
      'mode.complete.yes': '已就緒，可以使用',
      'mode.complete.no': '未就緒 —— 舊的音訊堆疊沒被拆掉',
      'mode.kv.adapter': 'Focusrite 音訊節點',

      'mode.evidence': '判斷依據',
      'mode.evidence.hint': '模式不是猜的，而是從裝置實際綁定的服務推出來的。以下是原始數據。',
      'mode.verdict.unknown': '無法判定',
      'mode.kv.parent': '母節點服務',
      'mode.kv.audio': '音訊介面服務',
      'mode.kv.inf': '綁定的 INF',
      'mode.kv.status': '狀態 / 問題碼',
      'mode.kv.endpoints': '在線的音訊端點',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': '原廠驅動 INF',
      'mode.kv.focusriteinf.none': '找不到（無法切換到錄音模式）',

      'mode.why': '為什麼要分兩種模式',
      'mode.why.body':
        '原廠驅動在音訊串流丟包後<strong>不會重新同步</strong>，會卡在持續電流音或直接沒聲音的狀態。' +
        'Windows 內建的 UAC2 類別驅動沒有這個問題，但它沒有原生 ASIO，' +
        '全雙工延遲被音訊引擎鎖在約 46 ms。<br><br>' +
        '而失效幾乎只發生在<strong>日常使用</strong>——大量程式反覆開關音訊串流、切換取樣率；' +
        'DAW 工作時反而穩定，因為那是單一串流、固定取樣率、一路持有到結束。' +
        '所以按情境切換，能同時拿到兩邊的好處。',

      'mode.broken.title': '裝置目前沒有可用的驅動',
      'mode.broken.body': '這通常代表切換到一半失敗了。',
      'mode.broken.body.detail':
        '裝置綁在「{service}」上，問題碼 {problem}。' +
        '如果 Windows 現在完全找不到音訊裝置，按右邊的按鈕即可救回。',
      'mode.broken.action': '修復裝置綁定',

      'toast.mode.start': '正在切換到{mode}',
      'toast.mode.start.sub': '裝置重新列舉中，音訊會中斷約 10 秒',
      'toast.mode.ok': '已切換到{mode}',
      'toast.mode.fail': '切換失敗',
      'toast.mode.repaired': '裝置綁定已修復',
      'toast.mode.repair.fail': '修復失敗',

      'ev.mode_manual': '切換驅動模式',
      'ev.mode_repair': '修復裝置綁定',
      'ev.reset_manual': '手動重置',
      'ev.reset_hotkey': '熱鍵重置',
      'ev.reset_tray': '系統匣重置',
      'ev.reset_auto': '自動重置',
      'ev.anomaly': '偵測到異常',
      'ev.auto_skipped': '略過自動重置',
      'ev.auto_suspended': '自動復原已暫停',
      'ev.ghost_cleanup': '清理幽靈裝置',
      'ev.app_start': '程式啟動',
      'ev.app_stop': '程式結束',
    },

    'zh-Hans': {
      'app.title': 'Scarlett Guard',

      'nav.status': '状态',
      'nav.mode': '驱动模式',
      'nav.detect': '自动检测',
      'nav.settings': '设置',
      'nav.history': '记录',
      'nav.maintenance': '维护',

      'view.status.title': '状态',
      'view.status.sub': 'Focusrite 设备的实时状况与一键重置',
      'view.mode.title': '驱动模式',
      'view.mode.sub': '按场景在稳定与低延迟之间切换',
      'view.detect.title': '自动检测',
      'view.detect.sub': '监听音频流，异常时自动恢复',
      'view.settings.title': '设置',
      'view.settings.sub': '热键、监听设备与常驻行为',
      'view.history.title': '记录',
      'view.history.sub': '每一次异常与重置的完整轨迹',
      'view.maintenance.title': '维护',
      'view.maintenance.sub': '幽灵设备清理与节点总览',

      'top.refresh': '刷新',
      'top.refresh.tip': '刷新设备状态',
      'top.minimise': '收进系统托盘',
      'top.minimise.tip': '收进系统托盘',

      'elev.checking': '检查权限中…',
      'elev.admin': '管理员',
      'elev.none': '权限不足',
      'banner.elev.title': '需要管理员权限',
      'banner.elev.body': '重置 PnP 设备必须提权执行，否则重置按钮无法工作。',
      'banner.elev.action': '以管理员重新启动',
      'banner.suspend.title': '自动恢复已暂停',
      'banner.suspend.body': '短时间内重置次数过多，已暂停以避免无限循环。',
      'banner.suspend.action': '重新启用',

      'status.detecting': '正在检测设备…',
      'status.notfound': '找不到 Focusrite 设备',
      'status.notfound.sub': '请确认 USB 已连接',
      'reset.label': '立即重置设备',
      'reset.sub': '等同于拔掉再插回 USB',
      'reset.sub.noadmin': '需要管理员权限才能执行',
      'reset.sub.nodevice': '找不到可重置的设备',

      'chip.online': '设备在线',
      'chip.offline': '离线（{status}）',
      'chip.driver.focusrite': 'Focusrite 专属驱动',
      'chip.driver.uac2': 'Windows 内置 UAC2 驱动',
      'chip.elevated': '已提权',
      'chip.notelevated': '未提权',
      'chip.ghosts': '{n} 个幽灵设备',

      'stat.last': '上次重置',
      'stat.none': '暂无记录',
      'stat.24h': '24 小时内',
      'stat.times': '次',
      'stat.7d': '7 天内 {n} 次',
      'stat.gap': '平均间隔',
      'stat.gap.foot': '两次重置之间',
      'unit.hours': '{n} 小时',

      'card.driver': '驱动信息',
      'driver.version': '驱动版本',
      'driver.provider': '驱动供应商',
      'driver.date': '驱动日期',
      'driver.manufacturer': '制造商',
      'driver.class': '设备类别',
      'driver.hint.focusrite':
        '当前使用 Focusrite 专属驱动。本工具的重置功能正是针对这套驱动的音频流问题设计的。',
      'driver.hint.uac2':
        '当前使用的是 Windows 内置的 UAC2 类驱动，理论上不会遇到 Focusrite 驱动的恢复缺陷。此时本工具主要作为保险。',

      'card.monitor': '音频监听',
      'monitor.hint':
        '监听 Scarlett 的<strong>录音端点</strong>而非播放 loopback —— 录音端拿到的是 ADC 的真实采样，才能反映硬件那一侧是否还活着。',
      'monitor.off': '未启用',
      'monitor.on': '监听中',
      'monitor.volume': '音量',
      'monitor.zcr': '过零率',
      'monitor.readout': 'gap {gap}s',
      'monitor.readout.base': 'gap {gap}s · 噪声底 {base} dB',

      'card.autorecover': '自动恢复',
      'autorecover.hint':
        '检测到异常时自动执行重置。这些检测是<strong>启发式规则，不是保证</strong> —— 建议先只开监听、观察几天仪表与记录，确认不会误判之后再打开自动恢复。',
      'row.cooldown': '冷却时间',
      'row.cooldown.sub': '两次自动重置之间的最短间隔',
      'row.maxreset': '每小时上限',
      'row.maxreset.sub': '超过就暂停自动恢复，避免无限循环',
      'unit.perhour': '{n} 次/时',

      'card.detectors': '检测器',
      'det.stall.title': '流冻结（stall）',
      'det.stall.sub': '音频回调停止进来，代表 driver 的 stream 时钟已停。最可靠的信号。',
      'det.time': '判定时间',
      'det.silence.title': '信号消失（silence）',
      'det.silence.sub':
        '连续比特级全零。模拟 ADC 正常时永远有噪声底，不可能长时间输出精确的零。',
      'det.duration': '持续时间',
      'det.silence.floor': '静音阈值',
      'det.silence.note':
        '阈值必须远低于实际噪声底（本机实测约 −104 dB），否则正常待机就会误判。另外若你在 Windows 中将此输入静音，也会产生全零而被判定为异常。',
      'det.noise.title': '电流声（noise）',
      'det.noise.sub': '音量高出噪声底一大截且过零率极高。人声与乐器的过零率远低于此。',
      'det.noise.margin': '高出噪声底',
      'det.noise.zcr': '过零率阈值',
      'det.noise.note':
        '最容易误判的一个。录制 hi-hat、失真吉他或白噪素材时可能触发，请依实测调整。',

      'card.hotkey': '全局热键',
      'hotkey.hint': '在任何前台窗口（含全屏 DAW）按下即可重置，不必切回本程序。',
      'hotkey.combo': '组合键',
      'hotkey.combo.sub': 'pynput 格式，例如 <ctrl>+<alt>+r',

      'card.monitordev': '监听设备',
      'dev.input': '录音端点',
      'dev.input.sub': '留空为自动选择 Focusrite',
      'dev.input.auto': '自动选择 Focusrite',
      'dev.samplerate': '采样率',
      'dev.samplerate.sub': '需与设备当前设置一致',
      'dev.samplerate.auto': '自动（跟随设备）',
      'dev.blocksize': '监听块大小',
      'dev.blocksize.sub':
        '越小检测反应越快，CPU 负担略高。这是<strong>本程序采集音频</strong>的块，不是 Focusrite 的 ASIO Buffer Size',
      'dev.blocksize.note':
        'Focusrite 自己的 ASIO Buffer Size 只能在 Focusrite Control 2 的 Device Settings 里改，没有公开 API 可供外部程序设置 —— 本程序改用 <code>pnputil</code> 重置设备达成同样的“重建 stream”效果，不需要去动那个设置。',

      'card.behaviour': '行为',
      'beh.autostart': '开机自动启动',
      'beh.autostart.sub': '用任务计划程序建立高权限登录任务，不会弹 UAC',
      'beh.closetray': '关闭窗口时收进托盘',
      'beh.closetray.sub': '保持常驻，热键才会持续有效',
      'beh.notify': '重置后显示系统通知',
      'beh.notify.sub': '由托盘图标发出',
      'beh.settle': '重置后缓冲时间',
      'beh.settle.sub': '等待设备与驱动稳定再恢复监听',

      'card.language': '语言',
      'lang.label': '界面语言',
      'lang.sub': '更改后立即应用，托盘菜单需重启程序',
      'lang.auto': '自动（跟随系统）',

      'card.paths': '数据位置',
      'paths.config': '配置文件',
      'paths.history': '记录文件',
      'btn.opendata': '打开文件夹',
      'btn.resetsettings': '恢复默认设置',

      'card.history': '事件记录',
      'btn.clear': '清空',
      'history.hint':
        '以 JSON Lines 保存，可直接用文本工具或 pandas 分析“到底多久坏一次、是否真的和 CPU 负载相关”。',
      'history.empty': '暂无记录',
      'hist.duration': '耗时 {ms} ms',
      'hist.method': '方式：{method}',
      'hist.removed': '移除 {removed} / {requested} 个',

      'card.ghosts': '幽灵设备',
      'ghosts.hint':
        '反复插拔与重装驱动累积下来的残留节点（状态为 Unknown）。<strong>尚未证实与断音问题有因果关系</strong>，但清干净可以排除干扰变量，让后续测试的结论更可信。',
      'ghosts.empty': '没有残留的幽灵设备',
      'ghosts.count': '{n} 个',
      'btn.scan': '重新扫描',
      'btn.removesel': '移除选中项',

      'card.alldevices': '所有 Focusrite 设备节点',
      'table.status': '状态',
      'table.name': '名称',
      'table.class': '类别',
      'table.id': 'Instance ID',
      'devices.empty': '没有找到任何 Focusrite 设备节点',

      'dialog.title': '确认',
      'dialog.cancel': '取消',
      'dialog.confirm': '确认移除',
      'dlg.resetsettings.title': '恢复默认设置',
      'dlg.resetsettings.body': '所有设置将回到出厂值，记录不受影响。',
      'dlg.clearhistory.title': '清空记录',
      'dlg.clearhistory.body': '所有事件记录将被永久删除，此操作无法撤销。',
      'dlg.removeghosts.title': '移除幽灵设备',
      'dlg.removeghosts.body':
        '即将移除 {n} 个设备节点。这些节点目前不在线，移除后若重新插入设备 Windows 会重新建立。此操作无法撤销。',

      'toast.refreshed': '已刷新',
      'toast.reset.ok': '设备已重置',
      'toast.reset.ok.sub': '流已重建',
      'toast.reset.fail': '重置失败',
      'toast.monitor.on': '已开始监听',
      'toast.monitor.off': '已停止监听',
      'toast.monitor.fail': '无法启动监听',
      'toast.autostart.ok': '已更新开机设置',
      'toast.autostart.fail': '设置失败',
      'toast.settings.reset': '已恢复默认设置',
      'toast.history.cleared': '记录已清空',
      'toast.scan.done': '已重新扫描',
      'toast.scan.found': '找到 {n} 个幽灵设备',
      'toast.ghosts.removed': '已移除 {n} 个',
      'toast.ghosts.fail': '移除失败',
      'toast.anomaly': '检测到异常：{label}',
      'toast.suspend': '自动恢复已暂停',
      'toast.autoresume': '自动恢复已重新启用',
      'toast.notelevated': '未以管理员身份运行',
      'toast.notelevated.body': '重置功能需要提权，可在上方横幅一键重新启动。',
      'toast.hotkeyfail': '热键注册失败',
      'toast.bootfail': '初始化失败',
      'toast.bridge': '桥接尚未就绪：{method}',

      'mode.switch.aria': '驱动模式',
      'mode.daily.name': '日常模式',
      'mode.daily.for': '听音乐、看视频、游戏',
      'mode.daily.trade': 'Windows 内置驱动 · 稳定 · 全双工约 46 ms',
      'mode.asio.name': '录音模式',
      'mode.asio.for': '练琴、录音、软件监听',
      'mode.asio.trade': '原厂驱动 + ASIO · 低延迟 · 可能需要重置',
      'mode.detecting': '正在读取驱动绑定…',
      'mode.hint':
        '切换会让设备重新枚举，音频中断约 <strong>10 秒</strong>，' +
        '正在录音或播放的程序需要重新选择设备。切换完全可逆，两个驱动都留在系统里。',
      'mode.status.ok': '当前是{mode}，设备运行正常',
      'mode.status.switching': '正在切换到{mode}，请稍候…',
      'mode.status.noadmin': '需要管理员权限才能切换驱动绑定',
      'mode.status.nodevice': '找不到 Focusrite 设备，请确认 USB 已连接',
      'mode.status.unhealthy': '设备状态异常（问题码 {problem}）',
      'mode.status.unknown': '无法判定模式：设备绑在“{service}”上',
      'mode.status.incomplete': '{mode}的驱动已换绑，但音频路径没有起来 —— 当前实际上没有可用设备',

      'mode.kv.complete': '音频路径',
      'mode.complete.yes': '已就绪，可以使用',
      'mode.complete.no': '未就绪 —— 旧的音频堆栈没被拆掉',
      'mode.kv.adapter': 'Focusrite 音频节点',

      'mode.evidence': '判断依据',
      'mode.evidence.hint': '模式不是猜的，而是从设备实际绑定的服务推出来的。以下是原始数据。',
      'mode.verdict.unknown': '无法判定',
      'mode.kv.parent': '母节点服务',
      'mode.kv.audio': '音频接口服务',
      'mode.kv.inf': '绑定的 INF',
      'mode.kv.status': '状态 / 问题码',
      'mode.kv.endpoints': '在线的音频端点',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': '原厂驱动 INF',
      'mode.kv.focusriteinf.none': '找不到（无法切换到录音模式）',

      'mode.why': '为什么要分两种模式',
      'mode.why.body':
        '原厂驱动在音频流丢包后<strong>不会重新同步</strong>，会卡在持续电流声或直接没声音的状态。' +
        'Windows 内置的 UAC2 类驱动没有这个问题，但它没有原生 ASIO，' +
        '全双工延迟被音频引擎锁在约 46 ms。<br><br>' +
        '而失效几乎只发生在<strong>日常使用</strong>——大量程序反复开关音频流、切换采样率；' +
        'DAW 工作时反而稳定，因为那是单一流、固定采样率、一路持有到结束。' +
        '所以按场景切换，能同时拿到两边的好处。',

      'mode.broken.title': '设备当前没有可用的驱动',
      'mode.broken.body': '这通常代表切换到一半失败了。',
      'mode.broken.body.detail':
        '设备绑在“{service}”上，问题码 {problem}。' +
        '如果 Windows 现在完全找不到音频设备，按右边的按钮即可救回。',
      'mode.broken.action': '修复设备绑定',

      'toast.mode.start': '正在切换到{mode}',
      'toast.mode.start.sub': '设备重新枚举中，音频会中断约 10 秒',
      'toast.mode.ok': '已切换到{mode}',
      'toast.mode.fail': '切换失败',
      'toast.mode.repaired': '设备绑定已修复',
      'toast.mode.repair.fail': '修复失败',

      'ev.mode_manual': '切换驱动模式',
      'ev.mode_repair': '修复设备绑定',
      'ev.reset_manual': '手动重置',
      'ev.reset_hotkey': '热键重置',
      'ev.reset_tray': '托盘重置',
      'ev.reset_auto': '自动重置',
      'ev.anomaly': '检测到异常',
      'ev.auto_skipped': '跳过自动重置',
      'ev.auto_suspended': '自动恢复已暂停',
      'ev.ghost_cleanup': '清理幽灵设备',
      'ev.app_start': '程序启动',
      'ev.app_stop': '程序结束',
    },

    en: {
      'app.title': 'Scarlett Guard',

      'nav.status': 'Status',
      'nav.mode': 'Driver mode',
      'nav.detect': 'Detection',
      'nav.settings': 'Settings',
      'nav.history': 'History',
      'nav.maintenance': 'Maintenance',

      'view.status.title': 'Status',
      'view.status.sub': 'Live device state and one-click reset',
      'view.mode.title': 'Driver mode',
      'view.mode.sub': 'Trade stability for latency, per situation',
      'view.detect.title': 'Detection',
      'view.detect.sub': 'Watch the audio stream and recover automatically',
      'view.settings.title': 'Settings',
      'view.settings.sub': 'Hotkey, monitored device and background behaviour',
      'view.history.title': 'History',
      'view.history.sub': 'Every anomaly and reset, on the record',
      'view.maintenance.title': 'Maintenance',
      'view.maintenance.sub': 'Phantom device cleanup and node overview',

      'top.refresh': 'Refresh',
      'top.refresh.tip': 'Refresh device state',
      'top.minimise': 'Hide to tray',
      'top.minimise.tip': 'Hide to tray',

      'elev.checking': 'Checking rights…',
      'elev.admin': 'Administrator',
      'elev.none': 'Not elevated',
      'banner.elev.title': 'Administrator rights required',
      'banner.elev.body':
        'Restarting a PnP device needs elevation — without it the reset button stays disabled.',
      'banner.elev.action': 'Restart as administrator',
      'banner.suspend.title': 'Auto-recovery suspended',
      'banner.suspend.body':
        'Too many resets in a short window. Paused to avoid an endless loop.',
      'banner.suspend.action': 'Re-enable',

      'status.detecting': 'Detecting device…',
      'status.notfound': 'No Focusrite device found',
      'status.notfound.sub': 'Check that the USB cable is connected',
      'reset.label': 'Reset device now',
      'reset.sub': 'Equivalent to unplugging and replugging the USB cable',
      'reset.sub.noadmin': 'Requires administrator rights',
      'reset.sub.nodevice': 'No device available to reset',

      'chip.online': 'Device online',
      'chip.offline': 'Offline ({status})',
      'chip.driver.focusrite': 'Focusrite driver',
      'chip.driver.uac2': 'Windows UAC2 class driver',
      'chip.elevated': 'Elevated',
      'chip.notelevated': 'Not elevated',
      'chip.ghosts': '{n} phantom devices',

      'stat.last': 'Last reset',
      'stat.none': 'No history yet',
      'stat.24h': 'Last 24 hours',
      'stat.times': '',
      'stat.7d': '{n} in the last 7 days',
      'stat.gap': 'Mean interval',
      'stat.gap.foot': 'Between consecutive resets',
      'unit.hours': '{n} h',

      'card.driver': 'Driver',
      'driver.version': 'Driver version',
      'driver.provider': 'Driver provider',
      'driver.date': 'Driver date',
      'driver.manufacturer': 'Manufacturer',
      'driver.class': 'Device class',
      'driver.hint.focusrite':
        "You're on the Focusrite driver. This tool's reset exists precisely for the audio-stream problems that driver exhibits.",
      'driver.hint.uac2':
        "You're on the built-in Windows UAC2 class driver, which shouldn't exhibit the Focusrite driver's recovery defect. This tool is mainly insurance here.",

      'card.monitor': 'Audio monitoring',
      'monitor.hint':
        "Monitors the Scarlett's <strong>capture endpoint</strong> rather than a playback loopback — capture carries the real ADC samples, so it reflects whether the hardware side is still alive.",
      'monitor.off': 'Off',
      'monitor.on': 'Monitoring',
      'monitor.volume': 'Level',
      'monitor.zcr': 'ZCR',
      'monitor.readout': 'gap {gap}s',
      'monitor.readout.base': 'gap {gap}s · floor {base} dB',

      'card.autorecover': 'Auto-recovery',
      'autorecover.hint':
        'Reset automatically when an anomaly is detected. These detectors are <strong>heuristics, not guarantees</strong> — run monitoring alone for a few days first, watch the meters and the log, and only enable auto-recovery once you trust it.',
      'row.cooldown': 'Cooldown',
      'row.cooldown.sub': 'Minimum gap between two automatic resets',
      'row.maxreset': 'Hourly limit',
      'row.maxreset.sub': 'Suspends auto-recovery when exceeded, to avoid a loop',
      'unit.perhour': '{n}/hour',

      'card.detectors': 'Detectors',
      'det.stall.title': 'Stream stall',
      'det.stall.sub':
        "Audio callbacks stop arriving — the driver's stream clock has frozen. The most reliable signal.",
      'det.time': 'Trigger after',
      'det.silence.title': 'Signal loss',
      'det.silence.sub':
        'Sustained bit-exact zero. A working analogue ADC always has a noise floor, so it cannot output exact zeros for long.',
      'det.duration': 'Sustained for',
      'det.silence.floor': 'Silence threshold',
      'det.silence.note':
        'Must sit far below the real noise floor (measured ≈ −104 dB on this machine), or normal idle will trip it. Muting this input in Windows also produces zeros and will read as an anomaly.',
      'det.noise.title': 'Static / crackle',
      'det.noise.sub':
        'Level far above the learned noise floor with a very high zero-crossing rate. Voice and instruments sit well below that.',
      'det.noise.margin': 'Above noise floor',
      'det.noise.zcr': 'ZCR threshold',
      'det.noise.note':
        'The most false-positive-prone detector. Hi-hats, distorted guitar or white-noise material can trip it — tune against your own material.',

      'card.hotkey': 'Global hotkey',
      'hotkey.hint':
        'Resets from any foreground window, including full-screen DAWs — no need to switch back here.',
      'hotkey.combo': 'Key combination',
      'hotkey.combo.sub': 'pynput syntax, e.g. <ctrl>+<alt>+r',

      'card.monitordev': 'Monitored device',
      'dev.input': 'Capture endpoint',
      'dev.input.sub': 'Leave empty to pick the Focusrite automatically',
      'dev.input.auto': 'Auto-select Focusrite',
      'dev.samplerate': 'Sample rate',
      'dev.samplerate.sub': 'Must match the device’s current setting',
      'dev.samplerate.auto': 'Auto (follow device)',
      'dev.blocksize': 'Capture block size',
      'dev.blocksize.sub':
        "Smaller reacts faster at slightly higher CPU cost. This is <strong>this app's</strong> capture block — not the Focusrite ASIO buffer size",
      'dev.blocksize.note':
        'The Focusrite ASIO buffer size can only be changed in Focusrite Control 2 — there is no public API for it. This app uses <code>pnputil</code> to restart the device instead, which rebuilds the stream just the same without touching that setting.',

      'card.behaviour': 'Behaviour',
      'beh.autostart': 'Start with Windows',
      'beh.autostart.sub': 'Creates an elevated logon task, so no UAC prompt',
      'beh.closetray': 'Closing the window hides to tray',
      'beh.closetray.sub': 'Stays resident so the hotkey keeps working',
      'beh.notify': 'System notification after reset',
      'beh.notify.sub': 'Raised by the tray icon',
      'beh.settle': 'Settle time after reset',
      'beh.settle.sub': 'Wait for device and driver to stabilise before resuming monitoring',

      'card.language': 'Language',
      'lang.label': 'Interface language',
      'lang.sub': 'Applies immediately; the tray menu updates on next launch',
      'lang.auto': 'Auto (follow system)',

      'card.paths': 'Data location',
      'paths.config': 'Config file',
      'paths.history': 'History file',
      'btn.opendata': 'Open folder',
      'btn.resetsettings': 'Restore defaults',

      'card.history': 'Event log',
      'btn.clear': 'Clear',
      'history.hint':
        'Stored as JSON Lines, so you can analyse it directly with a text tool or pandas — how often it actually breaks, and whether it really correlates with CPU load.',
      'history.empty': 'No entries yet',
      'hist.duration': 'took {ms} ms',
      'hist.method': 'via {method}',
      'hist.removed': 'removed {removed} of {requested}',

      'card.ghosts': 'Phantom devices',
      'ghosts.hint':
        'Leftover nodes (status Unknown) accumulated from repeated replugging and driver reinstalls. <strong>Not proven to cause the dropouts</strong>, but clearing them removes a confounding variable and makes later testing more trustworthy.',
      'ghosts.empty': 'No phantom devices',
      'ghosts.count': '{n}',
      'btn.scan': 'Rescan',
      'btn.removesel': 'Remove selected',

      'card.alldevices': 'All Focusrite device nodes',
      'table.status': 'Status',
      'table.name': 'Name',
      'table.class': 'Class',
      'table.id': 'Instance ID',
      'devices.empty': 'No Focusrite device nodes found',

      'dialog.title': 'Confirm',
      'dialog.cancel': 'Cancel',
      'dialog.confirm': 'Remove',
      'dlg.resetsettings.title': 'Restore defaults',
      'dlg.resetsettings.body':
        'All settings return to their factory values. The event log is untouched.',
      'dlg.clearhistory.title': 'Clear history',
      'dlg.clearhistory.body':
        'All event records will be permanently deleted. This cannot be undone.',
      'dlg.removeghosts.title': 'Remove phantom devices',
      'dlg.removeghosts.body':
        'About to remove {n} device node(s). They are currently offline; Windows will recreate them if the device is plugged in again. This cannot be undone.',

      'toast.refreshed': 'Refreshed',
      'toast.reset.ok': 'Device reset',
      'toast.reset.ok.sub': 'Stream rebuilt',
      'toast.reset.fail': 'Reset failed',
      'toast.monitor.on': 'Monitoring started',
      'toast.monitor.off': 'Monitoring stopped',
      'toast.monitor.fail': 'Could not start monitoring',
      'toast.autostart.ok': 'Startup setting updated',
      'toast.autostart.fail': 'Could not update setting',
      'toast.settings.reset': 'Defaults restored',
      'toast.history.cleared': 'History cleared',
      'toast.scan.done': 'Rescanned',
      'toast.scan.found': 'Found {n} phantom device(s)',
      'toast.ghosts.removed': 'Removed {n}',
      'toast.ghosts.fail': 'Removal failed',
      'toast.anomaly': 'Anomaly detected: {label}',
      'toast.suspend': 'Auto-recovery suspended',
      'toast.autoresume': 'Auto-recovery re-enabled',
      'toast.notelevated': 'Not running as administrator',
      'toast.notelevated.body':
        'Reset needs elevation — use the banner above to relaunch.',
      'toast.hotkeyfail': 'Hotkey registration failed',
      'toast.bootfail': 'Initialisation failed',
      'toast.bridge': 'Bridge not ready: {method}',

      'mode.switch.aria': 'Driver mode',
      'mode.daily.name': 'Everyday',
      'mode.daily.for': 'Music, video, games',
      'mode.daily.trade': 'Built-in driver · stable · ~46 ms full duplex',
      'mode.asio.name': 'Studio',
      'mode.asio.for': 'Practice, tracking, software monitoring',
      'mode.asio.trade': 'Focusrite driver + ASIO · low latency · may need resets',
      'mode.detecting': 'Reading driver binding…',
      'mode.hint':
        'Switching re-enumerates the device, so audio drops for about <strong>10 seconds</strong> ' +
        'and anything currently playing or recording will need to pick the device again. ' +
        'The switch is fully reversible — both drivers stay installed.',
      'mode.status.ok': 'In {mode} — device is healthy',
      'mode.status.switching': 'Switching to {mode}…',
      'mode.status.noadmin': 'Administrator rights are required to rebind the driver',
      'mode.status.nodevice': 'No Focusrite device found — check the USB connection',
      'mode.status.unhealthy': 'Device is unhealthy (problem code {problem})',
      'mode.status.unknown': 'Cannot determine the mode: the device is bound to “{service}”',
      'mode.status.incomplete':
        'The driver for {mode} is bound, but the audio path never came up — there is no usable device right now',

      'mode.kv.complete': 'Audio path',
      'mode.complete.yes': 'Ready to use',
      'mode.complete.no': 'Not ready — the old audio stack was never torn down',
      'mode.kv.adapter': 'Focusrite audio node',

      'mode.evidence': 'Evidence',
      'mode.evidence.hint':
        'The mode is not guessed — it is derived from the service the device is actually bound to. Raw data below.',
      'mode.verdict.unknown': 'Undetermined',
      'mode.kv.parent': 'Parent service',
      'mode.kv.audio': 'Audio interface service',
      'mode.kv.inf': 'Bound INF',
      'mode.kv.status': 'Status / problem code',
      'mode.kv.endpoints': 'Live audio endpoints',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': 'Focusrite INF',
      'mode.kv.focusriteinf.none': 'Not found — Studio mode unavailable',

      'mode.why': 'Why two modes',
      'mode.why.body':
        'The Focusrite driver <strong>does not resynchronise</strong> after a dropped audio packet — ' +
        'it gets stuck emitting static, or goes silent. Windows’ built-in UAC2 class driver ' +
        'does not have that flaw, but it offers no native ASIO, so the audio engine pins ' +
        'full-duplex latency at roughly 46 ms.<br><br>' +
        'In practice the failures happen almost exclusively during <strong>everyday use</strong>, ' +
        'where many apps repeatedly open and close streams and change sample rates. DAW sessions ' +
        'are comparatively stable: one stream, one sample rate, held open from start to finish. ' +
        'Switching per situation gets you both halves.',

      'mode.broken.title': 'The device has no working driver',
      'mode.broken.body': 'This usually means a switch failed halfway through.',
      'mode.broken.body.detail':
        'The device is bound to “{service}” with problem code {problem}. ' +
        'If Windows currently shows no audio devices at all, the button on the right will recover it.',
      'mode.broken.action': 'Repair device binding',

      'toast.mode.start': 'Switching to {mode}',
      'toast.mode.start.sub': 'Re-enumerating the device — audio drops for about 10 seconds',
      'toast.mode.ok': 'Switched to {mode}',
      'toast.mode.fail': 'Switch failed',
      'toast.mode.repaired': 'Device binding repaired',
      'toast.mode.repair.fail': 'Repair failed',

      'ev.mode_manual': 'Driver mode switch',
      'ev.mode_repair': 'Device binding repair',
      'ev.reset_manual': 'Manual reset',
      'ev.reset_hotkey': 'Hotkey reset',
      'ev.reset_tray': 'Tray reset',
      'ev.reset_auto': 'Automatic reset',
      'ev.anomaly': 'Anomaly detected',
      'ev.auto_skipped': 'Automatic reset skipped',
      'ev.auto_suspended': 'Auto-recovery suspended',
      'ev.ghost_cleanup': 'Phantom device cleanup',
      'ev.app_start': 'App started',
      'ev.app_stop': 'App stopped',
    },
  };

  const LANGUAGES = [
    { code: 'zh-Hant', label: '繁體中文' },
    { code: 'zh-Hans', label: '简体中文' },
    { code: 'en', label: 'English' },
  ];

  let current = 'zh-Hant';

  function resolve(code) {
    if (code && code !== 'auto' && CATALOG[code]) return code;
    const tags = (navigator.languages || [navigator.language || 'en']).map((x) =>
      String(x).toLowerCase()
    );
    for (const tag of tags) {
      if (tag.startsWith('zh')) {
        // 只有明確標成簡體地區的才給簡體，其餘華語一律繁體
        return /hans|\b(cn|sg|my)\b/.test(tag) ? 'zh-Hans' : 'zh-Hant';
      }
      if (tag.startsWith('en')) return 'en';
    }
    return 'en';
  }

  function setLanguage(code) {
    current = resolve(code);
    document.documentElement.lang = current;
    return current;
  }

  function t(key, params) {
    const table = CATALOG[current] || CATALOG.en;
    let text = table[key];
    if (text == null) text = CATALOG.en[key];
    if (text == null) return key;
    if (params) {
      text = text.replace(/\{(\w+)\}/g, (match, name) =>
        params[name] == null ? match : String(params[name])
      );
    }
    return text;
  }

  /** 套用所有 data-i18n 標記。允許重複呼叫，切換語言時直接重跑。 */
  function apply(root = document) {
    root.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll('[data-i18n-html]').forEach((el) => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    root.querySelectorAll('[data-i18n-title]').forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
    root.querySelectorAll('[data-i18n-aria]').forEach((el) => {
      el.setAttribute('aria-label', t(el.dataset.i18nAria));
    });
  }

  return { t, apply, setLanguage, resolve, get current() { return current; }, LANGUAGES };
})();
