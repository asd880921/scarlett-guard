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

## 其他功能

### 🧹 幽靈裝置清理

反覆切換模式或插拔 USB 後，Windows 可能殘留已失效的裝置節點（Ghost Devices），造成音訊裝置名稱出現 `2-`、`3-` 等編號，甚至影響預設播放裝置。

可於 **設定頁** 一鍵清理這些殘留裝置。

### 📝 最近動作

所有模式切換、裝置重置與清理紀錄都會顯示於主畫面下方，並同步保存為 **JSON Lines**，方便查閱與除錯。

### 🔍 技術資訊

主畫面提供可收合的技術資訊，包含目前驅動模式、裝置狀態與系統偵測結果，方便排查問題。

### 🌐 多語系

支援：

* 繁體中文
* 简体中文
* English

預設跟隨 Windows 系統語言，也可於設定頁手動切換。

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