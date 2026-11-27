"""Local input state: current physical keys, short visual markers, and motion."""

from dataclasses import dataclass, replace
import math
import os
import sys
import threading
import time

from keyboard_distributions import DISTRIBUTIONS
from keyboard_layout import Keyboard

PULSE_SECONDS = .20
HINT_SECONDS = .36
RELEASE_GRACE = .022
KEY_RECONCILE_INTERVAL = .25


def is_wayland(platform):
    return sys.platform.startswith('linux') and (platform.startswith('wayland') or os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'
            or bool(os.environ.get('WAYLAND_DISPLAY')))


def supports_global_input(platform):
    if sys.platform == 'darwin':
        return platform == 'cocoa'
    if sys.platform == 'win32':
        return platform == 'windows'
    return (sys.platform.startswith('linux') and platform == 'xcb'
            and bool(os.environ.get('DISPLAY')) and not is_wayland(platform))


@dataclass(frozen=True)
class KeyHint:
    identifier: str | None = None
    stamp: float = -math.inf


@dataclass(frozen=True)
class Activity:
    keyboard: float = -math.inf
    mouse: float = -math.inf
    click: float = -math.inf
    scroll: float = -math.inf
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    key_interval: float = .33
    # Real pointer displacement since the previous snapshot, in screen pixels.
    motion_x: float = 0.0
    motion_y: float = 0.0
    held: frozenset[str] = frozenset()
    pulses: frozenset[str] = frozenset()
    hints: tuple[KeyHint, KeyHint] = (KeyHint(), KeyHint())
    latest: KeyHint = KeyHint()
    any_held: bool = False
    layout: str | None = None
    # Unsigned totals since the previous snapshot; repeated keys add no edges.
    new_presses: int = 0
    pointer_distance: float = 0.0
    wheel_distance: float = 0.0

    @property
    def pressed(self):
        return self.held | self.pulses


class ActivityMonitor:
    def __init__(self, global_input, wake_callback=None, keyboard=None):
        self.keyboard = keyboard or Keyboard()
        self.global_input = global_input
        self.native_pointer = False
        self.enabled = False
        self._lock = threading.Lock()
        self._activity = Activity()
        self._listeners = []
        self._keyboard_listener = None
        self._reader = None
        self._next_layout_check = 0.0
        self._next_reconcile = 0.0
        self._global_position = self._local_position = None
        self._down = {}
        self._releases = {}
        self._pulses = {}
        self._hints = [KeyHint(), KeyHint()]
        self._latest = KeyHint()
        self._last_press = -math.inf
        self._motion = [0.0, 0.0]
        self._wheel = [0.0, 0.0]
        self._new_presses = 0
        self._pointer_distance = self._wheel_distance = 0.0
        self._dragging = False
        self._drop_grace_until = -math.inf
        self._wake_callback = wake_callback
        self._notice_pending = False
        self._context_click = False

    def _notify(self):
        # One queued UI notice per snapshot, even during dense pointer input.
        if self._wake_callback is not None and not self._notice_pending:
            self._notice_pending = True
            self._wake_callback()

    @property
    def global_pointer_active(self):
        return self.enabled and (self.native_pointer or
                                 len(self._listeners) > 1 and self._listeners[1].is_alive())

    def set_enabled(self, enabled):
        if enabled == self.enabled:
            return
        self.stop()
        with self._lock:
            self.enabled = enabled
        if not enabled or not self.global_input or sys.platform != 'linux':
            return
        try:
            from x11_input import start_listeners
            start_listeners(self)
        except Exception:
            self.stop()
            with self._lock:
                self.enabled = enabled  # Local interactions remain available.

    def set_layout(self, layout, source=None):
        layout = layout if layout in DISTRIBUTIONS else None
        with self._lock:
            if (source is None or source is self._keyboard_listener) and layout != self._activity.layout:
                self._activity = replace(self._activity, layout=layout)

    def set_keyboard(self, keyboard):
        with self._lock:
            self.keyboard = keyboard
            self._hints = [KeyHint(), KeyHint()]
            self._latest = KeyHint()
            self._pulses.clear()
            return frozenset(key for key, _ in self._down.values() if key in keyboard.by_id)

    def key_down(self, identifier, code=None, server_time=None, source=None, initial=False):
        if code is None:
            code = identifier  # Synthetic input can use the physical position directly.
        elif not isinstance(code, tuple) and (not isinstance(code, int) or not 8 <= code < 256):
            return
        now = time.monotonic()
        with self._lock:
            if not self.enabled or (source is not None and source is not self._keyboard_listener):
                return
            self._activity = replace(self._activity, keyboard=now)
            self._notify()
            pending = self._releases.pop(code, None)
            if code in self._down:
                # Core X11 repeat produces release/press with the same server time.
                if pending is None or (pending[1] == server_time and
                                       (server_time is not None or now < pending[0])):
                    return
            self._down[code] = (identifier, now)
            if not initial:
                self._new_presses += 1
                gap = now - self._last_press
                interval = .33 if gap > .8 else max(1 / 60, min(.5, gap))
                if interval > self._activity.key_interval and gap <= .8:
                    interval = (interval + self._activity.key_interval) * .5
                self._last_press = now
                self._activity = replace(self._activity, key_interval=interval)
            if identifier in self.keyboard.by_id:
                self._pulses[identifier] = now + PULSE_SECONDS
                hint = KeyHint(identifier, now)
                sector = self.keyboard.by_id[identifier].preferred_paw
                self._hints[sector] = hint
                self._latest = hint

    def key_up(self, code, server_time=None, source=None, *, immediate=False):
        with self._lock:
            if self.enabled and (source is None or source is self._keyboard_listener) and code in self._down:
                now = time.monotonic()
                if immediate:
                    self._down.pop(code)
                else:
                    self._releases[code] = now + RELEASE_GRACE, server_time
                self._activity = replace(self._activity, keyboard=now)
                self._notify()

    def _move(self, x, y):
        self.pointer_moved(x, y)

    def _click(self, x, y, button, pressed):
        if pressed:
            self.pointer_click(context=button.name == 'right')

    def _scroll(self, x, y, dx, dy):
        del x, y
        self.pointer_scrolled(dx, dy)

    def pointer_scrolled(self, dx, dy):
        with self._lock:
            if self.enabled and (dx or dy):
                self._activity = replace(self._activity, scroll=time.monotonic())
                self._wheel_distance += abs(dx) + abs(dy)
                self._wheel[0] = max(-8, min(8, self._wheel[0] + dx))
                self._wheel[1] = max(-8, min(8, self._wheel[1] + dy))
                self._notify()

    def pointer_moved(self, x, y, local=False):
        with self._lock:
            if not self.enabled:
                return
            previous = self._local_position if local else self._global_position
            position = (x, y)
            if previous == position:
                return
            if local:
                self._local_position = position
            else:
                self._global_position = position
            if previous is None or self._dragging:
                return
            if local and self.global_pointer_active and self._global_position is not None:
                return
            dx, dy = x - previous[0], y - previous[1]
            self._pointer_distance += math.hypot(dx, dy)
            self._motion[0] = max(-240, min(240, self._motion[0] + dx))
            self._motion[1] = max(-240, min(240, self._motion[1] + dy))
            self._activity = replace(self._activity, mouse=time.monotonic())
            self._notify()

    def reset_pointer_origin(self):
        with self._lock:
            self._global_position = None

    def pointer_delta(self, dx, dy):
        """Relative hardware movement when desktop cursor coordinates are unavailable."""
        with self._lock:
            if not self.enabled or self._dragging or not (dx or dy):
                return
            self._pointer_distance += math.hypot(dx, dy)
            self._motion[0] = max(-240, min(240, self._motion[0] + dx))
            self._motion[1] = max(-240, min(240, self._motion[1] + dy))
            self._activity = replace(self._activity, mouse=time.monotonic())
            self._notify()

    def set_dragging(self, dragging):
        # Keep each listener's last coordinate current while the window moves.
        # The next genuine movement then starts at the release position.
        with self._lock:
            now = time.monotonic()
            if self._dragging and not dragging:
                self._drop_grace_until = now + RELEASE_GRACE
                self._pulses.clear()
                self._wheel[:] = (0., 0.)
                self._wheel_distance = 0.
                self._activity = replace(self._activity, scroll=-math.inf, click=-math.inf)
            self._dragging = dragging
            self._motion[:] = (0.0, 0.0)
            self._pointer_distance = 0.0
            self._activity = replace(self._activity, mouse=-math.inf)
            return now

    def discard_menu_pointer(self):
        # Navigating Miga's own popup while asleep is an explicit control. Retain
        # all keyboard edges and the current pointer coordinates for the next move.
        with self._lock:
            self._activity = replace(self._activity, mouse=-math.inf, click=-math.inf, scroll=-math.inf)
            self._motion[:] = (0.0, 0.0)
            self._wheel[:] = (0.0, 0.0)
            self._pointer_distance = self._wheel_distance = 0.0

    def pointer_click(self, context=False):
        with self._lock:
            if self.enabled:
                self._context_click = context
                self._activity = replace(self._activity, click=time.monotonic())
                self._notify()

    def _clear_keys(self):
        self._drop_grace_until = -math.inf
        self._down.clear(); self._releases.clear(); self._pulses.clear()
        self._hints = [KeyHint(), KeyHint()]; self._latest = KeyHint()

    def snapshot(self, context_target=None):
        now = time.monotonic()
        listener = self._keyboard_listener
        if self.enabled and listener and self._reader and now >= self._next_layout_check:
            self._next_layout_check = now + 2
            try:
                listener.refresh_layout()
            except Exception:
                self.set_layout(None, listener)
        bitmap = None
        sampled_at = now
        # Query only a current bitmap while keys are held. This repairs missed releases,
        # rather than retaining a stale held key indefinitely. No event history is read.
        if self.enabled and self._reader and self._down and now >= self._next_reconcile:
            self._next_reconcile = now + KEY_RECONCILE_INTERVAL
            try:
                bitmap = self._reader()
            except Exception:
                pass
        with self._lock:
            if self._context_click:
                # RECORD can deliver the right click before Qt opens the local popup.
                if context_target is not None and context_target():
                    self._activity = replace(self._activity, click=-math.inf)
                self._context_click = False
            if self._keyboard_listener is not None and not self._keyboard_listener.is_alive():
                self._clear_keys(); self._reader = None
                if self._activity.layout is not None:
                    self._activity = replace(self._activity, layout=None)
            if bitmap is not None:
                for code, (_, pressed_at) in list(self._down.items()):
                    if isinstance(code, int) and pressed_at <= sampled_at and not bitmap[code // 8] & (1 << (code % 8)):
                        self._down.pop(code, None); self._releases.pop(code, None)
            for code, (deadline, _) in list(self._releases.items()):
                if now >= deadline:
                    self._down.pop(code, None); self._releases.pop(code, None)
            self._pulses = {key: deadline for key, deadline in self._pulses.items() if deadline > now}
            self._hints = [hint if now - hint.stamp < HINT_SECONDS else KeyHint() for hint in self._hints]
            if now - self._latest.stamp >= HINT_SECONDS:
                self._latest = KeyHint()
            down = self._down
            if self._releases and now < self._drop_grace_until:
                # X11 still needs the pending release to recognize autorepeat.
                # Only the animation filters keys already released before drop.
                down = {code: key for code, key in down.items()
                        if code not in self._releases or self._releases[code][0] > self._drop_grace_until}
            result = replace(self._activity, held=frozenset(key for key, _ in down.values() if key in self.keyboard.by_id),
                           pulses=frozenset(self._pulses), hints=tuple(self._hints), latest=self._latest,
                           any_held=bool(down), motion_x=self._motion[0], motion_y=self._motion[1],
                           scroll_x=self._wheel[0], scroll_y=self._wheel[1],
                           new_presses=self._new_presses, pointer_distance=self._pointer_distance,
                           wheel_distance=self._wheel_distance)
            self._motion[:] = (0.0, 0.0)
            self._wheel[:] = (0.0, 0.0)
            self._new_presses = 0
            self._pointer_distance = self._wheel_distance = 0.0
            self._notice_pending = False
            return result

    def _stop_listeners(self):
        listeners, self._listeners = self._listeners, []
        self._keyboard_listener = self._reader = None
        for listener in listeners:
            try:
                listener.stop()
            except Exception:
                pass
        for listener in listeners:
            if listener.ident is not None:
                try:
                    listener.join(timeout=.4)
                except Exception:
                    pass

    def clear_input(self):
        with self._lock:
            self._activity = Activity()
            self._context_click = False
            self._clear_keys()
            self._next_layout_check = 0.0
            self._next_reconcile = 0.0
            self._global_position = self._local_position = None
            self._last_press = -math.inf
            self._motion[:] = (0.0, 0.0)
            self._wheel[:] = (0.0, 0.0)
            self._new_presses = 0
            self._pointer_distance = self._wheel_distance = 0.0
            self._notice_pending = False

    def stop(self):
        self.enabled = False
        self.clear_input()
        self._stop_listeners()
