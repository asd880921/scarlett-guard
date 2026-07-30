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

## Driver mode: switch to fit what you're doing

The Focusrite driver and Windows' built-in UAC2 class driver each have something the
other can't offer — and their weaknesses happen to fall in different situations.
The **Driver mode** page switches between them in one click.

| Mode | Bound driver | Good for | Cost |
|---|---|---|---|
| **Everyday** | Built-in `usbaudio2` | Music, video, games | No native ASIO; ~46 ms full-duplex latency |
| **Studio** | Focusrite driver + ASIO | Practice, tracking, software monitoring | Doesn't resync after a dropped packet, so it may need resets |

**Why splitting them helps:** in practice the failures happen almost exclusively during
*everyday* use, where many apps repeatedly open and close audio streams and change sample
rates. DAW sessions are comparatively stable — one stream, one sample rate, held open from
start to finish. Switching per situation gets you both halves.

**The switch is fully reversible and both drivers stay installed** — nothing has to be
reinstalled. The tray menu offers the same switch without opening the window. Audio drops
during a switch, and anything currently playing or recording will need to pick the device
again. Measured on one machine over four consecutive round trips:

| Direction | Time | Audio engine paused |
|---|---|---|
| Studio → Everyday | ~12 s | No |
| Everyday → Studio | ~17 s | Yes |

### Why one direction is slower (and why it used to need a reboot)

The two modes have differently shaped device trees, and that difference explains everything:

```
Everyday                                Studio
USB\VID_xxxx&PID_xxxx → usbccgp         USB\VID_xxxx&PID_xxxx → FocusriteUsb
  └ &MI_00 → usbaudio2  ← audio here    ROOT\FOCUSRITEUSBNEW → FocusriteUsbSwRoot
                                          └ FOCUSRITEUSB\AUDIO&ADAPTER → audio here
```

**In Everyday mode the audio function is a descendant of the USB device; in Studio mode it
hangs off a separate software root.**

- **Studio → Everyday:** tearing down the USB side just turns the Focusrite audio node into
  a phantom. No handles block it, so it completes immediately.
- **Everyday → Studio:** the `MI_00` child has to go first, but the audio endpoints it owns
  are held open by `AudioEndpointBuilder`. While those handles are open the stack can't be
  removed, so PnP defers the driver swap to the next boot. **That is the real cause of
  "the switch needs a reboot to take effect."**

The fix is to release those handles first: stop `Audiosrv` and `AudioEndpointBuilder`,
disable the device (which tears down every child), rebind, re-enable, restore the services.
The app predicts whether this is needed by checking for a live `usbaudio2` child, so it
never pays the cost unnecessarily. Service restoration lives in a `finally` block and runs
whether the rebind succeeded or not.

### What gets verified is the audio path, not the driver binding

These are two different things. There is a failure mode that is very easy to miss: **the
parent rebinds to `FocusriteUsb` with a perfectly clean problem code, but the old
`usbaudio2` child is still alive and the Focusrite audio node was never created** — the UI
says "Switched to Studio" while not a single ASIO device exists.

So the acceptance test is that the audio function actually came up: Studio mode requires an
`AUDIO&ADAPTER` node **and** no live `usbaudio2` child; Everyday mode requires the
`usbaudio2` child to be online. The first row of the Evidence panel, "Audio path", reports
exactly that, and an unready state is reported as an error rather than a success.

> Windows' rebind API returns `bRebootRequired`, and it **cannot be trusted** — across eight
> consecutive round trips it took effect immediately every time while reporting that a reboot
> was required every time. The app only believes `CM_PROB_NEED_RESTART` (Code 14), and when
> that does appear it first tries to clear it with a software reset.

### The verdict is auditable

The mode isn't guessed. The page lists the service the device is actually bound to, the
INF, the problem code, and the live audio endpoints:

```
Parent service          usbccgp        ← built-in USB composite (Everyday)
Audio interface service usbaudio2      ← built-in UAC2 class driver
Bound INF               usb.inf
Live audio endpoints    Microphone (Scarlett Solo 4th Gen), Speakers (Scarlett Solo 4th Gen)
```

In Studio mode the parent service is `FocusriteUsb`, and the audio child interface is not
enumerated at all — the Focusrite driver takes over enumeration of the whole composite device.

### If a switch fails

`pnputil` cannot do this: the built-in `usb.inf` is always outranked by the Focusrite
driver, and [Microsoft's documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax)
states plainly that PnPUtil will not force a driver that isn't the highest ranked one.
So this uses `newdev.dll`'s `UpdateDriverForPlugAndPlayDevicesW` with `INSTALLFLAG_FORCE`.

If a switch fails halfway, the device ends up with no driver — the symptom is that
**Windows shows no audio output or input devices at all**. A **Repair device binding**
button then appears at the top of the Driver mode page; it rescans PnP and forces the
device back onto the built-in driver. That driver is in-box and cannot be missing, so this
recovery path always works.

> ⚠️ **Don't uninstall "Focusrite Audio Drivers".** That removes the driver package from the
> driver store, and Studio mode becomes unavailable. Focusrite Control 2 and the driver
> package are separate entries; in Everyday mode neither registers a service or a running
> process, so leaving them installed costs nothing.

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
  driver_mode.py           forced rebind between Focusrite and the class driver
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
