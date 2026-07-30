<div align="center">
  <p><b>English</b> · <a href="README.zh-TW.md">繁體中文</a></p>
  <img src="assets/icon.png" width="128" alt="Scarlett Guard"><br>
  <h1>Scarlett Guard</h1>
  <p>One-click switching between Everyday and Studio mode on a Focusrite Scarlett, so driver failures stop affecting your day-to-day use.</p>
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

## Two modes, one click

| Mode | What it uses |
|---|---|
| **Everyday** | Windows' built-in `usbaudio2` driver |
| **Studio** | Focusrite's own ASIO driver |

**Both drivers stay installed. Switch whenever you like — no reinstalling drivers, no reboot, effective immediately.**

## Install

[Download `scarlett-guard.zip`](https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip), unzip it, then right-click `Scarlett Guard.exe` and **Run as administrator**. No Python needed.

> Unzip first. Don't run it from inside the archive.

Rebinding a driver requires administrator rights. The app won't throw a UAC prompt at you on launch — unelevated it still opens, only switching and reset are disabled, and a banner at the top lets you decide whether to relaunch.

Turn on **Start with Windows** in Settings and it will sit in the tray. That uses a Task Scheduler logon task, so you won't see UAC again after that.

---

## What this is for

Listening or recording through a Focusrite Scarlett, you occasionally hit an audio failure: continuous crackling, static, or the audio disappearing entirely. It usually can't recover on its own — you have to replug the USB cable, or change the sample rate in Focusrite Control 2, so the driver reloads and things go back to normal.

This kind of driver failure is a common complaint among Windows users. Simply removing the official Focusrite driver does reduce the disruption to everyday use, but it also costs you the low-latency recording that the official ASIO driver provides.


> ⚠️ **Don't uninstall Focusrite Audio Drivers**
>
> This tool needs the official Focusrite driver to stay installed in order to switch back to Studio mode and use the official ASIO.
> **Focusrite Audio Drivers** and **Focusrite Control 2** are two separate components. Even if you stay in Everyday mode indefinitely, neither adds background processes or system load.

---

## Other features

### 🧹 Phantom device cleanup

After repeated mode switches or USB replugs, Windows can leave dead device nodes behind (ghost devices), which makes audio device names sprout numbers like `2-` or `3-`, and can even knock your default playback device off.

Clear them out from the **Settings** page in one click.

### 📝 Recent activity

Every mode switch, device reset and cleanup is shown at the bottom of the main screen, and saved as **JSON Lines** for easy review and debugging.

### 🔍 Technical detail

The main screen has a collapsible technical panel with the current driver mode, device state and system probe results, for tracking problems down.

### 🌐 Languages

Supported:

* 繁體中文
* 简体中文
* English

Follows the Windows system language by default, and can be switched manually in Settings.

---

## Settings and data

All settings and logs are stored in:

```text
%APPDATA%\ScarlettGuard\
```

The global hotkey uses `pynput` syntax (for example `<ctrl>+<alt>+r`) and is validated as you type; if a combination is invalid, it automatically reverts to the last one that worked.


---

## Known limitations

Windows only — it relies on `pnputil`, `newdev.dll` and Windows' PnP management commands.
Switching and resetting both interrupt an in-progress recording, the same as replugging USB.
This tool mitigates the symptom; it does not fix the driver itself.

---

## Licence

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify and distribute this software, but if you distribute a modified version, you must make the corresponding source code available under the GPL-3.0 terms.
See [LICENSE](LICENSE) for the full text.
