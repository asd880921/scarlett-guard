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
      'nav.status': '狀態',
      'nav.settings': '設定',
      'view.status.title': '狀態',
      'view.status.sub': '在穩定與低延遲之間切換，並在需要時重置裝置',
      'view.settings.title': '設定',
      'view.settings.sub': '熱鍵、常駐行為與維護',
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
      'status.notfound': '找不到 Focusrite 裝置',
      'reset.label': '立即重置裝置',
      'reset.sub': '等同於拔掉再插回 USB',
      'reset.sub.noadmin': '需要系統管理員權限才能執行',
      'reset.sub.nodevice': '找不到可重置的裝置',

      'chip.online': '裝置在線',
      'driver.version': '驅動版本',
      'driver.date': '驅動日期',
      'card.language': '語言',
      'lang.label': '介面語言',
      'lang.label.sub': '「自動」跟隨 Windows 的顯示語言；切換後立即生效，不需重新啟動',
      'lang.auto': '自動（跟隨系統）',
      'card.hotkey': '全域熱鍵',
      'hotkey.combo': '按下時重置裝置',
      'hotkey.combo.sub': 'pynput 格式，例如 <ctrl>+<alt>+r · 僅在錄音模式有效',
      'card.behaviour': '行為',
      'beh.autostart': '開機自動啟動',
      'beh.autostart.sub': '以工作排程器建立高權限登入工作，不會跳 UAC',
      'beh.closetray': '關閉視窗時收進系統匣',
      'beh.closetray.sub': '保持常駐，熱鍵才會持續有效',
      'beh.notify': '重置後顯示系統通知',
      'beh.notify.sub': '由系統匣圖示發出',

      'paths.config': '設定檔',
      'paths.history': '紀錄檔',
      'btn.opendata': '開啟資料夾',
      'btn.resetsettings': '回復預設設定',

      'btn.clear': '清空',
      'hist.duration': '耗時 {ms} ms',
      'hist.removed': '移除 {removed} / {requested} 個',

      'card.ghosts': '幽靈裝置',
      'ghosts.hint': '反覆切換模式與插拔會留下狀態為 Unknown 的節點。清掉可以讓端點名稱不再累積編號前綴。',
      'ghosts.empty': '沒有殘留的幽靈裝置',
      'ghosts.count': '{n} 個',
      'btn.scan': '重新掃描',
      'btn.removesel': '移除選取項目',

      'table.status': '狀態',
      'table.name': '名稱',
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
      'toast.autostart.ok': '已更新開機設定',
      'toast.autostart.fail': '設定失敗',
      'toast.settings.reset': '已回復預設設定',
      'toast.history.cleared': '紀錄已清空',
      'toast.scan.done': '已重新掃描',
      'toast.scan.found': '找到 {n} 個幽靈裝置',
      'toast.ghosts.removed': '已移除 {n} 個',
      'toast.ghosts.fail': '移除失敗',
      'toast.notelevated': '未以系統管理員執行',
      'toast.notelevated.body': '重置功能需要提權，可在上方橫幅一鍵重新啟動。',
      'toast.hotkeyfail': '熱鍵註冊失敗',
      'toast.bootfail': '初始化失敗',
      'toast.bridge': '橋接尚未就緒：{method}',

      // --- 驅動模式 ---
      'mode.switch.aria': '驅動模式',
      'mode.daily.name': '日常模式',
      'mode.daily.for': '聽音樂、看影片、遊戲',
      'mode.asio.name': '錄音模式',
      'mode.asio.for': '練琴、錄音、軟體監聽',
      'mode.detecting': '正在讀取驅動綁定…',
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

      'mode.kv.parent': '母節點服務',
      'mode.kv.audio': '音訊介面服務',
      'mode.kv.inf': '綁定的 INF',
      'mode.kv.status': '狀態 / 問題碼',
      'mode.kv.endpoints': '在線的音訊端點',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': '原廠驅動 INF',
      'mode.kv.focusriteinf.none': '找不到（無法切換到錄音模式）',

      'mode.broken.title': '裝置目前沒有可用的驅動',
      'mode.broken.body': '裝置綁在「{service}」上，音訊路徑沒有起來。',
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
      'ev.ghost_cleanup': '清理幽靈裝置',
      'ev.app_start': '程式啟動',
      'ev.app_stop': '程式結束',
      'tech.title': '技術細節',
      'log.title': '最近動作',
      'log.empty': '還沒有任何紀錄',
      'card.data': '設定與紀錄',
      'reset.sub.dailymode': '僅在錄音模式可用',
      'update.available': '發現新版本 v{version}',
      'update.tip': '開啟 v{version} 的下載頁',

      // --- 系統音效 ---
      'nav.audio': '音效',
      'view.audio.title': '音效',
      'view.audio.sub': '切換裝置、調整系統與各個應用程式的音量',
      'audio.system': '系統',
      'audio.output.volume': '音量',
      'audio.output.device': '輸出裝置',
      'audio.output.mute': '輸出靜音',
      'audio.input.volume': '麥克風音量',
      'audio.input.device': '輸入裝置',
      'audio.input.mute': '麥克風靜音',
      'audio.apps': '應用程式',
      'audio.apps.count': '{n} 個',
      'audio.apps.empty': '目前沒有應用程式在使用音訊',
      'audio.systemsounds': '系統音效',
      'audio.unknownapp': '未知的應用程式',
      'audio.app.mute': '靜音這個應用程式',
      'audio.nodevice': '沒有可用的裝置',
      'audio.none.title': '找不到可用的輸出裝置',
      'audio.none.body': '請確認喇叭或音訊介面已連接，並且沒有被系統停用。',
      'audio.rescan': '重新掃描',
      'audio.resetapps': '重設應用程式音量',
      'audio.resetapps.hint':
        '把所有應用程式的音量拉回 100% 並解除靜音。切換驅動模式後音量常被打亂，這是最快的收拾方式。',
      'audio.reset.done': '已重設應用程式音量',
      'audio.reset.done.sub': '共 {n} 個工作階段',
      'audio.reset.fail': '重設失敗',
      'audio.device.switched': '已切換預設裝置',
      'audio.device.fail': '切換裝置失敗',
      'audio.fail': '讀取音訊狀態失敗',
      'ev.audio_default': '切換預設音訊裝置',
      'ev.audio_reset': '重設應用程式音量',
    },

    'zh-Hans': {
      'nav.status': '状态',
      'nav.settings': '设置',
      'view.status.title': '状态',
      'view.status.sub': '在稳定与低延迟之间切换，并在需要时重置设备',
      'view.settings.title': '设置',
      'view.settings.sub': '热键、常驻行为与维护',
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
      'status.notfound': '找不到 Focusrite 设备',
      'reset.label': '立即重置设备',
      'reset.sub': '等同于拔掉再插回 USB',
      'reset.sub.noadmin': '需要管理员权限才能执行',
      'reset.sub.nodevice': '找不到可重置的设备',

      'chip.online': '设备在线',
      'driver.version': '驱动版本',
      'driver.date': '驱动日期',
      'card.language': '语言',
      'lang.label': '界面语言',
      'lang.label.sub': '「自动」跟随 Windows 的显示语言；切换后立即生效，无需重启',
      'lang.auto': '自动（跟随系统）',
      'card.hotkey': '全局热键',
      'hotkey.combo': '按下时重置设备',
      'hotkey.combo.sub': 'pynput 格式，例如 <ctrl>+<alt>+r · 仅在录音模式有效',
      'card.behaviour': '行为',
      'beh.autostart': '开机自动启动',
      'beh.autostart.sub': '用任务计划程序建立高权限登录任务，不会弹 UAC',
      'beh.closetray': '关闭窗口时收进托盘',
      'beh.closetray.sub': '保持常驻，热键才会持续有效',
      'beh.notify': '重置后显示系统通知',
      'beh.notify.sub': '由托盘图标发出',

      'paths.config': '配置文件',
      'paths.history': '记录文件',
      'btn.opendata': '打开文件夹',
      'btn.resetsettings': '恢复默认设置',

      'btn.clear': '清空',
      'hist.duration': '耗时 {ms} ms',
      'hist.removed': '移除 {removed} / {requested} 个',

      'card.ghosts': '幽灵设备',
      'ghosts.hint': '反复切换模式与插拔会留下状态为 Unknown 的节点。清掉可以让端点名称不再累积编号前缀。',
      'ghosts.empty': '没有残留的幽灵设备',
      'ghosts.count': '{n} 个',
      'btn.scan': '重新扫描',
      'btn.removesel': '移除选中项',

      'table.status': '状态',
      'table.name': '名称',
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
      'toast.autostart.ok': '已更新开机设置',
      'toast.autostart.fail': '设置失败',
      'toast.settings.reset': '已恢复默认设置',
      'toast.history.cleared': '记录已清空',
      'toast.scan.done': '已重新扫描',
      'toast.scan.found': '找到 {n} 个幽灵设备',
      'toast.ghosts.removed': '已移除 {n} 个',
      'toast.ghosts.fail': '移除失败',
      'toast.notelevated': '未以管理员身份运行',
      'toast.notelevated.body': '重置功能需要提权，可在上方横幅一键重新启动。',
      'toast.hotkeyfail': '热键注册失败',
      'toast.bootfail': '初始化失败',
      'toast.bridge': '桥接尚未就绪：{method}',

      'mode.switch.aria': '驱动模式',
      'mode.daily.name': '日常模式',
      'mode.daily.for': '听音乐、看视频、游戏',
      'mode.asio.name': '录音模式',
      'mode.asio.for': '练琴、录音、软件监听',
      'mode.detecting': '正在读取驱动绑定…',
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

      'mode.kv.parent': '母节点服务',
      'mode.kv.audio': '音频接口服务',
      'mode.kv.inf': '绑定的 INF',
      'mode.kv.status': '状态 / 问题码',
      'mode.kv.endpoints': '在线的音频端点',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': '原厂驱动 INF',
      'mode.kv.focusriteinf.none': '找不到（无法切换到录音模式）',

      'mode.broken.title': '设备当前没有可用的驱动',
      'mode.broken.body': '设备绑在“{service}”上，音频路径没有起来。',
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
      'ev.ghost_cleanup': '清理幽灵设备',
      'ev.app_start': '程序启动',
      'ev.app_stop': '程序结束',
      'tech.title': '技术细节',
      'log.title': '最近动作',
      'log.empty': '还没有任何记录',
      'card.data': '设置与记录',
      'reset.sub.dailymode': '仅在录音模式可用',
      'update.available': '发现新版本 v{version}',
      'update.tip': '打开 v{version} 的下载页',

      // --- 系统音效 ---
      'nav.audio': '音效',
      'view.audio.title': '音效',
      'view.audio.sub': '切换设备、调整系统与各个应用程序的音量',
      'audio.system': '系统',
      'audio.output.volume': '音量',
      'audio.output.device': '输出设备',
      'audio.output.mute': '输出静音',
      'audio.input.volume': '麦克风音量',
      'audio.input.device': '输入设备',
      'audio.input.mute': '麦克风静音',
      'audio.apps': '应用程序',
      'audio.apps.count': '{n} 个',
      'audio.apps.empty': '当前没有应用程序在使用音频',
      'audio.systemsounds': '系统音效',
      'audio.unknownapp': '未知的应用程序',
      'audio.app.mute': '静音这个应用程序',
      'audio.nodevice': '没有可用的设备',
      'audio.none.title': '找不到可用的输出设备',
      'audio.none.body': '请确认扬声器或音频接口已连接，并且没有被系统停用。',
      'audio.rescan': '重新扫描',
      'audio.resetapps': '重置应用程序音量',
      'audio.resetapps.hint':
        '把所有应用程序的音量拉回 100% 并解除静音。切换驱动模式后音量常被打乱，这是最快的收拾方式。',
      'audio.reset.done': '已重置应用程序音量',
      'audio.reset.done.sub': '共 {n} 个会话',
      'audio.reset.fail': '重置失败',
      'audio.device.switched': '已切换默认设备',
      'audio.device.fail': '切换设备失败',
      'audio.fail': '读取音频状态失败',
      'ev.audio_default': '切换默认音频设备',
      'ev.audio_reset': '重置应用程序音量',
    },

    en: {
      'nav.status': 'Status',
      'nav.settings': 'Settings',
      'view.status.title': 'Status',
      'view.status.sub': 'Switch between stability and low latency, and reset when needed',
      'view.settings.title': 'Settings',
      'view.settings.sub': 'Hotkey, background behaviour and maintenance',
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
      'status.notfound': 'No Focusrite device found',
      'reset.label': 'Reset device now',
      'reset.sub': 'Equivalent to unplugging and replugging the USB cable',
      'reset.sub.noadmin': 'Requires administrator rights',
      'reset.sub.nodevice': 'No device available to reset',

      'chip.online': 'Device online',
      'driver.version': 'Driver version',
      'driver.date': 'Driver date',
      'card.language': 'Language',
      'lang.label': 'Interface language',
      'lang.label.sub': 'Auto follows the Windows display language · applies instantly, no restart',
      'lang.auto': 'Auto (follow system)',
      'card.hotkey': 'Global hotkey',
      'hotkey.combo': 'Resets the device when pressed',
      'hotkey.combo.sub': 'pynput syntax, e.g. <ctrl>+<alt>+r · Studio mode only',
      'card.behaviour': 'Behaviour',
      'beh.autostart': 'Start with Windows',
      'beh.autostart.sub': 'Creates an elevated logon task, so no UAC prompt',
      'beh.closetray': 'Closing the window hides to tray',
      'beh.closetray.sub': 'Stays resident so the hotkey keeps working',
      'beh.notify': 'System notification after reset',
      'beh.notify.sub': 'Raised by the tray icon',

      'paths.config': 'Config file',
      'paths.history': 'History file',
      'btn.opendata': 'Open folder',
      'btn.resetsettings': 'Restore defaults',

      'btn.clear': 'Clear',
      'hist.duration': 'took {ms} ms',
      'hist.removed': 'removed {removed} of {requested}',

      'card.ghosts': 'Phantom devices',
      'ghosts.hint': 'Repeated mode switches and replugs leave nodes with an Unknown status. Clearing them stops endpoint names from accumulating a numeric prefix.',
      'ghosts.empty': 'No phantom devices',
      'ghosts.count': '{n}',
      'btn.scan': 'Rescan',
      'btn.removesel': 'Remove selected',

      'table.status': 'Status',
      'table.name': 'Name',
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
      'toast.autostart.ok': 'Startup setting updated',
      'toast.autostart.fail': 'Could not update setting',
      'toast.settings.reset': 'Defaults restored',
      'toast.history.cleared': 'History cleared',
      'toast.scan.done': 'Rescanned',
      'toast.scan.found': 'Found {n} phantom device(s)',
      'toast.ghosts.removed': 'Removed {n}',
      'toast.ghosts.fail': 'Removal failed',
      'toast.notelevated': 'Not running as administrator',
      'toast.notelevated.body':
        'Reset needs elevation — use the banner above to relaunch.',
      'toast.hotkeyfail': 'Hotkey registration failed',
      'toast.bootfail': 'Initialisation failed',
      'toast.bridge': 'Bridge not ready: {method}',

      'mode.switch.aria': 'Driver mode',
      'mode.daily.name': 'Everyday',
      'mode.daily.for': 'Music, video, games',
      'mode.asio.name': 'Studio',
      'mode.asio.for': 'Practice, tracking, software monitoring',
      'mode.detecting': 'Reading driver binding…',
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

      'mode.kv.parent': 'Parent service',
      'mode.kv.audio': 'Audio interface service',
      'mode.kv.inf': 'Bound INF',
      'mode.kv.status': 'Status / problem code',
      'mode.kv.endpoints': 'Live audio endpoints',
      'mode.kv.hwid': 'Hardware ID',
      'mode.kv.focusriteinf': 'Focusrite INF',
      'mode.kv.focusriteinf.none': 'Not found — Studio mode unavailable',

      'mode.broken.title': 'The device has no working driver',
      'mode.broken.body': 'The device is bound to “{service}” and the audio path is not up.',
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
      'ev.ghost_cleanup': 'Phantom device cleanup',
      'ev.app_start': 'App started',
      'ev.app_stop': 'App stopped',
      'tech.title': 'Technical detail',
      'log.title': 'Recent activity',
      'log.empty': 'Nothing logged yet',
      'card.data': 'Settings and log',
      'reset.sub.dailymode': 'Available in Studio mode only',
      'update.available': 'New version available: v{version}',
      'update.tip': 'Open the download page for v{version}',

      // --- System audio ---
      'nav.audio': 'Audio',
      'view.audio.title': 'Audio',
      'view.audio.sub': 'Switch devices and set system and per-app volumes',
      'audio.system': 'System',
      'audio.output.volume': 'Volume',
      'audio.output.device': 'Output device',
      'audio.output.mute': 'Mute output',
      'audio.input.volume': 'Microphone volume',
      'audio.input.device': 'Input device',
      'audio.input.mute': 'Mute microphone',
      'audio.apps': 'Apps',
      'audio.apps.count': '{n}',
      'audio.apps.empty': 'No app is using audio right now',
      'audio.systemsounds': 'System sounds',
      'audio.unknownapp': 'Unknown app',
      'audio.app.mute': 'Mute this app',
      'audio.nodevice': 'No device available',
      'audio.none.title': 'No output device found',
      'audio.none.body':
        'Check that speakers or an audio interface are connected and not disabled in Windows.',
      'audio.rescan': 'Rescan',
      'audio.resetapps': 'Reset app volumes',
      'audio.resetapps.hint':
        'Sets every app back to 100% and unmutes it. Switching driver mode often scrambles these, and this is the quickest way to clean up.',
      'audio.reset.done': 'App volumes reset',
      'audio.reset.done.sub': '{n} session(s)',
      'audio.reset.fail': 'Reset failed',
      'audio.device.switched': 'Default device switched',
      'audio.device.fail': 'Could not switch device',
      'audio.fail': 'Could not read audio state',
      'ev.audio_default': 'Default audio device switched',
      'ev.audio_reset': 'App volumes reset',
    },
  };

  const LANGUAGES = [
    { code: 'zh-Hant', label: '繁體中文' },
    { code: 'zh-Hans', label: '简体中文' },
    { code: 'en', label: 'English' },
  ];

  let current = 'en';

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
