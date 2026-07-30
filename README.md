<div align="center">
  <img src="assets/icon.ico" alt="icon"><br>
  <h1>Scarlett Guard</h1>
  <p>One-click switching between Everyday and Studio mode on a Focusrite Scarlett. Driver failures stop getting in the way of everyday use.</p>
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
  <p><b>English</b> · <a href="README.zh-TW.md">繁體中文</a></p>
</div>

---

## Two modes, one click

|  | Driver | When | Time to switch |
|---|---|---|---|
| **Everyday** | Windows' built-in `usbaudio2` | Music, video, games | ~12 s |
| **Studio** | Focusrite driver + ASIO | Practice, tracking, software monitoring | ~17 s |

Click it on the main screen, or use the tray menu without opening the window. Audio drops during a switch, and whatever is playing or recording will need to pick the device again.

Both drivers stay installed. Switch back any time — no reinstall, no reboot.

## Install

[Download `scarlett-guard.zip`](https://github.com/asd880921/scarlett-guard/releases/latest/download/scarlett-guard.zip), unzip it, then right-click `Scarlett Guard.exe` and **Run as administrator**. No Python needed.

> Unzip first. Don't run it from inside the archive.

Rebinding a driver needs administrator rights. The app won't throw a UAC prompt at you on launch — unelevated it still opens, switching and reset are just disabled, and a banner offers to relaunch.

Turn on **Start with Windows** in Settings and it lives in the tray. That uses a Task Scheduler logon task, so you won't see UAC again after that.

---

## What this is for

Playing or recording through a Scarlett, the audio sometimes turns into continuous static, or vanishes. It never recovers on its own. Only replugging the USB cable, or nudging the sample rate in Focusrite Control 2, brings it back.

The fault is in the Focusrite driver's error recovery. Windows' built-in class driver doesn't have it, but it also has no native ASIO, which pins full-duplex latency around 46 ms.

In practice the failures cluster in everyday use, where dozens of apps open and close audio streams and change sample rates. DAW sessions are comparatively solid, because that's one stream held from start to finish.

Rather than pick one and live with it, switch to fit what you're doing.

## When things go wrong

**A failed switch** leaves the device with no usable driver, and Windows shows no audio devices at all. A **Repair device binding** button appears at the top of the main screen; it rescans PnP and forces the device back onto the built-in driver. That driver is in-box and can't be missing, so this always works.

**Static or a dropout in Studio mode** is what reset is for. It makes the driver tear the audio stream down and rebuild it, the same as replugging USB, but in about three seconds.

| How | Action |
|---|---|
| Global hotkey | `Ctrl` + `Alt` + `R`, works in full-screen DAWs and games |
| Tray | Right-click → Reset device now |
| Main screen | The button under the mode switcher |

Reset is disabled in Everyday mode. The built-in driver doesn't have the flaw, and pressing it would fail anyway — `pnputil` can't tear down a child node the audio engine is holding, so it just returns exit 3010. The hotkey does nothing in Everyday mode, on purpose.

> ⚠️ Don't uninstall "Focusrite Audio Drivers". That drops the package from the driver store and Studio mode stops being available. It's a separate entry from Focusrite Control 2, and in Everyday mode neither one registers a service or a running process, so leaving them installed costs nothing.

## Also in the box

**Phantom device cleanup.** Repeated switching and replugging leaves a pile of `Unknown` nodes behind, and makes endpoint names sprout a `2-` / `3-` prefix, which knocks your default output device off. Settings lists them for removal.

**Recent activity.** Every switch, reset and cleanup is recorded, collapsed at the bottom of the main screen. Plain JSON Lines, open it in any editor.

**Technical detail.** Also collapsed down there. The raw data behind the mode verdict — which service the device is bound to, whether the audio path came up, every node in the system.

**Languages.** Traditional Chinese / Simplified Chinese / English, following the system locale, switchable in Settings.

Settings and logs live in `%APPDATA%\ScarlettGuard\`. Hotkeys use pynput syntax (`<ctrl>+<alt>+r`), validated as you type, with an automatic fall back to the last working combination.

---

<details>
<summary><b>Deeper: why switching used to need a reboot</b></summary>

The two modes have differently shaped device trees, and that's the crux of it:

```
Everyday                                Studio
USB\VID_xxxx&PID_xxxx → usbccgp         USB\VID_xxxx&PID_xxxx → FocusriteUsb
  └ &MI_00 → usbaudio2  ← audio here    ROOT\FOCUSRITEUSBNEW → FocusriteUsbSwRoot
                                          └ FOCUSRITEUSB\AUDIO&ADAPTER → audio here
```

In Everyday mode the audio function is a descendant of the USB device. In Studio mode it hangs off a separate software root.

Switching to Everyday, the USB side comes down and the Focusrite audio node simply becomes a phantom. Nothing is holding it, so it finishes on the spot.

Switching to Studio is the awkward direction. `MI_00` has to go first, but `AudioEndpointBuilder` is holding the audio endpoints it owns. While those handles are open the stack can't be removed, so PnP defers the driver swap to the next boot. That is the real reason a switch used to "need a reboot to take effect".

The fix is to release the handles first: stop `Audiosrv` and `AudioEndpointBuilder`, disable the device (which takes every child down with it), rebind, re-enable, restore the services. The app checks for a live `usbaudio2` child to decide whether this is needed, so it never pays the cost for nothing. Service restoration sits in a `finally` block and runs whether the rebind worked or not.

### What gets verified is the audio path, not the binding

Those aren't the same thing, and there's a failure mode that's easy to miss: the parent binds to `FocusriteUsb` with a perfectly clean problem code, but the old `usbaudio2` child is still alive and the Focusrite audio node was never created. The UI says "Switched to Studio" while not one ASIO device exists.

So the test is whether the audio function actually came up. Studio mode wants an `AUDIO&ADAPTER` node and no live `usbaudio2` child; Everyday mode wants the `usbaudio2` child online. That's the "Audio path" row at the top of Technical detail, and a failure is reported as a failure instead of dressed up as success.

### Don't believe Windows when it asks for a reboot

The rebind API's `bRebootRequired` is wildly conservative. Across eight consecutive round trips it took effect immediately every single time, and reported that a reboot was required every single time. The app only believes `CM_PROB_NEED_RESTART` (Code 14), and when that does show up it tries a software reset first.

### pnputil can't do the rebind

The built-in `usb.inf` only matches on compatible ID `USB\COMPOSITE` at driver rank `00FF2006`, which the Focusrite driver's `00FF0001` always beats. [Microsoft's own documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax) is blunt about it:

> If the driver is not the highest ranked driver on the system, PnPUtil will not force it onto the device.

So this uses `newdev.dll`'s `UpdateDriverForPlugAndPlayDevicesW` with `INSTALLFLAG_FORCE` — the mechanism behind `devcon update`, and the same path Device Manager takes when you pick a driver from the list. It leaves the driver store untouched, which is why both drivers survive.

### Why the tray menu has no checkmarks

The Windows tray menu is a one-shot snapshot. pystray rebuilds the HMENU at startup and after each menu click, and its own docs say "not all supported platforms allow the menu to be generated when shown". So `checked` and `enabled` never update when something changes externally — trigger a switch from the tray and the menu freezes in its disabled state, permanently.

Keeping them accurate would mean rebuilding a Win32 menu from a background thread, which isn't worth it on a surface this fragile. So menu items are always clickable, the current mode lives in the tooltip, and anything that doesn't apply right now is refused by the service layer with a notification.

</details>

---

## Known limitations

Windows only. It leans on `pnputil`, `newdev.dll` and Windows' PnP management commands.

Switching and resetting both interrupt an in-progress recording, exactly like unplugging USB.

This mitigates the symptom. It does not fix the driver.

## Development

<details>
<summary>Running from source, and building</summary>

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
start.bat                                            # launch elevated
powershell -ExecutionPolicy Bypass -File build.ps1   # build dist/scarlett-guard.zip
```

To release: bump `VERSION`, commit, `git tag v2.0.0`, `git push origin v2.0.0`.
GitHub Actions checks `VERSION` against the tag, runs the UI check, builds, and creates the Release.

```
run.py                     Launcher
start.bat                  Launch elevated
build.ps1                  One-shot build (onedir + zip)
scarlett_guard.spec        PyInstaller config
VERSION                    Single source of truth for the version
tools/check_ui.py          UI consistency check
tools/make_icon.py         Generates assets/icon.ico from the tray drawing code
src/scarlett_guard/
  main.py                  Wires up the service, tray and window
  service.py               Core service layer; UI and tray only talk to this
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

pywebview (WebView2) hosts the interface, pynput handles the global hotkey, pystray the tray.

Run `python tools/check_ui.py` after touching the UI. There's no compile step, so a typo in a copy key or a reference to a missing element just leaves the screen quietly half-broken.

Visuals and motion follow Apple's interface design principles: layered translucent materials, gradient scroll edges instead of dividers, size-specific tracking, press feedback on pointer-down, and support for `prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast` alongside light and dark themes.

</details>
