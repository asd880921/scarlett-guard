"""後端文案。

前端有自己的 ui/i18n.js；這裡負責的是 Python 產生、再送到 UI 或系統匣
顯示的字串（錯誤訊息、系統通知、系統匣選單）。

語言由 config 的 language 決定，"auto" 時跟隨系統地區設定。
"""
from __future__ import annotations

import locale
from typing import Any

DEFAULT = "zh-Hant"
SUPPORTED = ("zh-Hant", "zh-Hans", "en")

CATALOG: dict[str, dict[str, str]] = {
    "zh-Hant": {
        # --- 裝置 ---
        "dev.notarget": "找不到目標裝置",
        "dev.notarget.detail": "請先在設定中選擇要重置的 Focusrite 裝置。",
        "dev.needadmin": "需要系統管理員權限",
        "dev.needadmin.detail": "重置 PnP 裝置必須以系統管理員身分執行，請用視窗上方的按鈕重新啟動。",
        "dev.reset.ok": "裝置已重置",
        "dev.reset.fail": "重置失敗",
        "dev.pnputil.fail": "pnputil 執行失敗",
        "dev.pnputil.detail": "pnputil 失敗（exit {code}）：{output}\n備援方式也失敗：{fallback}",
        "dev.notfound": "找不到 Focusrite 裝置",
        "dev.notfound.detail": "請確認 USB 已連接。",
        "dev.busy": "已有重置作業進行中",
        "dev.busy.detail": "請等目前的作業完成再試。",
        "reset.blocked": "日常模式下不需要重置",
        "reset.blocked.detail": "Windows 內建驅動沒有原廠驅動的串流復原缺陷，而且此時 pnputil 也拆不掉音訊子節點（exit 3010）。切到錄音模式才需要、也才能重置。",
        "ghost.needadmin.detail": "移除裝置節點需要系統管理員權限。",
        "ghost.removed": "已移除幽靈裝置",
        "ghost.fail": "移除失敗",
        "ghost.skip": "略過：此裝置目前並非幽靈狀態",
        # --- 驅動模式 ---
        "mode.daily": "日常模式",
        "mode.asio": "錄音模式",
        "mode.badmode": "未知的模式代號",
        "mode.needadmin.detail": "切換驅動綁定必須以系統管理員身分執行，請用視窗上方的按鈕重新啟動。",
        "mode.already": "已經是{mode}",
        "mode.nohwid": "無法從裝置 ID 推導出 hardware ID",
        "mode.noinf": "找不到 Windows 內建的 usb.inf",
        "mode.nofocusrite": "找不到 Focusrite 原廠驅動",
        "mode.nofocusrite.detail": "driver store 與安裝目錄裡都找不到 focusritecustom.inf。請重新安裝 Focusrite 驅動，或在設定裡指定 INF 路徑。",
        "mode.ok": "已切換到{mode}",
        "mode.ok.detail": "母節點服務：{service}；音訊介面服務：{audio}",
        "mode.fail": "切換到{mode}失敗",
        "mode.fail.detail": "強制綁定失敗。\nINF：{inf}\nHardware ID：{hwid}\n錯誤：{error}",
        "mode.verifyfail": "切換到{mode}後驗證失敗",
        "mode.verifyfail.detail": "裝置目前的服務是「{service}」，問題碼「{problem}」。若 Windows 現在找不到任何音訊裝置，請按「修復裝置綁定」。",
        "mode.unhealthy": "已切換到{mode}，但裝置狀態異常",
        "mode.unhealthy.detail": "問題碼：{problem}。可以試著按「修復裝置綁定」。",
        "mode.incomplete": "{mode}的驅動換綁完成，但音訊路徑沒有起來",
        "mode.incomplete.detail": "母節點換綁成功，但舊的音訊堆疊沒被拆掉：Focusrite 音訊節點「{adapter}」、USB 子介面服務「{child}」。這代表實際上還沒有可用的 ASIO 裝置。請再按一次切換，或按「修復裝置綁定」。",
        "mode.reboot": "以下節點卡在待重啟狀態，兩級處理都未能化解，這次確實需要重新開機：{nodes}",
        "mode.restartcleared": "曾出現待重啟狀態，已用軟體重置化解，不需重新開機。",
        "mode.escalated": "舊的裝置堆疊被音訊引擎的 handle 卡住，已暫停 Windows 音訊服務完成換綁，不需重新開機。其他程式的音訊可能需要重新選擇裝置。",
        "mode.repair.nothing": "裝置綁定正常，無需修復",
        "mode.busy": "已有切換作業進行中",
        "mode.busy.detail": "請等目前的作業完成再試。",
        # --- 熱鍵 ---
        "hk.disabled": "熱鍵已停用",
        "hk.nopynput": "pynput 無法載入：{error}",
        "hk.empty": "熱鍵組合為空",
        "hk.failed": "熱鍵註冊失敗：{error}",
        "hk.registered": "熱鍵已註冊：{combo}",
        "hk.reverted": "已還原為先前的組合：{combo}",
        "hk.valid": "格式正確",
        "hk.invalid": "格式錯誤：{error}",
        "hk.noload": "pynput 無法載入",
        # --- 開機啟動 ---
        "auto.enabled": "已設定為開機自動啟動（以系統管理員權限）",
        "auto.disabled": "已取消開機自動啟動",
        "auto.enablefail": "設定失敗：{detail}",
        "auto.disablefail": "取消失敗：{detail}",
        # --- 系統匣 ---
        "tray.reset": "立即重置裝置",
        "tray.open": "開啟 Scarlett Guard",
        "tray.mode.daily": "切換到日常模式",
        "tray.mode.asio": "切換到錄音模式",
        "tray.quit": "結束",
        "tray.title": "Scarlett Guard",
        "tray.reset.ok": "裝置已重置",
        "tray.reset.fail": "重置失敗：{message}",
        # --- 設定 ---
        "cfg.restored": "已回復預設設定",
    },
    "zh-Hans": {
        "dev.notarget": "找不到目标设备",
        "dev.notarget.detail": "请先在设置中选择要重置的 Focusrite 设备。",
        "dev.needadmin": "需要管理员权限",
        "dev.needadmin.detail": "重置 PnP 设备必须以管理员身份执行，请用窗口上方的按钮重新启动。",
        "dev.reset.ok": "设备已重置",
        "dev.reset.fail": "重置失败",
        "dev.pnputil.fail": "pnputil 执行失败",
        "dev.pnputil.detail": "pnputil 失败（exit {code}）：{output}\n备用方式也失败：{fallback}",
        "dev.notfound": "找不到 Focusrite 设备",
        "dev.notfound.detail": "请确认 USB 已连接。",
        "dev.busy": "已有重置作业进行中",
        "dev.busy.detail": "请等当前的作业完成再试。",
        "reset.blocked": "日常模式下不需要重置",
        "reset.blocked.detail": "Windows 内置驱动没有原厂驱动的流恢复缺陷，而且此时 pnputil 也拆不掉音频子节点（exit 3010）。切到录音模式才需要、也才能重置。",
        "ghost.needadmin.detail": "移除设备节点需要管理员权限。",
        "ghost.removed": "已移除幽灵设备",
        "ghost.fail": "移除失败",
        "ghost.skip": "跳过：此设备当前并非幽灵状态",
        "mode.daily": "日常模式",
        "mode.asio": "录音模式",
        "mode.badmode": "未知的模式代号",
        "mode.needadmin.detail": "切换驱动绑定必须以管理员身份执行，请用窗口上方的按钮重新启动。",
        "mode.already": "已经是{mode}",
        "mode.nohwid": "无法从设备 ID 推导出 hardware ID",
        "mode.noinf": "找不到 Windows 内置的 usb.inf",
        "mode.nofocusrite": "找不到 Focusrite 原厂驱动",
        "mode.nofocusrite.detail": "driver store 与安装目录里都找不到 focusritecustom.inf。请重新安装 Focusrite 驱动，或在设置里指定 INF 路径。",
        "mode.ok": "已切换到{mode}",
        "mode.ok.detail": "母节点服务：{service}；音频接口服务：{audio}",
        "mode.fail": "切换到{mode}失败",
        "mode.fail.detail": "强制绑定失败。\nINF：{inf}\nHardware ID：{hwid}\n错误：{error}",
        "mode.verifyfail": "切换到{mode}后验证失败",
        "mode.verifyfail.detail": "设备当前的服务是“{service}”，问题码“{problem}”。若 Windows 现在找不到任何音频设备，请按“修复设备绑定”。",
        "mode.unhealthy": "已切换到{mode}，但设备状态异常",
        "mode.unhealthy.detail": "问题码：{problem}。可以试着按“修复设备绑定”。",
        "mode.incomplete": "{mode}的驱动换绑完成，但音频路径没有起来",
        "mode.incomplete.detail": "母节点换绑成功，但旧的音频堆栈没被拆掉：Focusrite 音频节点“{adapter}”、USB 子接口服务“{child}”。这代表实际上还没有可用的 ASIO 设备。请再按一次切换，或按“修复设备绑定”。",
        "mode.reboot": "以下节点卡在待重启状态，两级处理都未能化解，这次确实需要重新启动：{nodes}",
        "mode.restartcleared": "曾出现待重启状态，已用软件重置化解，不需重新启动。",
        "mode.escalated": "旧的设备堆栈被音频引擎的 handle 卡住，已暂停 Windows 音频服务完成换绑，不需重新启动。其他程序的音频可能需要重新选择设备。",
        "mode.repair.nothing": "设备绑定正常，无需修复",
        "mode.busy": "已有切换作业进行中",
        "mode.busy.detail": "请等当前的作业完成再试。",
        "hk.disabled": "热键已停用",
        "hk.nopynput": "pynput 无法加载：{error}",
        "hk.empty": "热键组合为空",
        "hk.failed": "热键注册失败：{error}",
        "hk.registered": "热键已注册：{combo}",
        "hk.reverted": "已还原为先前的组合：{combo}",
        "hk.valid": "格式正确",
        "hk.invalid": "格式错误：{error}",
        "hk.noload": "pynput 无法加载",
        "auto.enabled": "已设为开机自动启动（以管理员权限）",
        "auto.disabled": "已取消开机自动启动",
        "auto.enablefail": "设置失败：{detail}",
        "auto.disablefail": "取消失败：{detail}",
        "tray.reset": "立即重置设备",
        "tray.open": "打开 Scarlett Guard",
        "tray.mode.daily": "切换到日常模式",
        "tray.mode.asio": "切换到录音模式",
        "tray.quit": "退出",
        "tray.title": "Scarlett Guard",
        "tray.reset.ok": "设备已重置",
        "tray.reset.fail": "重置失败：{message}",
        "cfg.restored": "已恢复默认设置",
    },
    "en": {
        "dev.notarget": "No target device",
        "dev.notarget.detail": "Pick the Focusrite device to reset in Settings first.",
        "dev.needadmin": "Administrator rights required",
        "dev.needadmin.detail": "Restarting a PnP device requires elevation — use the button at the top of the window to relaunch.",
        "dev.reset.ok": "Device reset",
        "dev.reset.fail": "Reset failed",
        "dev.pnputil.fail": "pnputil failed",
        "dev.pnputil.detail": "pnputil failed (exit {code}): {output}\nFallback also failed: {fallback}",
        "dev.notfound": "No Focusrite device found",
        "dev.notfound.detail": "Check that the USB cable is connected.",
        "dev.busy": "A reset is already in progress",
        "dev.busy.detail": "Wait for the current operation to finish.",
        "reset.blocked": "No reset needed in Everyday mode",
        "reset.blocked.detail": "The built-in driver does not have the Focusrite driver's stream-recovery flaw, and pnputil cannot tear down the audio child node here anyway (exit 3010). Switch to Studio mode if you need a reset.",
        "ghost.needadmin.detail": "Removing a device node requires administrator rights.",
        "ghost.removed": "Phantom device removed",
        "ghost.fail": "Removal failed",
        "ghost.skip": "Skipped: this device is not currently a phantom",
        "mode.daily": "Everyday mode",
        "mode.asio": "Studio mode",
        "mode.badmode": "Unknown mode identifier",
        "mode.needadmin.detail": "Rebinding a driver requires elevation — use the button at the top of the window to relaunch.",
        "mode.already": "Already in {mode}",
        "mode.nohwid": "Could not derive a hardware ID from the device instance ID",
        "mode.noinf": "Windows' built-in usb.inf is missing",
        "mode.nofocusrite": "Focusrite driver not found",
        "mode.nofocusrite.detail": "focusritecustom.inf was not found in the driver store or the install directory. Reinstall the Focusrite driver, or point at the INF in Settings.",
        "mode.ok": "Switched to {mode}",
        "mode.ok.detail": "Parent service: {service}; audio interface service: {audio}",
        "mode.fail": "Could not switch to {mode}",
        "mode.fail.detail": "Forced rebind failed.\nINF: {inf}\nHardware ID: {hwid}\nError: {error}",
        "mode.verifyfail": "Verification failed after switching to {mode}",
        "mode.verifyfail.detail": "The device is bound to “{service}” with problem code “{problem}”. If Windows now shows no audio devices at all, press “Repair device binding”.",
        "mode.unhealthy": "Switched to {mode}, but the device is unhealthy",
        "mode.unhealthy.detail": "Problem code: {problem}. Try “Repair device binding”.",
        "mode.incomplete": "The driver rebind for {mode} completed, but the audio path never came up",
        "mode.incomplete.detail": "The parent node rebound successfully, but the old audio stack was never torn down: Focusrite audio node “{adapter}”, USB child interface service “{child}”. That means there is no usable ASIO device yet. Switch again, or press “Repair device binding”.",
        "mode.reboot": "These nodes are stuck pending a restart and neither remedy cleared it, so a reboot really is needed this time: {nodes}",
        "mode.restartcleared": "A pending-restart state appeared and was cleared with a software reset — no reboot needed.",
        "mode.escalated": "The old device stack was pinned by the audio engine's handles, so the Windows audio services were paused to complete the rebind — no reboot needed. Other apps may need to pick their audio device again.",
        "mode.repair.nothing": "Device binding is healthy — nothing to repair",
        "mode.busy": "A switch is already in progress",
        "mode.busy.detail": "Wait for the current operation to finish.",
        "hk.disabled": "Hotkey disabled",
        "hk.nopynput": "Could not load pynput: {error}",
        "hk.empty": "Hotkey combination is empty",
        "hk.failed": "Hotkey registration failed: {error}",
        "hk.registered": "Hotkey registered: {combo}",
        "hk.reverted": "Reverted to the previous combination: {combo}",
        "hk.valid": "Valid",
        "hk.invalid": "Invalid: {error}",
        "hk.noload": "Could not load pynput",
        "auto.enabled": "Will start with Windows (elevated)",
        "auto.disabled": "Startup entry removed",
        "auto.enablefail": "Could not enable: {detail}",
        "auto.disablefail": "Could not disable: {detail}",
        "tray.reset": "Reset device now",
        "tray.open": "Open Scarlett Guard",
        "tray.mode.daily": "Switch to Everyday mode",
        "tray.mode.asio": "Switch to Studio mode",
        "tray.quit": "Quit",
        "tray.title": "Scarlett Guard",
        "tray.reset.ok": "Device reset",
        "tray.reset.fail": "Reset failed: {message}",
        "cfg.restored": "Defaults restored",
    },
}

_current = DEFAULT


def resolve(code: str | None) -> str:
    """把設定值（可能是 "auto"）解析成實際語言代碼。"""
    if code and code in SUPPORTED:
        return code
    try:
        tag = (locale.getdefaultlocale()[0] or "").lower()
    except (ValueError, TypeError):
        tag = ""
    if tag.startswith("zh"):
        # 只有明確標成簡體地區的才給簡體，其餘華語一律繁體
        return "zh-Hans" if any(x in tag for x in ("hans", "cn", "sg", "my")) else "zh-Hant"
    if tag.startswith("en"):
        return "en"
    return DEFAULT


def set_language(code: str | None) -> str:
    global _current
    _current = resolve(code)
    return _current


def current() -> str:
    return _current


def t(key: str, **params: Any) -> str:
    table = CATALOG.get(_current) or CATALOG[DEFAULT]
    text = table.get(key) or CATALOG["en"].get(key) or key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text
