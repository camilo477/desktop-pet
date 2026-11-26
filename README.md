# Miga · Desktop Pet

An original charcoal cat sitting on an invisible floor with a small keyboard
and mouse. Miga uses Python, PySide6 and SVG to accompany your activity in a
transparent desktop window. Linux, Windows and macOS share the same cat, keyboard,
appearances, gestures and animation code.

## Platform status

| Platform | Available integration | Automated and native checks | Hands-on validation remaining |
| --- | --- | --- | --- |
| Linux X11 | Global physical input and XKB | Native X11 input, Qt rendering and launcher | Additional desktops and monitor arrangements |
| Linux Wayland | Seat idle and wake when available, KDE layout or single configured GNOME source, local interaction | Native nested GNOME 46, virtual KWin 6.6 and headless Weston 13 | Fedora KDE desktop, mixed physical scales and hotplug |
| Windows x64 | Raw Input, installer and portable folder | Windows Server 2025 x64, native input and packaging | Windows 11/10 client desktops and hardware |
| macOS arm64 and x86_64 | Cocoa panel, optional Quartz input, Finder app and CLI | macOS 15 on both architectures, synthetic input through the session tap, transparent hit targets, app builds and local IPC | Granting and revoking permission, physical input devices, Secure Input, Spaces and mixed-DPI displays |

## Features

- Minimal charcoal silhouettes, warm golden eyes, grounded haunches and
  subtle flat shading that follows the body and its continuous forelegs.
- A shared body deformation keeps the chest, neck, shoulders and head connected.
- Five physical keyboard sizes with ANSI or ISO keys and eight sets of legends.
  Each keycap supplies the target for the paw and the highlight for a press.
- Peripherals face the cat: the space bar is nearest its paws and its right-hand
  mouse appears on the viewer's left.
- Actual key presses, holds and releases on X11, Windows and permitted macOS sessions, including simultaneous keys.
- On native Wayland, a compositor idle notification can keep Miga awake while you work in another window. The **Wayland** submenu shows the current capabilities.
- Both paws participate in typing; one can keep using the mouse while the other types.
- Typing speed follows actual press cadence and reach distance, with continuous
  redirection instead of queued strokes.
- Actual paw contacts produce small coordinated chest, head and key reactions.
- The mouse travels across a bounded area with its paw, then stays where it was left.
- Scrolling reaches and holds the mouse without moving it; the other paw can type.
- Coordinated eyes, head, whiskers, torso, ears and flexible tail, at up to 30 FPS.
- Eight procedural expressions: calm, focused, excited, impatient, surprised,
  curious, contented during head pats, and drowsy as Miga settles down.
- Eye aperture, feline pupil width, ear angle and tail-tip motion change together.
  Physical key cadence is smoothed over roughly one second. Gentle typing keeps
  Miga relaxed. Sustained typing above about four presses per second can bring
  concentration, faster bursts can bring excitement, and sustained activity
  above roughly nine can occasionally bring a few seconds of impatience.
- A sudden resumption can briefly widen Miga's eyes. Pointer travel and scrolling
  have separate intensity measurements. Holding a key keeps the paw planted.
- Eyes and head respond independently to shared attention; facial features use
  a small projected surface to follow turns and downward glances.
- Miga occasionally stretches its forelegs, kneads the floor behind the keyboard,
  or uses a forepaw to rub beside an ear. It can shake its head, flick one ear,
  shift its weight, tuck its tail or look up and to either side. Paw licking,
  face washing and yawning are also part of its idle repertoire.
- Miga falls asleep seated at the keyboard. Its eyes close, its head dips to one
  side and three Zs drift up beside its head as its breathing slows.
- Keyboard, pointer and scroll input redirect the paws from their current
  positions during any idle action or while waking. Pressed keys light up on
  the next frame. Contact follows when a paw actually reaches the peripheral.
- Head pats, sustained petting, independent ear flicks and a flexible tail
  that draws back at a touch. The touch targets follow the painted pose.
- Nearby pointer motion can draw Miga's gaze toward its face. Lifting Miga
  tucks its paws and lets its body lean gently into changes of direction.
- Three sizes, an optional always-on-top mode, activity control and animation pause.
- Position and preferences saved with QSettings.

Input processing is entirely local. It keeps only currently held physical key
identifiers, brief visual markers, the latest paw targets, activity timestamps
and short-lived aggregate rates in memory. It does not reconstruct text,
keep a typing history, write input logs,
send telemetry or connect to the internet. **Reaccionar a actividad** disables
input listeners and immediately clears input state. Pausing also stops listeners
and clears held keys.

## Technologies

Python 3, PySide6 (Qt Widgets, Qt SVG, local IPC and QSettings) and original
SVG artwork. Native Wayland can use two optional Linux bindings, PyWayland for
seat idle notifications and dbus-next for desktop idle and keyboard settings.
X11 uses pynput. Windows uses Raw Input through ctypes.
macOS uses the PyObjC Quartz and Cocoa bindings and native Text Input Source Services.
The application uses PySide6 Essentials.

## Linux requirements

- Linux with Python 3.10 or newer, pip and support for virtual environments.
- A graphical desktop with compositing enabled.
- Qt's platform libraries for your desktop, usually supplied by the distribution.
  Some distributions also need Python headers and a C compiler to install
  pynput's transitive dependencies when binary wheels are unavailable.

## Linux installation

```sh
git clone https://github.com/camilo477/desktop-pet.git
cd desktop-pet
./install.sh
```

The installer creates `.venv` in this directory and a launcher in
`~/.local/bin/miga`. It needs no administrator privileges and can be run
again. On upgrade, it removes the old `mascota` link if it points to this
checkout. Existing preferences and running instances carry over. Keep the
project directory in place. Installation may download packages;
the application then runs entirely offline.

If `~/.local/bin` is missing from your PATH, add this line once to your shell
configuration and open a new terminal:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The installer does not change your shell configuration or set up automatic startup.

## Windows installation and status

Miga targets **Windows 11 x64** and **Windows 10 x64, version 1809 or newer**
with a compatible Qt wheel. The Windows installation pins the Qt family below
6.13. Install 64-bit Python (3.12 recommended), extract the project to a
permanent folder, and run this from that folder in PowerShell:

```powershell
py -3 .\windows\setup.py install
```

Open **Miga Desktop Pet** in Start, or run `miga` and `miga off` in a new
PowerShell or CMD window. The installer creates a private virtual environment,
a Start Menu shortcut and a current-user PATH entry. To uninstall, run
`py -3 .\windows\setup.py uninstall` from the same folder. Preferences survive.
A portable folder can also be built on Windows with `windows/build.ps1`.
[Windows walkthrough and desktop checks (Spanish)](WINDOWS.md) ·
[Qt platform requirements](https://doc.qt.io/qt-6/windows.html).

Automated tests on Windows Server 2025 x64 cover native input delivery, focus,
transparent hit targets at five scale factors, concurrent starts, orderly
shutdown and the portable build. Physical Windows 11/10 desktops, mixed-DPI
monitor transitions, secure desktops and hardware sleep/resume still need
hands-on validation. [Windows test runs](https://github.com/camilo477/desktop-pet/actions/workflows/windows.yml).

## macOS installation and status

Miga targets macOS **15 or later**, with separate native Apple Silicon and Intel
apps. With native Python 3.12 and Apple command line tools, run
`./macos/install.sh` in the project folder. Open **Miga** in your personal
Applications folder, or put `~/.local/bin` on PATH and run `miga`. Use
`miga off` to quit and `./macos/uninstall.sh` to remove the installation.

Global input is optional. Miga checks Input Monitoring access and offers a
permission request in its context menu. With access, a listen-only Quartz
session tap feeds physical positions, pointer motion and both wheel axes to
the shared animation controller. Without access, local petting, dragging,
customization and idle behavior remain available. The automatic keyboard
uses known input source IDs. An unknown source shows the US fallback, and all
eight supported layouts are available manually.

`./macos/build.sh` produces a standalone, ad-hoc-signed development app.
Developer ID signing and Apple notarization are pending.
[Mac installation, permissions and manual checks](MACOS.md) ·
[Native Mac test runs](https://github.com/camilo477/desktop-pet/actions/workflows/macos.yml).

## Usage

```sh
miga       # Start in the background; the terminal can be closed.
miga off   # Save preferences and close only this application.
```

The command works from any directory. Repeated starts reuse the existing
instance. A user-only Unix socket or Windows named pipe handles ping and
shutdown. An OS-held lock protects startup and releases on process exit.
On Windows both the lock and pipe discovery are scoped to the interactive session.

Click Miga's head for a short pat. Hold the left button still on its head for
about a third of a second to keep petting it. Miga leans into your hand, closes
its eyes and gradually opens them again over about 0.7 seconds after release.
Click either ear for a quick flick, or touch the visible tail to make it curl
away. Moving the pointer close to its face briefly draws its attention.

To pick Miga up, hold the left button on its silhouette or peripherals and move
past the desktop's normal drag distance. This also works halfway through a pat.
The keyboard and mouse move with the window. Miga tucks its forepaws and
leans against acceleration, then rocks back slightly as the window brakes.
Its head and tail follow with a short delay. Moving quickly in a straight line
keeps its gaze steady. Repeated brisk reversals or tight circles
can make its gaze wander and its ears tip sideways while it is still lifted.
On release, Miga braces its paws and regains its seated balance over about
one to four seconds, depending on the shaking.

Real keys light up during the drag. A held key, new typing, pointer motion or
scroll takes priority on the first frame after release. Petting or picking
Miga up again also interrupts recovery. On Wayland, shake detection needs
actual window displacement from the compositor. When positions are hidden,
the pet keeps its suspended pose. Empty areas pass clicks where supported.

The right-click menu offers **Tamaño** (150, 200 or 300
logical pixels), **Teclado**, **Apariencia**, **Siempre visible**, **Reaccionar a actividad**, **Pausar animaciones** / **Reanudar
animaciones**, and **Salir**. Medium (200 × 200) is the default size.

Pausing stops the animation timer and input listeners while keeping dragging
and menu controls available. Disabling activity reactions stops global input
listeners; direct touch, lifting and normal idle behaviors continue.

The mouse paw returns to the keyboard after approximately 500 ms without real
pointer movement or scrolling, followed by a smooth transfer. A stationary pointer or a
click alone does not keep the paw on the mouse. Interest in a nearby face-level
pointer fades when it stops. When typing without pointer motion, attention moves to the keyboard.
Scrolling without pointer movement directs attention to the small mouse.
Mouse travel follows the cat's peripheral plane, with both horizontal and
vertical directions reversed relative to the viewer.

Held keys stay visibly pressed without repeating the paw's stroke. Fast taps
leave a brief visual mark; rapid typing updates current paw targets rather than
queuing a delayed sequence. All recognized pressed keys are shown even when
there are more held keys than available paws.

After 15 seconds without observed activity, occasional idle actions can begin.
Each lasts roughly one to five seconds, with 12–27 seconds of rest between
completed actions. Miga avoids repeating its last choice. After one minute it
gradually relaxes and favors quieter movements. After three minutes it falls
asleep seated. Its own movements leave the inactivity timer running. A held
key keeps it awake. Input or a direct click wakes it smoothly.
Sleep runs at about 10 FPS; pausing stops rendering entirely. These intervals
are simple constants in `animations.py`.

## Choosing a coat and facial colors

Right-click Miga and open **Apariencia**. The default **Miga original** keeps
the original charcoal fur, gold eyes and dark nose.

- **Pelaje** offers original charcoal, solid black, orange tabby, blue-gray,
  gray tabby, warm white, black-and-white bicolor, tuxedo, Siamese colorpoint,
  calico and tortoiseshell.
- **Ojos** offers automatic, gold, amber, green, blue, hazel, copper, gray
  and heterochromia (one blue eye and one green eye).
- **Nariz** offers automatic, black, dark gray, pink and warm brown. Automatic
  eye and nose colors follow the coat. Manual choices carry over across coats.
- **Restaurar apariencia original** restores the charcoal coat and both
  automatic colors. The keyboard, window and activity settings keep their values.

Changes appear on the current pose, including during sleep or pause, and are
saved for the next launch. Face markings follow the projected face, body patches
follow the chest, and leg and tail markings bend with their surfaces. All coats
share the same anatomy, hit targets, expressions and behavior. All artwork is local.

## Choosing a keyboard

Right-click Miga and open **Teclado**. These choices apply immediately and are
saved for the next launch. Your computer keeps its own keyboard settings.

- **Distribución** sets the legends. Choose **Automática**, US or UK QWERTY,
  Latin American or Spain Spanish, German QWERTZ, French AZERTY (traditional),
  US Dvorak or standard Colemak. For example, pressing the physical US Q
  position lights A on French AZERTY and the apostrophe on Dvorak.
- **Formato** selects the physical arrangement. The compact layouts represent
  common designs. The table counts physical caps, including Fn where shown.
- **Estándar físico** selects ANSI or ISO. ISO has a two-row, stepped Enter,
  a shorter left Shift and one extra key. ANSI has a horizontal Enter and
  places the backslash position above it. All five formats support both.

| Format | ANSI | ISO | Dedicated blocks |
|---|---:|---:|---|
| 100 % | 104 | 105 | Function row, navigation, arrows and number pad |
| TKL | 87 | 88 | Function row, navigation and arrows |
| 75 % | 83 | 84 | Close-spaced function row, arrows and a navigation column |
| 65 % | 68 | 69 | Arrows and a navigation column |
| 60 % | 61 | 62 | Number row, main typing block and modifiers |

New and upgraded installations default to **Automática**, **100 %** and **ISO**.
Smaller boards keep the same key pitch. The mouse moves slightly closer and the
paws settle around the selected board. Changing geometry preserves physical
holds and releases targets for keys that disappear. Pressing an absent key still
counts as activity. Firmware can send a function or navigation code without
revealing the underlying switch or Fn layer, so Miga only reaches identifiable,
represented positions. Small legends appear as the rendering resolution permits.

## Windows desktop integration

- The window registers for passive Raw Input while reactions are enabled.
  Make codes and E0/E1 prefixes identify physical positions independently of
  the key label. Repeats share a held switch. A short reconciliation checks
  only held switches, and device removal, session changes and power events
  clear transient input. Windows can restrict input on protected desktops.
- Pointer movement uses Qt desktop coordinates. Mouse buttons and both wheel
  axes feed the same animation controller as on X11. Pausing unregisters input.
- Automatic layout selection checks the foreground thread about once per
  second. It uses Windows keyboard identifiers, including the built-in
  Dvorak and Colemak variants. Unidentified variants show the US fallback.
  All eight layouts can be selected manually. Window titles, application
  names and typed characters are never queried.
- Qt supplies a translucent, frameless tool window and per-monitor scaling.
  Windows uses the painted alpha surface for hit testing. Direct clicks keep
  the working window active. The context menu can take temporary popup focus.
  Topmost applies to ordinary desktop windows within the current session.

[Windows layout identifiers](https://learn.microsoft.com/en-us/globalization/windows-keyboard-layouts) ·
[Win32 layered window hit testing](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows).

## Linux compatibility

- **X11:** global input uses pynput's pinned X backend, with Qt cursor tracking.
  A compositor and X11 RECORD support are needed. XKB key names identify the
  physical switches independently of the character produced, modifiers or Num
  Lock. Automatic mode uses the active group and the XKB rules, layout and
  variant published by the server. Key events carry group changes. Miga also
  checks the group and configuration about every two seconds while listeners
  run, including when the keyboard is idle. Physical names refresh when the
  rules change or listeners restart. A custom keymap that leaves the rules
  metadata unchanged may need manual selection or a restart of activity reactions.
  Unknown or unavailable layouts show an explicit US fallback in the menu.
  Positions with unknown physical names contribute activity only.
- **Native Wayland.** Miga uses seat idle notifications or Mutter's idle monitor to
  stay awake during desktop activity and wake on its return. With neither source
  available, its sleep clock follows local interactions. KDE can supply the
  active keyboard group. On GNOME a single configured XKB source can supply
  the legends. The keyboard menu always offers manual selection.
- Global physical keys, pointer motion and scrolling in other applications are
  unavailable in Wayland sessions, including when Qt runs under XWayland.
  Native Wayland uses the compositor for dragging and final window placement.
  See the [Wayland compatibility table and desktop checks](WAYLAND.md).

## Known limitations

Always-on-top, task switching, exact placement and monitor restoration depend on
the compositor. Native Wayland can hide position changes and the final button
release during a system move. Miga limits its directional sway to reported
motion. X11 global reactions require a working RECORD extension.

Each represented key lights on the first available frame. The paws follow the
current targets. Fast typing can redirect a paw before it lands, and with one
paw reserved for the mouse a distant key may exceed the other paw's reach.
A contact reaction occurs only when the paw reaches the key.

## Performance and verification

At 300 logical pixels, repeated synthetic typing in an isolated X11 session
averaged 6.4% of one CPU core with the original coat, 7.7% with the orange tabby
and 8.4% with the calico. The widget painted about 29.4 frames per second.
Seated sleep averaged 1.9% and 10 FPS. Pausing stopped periodic frames and
released the input listeners. Resident memory in these runs was approximately
102 MiB. The same workload on the preceding revision averaged 7.5%, 9.1% and
10.3% respectively during typing. Hardware, Qt, desktop services and scaling
affect these measurements.

On macOS the visible, awake panel uses an AppKit display link at a preferred
30 FPS. In paired macOS 15 runner samples, visible widget paints during typing
increased from 10.6 to 29.9 per second on Apple Silicon and from 24.9 to 30.0
on Intel. The higher frame rate used more CPU in both samples. Qt schedules
sleeping or occluded windows. The macOS workflow can
compare two revisions on the same runner by setting its optional
`comparison` input. It reports timer delivery, generated frames and widget
paints separately. Physical display latency requires a desktop measurement.
[Native macOS checks](https://github.com/camilo477/desktop-pet/actions/workflows/macos.yml)
