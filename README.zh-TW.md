# Scarlett Guard

[English](README.md) · **繁體中文**

## ⇄ 讓 Scarlett 在「穩定」與「低延遲」之間一鍵切換

Focusrite 原廠驅動有原生 ASIO，但音訊串流丟包後不會重新同步；Windows 內建的
UAC2 類別驅動很穩，但沒有 ASIO。**Scarlett Guard 讓你按情境在兩者之間切換，
約 15 秒、完全可逆，不需要重新開機。**

Windows 10 / 11 ・ Python 3.11+
針對 **Scarlett Solo 4th Gen** 開發與實測，任何 Focusrite USB 介面都適用。

---

## 這個工具在解決什麼問題

用 Scarlett 聽音樂或錄音時，聲音偶爾會突然變成持續的電流音、或是直接消失，
而且**不會自己恢復**。

實測定位到的結論是：問題在原廠驅動的錯誤復原邏輯，而 Windows 內建的類別驅動
沒有這個缺陷。但內建驅動沒有原生 ASIO，全雙工延遲被音訊引擎鎖在約 46 ms。

而失效幾乎只發生在**日常使用**——大量程式反覆開關音訊串流、切換取樣率。
DAW 工作時反而穩定，因為那是單一串流、固定取樣率、一路持有到結束。

所以最合理的用法不是二選一，而是按情境切換。

---

## 快速開始

```powershell
cd scarlett-guard
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
start.bat
```

之後把設定頁的「開機自動啟動」打開，它就會常駐在系統匣裡待命。

<details>
<summary>其他啟動方式</summary>

```powershell
# 不提權啟動（視窗開得起來，但切換與重置會停用）
.venv\Scripts\python.exe run.py

# 啟動後直接收進系統匣，不顯示視窗
.venv\Scripts\pythonw.exe run.py --tray
```

</details>

---

## 驅動模式

| 模式 | 綁定的驅動 | 適用 |
|---|---|---|
| **日常模式** | Windows 內建 `usbaudio2` | 聽音樂、看影片、遊戲 |
| **錄音模式** | Focusrite 原廠 + ASIO | 練琴、錄音、軟體監聽 |

從主畫面的分段控制切換，或直接用系統匣選單，不必開視窗。
切換期間音訊會中斷，正在播放或錄音的程式需要重新選擇裝置。
**兩個驅動都留在系統裡**，切換完全可逆，不需重裝任何東西。

實測耗時（同一台機器，四次連續來回）：

| 方向 | 耗時 | 需要暫停音訊引擎 |
|---|---|---|
| 錄音 → 日常 | 約 12 秒 | 否 |
| 日常 → 錄音 | 約 17 秒 | 是 |

### 為什麼往錄音模式比較慢（以及為什麼曾經需要重開機）

兩種模式的裝置樹形狀不同：

```
日常模式                                錄音模式
USB\VID_xxxx&PID_xxxx → usbccgp        USB\VID_xxxx&PID_xxxx → FocusriteUsb
  └ &MI_00 → usbaudio2  ← 音訊在這      ROOT\FOCUSRITEUSBNEW → FocusriteUsbSwRoot
                                          └ FOCUSRITEUSB\AUDIO&ADAPTER → 音訊在這
```

**日常模式的音訊 function 是 USB 裝置的子孫，錄音模式的則掛在獨立的軟體根上。**

- **錄音 → 日常**：拆掉 USB 那一側時，Focusrite 的音訊節點只是變成幽靈，
  沒有 handle 阻擋，所以當場完成。
- **日常 → 錄音**：必須先拆掉 `MI_00` 子節點，但它持有的音訊端點被
  `AudioEndpointBuilder` 抓著 —— handle 沒放掉就拆不掉，PnP 只能把驅動替換排到
  下次開機。**這就是「切換後要重開機才生效」的真正原因。**

解法是換綁前先停掉 `Audiosrv` 與 `AudioEndpointBuilder` 放掉那些 handle，
再停用裝置（連帶拆掉所有子節點）、換綁、啟用、還原服務。程式會依「目前有沒有
活著的 `usbaudio2` 子節點」預測是否需要走這條路，所以不會在不必要時付這個代價。
服務還原寫在 `finally` 裡，不管換綁成功或失敗都一定執行。

### 驗證的是「音訊路徑」，不是「綁到哪個驅動」

這兩件事必須分開。有一種失敗極難察覺：**母節點成功換綁到 `FocusriteUsb`、
問題碼一切正常，但舊的 `usbaudio2` 子節點還活著，Focusrite 的音訊節點根本沒生出來**
—— 畫面顯示「已切換到錄音模式」，實際上一個 ASIO 裝置都沒有。

所以驗收條件是**音訊 function 真的上線**：錄音模式要看到 `AUDIO&ADAPTER` 節點且
沒有活著的 `usbaudio2` 子節點；日常模式要看到 `usbaudio2` 子節點在線。
「技術細節」第一行的「音訊路徑」顯示的就是這個結論，未就緒時會明確報錯而不是假裝成功。

> Windows 換綁 API 回傳的 `bRebootRequired` **不可信** —— 實測連續八次來回切換，
> 每次都當場生效，但每次都回報需要重開機。程式只認 `CM_PROB_NEED_RESTART`（Code 14），
> 而且真的出現時會先用軟體重置去化解。

### 如果切換失敗

萬一切換到一半失敗，裝置會變成沒有可用驅動 —— 症狀是
**Windows 完全找不到任何音訊輸出／輸入裝置**。這時主畫面最上方會出現
**「修復裝置綁定」**，它會重掃 PnP 並強制綁回內建驅動。
內建驅動是 in-box 的、不可能不存在，所以這條救援路徑永遠可用。

> ⚠️ **不要卸載「Focusrite Audio Drivers」。** 那會把驅動包從 driver store 移除，
> 就再也切不回錄音模式了。Focusrite Control 2 和驅動包是兩個獨立的安裝項目；
> 在日常模式下它們沒有註冊任何常駐服務或程序，留著不佔資源。

---

## 重置裝置

在錄音模式下如果真的遇到電流音或斷音，重置會強迫驅動把音訊串流整個拆掉重建 ——
效果等同拔插 USB，但約 3 秒完成、不用碰線材。

| 方式 | 操作 |
|---|---|
| **全域熱鍵**（最快） | `Ctrl` + `Alt` + `R`，在全螢幕 DAW 或遊戲裡同樣有效 |
| **系統匣** | 右鍵圖示 → 立即重置裝置 |
| **主畫面** | 模式切換器下方的按鈕 |

> 系統匣圖示的**左鍵雙擊是開啟視窗，不是重置** —— 重置會中斷音訊，
> 綁在這麼容易誤觸的操作上代價太高。

---

## 其他功能

**幽靈裝置清理** —— 反覆切換模式與插拔會累積狀態為 `Unknown` 的殘留節點，
而且會讓端點名稱長出 `2-`、`3-` 這類編號前綴，導致預設輸出裝置跑掉。
設定頁可以列出來勾選移除。

**事件紀錄** —— 每次切換、重置與清理都會記下來，收在主畫面的「最近動作」裡。
純文字 JSON Lines，也可以直接用文字編輯器打開。

**技術細節** —— 收合在主畫面下方：模式的判斷依據、驅動版本、以及裝置在系統裡
註冊的所有節點。模式不是猜的，這裡列的是推導它的原始數據。

**多語系** —— 繁體中文 / 简体中文 / English，預設跟隨系統語言，
可在設定頁切換，切換後立即套用（系統匣選單需重新啟動程式）。

**常駐** —— 關閉視窗會收進系統匣讓熱鍵持續有效；圖示會以顏色顯示狀態；
重複啟動不會開出第二份，而是把已在執行的視窗叫出來。

---

## 關於系統管理員權限

換綁驅動與重置 PnP 裝置都是 Windows 要求提權的操作。

它**不會**在啟動時就丟一個沒頭沒尾的 UAC 對話框。未提權時程式照樣開得起來，
只是切換與重置停用，並在視窗上方顯示橫幅與「以管理員重新啟動」按鈕，由你決定。

如果不想每次都按 UAC，打開設定頁的**開機自動啟動**即可 ——
它建立的是工作排程器的登入工作，能以高權限直接啟動而不跳 UAC。

---

## 設定與資料

都存在 `%APPDATA%\ScarlettGuard\`（設定頁有按鈕可直接開啟）：

| 檔案 | 內容 |
|---|---|
| `config.json` | 所有設定 |
| `history.jsonl` | 事件紀錄 |

**熱鍵格式**使用 pynput 語法，例如 `<ctrl>+<alt>+r`、`<ctrl>+<shift>+<f9>`。
輸入時會即時驗證；萬一設成無效組合，程式會自動退回上一個能用的。

`config.json` 裡另有兩個不出現在 UI 的項目：`post_reset_settle_seconds` 與
`mode_settle_seconds`（等裝置安定的秒數）。預設值已經實測夠用，需要時可直接改檔案。

---

## 已知限制

- **僅支援 Windows** —— 依賴 `pnputil`、`newdev.dll` 與 Windows 的 PnP 管理指令。
- **切換與重置會中斷正在進行的錄音**，效果等同拔插 USB。
- **`pnputil` 做不到換綁** —— 內建的 `usb.inf` 永遠被原廠驅動的 driver rank 壓過，
  而[官方文件](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax)
  明載 PnPUtil 不會強制安裝被 outrank 的驅動。本程式改用 `newdev.dll` 的
  `UpdateDriverForPlugAndPlayDevicesW` + `INSTALLFLAG_FORCE`（即 `devcon update`
  的底層機制）。
- 本工具**緩解症狀，不修復驅動本身**。

---

## 開發者資訊

<details>
<summary>專案結構與技術棧</summary>

```
run.py                     啟動器（免安裝，直接執行）
start.bat                  以系統管理員啟動
tools/check_ui.py          介面一致性檢查（三語 key、文案引用、DOM id）
src/scarlett_guard/
  main.py                  組裝服務、系統匣與視窗
  service.py               核心服務層：UI 與系統匣都只跟這一層對話
  driver_mode.py           原廠驅動 ↔ 內建類別驅動的強制換綁
  device.py                PnP 探索、重置、幽靈裝置移除
  hotkey.py                全域熱鍵
  tray.py                  系統匣圖示
  autostart.py             工作排程器整合
  elevation.py             UAC 提權
  single_instance.py       單一實例控制
  config.py / history.py   設定與紀錄持久化
  i18n.py                  後端文案
  api.py                   JS ↔ Python 橋接
  ui/                      介面（HTML / CSS / JS）
```

介面以 pywebview（WebView2）承載，全域熱鍵用 pynput，系統匣用 pystray。

改動 UI 後請跑 `python tools/check_ui.py` —— UI 沒有編譯期，
打錯文案 key 或找不存在的元素只會讓畫面安靜地半殘。

視覺與動態依循 Apple 的介面設計原則：半透明材質分層、捲動邊緣漸層取代硬分隔線、
字距隨字級變化、所有按壓回饋在 pointer-down 當下發生，並支援
`prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast`
與淺色深色主題。

</details>

---

## 授權

MIT
