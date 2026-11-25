"""Optional X11 input activity, reduced immediately to bounded timestamps."""

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


class ActivityMonitor:
    def __init__(self, global_input: bool) -> None:
        self.global_input = global_input
        self.enabled = False
        self._lock = threading.Lock()
        self._activity = Activity()
        self._listeners = []

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
                                          old.key_interval * 0.65 + interval * 0.35)

    def _move(self, x, y) -> None:
        del x, y
        self.pointer_activity()

    def _click(self, x, y, button, pressed) -> None:
        del x, y, button
        if pressed:
            self.pointer_activity(click=True)

    def _scroll(self, x, y, dx, dy) -> None:
        del x, y, dx, dy
        self.pointer_activity()

    def pointer_activity(self, click: bool = False) -> None:
        now = time.monotonic()
        with self._lock:
            if self.enabled:
                old = self._activity
                self._activity = Activity(old.keyboard, now,
                                          now if click else old.click, old.key_interval)

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
        self._stop_listeners()
