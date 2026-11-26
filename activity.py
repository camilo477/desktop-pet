"""Local input state: current physical keys, short visual markers, and motion."""

from dataclasses import dataclass, replace
import math
import os
import threading
import time

from keyboard_layout import BY_ID, BY_SCAN, key_for_symbol

PULSE_SECONDS = .20
HINT_SECONDS = .36
RELEASE_GRACE = .022
KEY_RECONCILE_INTERVAL = .25


def is_wayland(platform):
    return (platform.startswith('wayland') or os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'
            or bool(os.environ.get('WAYLAND_DISPLAY')))


def supports_global_input(platform):
    return platform == 'xcb' and bool(os.environ.get('DISPLAY')) and not is_wayland(platform)


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
    layout: str = 'us'
    # Unsigned totals since the previous snapshot; repeated keys add no edges.
    new_presses: int = 0
    pointer_distance: float = 0.0
    wheel_distance: float = 0.0

    @property
    def pressed(self):
        return self.held | self.pulses


class ActivityMonitor:
    def __init__(self, global_input, wake_callback=None):
        self.global_input = global_input
        self.enabled = False
        self._lock = threading.Lock()
        self._activity = Activity()
        self._listeners = []
        self._keyboard_listener = None
        self._reader = None
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
        self._wake_callback = wake_callback
        self._notice_pending = False

    def _notify(self):
        # One queued UI notice per snapshot, even during dense pointer input.
        if self._wake_callback is not None and not self._notice_pending:
            self._notice_pending = True
            self._wake_callback()

    @property
    def global_pointer_active(self):
        return self.enabled and len(self._listeners) > 1 and self._listeners[1].is_alive()

    def set_enabled(self, enabled):
        if enabled == self.enabled:
            return
        self.stop()
        with self._lock:
            self.enabled = enabled
        if not enabled or not self.global_input:
            return
        os.environ['PYNPUT_BACKEND_KEYBOARD'] = 'xorg'
        os.environ['PYNPUT_BACKEND_MOUSE'] = 'xorg'
        try:
            from pynput import keyboard, mouse
            monitor = self

            # This small adapter uses the pinned X11 backend's raw hook. It avoids
            # translating physical input into text, including under Shift or Caps Lock.
            class PhysicalKeyboard(keyboard.Listener):
                def _initialize(self, display):
                    if not self.running:
                        raise self.StopException()
                    self.layouts, self.variants = ['us'], ['']
                    try:
                        prop = display.screen().root.get_full_property(display.intern_atom('_XKB_RULES_NAMES'), 0)
                        parts = bytes(prop.value).decode('ascii', errors='ignore').split('\0')
                        self.layouts = parts[2].split(',') or ['us']
                        self.variants = parts[3].split(',')
                    except Exception:
                        pass
                    self.keymap = {}
                    for code in range(8, 256):
                        self.keymap[code] = key_for_symbol(display.keycode_to_keysym(code, 0), self.layouts[0])
                    monitor.set_layout(self.layouts[0], self)
                    with monitor._lock:
                        if not self.running or monitor._keyboard_listener is not self:
                            raise self.StopException()
                        monitor._reader = display.query_keymap
                    for code in self._current_codes(display.query_keymap()):
                        monitor.key_down(self._identifier(code, 0), code, source=self, initial=True)
                    if not self.running:
                        raise self.StopException()

                @staticmethod
                def _current_codes(bitmap):
                    return [code for code in range(8, 256) if bitmap[code // 8] & (1 << (code % 8))]

                def _identifier(self, code, group):
                    layout = self.layouts[min(group, len(self.layouts) - 1)]
                    variant = self.variants[min(group, len(self.variants) - 1)] if self.variants else ''
                    known = layout in ('us', 'es', 'latam', 'gb') and variant not in ('dvorak', 'colemak')
                    return BY_SCAN.get(code) if known else self.keymap.get(code)

                def _handle_message(self, display, event, injected):
                    if monitor._keyboard_listener is not self:
                        return
                    code, kind, stamp = int(event.detail), int(event.type), int(event.time)
                    group = (int(event.state) >> 13) & 3
                    layout = self.layouts[min(group, len(self.layouts) - 1)]
                    monitor.set_layout(layout, self)
                    if kind == 2:  # X11 KeyPress and KeyRelease; no character conversion.
                        monitor.key_down(self._identifier(code, group), code, stamp, self)
                    elif kind == 3:
                        monitor.key_up(code, stamp, self)

                def _stop_platform(self):
                    if hasattr(self, '_context'):
                        super()._stop_platform()

            class PointerListener(mouse.Listener):
                def _initialize(self, display):
                    if not self.running:
                        raise self.StopException()
                    super()._initialize(display)
                    pointer = display.screen().root.query_pointer()
                    with monitor._lock:
                        if self.running:
                            monitor._global_position = (pointer.root_x, pointer.root_y)

                def _stop_platform(self):
                    if hasattr(self, '_context'):
                        super()._stop_platform()

            self._keyboard_listener = PhysicalKeyboard(suppress=False)
            self._listeners = [self._keyboard_listener,
                               PointerListener(on_move=self._move, on_click=self._click,
                                               on_scroll=self._scroll, suppress=False)]
            for listener in self._listeners:
                listener.start()
        except Exception:
            self.stop()
            with self._lock:
                self.enabled = enabled  # Keep local interaction available after backend failure.

    def set_layout(self, layout, source=None):
        layout = layout if layout in ('es', 'latam') else 'us'
        with self._lock:
            if source is None or source is self._keyboard_listener:
                self._activity = replace(self._activity, layout=layout)

    def key_down(self, identifier, code=None, server_time=None, source=None, initial=False):
        if code is None:
            key = BY_ID.get(identifier)
            if key is None:
                return
            code = key.scan
        if not isinstance(code, int) or not 8 <= code < 256:
            return
        identifier = identifier if identifier in BY_ID else None
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
            if identifier is not None:
                gap = now - self._last_press
                interval = .33 if gap > .8 else max(1 / 60, min(.5, gap))
                if interval > self._activity.key_interval and gap <= .8:
                    interval = (interval + self._activity.key_interval) * .5
                self._last_press = now
                self._activity = replace(self._activity, key_interval=interval)
                self._pulses[identifier] = now + PULSE_SECONDS
                hint = KeyHint(identifier, now)
                sector = BY_ID[identifier].preferred_paw
                self._hints[sector] = hint
                self._latest = hint

    def key_up(self, code, server_time=None, source=None):
        with self._lock:
            if self.enabled and (source is None or source is self._keyboard_listener) and code in self._down:
                now = time.monotonic()
                self._releases[code] = now + RELEASE_GRACE, server_time
                self._activity = replace(self._activity, keyboard=now)
                self._notify()

    def _move(self, x, y):
        self.pointer_moved(x, y)

    def _click(self, x, y, button, pressed):
        del x, y, button
        if pressed:
            self.pointer_click()

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
            if (local and self.global_input and len(self._listeners) > 1
                    and self._listeners[1].is_alive() and self._global_position is not None):
                return
            dx, dy = x - previous[0], y - previous[1]
            self._pointer_distance += math.hypot(dx, dy)
            self._motion[0] = max(-240, min(240, self._motion[0] + dx))
            self._motion[1] = max(-240, min(240, self._motion[1] + dy))
            self._activity = replace(self._activity, mouse=time.monotonic())
            self._notify()

    def set_dragging(self, dragging):
        # Keep each listener's last coordinate current while the window moves.
        # The next genuine movement then starts at the release position.
        with self._lock:
            self._dragging = dragging
            self._motion[:] = (0.0, 0.0)
            self._pointer_distance = 0.0
            self._activity = replace(self._activity, mouse=-math.inf)

    def pointer_click(self):
        with self._lock:
            if self.enabled:
                self._activity = replace(self._activity, click=time.monotonic())
                self._notify()

    def _clear_keys(self):
        self._down.clear(); self._releases.clear(); self._pulses.clear()
        self._hints = [KeyHint(), KeyHint()]; self._latest = KeyHint()

    def snapshot(self):
        now = time.monotonic()
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
            if self._keyboard_listener is not None and not self._keyboard_listener.is_alive():
                self._clear_keys(); self._reader = None
            if bitmap is not None:
                for code, (_, pressed_at) in list(self._down.items()):
                    if pressed_at <= sampled_at and not bitmap[code // 8] & (1 << (code % 8)):
                        self._down.pop(code, None); self._releases.pop(code, None)
            for code, (deadline, _) in list(self._releases.items()):
                if now >= deadline:
                    self._down.pop(code, None); self._releases.pop(code, None)
            self._pulses = {key: deadline for key, deadline in self._pulses.items() if deadline > now}
            self._hints = [hint if now - hint.stamp < HINT_SECONDS else KeyHint() for hint in self._hints]
            if now - self._latest.stamp >= HINT_SECONDS:
                self._latest = KeyHint()
            result = replace(self._activity, held=frozenset(key for key, _ in self._down.values() if key),
                           pulses=frozenset(self._pulses), hints=tuple(self._hints), latest=self._latest,
                           any_held=bool(self._down), motion_x=self._motion[0], motion_y=self._motion[1],
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

    def stop(self):
        with self._lock:
            self.enabled = False
            self._activity = Activity(layout=self._activity.layout)
            self._clear_keys()
            self._next_reconcile = 0.0
            self._global_position = self._local_position = None
            self._last_press = -math.inf
            self._motion[:] = (0.0, 0.0)
            self._wheel[:] = (0.0, 0.0)
            self._new_presses = 0
            self._pointer_distance = self._wheel_distance = 0.0
            self._notice_pending = False
        self._stop_listeners()
