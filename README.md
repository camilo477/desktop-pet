# Miga · Desktop Pet

An original little ginger cat at a wooden desk, built for Linux with Python,
PySide6 and SVG. The transparent window stays above other windows without
taking keyboard focus. Miga breathes, blinks and occasionally flicks its tail.

## Features

- Original layered SVG artwork, with smooth independent animations at up to 30 FPS.
- Keyboard paws, mouse movement and click reactions on X11.
- Gently interpolated eyes and head that follow the pointer.
- Dragging, a small reaction when petted, and clicks through empty window areas.
- Three sizes, an optional always-on-top mode, activity control and animation pause.
- Position and preferences saved with QSettings.

Input callbacks immediately discard key values. Only the latest activity times
and a smoothed typing interval are kept in memory. No input history, logs,
telemetry or network connections are used.

## Requirements

- Linux with Python 3.10 or newer and support for virtual environments.
- A graphical desktop with compositing enabled.

## Installation and use

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Drag the cat with the left mouse button. Click for a small reaction. The
right-click menu offers **Tamaño** (150, 200 or 300 logical pixels), **Siempre
visible**, **Reaccionar a actividad**, **Pausar animaciones** / **Reanudar
animaciones**, and **Salir**. Medium (200 × 200) is the default size.

Pausing stops the animation timer and input listeners while keeping dragging
and menu controls available. Disabling activity reactions stops global input
listeners; breathing, blinking and occasional tail movement continue.

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

The window and global input have been checked on GNOME/X11. Native Wayland,
KDE Plasma and physical multi-monitor setups require further manual checks.
