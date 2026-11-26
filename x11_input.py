"""X11 RECORD listeners backed by physical XKB key names."""

import os


def start_listeners(monitor):
    os.environ['PYNPUT_BACKEND_KEYBOARD'] = 'xorg'
    os.environ['PYNPUT_BACKEND_MOUSE'] = 'xorg'
    from pynput import keyboard, mouse
    from x11_keyboard import XkbKeyboard

    # This small adapter uses the pinned X11 backend's raw hook. It avoids
    # translating physical input into text, including under Shift or Caps Lock.
    class PhysicalKeyboard(keyboard.Listener):
        def _initialize(self, display):
            if not self.running:
                raise self.StopException()
            self.xkb = None
            try:
                self.xkb = XkbKeyboard(display)
                self.refresh_layout()
            except Exception:
                monitor.set_layout(None, self)
            with monitor._lock:
                if not self.running or monitor._keyboard_listener is not self:
                    raise self.StopException()
                monitor._reader = display.query_keymap
            for code in self._current_codes(display.query_keymap()):
                monitor.key_down(self.xkb.positions.get(code) if self.xkb else None,
                                 code, source=self, initial=True)
            if not self.running:
                raise self.StopException()

        @staticmethod
        def _current_codes(bitmap):
            return [code for code in range(8, 256) if bitmap[code // 8] & (1 << (code % 8))]

        def refresh_layout(self):
            if self.xkb:
                monitor.set_layout(self.xkb.refresh(), self)

        def _handle_message(self, display, event, injected):
            if monitor._keyboard_listener is not self:
                return
            code, kind, stamp = int(event.detail), int(event.type), int(event.time)
            group = (int(event.state) >> 13) & 3
            if self.xkb:
                monitor.set_layout(self.xkb.layout(group), self)
            if kind == 2:  # X11 KeyPress and KeyRelease; no character conversion.
                monitor.key_down(self.xkb.positions.get(code) if self.xkb else None, code, stamp, self)
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

    monitor._keyboard_listener = PhysicalKeyboard(suppress=False)
    monitor._listeners = [monitor._keyboard_listener,
                       PointerListener(on_move=monitor._move, on_click=monitor._click,
                                       on_scroll=monitor._scroll, suppress=False)]
    for listener in monitor._listeners:
        listener.start()
