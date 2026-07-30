<div align="center">
  <img src="assets/icon.ico" alt="icon"><br>
  <h1>Scarlett Guard</h1>
  <p>一鍵切換 Focusrite Scarlett 日常 / 錄音模式，讓日常使用不再受驅動異常影響。</p>
  <p>
    <a href="https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip">
      <img src="https://shieldcn.dev/github/downloads-asset/asd880921/scarlett-guard/scarlett-guard.zip.svg?style=for-the-badge&label=downloads&labelColor=24292f&color=2ea44f" alt="Downloads" />
    </a>
  </p>
  <p>
    <img src="https://img.shields.io/github/v/release/asd880921/scarlett-guard?style=for-the-badge&label=latest%20release" alt="Latest release" />
    <img src="https://img.shields.io/badge/license-MIT-22C55E?style=for-the-badge" alt="License MIT" />
    <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=for-the-badge" alt="Windows 10 | 11" />
  </p>
  <p><a href="README.md">English</a> · <b>繁體中文</b></p>
</div>

---

## 兩個模式，一鍵切換

|  | 用哪個驅動 | 什麼時候用 | 切過去要多久 |
|---|---|---|---|
| **日常模式** | Windows 內建 `usbaudio2` | 聽音樂、看影片、遊戲 | 約 12 秒 |
| **錄音模式** | Focusrite 原廠 + ASIO | 練琴、錄音、軟體監聽 | 約 17 秒 |

從主畫面點，或直接用系統匣選單，不必開視窗。切換期間音訊會斷，正在播放或錄音的程式要重新選一次裝置。

兩個驅動都留在系統裡，隨時切回去，不用重裝任何東西，也不用重開機。

## 安裝

[下載 `scarlett-guard.zip`](https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip)，解壓縮，對 `Scarlett Guard.exe` 按右鍵**以系統管理員身分執行**。不需要裝 Python。

> 請先解壓縮再執行，不要直接在壓縮檔裡點開。

換綁驅動需要系統管理員權限。程式不會一啟動就丟 UAC 給你，未提權時照樣開得起來，只是切換和重置停用，視窗上方會有按鈕讓你決定要不要重開。

把設定頁的「開機自動啟動」打開，它就會常駐在系統匣。那走的是工作排程器的登入工作，之後不會再跳 UAC。

---

## 這是在解決什麼

用 Scarlett 聽音樂或錄音，聲音偶爾會變成持續的電流音，或整個消失。它不會自己好，只有拔插 USB、或去 Focusrite Control 2 把取樣率切一下才會回來。

問題在原廠驅動的錯誤復原邏輯。Windows 內建的類別驅動沒這個毛病，但它沒有原生 ASIO，全雙工延遲被卡在 46 ms 左右。

實際用下來，出事幾乎都發生在日常使用的時候，一堆程式反覆開關音訊串流、切換取樣率。開 DAW 反而穩，因為那是一條串流從頭持有到尾。

與其挑一個忍受，不如按情境換。

## 出問題的時候

**切換失敗** 會讓裝置沒有可用的驅動，症狀是 Windows 完全找不到任何音訊裝置。這時主畫面最上方會出現「修復裝置綁定」，按下去會重掃 PnP 並強制綁回內建驅動。內建驅動是 in-box 的，不可能不存在，所以這條路永遠走得通。

**錄音模式下遇到電流音或斷音**，用重置。它強迫驅動把音訊串流拆掉重建，等同拔插 USB，但三秒就好。三種觸發方式：

| 方式 | 操作 |
|---|---|
| 全域熱鍵 | `Ctrl` + `Alt` + `R`，全螢幕 DAW 或遊戲裡都有效 |
| 系統匣 | 右鍵 → 立即重置裝置 |
| 主畫面 | 模式切換器下面那顆按鈕 |

重置在日常模式下是停用的。內建驅動本來就沒有那個缺陷，而且真的按下去也會失敗（`pnputil` 拆不掉被音訊引擎持有的子節點，只會回 exit 3010）。熱鍵在日常模式按下去不會有任何反應，這是故意的。

> ⚠️ 不要卸載「Focusrite Audio Drivers」。那會把驅動包從 driver store 移除，之後就切不回錄音模式了。它和 Focusrite Control 2 是兩個獨立的安裝項目，日常模式下都不會註冊任何常駐服務或程序，留著不佔資源。

## 其他

**幽靈裝置清理**：反覆切換和插拔會留下一堆狀態是 `Unknown` 的節點，還會讓端點名稱長出 `2-`、`3-` 這種編號前綴，害預設輸出裝置跑掉。設定頁可以列出來清掉。

**最近動作**：每次切換、重置、清理都會記下來，收在主畫面下方。純文字 JSON Lines，直接用編輯器打開也行。

**技術細節**：也在主畫面下方，收合著。裡面是模式判斷的原始數據 —— 裝置綁在哪個服務上、音訊路徑起來了沒、系統裡有哪些節點。

**多語系**：繁中 / 简中 / English，跟隨系統語言，設定頁可切換。

設定和紀錄都在 `%APPDATA%\ScarlettGuard\`。熱鍵用 pynput 格式（`<ctrl>+<alt>+r`），輸入時即時驗證，設壞了會自動退回上一個能用的。

---

<details>
<summary><b>深入：為什麼切換曾經需要重開機</b></summary>

兩個模式的裝置樹形狀不一樣，這是一切的關鍵：

```
日常模式                                錄音模式
USB\VID_xxxx&PID_xxxx → usbccgp        USB\VID_xxxx&PID_xxxx → FocusriteUsb
  └ &MI_00 → usbaudio2  ← 音訊在這      ROOT\FOCUSRITEUSBNEW → FocusriteUsbSwRoot
                                          └ FOCUSRITEUSB\AUDIO&ADAPTER → 音訊在這
```

日常模式的音訊 function 是 USB 裝置的子孫，錄音模式的則掛在獨立的軟體根上。

往日常切的時候，拆掉 USB 那一側，Focusrite 的音訊節點只是變成幽靈，沒有東西擋著，當場就完成。

往錄音切就麻煩了。得先拆掉 `MI_00`，但它持有的音訊端點被 `AudioEndpointBuilder` 抓著。handle 沒放掉就拆不掉，PnP 只好把驅動替換排到下次開機。這就是「切換後要重開機才生效」的真正原因。

解法是換綁前先停掉 `Audiosrv` 和 `AudioEndpointBuilder`，把 handle 放掉，再停用裝置（連帶拆掉所有子節點）、換綁、啟用、還原服務。程式會先看有沒有活著的 `usbaudio2` 子節點來決定要不要走這條路，不必要時不付這個成本。服務還原寫在 `finally` 裡，換綁成功與否都一定會執行。

### 驗的是音訊路徑，不是驅動綁定

這兩件事不一樣。有一種失敗很難察覺：母節點成功綁上 `FocusriteUsb`、問題碼乾乾淨淨，但舊的 `usbaudio2` 子節點還活著，Focusrite 的音訊節點根本沒生出來。畫面顯示「已切換到錄音模式」，實際上一個 ASIO 裝置都沒有。

所以驗收條件是音訊 function 真的上線：錄音模式要看到 `AUDIO&ADAPTER` 節點，而且沒有活著的 `usbaudio2` 子節點；日常模式要看到 `usbaudio2` 子節點在線。「技術細節」第一行的「音訊路徑」就是這個結論，沒起來會直接報錯，不會假裝成功。

### Windows 說要重開機的時候別信它

換綁 API 回傳的 `bRebootRequired` 極度保守。連續八次來回切換，每次都當場生效，但每次都回報需要重開機。程式只認 `CM_PROB_NEED_RESTART`（Code 14），而且真的出現時會先用軟體重置去化解。

### pnputil 做不到換綁

內建的 `usb.inf` 只以 compatible ID `USB\COMPOSITE` 匹配，driver rank `00FF2006`，永遠被原廠的 `00FF0001` 壓過。而 [官方文件](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax) 寫得很明白：

> If the driver is not the highest ranked driver on the system, PnPUtil will not force it onto the device.

所以這裡走的是 `newdev.dll` 的 `UpdateDriverForPlugAndPlayDevicesW` 加 `INSTALLFLAG_FORCE`，也就是 `devcon update` 的底層機制，同時也是裝置管理員「讓我從清單中挑選」走的路徑。好處是完全不動 driver store，兩個驅動都留著。

### 系統匣選單為什麼沒有勾號

Windows 的托盤選單是一次性快照。pystray 只在啟動時、以及每次點擊選單項目之後重建 HMENU，它自己的文件就寫著 "not all supported platforms allow the menu to be generated when shown"。這代表 `checked` / `enabled` 在外部條件改變時不會更新 —— 從托盤觸發一次切換，選單就會凍在停用狀態，之後永遠不會恢復。

要維持它們正確就得從背景執行緒重建 Win32 選單，在托盤這種脆弱的表面上不值得。所以選單項目一律可點，目前模式改用 tooltip 呈現，不適用的動作由 service 層擋下並給你通知。

</details>

---

## 已知限制

只支援 Windows，靠的是 `pnputil`、`newdev.dll` 和 Windows 的 PnP 管理指令。

切換和重置都會中斷正在進行的錄音，效果等同拔插 USB。

這個工具緩解症狀，不修驅動本身。

## 開發

<details>
<summary>從原始碼執行與打包</summary>

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
start.bat                                       # 以系統管理員啟動
powershell -ExecutionPolicy Bypass -File build.ps1   # 打包成 dist/scarlett-guard.zip
```

發佈：更新 `VERSION` → commit → `git tag v2.0.0` → `git push origin v2.0.0`。
GitHub Actions 會核對 `VERSION` 與 tag 是否一致，跑介面檢查、打包，然後自動建 Release。

```
run.py                     啟動器
start.bat                  以系統管理員啟動
build.ps1                  一鍵建置（onedir + zip）
scarlett_guard.spec        PyInstaller 設定
VERSION                    版本號單一來源
tools/check_ui.py          介面一致性檢查
tools/make_icon.py         從系統匣的繪製程式產生 assets/icon.ico
src/scarlett_guard/
  main.py                  組裝服務、系統匣與視窗
  service.py               核心服務層，UI 與系統匣都只跟這一層對話
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

pywebview（WebView2）承載介面，pynput 做全域熱鍵，pystray 做系統匣。

改完 UI 記得跑 `python tools/check_ui.py`。UI 沒有編譯期，文案 key 打錯或找一個不存在的元素，只會讓畫面安靜地半殘。

視覺與動態依循 Apple 的介面設計原則：半透明材質分層、捲動邊緣用漸層而不是分隔線、字距隨字級變化、按壓回饋在 pointer-down 當下發生，並支援 `prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast` 和淺色深色主題。

</details>
