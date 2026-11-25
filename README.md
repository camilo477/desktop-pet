# Miga · Desktop Pet

An original little ginger cat at a wooden desk, built for Linux with Python,
PySide6 and SVG. The transparent window stays above other windows without
taking keyboard focus. Miga breathes, blinks and occasionally flicks its tail.

## Requirements

- Linux with Python 3.10 or newer and support for virtual environments.
- A graphical desktop with compositing enabled.

## Installation and use

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Drag the cat with the left mouse button. Click for a small reaction; right-click
and choose **Salir** to close it.

## Linux compatibility

The transparent window needs compositor support. Window placement and keeping
the pet above other applications depend on the desktop's window manager.
