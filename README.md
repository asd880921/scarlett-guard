# Scarlett Guard

**English** · [繁體中文](README.zh-TW.md)

## ⇄ Switch your Scarlett between stability and low latency, in one click

The Focusrite driver gives you native ASIO but never resynchronises after a dropped audio
packet. Windows' built-in UAC2 class driver is rock solid but offers no ASIO. **Scarlett
Guard lets you switch between them to fit what you're doing — about 15 seconds, fully
reversible, no reboot.**

Windows 10 / 11 · Python 3.11+
Developed and measured against a **Scarlett Solo 4th Gen**; any Focusrite USB interface works.

---

## The problem this solves

Playing or recording through a Scarlett, the audio occasionally turns into continuous static
or disappears outright — and **it never recovers on its own**.

The measured conclusion: the fault is in the Focusrite driver's error-recovery logic, and
Windows' built-in class driver doesn't have it. But the built-in driver has no native ASIO,
so the audio engine pins full-duplex latency at roughly 46 ms.

In practice the failures happen almost exclusively during **everyday use**, where many apps
repeatedly open and close audio streams and change sample rates. DAW sessions are
comparatively stable: one stream, one sample rate, held open from start to finish.

So the sensible answer isn't to pick one — it's to switch per situation.

---

## Quick start

```powershell
cd scarlett-guard
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
start.bat
```

Then turn on **Start with Windows** in Settings and it will sit in the tray.

<details>
<summary>Other ways to launch</summary>

```powershell
# Unelevated (the window opens, but switching and reset are disabled)
.venv\Scripts\python.exe run.py

# Start straight into the tray with no window
.venv\Scripts\pythonw.exe run.py --tray
```

</details>

---

## Driver mode

| Mode | Bound driver | Good for |
|---|---|---|
| **Everyday** | Built-in `usbaudio2` | Music, video, games |
| **Studio** | Focusrite driver + ASIO | Practice, tracking, software monitoring |

Switch from the segmented control on the main screen, or straight from the tray menu without
opening the window. Audio drops during a switch and anything currently playing or recording
will need to pick the device again. **Both drivers stay installed** — the switch is fully
reversible and nothing has to be reinstalled.

Measured over four consecutive round trips on one machine:

| Direction | Time | Audio engine paused |
|---|---|---|
| Studio → Everyday | ~12 s | No |
| Everyday → Studio | ~17 s | Yes |

### Why one direction is slower (and why it used to need a reboot)

The two modes have differently shaped device trees:

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
The app predicts whether this is needed by checking for a live `usbaudio2` child, so it never
pays the cost unnecessarily. Service restoration lives in a `finally` block and runs whether
the rebind succeeded or not.

### What gets verified is the audio path, not the driver binding

These are two different things, and there is a failure mode that is very easy to miss: **the
parent rebinds to `FocusriteUsb` with a perfectly clean problem code, but the old `usbaudio2`
child is still alive and the Focusrite audio node was never created** — the UI says
"Switched to Studio" while not a single ASIO device exists.

So the acceptance test is that the audio function actually came up: Studio mode requires an
`AUDIO&ADAPTER` node **and** no live `usbaudio2` child; Everyday mode requires the
`usbaudio2` child to be online. The first row under "Technical detail" reports exactly that,
and an unready state is surfaced as an error rather than a success.

> Windows' rebind API returns `bRebootRequired`, and it **cannot be trusted** — across eight
> consecutive round trips it took effect immediately every time while reporting that a reboot
> was required every time. The app only believes `CM_PROB_NEED_RESTART` (Code 14), and when
> that does appear it first tries to clear it with a software reset.

### If a switch fails

If a switch fails halfway, the device ends up with no working driver — the symptom is that
**Windows shows no audio output or input devices at all**. A **Repair device binding** button
then appears at the top of the main screen; it rescans PnP and forces the device back onto
the built-in driver. That driver is in-box and cannot be missing, so this recovery path
always works.

> ⚠️ **Don't uninstall "Focusrite Audio Drivers".** That removes the driver package from the
> driver store and Studio mode becomes unavailable. Focusrite Control 2 and the driver package
> are separate entries; in Everyday mode neither registers a service or a running process, so
> leaving them installed costs nothing.

---

## Resetting the device

If static or a dropout does hit while in Studio mode, a reset forces the driver to tear the
audio stream down and rebuild it — the same effect as unplugging the USB cable, but it takes
about 3 seconds and you never touch the cable.

| How | Action |
|---|---|
| **Global hotkey** (fastest) | `Ctrl` + `Alt` + `R`, works inside a full-screen DAW or game |
| **Tray** | Right-click the icon → Reset device now |
| **Main screen** | The button under the mode switcher |

> Double-clicking the tray icon **opens the window, it does not reset** — a reset interrupts
> audio, which is too costly to attach to something that easy to hit by accident.

---

## Other features

**Phantom device cleanup** — repeated mode switches and replugs accumulate leftover nodes with
an `Unknown` status, and they make endpoint names grow a `2-` / `3-` prefix, which knocks the
default output device off. Settings lists them for selective removal.

**Event log** — every switch, reset and cleanup is recorded, tucked under "Recent activity" on
the main screen. Plain JSON Lines, readable in any text editor.

**Technical detail** — collapsed at the bottom of the main screen: the evidence behind the
mode verdict, the driver version, and every node the device registers in the system. The mode
is not guessed, and this is the raw data it is derived from.

**Languages** — Traditional Chinese / Simplified Chinese / English, following the system
locale by default, switchable in Settings and applied instantly (the tray menu needs a
restart).

**Resident** — closing the window hides it to the tray so the hotkey keeps working; the icon
colour reflects state; launching again brings the existing window forward instead of opening a
second copy.

---

## About administrator rights

Rebinding a driver and restarting a PnP device both require elevation.

The app does **not** throw an unexplained UAC prompt at startup. Unelevated it still opens —
switching and reset are simply disabled, and a banner at the top offers to relaunch as
administrator. Your call.

To avoid the UAC prompt entirely, turn on **Start with Windows** in Settings: it creates a
Task Scheduler logon task that launches elevated without prompting.

---

## Settings and data

Both live in `%APPDATA%\ScarlettGuard\` (Settings has a button to open it):

| File | Contents |
|---|---|
| `config.json` | All settings |
| `history.jsonl` | Event log |

**Hotkey format** uses pynput syntax, e.g. `<ctrl>+<alt>+r`, `<ctrl>+<shift>+<f9>`. Input is
validated as you type; an invalid combination falls back to the last working one.

`config.json` holds two settings that deliberately don't appear in the UI:
`post_reset_settle_seconds` and `mode_settle_seconds` (how long to wait for the device to
settle). The defaults are measured and adequate; edit the file if you need to change them.

---

## Known limitations

- **Windows only** — it depends on `pnputil`, `newdev.dll` and Windows' PnP management commands.
- **Switching and resetting interrupt an in-progress recording**, the same as unplugging USB.
- **`pnputil` cannot do the rebind** — the built-in `usb.inf` is always outranked by the
  Focusrite driver, and [Microsoft's documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax)
  states plainly that PnPUtil will not force a driver that isn't the highest ranked one. This
  app uses `newdev.dll`'s `UpdateDriverForPlugAndPlayDevicesW` with `INSTALLFLAG_FORCE` — the
  mechanism behind `devcon update`.
- This tool **mitigates the symptom; it does not fix the driver**.

---

## For developers

<details>
<summary>Project layout and stack</summary>

```
run.py                     Launcher (no install needed)
start.bat                  Launch elevated
tools/check_ui.py          UI consistency check (3-language keys, copy refs, DOM ids)
src/scarlett_guard/
  main.py                  Wires up the service, tray and window
  service.py               Core service layer — UI and tray only talk to this
  driver_mode.py           Forced rebind between Focusrite and the class driver
  device.py                PnP discovery, reset, phantom device removal
  hotkey.py                Global hotkey
  tray.py                  Tray icon
  autostart.py             Task Scheduler integration
  elevation.py             UAC elevation
  single_instance.py       Single-instance control
  config.py / history.py   Settings and log persistence
  i18n.py                  Backend copy
  api.py                   JS ↔ Python bridge
  ui/                      Interface (HTML / CSS / JS)
```

The interface is hosted in pywebview (WebView2), the global hotkey uses pynput, the tray uses
pystray.

After changing the UI, run `python tools/check_ui.py` — the UI has no compile step, so a typo
in a copy key or a missing element only makes the screen quietly half-broken.

Visuals and motion follow Apple's interface design principles: layered translucent materials,
gradient scroll edges instead of hard dividers, size-specific tracking, press feedback on
pointer-down, and support for `prefers-reduced-motion` / `prefers-reduced-transparency` /
`prefers-contrast` plus light and dark themes.

</details>

---

## Licence

MIT
