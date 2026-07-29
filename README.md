# Scarlett Guard

> Focusrite Scarlett 介面的「軟體版 USB 拔插」工具 —— 一鍵、熱鍵、或自動偵測後重建音訊串流，
> 不必伸手去拔線，也不必再去 Focusrite Device Settings 切換 Sample Rate。

Windows / Python 3.11+ ／ 針對 **Scarlett Solo 4th Gen** 開發與實測，
但對任何 Focusrite USB 裝置（VID `1235`）都適用。

---

## 這個工具在解決什麼問題

Focusrite 的 Windows 專屬驅動在 USB isochronous 傳輸丟包後**無法自我復原**：
stream 的讀寫指標一旦錯位就不再重新同步，於是聲音卡在持續電流音，或整條串流凍住變成沒聲音。
CPU 尖峰只是提高丟包機率的「觸發條件」，不是根因。

社群長年只有兩種解法，而它們的本質是同一件事 —— **強制把 stream 拆掉重建**：

1. 重新插拔 USB（裝置重新列舉 → driver 重開 stream）
2. 在 Device Settings 切換 Sample Rate / Buffer Size（driver 必須關閉再重開 pipeline）

`pnputil /restart-device` 可以在軟體層做到完全相同的事。本工具就是圍繞這一點打造的。

> 完整的問題分析、證據與其他替代方案（含移除原廠驅動改用 FlexASIO）見上層目錄的
> [`RESEARCH.md`](../RESEARCH.md)。

---

## 功能

### 重置
- **一鍵重置** —— 主畫面的大按鈕，約 1–2 秒完成
- **全域熱鍵** —— 預設 `Ctrl+Alt+R`，在全螢幕 DAW 裡也有效
- **系統匣選單** —— 右鍵第一項就是「立即重置裝置」。左鍵雙擊刻意**不**綁重置而是開啟視窗：
  重置會中斷音訊約三秒，誤觸代價太高，快速重置請用熱鍵
- 主要走 `pnputil /restart-device`，失敗時自動退回 `Disable-PnpDevice` + `Enable-PnpDevice`
- 重置後等待裝置重新上線，再依設定緩衝數秒才恢復監聽

### 自動偵測與自動復原
監聽 Scarlett 的**錄音端點**（而非播放 loopback）—— 錄音端拿到的是 ADC 的真實取樣，
才能反映硬體那一側是否還活著。三個獨立可關的偵測器：

| 偵測器 | 原理 | 可靠度 |
|---|---|---|
| **stall** | 音訊回呼停止進來 → driver 的 stream 時鐘已停 | 最高 |
| **silence** | 連續位元級全零。類比 ADC 正常時永遠有噪音底，不可能長時間輸出精確的零 | 高 |
| **noise** | 音量高出學習到的噪音底一大截、且過零率極高（電流音／白噪的特徵） | 最容易誤判 |

安全閥：**冷卻時間**（兩次自動重置的最短間隔）與**每小時上限**（超過就自動暫停，避免在裝置真的
壞掉時無限重置）。

> **誠實說明**：這些是啟發式規則，不是保證。建議先只開監聽、觀察幾天儀表與紀錄，
> 確認不會誤判之後，再打開自動復原。UI 提供即時儀表（波形、音量、過零率、學習到的噪音底）
> 讓你自己校準門檻。

### 紀錄與統計
- 每次異常、重置、略過、暫停都寫入 JSON Lines
- 統計：總次數、24 小時／7 天內次數、**平均間隔**、上次重置時間
- 可直接用文字工具或 pandas 分析「到底多久壞一次、是否真的和 CPU 負載相關」

### 維護
- **幽靈裝置清理** —— 列出反覆插拔與重裝驅動累積的殘留節點（狀態 Unknown），可勾選移除
- **所有節點總覽** —— 一次看清 Focusrite 在系統裡註冊了哪些裝置
- 顯示目前驅動版本、供應商、日期，並判斷你走的是 **Focusrite 專屬驅動**還是
  **Windows 內建 UAC2 類別驅動**

### 常駐
- 系統匣圖示帶狀態色（正常／忙碌／異常）
- 關閉視窗收進系統匣，熱鍵持續有效
- 開機自動啟動（用工作排程器的 `/RL HIGHEST`，**不會跳 UAC**）

---

## 安裝

```powershell
cd scarlett-guard
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 執行

```powershell
# 一般啟動（未提權時可開啟，但重置按鈕會停用並顯示提示）
.venv\Scripts\python.exe run.py

# 以系統管理員啟動（推薦）
start.bat

# 直接收進系統匣、不顯示視窗
.venv\Scripts\pythonw.exe run.py --tray
```

### 為什麼需要系統管理員權限

`pnputil /restart-device` 屬於 PnP 裝置管理操作，Windows 要求提權。
程式**不會**在啟動時就丟一個沒有前後文的 UAC 對話框 —— 未提權時照樣開得起來，
只是在畫面上方顯示橫幅並提供「以管理員重新啟動」按鈕，由你決定。

若嫌每次都要按 UAC 麻煩，開啟「開機自動啟動」即可：
工作排程器的登入工作能以高權限直接啟動而不跳 UAC。

---

## 設定

設定與紀錄存放在 `%APPDATA%\ScarlettGuard\`：

| 檔案 | 內容 |
|---|---|
| `config.json` | 所有設定 |
| `history.jsonl` | 事件紀錄（JSON Lines） |

熱鍵格式為 pynput 的語法，例如 `<ctrl>+<alt>+r`、`<ctrl>+<shift>+<f9>`。
輸入時會即時驗證；若設定成無效組合，程式會自動退回上一個能用的組合，
不會讓你失去這個功能。

### 門檻的預設值怎麼來的

`silence_floor_db` 預設 **−140 dB**，是依實機量測決定的：
Scarlett Solo 閒置時的噪音底約 **−104 dB**，門檻必須遠低於它才不會在正常待機時誤判；
而真正的位元級全零會落在 −240 dB，任何單一非零取樣也只會把 RMS 拉到 −170 dB 左右。

---

## 架構

```
run.py                     啟動器（免安裝，直接跑）
start.bat                  提權啟動
src/scarlett_guard/
  main.py                  組裝服務、系統匣與 webview 視窗
  service.py               核心服務層：UI 與系統匣都只跟這一層對話
  device.py                PnP 探索、重置、幽靈裝置移除
  monitor.py               音訊異常偵測（sounddevice + numpy）
  hotkey.py                全域熱鍵（pynput）
  tray.py                  系統匣圖示（pystray + Pillow）
  autostart.py             工作排程器整合
  elevation.py             UAC 提權
  config.py / history.py   設定與紀錄持久化
  api.py                   pywebview 的 JS ↔ Python 橋接
  ui/                      介面（HTML / CSS / JS）
```

介面用 pywebview（WebView2）承載，視覺與動態依循 Apple 的介面設計原則：
半透明材質分層、捲動邊緣漸層取代硬分隔線、字距隨字級變化、
所有按壓回饋在 pointer-down 當下發生，並完整支援
`prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast` 與淺色深色主題。

---

## 已知限制

- **僅支援 Windows。** 依賴 `pnputil` 與 PnP cmdlet。
- **DAW 以 ASIO 獨佔裝置時，監聽功能會被擋下。** 這是 Windows 音訊模型的正常行為，
  程式會明確告訴你，而不是靜默失敗。此時一鍵／熱鍵重置仍然完全可用。
- **重置會中斷正在進行的錄音。** 它就是拔插 USB，DAW 需要重新選擇裝置或重開串流。
- **自動偵測是啟發式的**，尤其 noise 偵測器可能被 hi-hat、破音吉他或白噪素材觸發。
- 本工具**緩解症狀，不修復驅動**。若要真正繞開根因，見 `RESEARCH.md` 的方案 A。

---

## 授權

MIT
