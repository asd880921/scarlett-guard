<div align="center">
  <p><a href="README.md">English</a> · <b>繁體中文</b></p>
  <img src="assets/icon.png" width="128" alt="Scarlett Guard"><br>
  <h1>Scarlett Guard</h1>
  <p>一鍵切換 Focusrite Scarlett 日常 / 錄音模式，讓日常使用不再受驅動異常影響。</p>
  <p>
    <a href="https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip">
      <img src="https://shieldcn.dev/github/downloads-asset/asd880921/scarlett-guard/scarlett-guard.zip.svg?style=for-the-badge&label=downloads&labelColor=24292f&color=2ea44f" alt="Downloads" />
    </a>
  </p>
  <p>
    <img src="https://img.shields.io/github/v/release/asd880921/scarlett-guard?style=for-the-badge&label=latest%20release" alt="Latest release" />
    <img src="https://img.shields.io/badge/license-GPL--3.0-22C55E?style=for-the-badge" alt="License GPL-3.0" />
  </p>
</div>

---

## 兩個模式，一鍵切換

| 模式 | 內容 |
|---|---|
| **日常模式** | Windows 內建 `usbaudio2` 驅動 |
| **錄音模式** | Focusrite 原廠 ASIO 驅動 |

**兩個驅動都留在系統裡，支援隨時切換，不用重裝驅動也不用重新開機，立即生效。**

裝置卡住時，「立即重置裝置」的效果等同拔插 USB，也可以用全域熱鍵觸發。展開「技術細節」可以看到驅動綁定、在線的音訊端點與問題碼。幽靈裝置清理、動作紀錄與語言設定都在設定頁。

![狀態頁](assets/review_status_tw.png)

---

## 音效

系統音量、麥克風、以及每個應用程式的音量都能直接調整，不用再開 Windows 設定。輸出與輸入裝置可以在這裡切換，每個應用程式都會顯示自己的圖示，不必靠檔名猜。切換驅動模式後音量常被打亂，「重設應用程式音量」一鍵全部拉回 100%。

![音效頁](assets/review_audio_tw.png)

---

## 安裝

[下載 `scarlett-guard.zip`](https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip)，解壓縮，對 `Scarlett Guard.exe` 按右鍵**以系統管理員身分執行**。不需要裝 Python。

> 請先解壓縮再執行，不要直接在壓縮檔裡點開。

換綁驅動需要系統管理員權限。程式不會一啟動就丟 UAC 給你，未提權時照樣開得起來，只是切換和重置停用，視窗上方會有按鈕讓你決定要不要重開。

把設定頁的「開機自動啟動」打開，它就會常駐在系統匣。那走的是工作排程器的登入工作，之後不會再跳 UAC。

---

## 這是在解決什麼

使用 Focusrite Scarlett 聽音樂或錄音時，偶爾會遇到音訊異常，例如持續的爆音、電流音，或音訊完全消失。通常無法自行恢復，需要重新插拔 USB，或在 Focusrite Control 2 中切換取樣率，讓驅動重新載入後才能恢復正常。

這類驅動異常是許多 Windows 使用者經常遇到的問題。然而，若直接移除 Focusrite 官方驅動，雖然能降低日常使用受到影響，卻也會失去官方 ASIO 驅動所提供的低延遲錄音能力。


> ⚠️ **請勿卸載 Focusrite Audio Drivers**
>
> 本工具需要保留 Focusrite 官方驅動，才能切換回錄音模式並使用官方 ASIO。
> **Focusrite Audio Drivers** 與 **Focusrite Control 2** 為兩個獨立元件，即使長時間使用日常模式，也不會因此增加額外的背景程式或系統負擔。

---

## 設定與資料

所有設定與紀錄皆儲存在：

```text
%APPDATA%\ScarlettGuard\
```

全域熱鍵採用 `pynput` 格式（例如 `<ctrl>+<alt>+r`），輸入時會即時驗證；若設定無效，會自動恢復至上一組可正常使用的設定。


---

## 已知限制

只支援 Windows，靠的是 `pnputil`、`newdev.dll` 和 Windows 的 PnP 管理指令。
切換和重置都會中斷正在進行的錄音，效果等同拔插 USB。
這個工具緩解症狀，不修驅動本身。

---

## 授權

本專案採用 GNU General Public License v3.0 (GPL-3.0) 授權。
你可以自由使用、修改與散布本軟體，但若散布修改後的版本，必須依照 GPL-3.0 授權條款公開相應原始碼。
詳細條款請參閱 [LICENSE](LICENSE)。
