# Miga · Desktop Pet

An original charcoal cat sitting on an invisible floor with a small keyboard
and mouse. Built for Linux with Python, PySide6 and SVG, Miga accompanies your
activity in a transparent window without taking keyboard focus.

## Features

- Minimal flat silhouettes, grounded haunches and continuous tapered forelegs.
- A shared body deformation keeps the chest, neck, shoulders and head connected.
- A full-size 105-key QWERTY keyboard, including function keys, navigation and
  a separate number pad. Key shapes also define the paws' contact targets.
- Peripherals face the cat: the space bar is nearest its paws and its right-hand
  mouse appears on the viewer's left.
- Actual key presses, holds and releases on X11, including simultaneous keys.
- Both paws participate in typing; one can keep using the mouse while the other types.
- Typing speed follows actual press cadence and reach distance, with continuous
  redirection instead of queued strokes.
- Actual paw contacts produce small coordinated chest, head and key reactions.
- The mouse travels across a bounded area with its paw, then stays where it was left.
- Scrolling reaches and holds the mouse without moving it; the other paw can type.
- Coordinated eyes, head, whiskers, torso, ears and flexible tail, at up to 30 FPS.
- Eyes and head respond independently to shared attention; facial features use
  a small projected surface to follow turns and downward glances.
- Occasional grooming, face washing, yawning, glancing and small posture changes.
- Gradual relaxation and a tucked sleeping posture with slow breathing and small Zzz.
- Smooth interruption of grooming and sleep when activity resumes.
- Head pats with a brief coordinated squint and lean, dragging, and clicks through empty areas.
- Three sizes, an optional always-on-top mode, activity control and animation pause.
- Position and preferences saved with QSettings.

Input processing is entirely local. It keeps only currently held physical key
identifiers, brief visual markers, the latest paw targets and activity timestamps
in memory. It does not reconstruct text, keep a typing history, write input logs,
send telemetry or connect to the internet. **Reaccionar a actividad** disables
input listeners and immediately clears input state. Pausing also stops listeners
and clears held keys.

## Technologies

Python 3, PySide6 (Qt Widgets, Qt SVG, local Qt sockets and QSettings), pynput
and original SVG artwork. Only PySide6 Essentials is installed; optional Qt
modules such as WebEngine are not needed.

## Requirements

- Linux with Python 3.10 or newer, pip and support for virtual environments.
- A graphical desktop with compositing enabled.
- Qt's platform libraries for your desktop, usually supplied by the distribution.
  Some distributions also need Python headers and a C compiler to install
  pynput's transitive dependencies when binary wheels are unavailable.

## Installation

```sh
git clone https://github.com/camilo477/desktop-pet.git
cd desktop-pet
./install.sh
```

The installer creates `.venv` in this directory and a launcher in
`~/.local/bin/mascota`. It needs no administrator privileges and can be run
again. Keep the project directory in place. Installation may download packages;
the application then runs entirely offline.

If `~/.local/bin` is missing from your PATH, add this line once to your shell
configuration and open a new terminal:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The installer does not change your shell configuration or set up automatic startup.

## Usage

```sh
mascota       # Start in the background; the terminal can be closed.
mascota off   # Save preferences and close only this application.
```

The command works from any directory. Repeated starts reuse the existing
instance. A private local socket handles shutdown, with a process lock protecting
startup and recovery after unexpected exits. No HTTP server or background service
is installed.

Drag the cat with the left mouse button. Click its head for a short pat reaction,
even with activity reactions disabled. Dragging and clicks elsewhere do not
trigger a head pat. The right-click menu offers **Tamaño** (150, 200 or 300
logical pixels), **Siempre
visible**, **Reaccionar a actividad**, **Pausar animaciones** / **Reanudar
animaciones**, and **Salir**. Medium (200 × 200) is the default size.

Pausing stops the animation timer and input listeners while keeping dragging
and menu controls available. Disabling activity reactions stops global input
listeners; normal idle behaviors continue.

The mouse paw returns to the keyboard after approximately 500 ms without real
pointer movement or scrolling, followed by a smooth transfer. A stationary pointer or a
click alone does not keep the paw on the mouse or keep the cat watching the
cursor. When typing without pointer motion, attention moves to the keyboard.
Scrolling without pointer movement directs attention to the small mouse.
Horizontal mouse travel follows the cat's right and left, opposite to the viewer.
Vertical travel follows screen directions.

Held keys stay visibly pressed without repeating the paw's stroke. Fast taps
leave a brief visual mark; rapid typing updates current paw targets rather than
queuing a delayed sequence. All recognized pressed keys are shown even when
there are more held keys than available paws.

After 15 seconds without observed activity, occasional idle actions can begin.
After one minute Miga gradually relaxes, and after three minutes it settles into
sleep. A held key keeps it awake. Input or a direct click wakes it smoothly.
Sleep runs at about 10 FPS; pausing stops rendering entirely. These intervals
are simple constants in `animations.py`.

## Linux compatibility

- **X11:** global input uses pynput's pinned X backend, with Qt cursor tracking.
  A compositor and the X server's input recording support are needed. Physical
  QWERTY positions are used for US, UK, Spanish and Latin American layouts;
  Spanish layouts display Ñ. Other layouts use an unshifted key mapping where
  a corresponding represented key can be identified.
  Number-pad positions remain distinct when Num Lock is off on supported physical layouts.
- **Wayland, including XWayland sessions:** global input listeners are disabled.
  Local pointer reactions, idle animations, clicks and menu controls remain
  available. Native Wayland dragging uses the compositor's move request.
  Relaxation and sleep use only activity actually observed by the application;
  they do not measure the computer's global inactivity on Wayland.
- Window placement, position restoration, click-through masking, hiding from
  task switchers and keeping the pet above other applications depend on the
  compositor. In particular, native Wayland may ignore placement and topmost
  requests. No root access, input-device permissions or desktop extensions
  are required.

## Known limitations

The window and global input have been checked on GNOME/X11. Native Wayland,
KDE Plasma and physical multi-monitor setups require further manual checks.
GNOME/Wayland and other compositors can restrict topmost behavior and exact
position restoration. Global keyboard and pointer tracking are unavailable in
Wayland sessions; local pointer tracking still works while the pointer is over
Miga. Without an X11 input-recording facility, global activity can be unavailable
even when local interactions work.

Two paws cannot physically cover every held key. Priority follows reach and
availability; all recognized keys still show their pressed state. Labels are
omitted when rendering resolution is too small, and unsupported keys do not
generate invented strokes. Keyboard layout changes take effect after restarting
input reactions; switching among existing XKB layout groups is detected while running.
With a paw reserved for the mouse, very distant keys may exceed the remaining
paw's comfortable reach. Their input state is still displayed; a contact reaction
only occurs if the paw actually reaches the key. The full-size layout includes
the extra ISO key, but does not reproduce every hardware-specific keycap shape.
