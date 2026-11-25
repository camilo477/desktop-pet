# Miga · Desktop Pet

An original charcoal cat with a compact keyboard and mouse, built for Linux
with Python, PySide6 and SVG. The transparent window stays above other windows
without taking keyboard focus. Miga breathes, blinks and occasionally flicks
its ears and flexible tail.

![Miga with a keyboard and mouse](assets/cat/miga.svg)

## Features

- Original layered SVG artwork, with smooth independent animations at up to 30 FPS.
- Articulated forelegs, varied typing movements and smooth keyboard/mouse transfers.
- Both paws rest at the keyboard; real pointer motion reaches for the mouse,
  then the paw returns after a short idle interval.
- Perspective-aware head shapes, coordinated facial features and quicker pupil tracking.
- Closing eyelids, subtle torso breathing and deformation along the tail.
- Dragging, a small reaction when petted, and clicks through empty window areas.
- Three sizes, an optional always-on-top mode, activity control and animation pause.
- Position and preferences saved with QSettings.

Input callbacks immediately discard key values. Only activity timing and the
current pointer position and motion are kept in memory. No input history,
logs, telemetry or internet connections are used.

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

Drag the cat with the left mouse button. Click for a small reaction. The
right-click menu offers **Tamaño** (150, 200 or 300 logical pixels), **Siempre
visible**, **Reaccionar a actividad**, **Pausar animaciones** / **Reanudar
animaciones**, and **Salir**. Medium (200 × 200) is the default size.

Pausing stops the animation timer and input listeners while keeping dragging
and menu controls available. Disabling activity reactions stops global input
listeners; breathing, blinking and occasional tail movement continue.

The mouse hand returns to the keyboard after approximately 500 ms without real
pointer movement, followed by a smooth transfer. A stationary pointer or a
click alone does not keep the hand on the mouse. Typing can continue with one
paw while the other uses the mouse.

## Linux compatibility

- **X11:** global activity uses pynput's X backend, with Qt cursor tracking.
  A compositor and the X server's input recording support are needed.
- **Wayland, including XWayland sessions:** global input listeners are disabled.
  Local pointer reactions, idle animations, clicks and menu controls remain
  available. Native Wayland dragging uses the compositor's move request.
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
