# Scarlett Guard

**English** · [繁體中文](README.zh-TW.md)

## ⚡ Automatically Recover Focusrite Audio
No need to unplug and reconnect your Focusrite Scarlett.

When audio starts crackling, popping, or cuts out, recover it instantly using a hotkey, the system tray, or automatic detection and recovery. Windows only.

Windows 10 / 11 · Python 3.11+
Built and tested against the **Scarlett Solo 4th Gen**; works with any Focusrite USB interface.

---

## The problem this solves

While recording or just listening, the Scarlett sometimes drops into continuous static —
or the sound disappears completely — and **it never recovers on its own**.
It happens more often when the CPU is busy.

For years the community has had exactly two fixes:

1. Unplug the USB cable and plug it back in
2. Open Focusrite Control 2 and toggle the sample rate or buffer size

Both do the same underlying thing: **force the driver to tear the audio stream down and
rebuild it**. Windows' own `pnputil /restart-device` achieves precisely that in software —
faster, without touching a cable, and without switching windows. Scarlett Guard is built
around that one idea.

Measured on a Scarlett Solo 4th Gen, a reset completes in about **3 seconds**.

---

## Quick start

```powershell
cd scarlett-guard
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then run:

```powershell
start.bat
```

That's it. Turn on **Start with Windows** in Settings and it will sit in the tray, ready.

<details>
<summary>Other ways to launch</summary>

```powershell
# Without elevation (the window opens, but the reset button stays disabled)
.venv\Scripts\python.exe run.py

# Start straight into the tray, no window
.venv\Scripts\pythonw.exe run.py --tray
```

</details>

---

## Using it

When the audio breaks, reset it any of these ways:

| Method | How |
|---|---|
| **Global hotkey** (fastest) | `Ctrl` + `Alt` + `R` — works from full-screen DAWs and games |
| **System tray** | Right-click the icon → first item, "Reset device now" |
| **Main window** | The large button on the Status page |

> Double-clicking the tray icon **opens the window; it does not reset**. A reset interrupts
> audio for a few seconds, which is too costly to attach to something that easy to hit by
> accident. Use the hotkey when you want speed.

Audio cuts out for a few seconds during a reset, and your DAW may need to re-select the
device or restart its stream — exactly as if you had unplugged the USB cable.

---

## Automatic detection (advanced, off by default)

Scarlett Guard can watch the interface's **capture input** continuously and reset for you
when something looks wrong.

Three detectors, each independently switchable:

| Detector | What it looks for | Reliability |
|---|---|---|
| **Stream stall** | Audio data stops arriving entirely — the driver's stream clock has stopped | Highest |
| **Signal loss** | The input sits at perfect digital silence (a working analogue input always has a faint noise floor) | High |
| **Static** | Level far above the usual noise floor with a waveform that looks like noise | Most false-positive-prone |

Two safety valves keep it from running away: a **cooldown** (minimum gap between two
automatic resets) and an **hourly limit** (auto-recovery suspends itself when exceeded, so a
genuinely broken device doesn't get reset forever).

> ⚠️ **Watch it before you enable auto-recovery.**
> These detectors are heuristics, not guarantees — the static detector especially can trip on
> hi-hats, distorted guitar, or white-noise material.
>
> Run monitoring alone for a few days first and watch the meters and the log. When the audio
> next breaks, check that the log actually recorded a matching anomaly, and that nothing fires
> during normal use. Then turn on auto-recovery. The Detection page has live meters
> (waveform, level, zero-crossing rate, learned noise floor) so you can tune the thresholds
> against your own material.

---

## Other features

**Log and statistics** — every reset and anomaly is recorded, with counts for the last 24
hours and 7 days plus the **mean interval** between resets. That answers the real question:
how often does this actually happen, and does it really correlate with CPU load? The log is
plain-text JSON Lines, so you can open it in any editor or load it straight into pandas.

**Phantom device cleanup** — repeated replugging and driver reinstalls leave dead device
nodes behind in Windows (shown with status Unknown). The Maintenance page lists them so you
can select and remove them. This is **not guaranteed** to help with dropouts, but clearing
them removes a confounding variable and makes later troubleshooting more trustworthy.

**Device information** — current driver version, provider and date, plus every node the
interface has registered in the system.

**Languages** — English, 繁體中文 and 简体中文. Follows your system language by default and
can be switched in Settings; changes apply immediately (the tray menu updates on next launch).

**Runs in the background** — closing the window hides it to the tray so the hotkey keeps
working; the tray icon shows status by colour (normal / working / problem); launching it
again brings the existing window forward instead of starting a second copy.

---

## About administrator rights

Restarting a PnP device is an operation Windows requires elevation for, so this program
needs administrator rights.

It deliberately does **not** throw a context-free UAC prompt at you on launch. Without
elevation the program still opens — the reset button is simply disabled, and a banner at the
top of the window offers a "Restart as administrator" button. Your call.

If you'd rather not click UAC every time, turn on **Start with Windows** in Settings — it
creates a Task Scheduler logon task that launches elevated without a prompt.

---

## Settings and data

Settings and logs live in `%APPDATA%\ScarlettGuard\` (the Settings page has a button that
opens the folder):

| File | Contents |
|---|---|
| `config.json` | All settings |
| `history.jsonl` | Event log |

**Hotkey format** uses pynput syntax, e.g. `<ctrl>+<alt>+r` or `<ctrl>+<shift>+<f9>`. It is
validated as you type; if you do manage to set an invalid combination, the program falls back
to the last working one rather than leaving you without a hotkey.

**The silence threshold defaults to −140 dB**, chosen from real measurements: an idle Scarlett
Solo sits at roughly −104 dB, so the threshold has to be far below that or normal idle would
register as "signal loss". If you change it, check it against the live values shown on the
Detection page.

---

## Known limitations

- **Windows only** — it relies on `pnputil` and Windows PnP management commands.
- **Audio monitoring is blocked while a DAW holds the device exclusively via ASIO.** That is
  normal Windows audio behaviour; the program tells you plainly instead of failing silently.
  Hotkey and button resets still work.
- **A reset interrupts recording in progress** — the effect is identical to unplugging USB.
- **Automatic detection is heuristic** and can both miss problems and fire on false alarms.
- This tool **treats the symptom; it does not fix the driver itself**.

---

## For developers

<details>
<summary>Project layout and stack</summary>

```
run.py                     Launcher (no install step, just run it)
start.bat                  Launch elevated
src/scarlett_guard/
  main.py                  Wires up service, tray and window
  service.py               Core service layer — UI and tray talk only to this
  device.py                PnP discovery, reset, phantom device removal
  monitor.py               Audio anomaly detection
  hotkey.py                Global hotkey
  tray.py                  Tray icon
  autostart.py             Task Scheduler integration
  elevation.py             UAC elevation
  single_instance.py       Single-instance control
  config.py / history.py   Settings and log persistence
  i18n.py                  Backend strings
  api.py                   JS ↔ Python bridge
  ui/                      Interface (HTML / CSS / JS)
```

The interface runs in pywebview (WebView2); audio detection uses sounddevice + numpy, the
global hotkey uses pynput, and the tray icon uses pystray.

Visuals and motion follow Apple's interface design principles: layered translucent materials,
gradient scroll edges instead of hard dividers, size-specific letter-spacing, press feedback
on pointer-down rather than on release, plus support for `prefers-reduced-motion`,
`prefers-reduced-transparency`, `prefers-contrast` and light/dark themes.

</details>

---

## Licence

MIT
