# Miga on Wayland

Start Miga with `miga` in your Wayland session and open the **Wayland** submenu
with a right click. **Actividad general** means that Miga can stay awake while
you work elsewhere and wake when you return. **Local** means that its sleep
clock follows the activity it receives in its own window. Petting, dragging,
appearance, manual keyboards and the context menu work in either mode.

KDE cursor tracking now drives Miga's eyes and mouse paw in other applications.
Physical keyboard, buttons and scroll are supported through read-only evdev
access after explicit device authorization. The menu reports actual connected
keyboards and pointer sources. The historical compositor matrix below predates
this optional physical input backend.

## Physical input

The Wayland backend opens authorized devices read-only with `evdev >= 2.0`.
Physical key positions feed the same animation as X11: no characters are
decoded, no input history is written, and no events are intercepted or injected.
Simultaneous keys and keyboards, immediate releases, both wheel axes, high
resolution wheels, input buffer overflow and device removal are handled.
KDE supplies global cursor coordinates in logical pixels, including across
rotated and offset monitors; raw relative mouse motion is a fallback elsewhere.
Pausing or disabling reactions closes the device handles. Devices also close
when the login session becomes inactive or locked, checked once per second.
Automatic reopening and device discovery use the same one-second interval.

Fedora normally restricts input devices to root and the input group. The optional
helper below grants a specific normal user **read access only to selected USB
keyboard/mouse models**. This permission is available to other processes under
that user account as well, not exclusively to Miga. Miga itself stays unprivileged.
A udev rule preserves the selection across reboot and reconnect; it does not
add the user to the input group or grant device write access.

For the SONiX `0c45:672e` keyboard and Logitech `046d:c246` mouse tested here,
review the change first, then authorize it through the desktop password prompt:

```sh
python3 scripts/wayland_input_access.py plan --uid "$(id -u)" --device 0c45:672e --device 046d:c246
pkexec /usr/bin/python3 -I "$PWD/scripts/wayland_input_access.py" install --uid "$(id -u)" --device 0c45:672e --device 046d:c246
```

Use the actual USB vendor/product IDs for other devices. Running
`udevadm info --query=property --name=/dev/input/eventN` shows `ID_VENDOR_ID` and `ID_MODEL_ID`.
To remove the rule and current read grants, run the same command with `remove`
in place of `install`, then restart Miga. The helper does not run automatically
during ordinary installation or startup.

`.venv/bin/python tests/linux_input.py` exercises physical input and cursor
delivery through the animation controller without reading the host's keyboard.
After authorization, `.venv/bin/python tests/linux_input_native.py --observe-seconds 30`
checks read-only device access and reports only which event categories reach the
animation controller. It never prints key identities, typed text or event history.
[Linux input events](https://docs.kernel.org/input/event-codes.html) ·
[python-evdev read-only devices](https://python-evdev.readthedocs.io/en/latest/apidoc.html).

## What has been checked

| Capability | GNOME Shell 46, Ubuntu 24.04, nested | KWin 6.6.7, Ubuntu 26.04, virtual output | Weston 13, headless kiosk | Sway, Hyprland and other compositors |
| --- | --- | --- | --- | --- |
| Native Qt surface and transparent rendering | Verified, including click-through to a second client | Verified transparent frames at three sizes | Verified transparent frame, mask and local petting | Implemented, native checks pending |
| General activity | Mutter idle watch, real 15/60/180 second progression and wake verified | Standard v2 notification and 15-second idle edge verified | No usable idle provider in this session. Local mode verified | Standard observer available when advertised with a seat. Native checks pending |
| Automatic keyboard legends | Single configured XKB source and live changes verified. Ambiguous sources fall back | Active US, German and Dvorak groups and live changes verified | Manual selection | Manual unless a supported source is identified |
| Physical keys, pointer travel and scroll in other applications | Unavailable | Unavailable | Unavailable | No passive detailed backend |
| System drag | Native request, release and return to rest verified | Native mechanism implemented. Interaction pending | Compositor-managed move exercised in earlier nested tests | Native mechanism implemented. Interaction pending |
| Always-on-top and exact placement | Raising the other window covered Miga with the hint both on and off | Compositor policy. Stacking pending | Kiosk shell controls placement | Compositor policy |
| Fractional scaling | Logical geometry, masks and frame sizes checked at five Qt scale factors | Physical mixed-DPI checks pending | Physical mixed-DPI checks pending | Pending |

The original KWin checks ran in an isolated GitHub runner. Additional native
checks on Fedora 44 KDE verified placement on a 1080 × 1920 portrait output
at (0, 0) and a 1920 × 1080 landscape output at (1080, 1052), both at 100% scale.
They cover switching outputs, all three sizes, actual keep-above state, saved
position across reopening, idle notifications and the KDE keyboard source.
Physical hotplug, physical dragging and mixed monitor scales still need manual
checks. [Native KWin checks](https://github.com/camilo477/desktop-pet/actions/workflows/wayland.yml).

## Idle and wake

Miga negotiates the advertised version of `ext_idle_notifier_v1` up to v2 and
subscribes to one 15-second idle transition per seat. Before that transition
the compositor only establishes that the seat is within the active interval.
When all observed seats are idle, the shared animation clock can start occasional
actions at 15 seconds, relax at 60 and enter seated sleep at 180. The first
resumed seat interrupts sleep and restores the active frame rate. A real local
interaction also takes effect immediately. [Wayland idle notification protocol](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-idle-notify/ext-idle-notify-v1.xml).

Version 2 reports input idle even while an application inhibits desktop idle.
On GNOME, Miga can instead subscribe to Mutter's core idle and one-shot active
watches and read the elapsed time. It prefers this clock to an available v1
standard notification. With v1 alone a desktop idle inhibitor can keep Miga
awake. Desktop D-Bus providers must match the Wayland compositor serving the
session, which matters on nested desktops. An unavailable provider drops out
and can be rediscovered while Miga runs. Losing Qt's entire display connection
can require relaunching Miga. [Mutter IdleMonitor interface](https://github.com/GNOME/mutter/blob/main/data/dbus-interfaces/org.gnome.Mutter.IdleMonitor.xml).

A general-activity resume carries no key identity, pointer displacement or typing rate. The
animation wakes without striking a key or reaching for the mouse. Pausing or
turning off **Reaccionar a actividad** disconnects the observers. Pausing also
stops the frame timer. Miga keeps the current idle state in memory and uses
local Unix connections. It needs no elevated privileges or desktop extensions.
The InputCapture portal routes input away from applications during capture,
which would interrupt normal work. [Portal InputCapture specification](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.InputCapture.html).

## Keyboard selection

- **KDE.** Miga reads the active index and layout list from KWin, and listens for
  group and list changes. Matching considers the XKB base and group description,
  including known variants such as US Dvorak and Colemak. An unfamiliar
  description falls back. [KWin keyboard layout implementation](https://invent.kde.org/plasma/kwin/-/blob/master/src/keyboard_layout.cpp).
- **GNOME.** The desktop Settings portal can expose the configured input
  sources. Miga accepts exactly one recognized XKB source and labels it
  **única configurada**. With several sources, an input method or an unknown
  variant, the active group is undetermined and the automatic menu identifies
  its US fallback. [GNOME settings portal implementation](https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome/-/blob/main/src/settings.c).
- **All desktops.** Choose **Teclado → Distribución** to override automatic
  selection. Source changes update the legends in place. The physical format,
  ANSI or ISO geometry, appearance and saved manual choice remain available.

## Window, monitors and installation

The ordinary Qt Wayland surface uses the existing alpha rendering and a
pose-dependent input region in logical coordinates. Qt requests a native
interactive move. The lift pose uses reported window movement for sway. If
the compositor withholds motion the pose stays suspended. If it consumes
release, local pointer re-entry, a subsequent event or a bounded check of
Qt's button state can settle the visual grip. After 30 seconds without any
reported drag motion, Miga also releases the visual pose if Qt still reports a
pressed button. A long stationary hold can look released in that case. The
compositor continues to control the actual move. [Qt system moves](https://doc.qt.io/qt-6/qwindow.html#startSystemMove).

On KDE, Miga loads a temporary KWin script that only manages its own process's
Miga toplevel. **Pantalla** selects an output, **Siempre visible** sets the
actual keep-above state, and saved coordinates are relative to that output's
usable area. The script reports real position and drag release, clamps after
resizing and output changes, and unloads on normal shutdown. It does not install
window rules, reserve panel space, alter other windows or require administrator
privileges. It remains connected while animations are paused. If scripting is
unavailable, native dragging remains available. [KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/).

KDE's launcher can create the Wayland socket before starting KWin. Miga accepts
that verified parent-child relationship as well as a direct compositor socket;
it still rejects an unrelated desktop sharing the session bus. This also fixes
automatic keyboard detection on Fedora's normal Plasma session.
[KWin Wayland launcher](https://github.com/KDE/kwin/blob/master/src/helpers/wayland_wrapper/kwin_wrapper.cpp).

Other Wayland compositors retain control of placement and stacking. Miga uses
native dragging, remembers the last output as a hint and preserves saved X11
coordinates separately. [XDG shell surface roles](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/stable/xdg-shell/xdg-shell.xml).

Run `.venv/bin/python tests/screens.py` for isolated placement and launcher
regressions. On a KDE Wayland desktop,
`.venv/bin/python tests/kwin_desktop.py --desktop` shows disposable test windows on each output and verifies native
placement using separate preferences; it does not move an existing Miga.

The normal Linux installer tries optional binary wheels for `pywayland` and
`dbus-next` independently inside the project environment. Missing PyWayland
leaves the D-Bus providers available. Missing both leaves the local pet.
Availability of compatible wheels depends on the Linux architecture and Python
version. An environment exposing only an inherited Wayland file descriptor,
without an independently usable named connection, also gets local behavior.
A native Linux Wayland session defaults to Qt Wayland. An explicitly chosen
Qt platform is respected. XWayland never enables the X11 input hooks.

## Check your desktop

1. Run `miga`, open **Wayland** and check the idle and keyboard sources.
2. In general activity mode, work in another window for three minutes. Miga
   should stay awake. Leave the desktop idle for three minutes, then return to
   the other window. Miga should wake without a fictitious key or mouse action.
3. Switch between known keyboard groups and try manual selection. On GNOME,
   compare a single source with a multi-source configuration if you already
   use one. Check the source description in **Teclado → Distribución**.
4. Drag from the head after petting, release, then click a transparent corner
   above another window. Try the three sizes, a compact board and a different
   coat. On a multi-monitor desktop check movement, stacking and fractional DPI.
5. Disable reactions, pause and resume. Reopen the menu to see the current
   capabilities. Use `miga off` for an orderly shutdown.

The nested GNOME test used controlled input in a separate Qt client. It verified
seated sleep, wake by keyboard and pointer, a live layout change while asleep,
delivery at eight anatomical and peripheral regions,
and one click delivered to the window behind a transparent corner. Qt scale
factors 1, 1.25, 1.5, 1.75 and 2 exercised backing pixels and logical masks at
150, 200 and 300 pixels. A separate temporary D-Bus test provider exercised
service loss and recovery. Synthetic provider tests covered v1/v2 selection
and twenty minutes of continuous activity. Native v1 idle inhibition,
desktop suspension, mixed physical outputs and stacking on a full Plasma
desktop require hands-on checks.

At 300 logical pixels with the original coat, seven-second samples in nested
GNOME measured 6.27% of one CPU core at 29.4 FPS during external activity,
1.92% at 10 FPS asleep and 0.01% at zero FPS paused. Resident memory was
110.6–111.4 MiB. In isolated X11, synthetic typing measured 7.28% at
29.3 FPS, sleep 2.21% at 10 FPS and pause 0.11% at zero FPS, around 82 MiB
resident. The active workloads differ because Wayland receives general activity.

Current X11 and macOS frame measurements are described in the
[performance notes](README.md#performance-and-verification).
