"""Optional X11 activity, retaining only current timing and pointer motion."""

from dataclasses import dataclass
import math
import os
import threading
import time


def is_wayland(platform: str) -> bool:
    return (
        platform.startswith("wayland")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def supports_global_input(platform: str) -> bool:
    return platform == "xcb" and bool(os.environ.get("DISPLAY")) and not is_wayland(platform)


@dataclass(frozen=True)
class Activity:
    keyboard: float = -math.inf
    mouse: float = -math.inf
    click: float = -math.inf
    key_interval: float = 0.15
    motion_x: float = 0.0
    motion_y: float = 0.0


class ActivityMonitor:
    def __init__(self, global_input: bool) -> None:
        self.global_input = global_input
        self.enabled = False
        self._lock = threading.Lock()
        self._activity = Activity()
        self._listeners = []
        self._global_position = None
        self._local_position = None

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self.enabled:
            return
        self.stop()
        with self._lock:
            self.enabled = enabled
        if not enabled or not self.global_input:
            return
        # Explicitly choose X, never the privileged device-input backend.
        os.environ["PYNPUT_BACKEND_KEYBOARD"] = "xorg"
        os.environ["PYNPUT_BACKEND_MOUSE"] = "xorg"
        try:
            from pynput import keyboard, mouse

            self._listeners = [
                keyboard.Listener(on_press=self._keyboard, suppress=False),
                mouse.Listener(on_move=self._move, on_click=self._click,
                               on_scroll=self._scroll, suppress=False),
            ]
            for listener in self._listeners:
                listener.start()
        except Exception:
            # An unavailable input backend must not prevent the pet from running.
            self._stop_listeners()

    def _keyboard(self, key) -> None:
        del key
        now = time.monotonic()
        with self._lock:
            if self.enabled:
                old = self._activity
                interval = now - old.keyboard
                interval = 0.15 if interval > 1.0 else max(0.065, min(interval, 0.3))
                self._activity = Activity(now, old.mouse, old.click,
                                          old.key_interval * 0.65 + interval * 0.35,
                                          old.motion_x, old.motion_y)

    def _move(self, x, y) -> None:
        self.pointer_moved(x, y)

    def _click(self, x, y, button, pressed) -> None:
        del x, y, button
        if pressed:
            self.pointer_click()

    def _scroll(self, x, y, dx, dy) -> None:
        del x, y, dx, dy
        self.pointer_click()

    def pointer_moved(self, x: float, y: float, local: bool = False) -> None:
        with self._lock:
            if not self.enabled:
                return
            # Qt and pynput may report different coordinate scales on high-DPI screens.
            previous = self._local_position if local else self._global_position
            position = (x, y)
            if previous == position:
                return
            if local:
                self._local_position = position
            else:
                self._global_position = position
            if previous is None:
                # A first position establishes a baseline, not evidence of movement.
                return
            dx, dy = x - previous[0], y - previous[1]
            old = self._activity
            self._activity = Activity(old.keyboard, time.monotonic(), old.click, old.key_interval,
                                      math.tanh(dx / 12.0), math.tanh(dy / 12.0))

    def pointer_click(self) -> None:
        with self._lock:
            if self.enabled:
                old = self._activity
                self._activity = Activity(old.keyboard, old.mouse, time.monotonic(),
                                          old.key_interval, old.motion_x, old.motion_y)

    def snapshot(self) -> Activity:
        with self._lock:
            return self._activity

    def _stop_listeners(self) -> None:
        listeners, self._listeners = self._listeners, []
        for listener in listeners:
            try:
                listener.stop()
            except Exception:
                pass
        for listener in listeners:
            if listener.ident is not None:
                try:
                    listener.join(timeout=0.4)
                except Exception:
                    pass

    def stop(self) -> None:
        with self._lock:
            self.enabled = False
            self._activity = Activity()
            self._global_position = None
            self._local_position = None
        self._stop_listeners()
