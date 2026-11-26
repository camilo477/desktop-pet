# Miga · Desktop Pet

An original charcoal cat sitting on an invisible floor with a small keyboard
and mouse. Built for Linux with Python, PySide6 and SVG, Miga accompanies your
activity in a transparent window without taking keyboard focus.

## Features

- Minimal charcoal silhouettes, warm golden eyes, grounded haunches and
  subtle flat shading that follows the body and its continuous forelegs.
- A shared body deformation keeps the chest, neck, shoulders and head connected.
- Five physical keyboard sizes with ANSI or ISO keys and eight sets of legends.
  Each keycap supplies the target for the paw and the highlight for a press.
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

## Usage

```sh
miga       # Start in the background; the terminal can be closed.
miga off   # Save preferences and close only this application.
```

The command works from any directory. Repeated starts reuse the existing
instance. A private local socket handles shutdown, with a process lock protecting
startup and recovery after unexpected exits. No HTTP server or background service
is installed.

Click Miga's head for a short pat. Hold the left button still on its head for
about a third of a second to keep petting it. Miga leans into your hand, closes
its eyes and gradually opens them again over about 0.7 seconds after release.
Click either ear for a quick flick, or touch the visible tail to make it curl
away. Moving the pointer close to its face briefly draws its attention.

To pick Miga up, hold the left button on its silhouette or peripherals and move
past the desktop's normal drag distance. This also works halfway through a pat.
The keyboard and mouse move with the window. Miga tucks its forepaws, leans
against the motion and settles when you stop. Real keys still light up during
the drag. On release, the paws can type, reach the mouse or scroll immediately
while the body regains its balance. The next pointer movement starts from the
release position. Empty areas allow clicks through where supported.

The right-click menu offers **Tamaño** (150, 200 or 300
logical pixels), **Teclado**, **Siempre visible**, **Reaccionar a actividad**, **Pausar animaciones** / **Reanudar
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
- **Wayland, including XWayland sessions:** global input listeners are disabled.
  Manual keyboard selection, local pointer reactions, idle animations, clicks and menu controls remain
  available. Native Wayland dragging uses the compositor's move request. Body
  sway uses position changes reported by Qt; a compositor that hides window
  coordinates can still move the pet, with reduced directional sway.
  Relaxation and sleep use only activity actually observed by the application;
  they do not measure the computer's global inactivity on Wayland.
- Window placement, position restoration, click-through masking, hiding from
  task switchers and keeping the pet above other applications depend on the
  compositor. In particular, native Wayland may ignore placement and topmost
  requests. No root access, input-device permissions or desktop extensions
  are required.

## Known limitations

The window and global input have been checked on GNOME/X11. Local petting and
compositor-managed dragging have also been checked in a nested Weston session.
On native Wayland the compositor may consume button release. Miga settles when
pointer focus returns, or estimates release if the grip has moved outside its
visible shape. GNOME/Wayland, KDE Plasma and physical multi-monitor setups
still require manual checks.
GNOME/Wayland and other compositors can restrict topmost behavior and exact
position restoration. Global keyboard and pointer tracking are unavailable in
Wayland sessions; local pointer tracking still works while the pointer is over
Miga. Without an X11 input-recording facility, global activity can be unavailable
even when local interactions work.

Each represented key lights on the first available frame. The paws follow the
current targets. Fast typing can redirect a paw before it lands, and with one
paw reserved for the mouse a distant key may exceed the other paw's reach.
A contact reaction occurs only when the paw reaches the key.
