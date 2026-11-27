"""Read-only evdev observation for Wayland, using existing device permissions."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from PySide6.QtCore import QObject, QSocketNotifier, QTimer
from PySide6.QtDBus import QDBusConnection, QDBusInterface


class SessionAccess:
    """Observe physical devices only in our active, unlocked login session."""

    def __init__(self):
        self.session = None
        self.bus = QDBusConnection.systemBus()

    def allowed(self):
        if self.session is None:
            session_id = os.environ.get('XDG_SESSION_ID')
            if not session_id or not self.bus.isConnected():
                return False
            manager = QDBusInterface('org.freedesktop.login1', '/org/freedesktop/login1',
                                     'org.freedesktop.login1.Manager', self.bus)
            manager.setTimeout(500)
            reply = manager.call('GetSession', session_id)
            args = reply.arguments()
            if not args or not hasattr(args[0], 'path'):
                return False
            self.session = QDBusInterface('org.freedesktop.login1', args[0].path(),
                                         'org.freedesktop.login1.Session', self.bus)
            self.session.setTimeout(500)
        return self.session.property('Active') is True and self.session.property('LockedHint') is False


@dataclass
class Device:
    handle: object
    notifier: object
    keyboard: bool
    pointer: bool
    held: set = field(default_factory=set)
    dropped: bool = False
    motion: list = field(default_factory=lambda: [0., 0.])
    wheel: dict = field(default_factory=dict)


class LinuxInput(QObject):
    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.monitor = pet.activity
        self.enabled = False
        self.devices = {}
        self.denied = 0
        self.error = None
        self.session_active = False
        self.session = SessionAccess()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.scan)
        try:
            from evdev import InputDevice, ecodes
            from linux_keyboard import POSITIONS
            self.open_device, self.codes, self.positions = InputDevice, ecodes, POSITIONS
        except ImportError:
            self.open_device = None
            self.error = 'Falta evdev; ejecuta install.sh'

    @property
    def keyboard_count(self):
        return sum(device.keyboard for device in self.devices.values())

    @property
    def pointer_count(self):
        return sum(device.pointer for device in self.devices.values())

    def configure(self, enabled):
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self.scan()
            self.timer.start()
        else:
            self.timer.stop()
            self.close_devices()

    def pointer_from_kwin(self):
        kwin = self.pet.kwin
        return bool(kwin and kwin.active and kwin.pointer_enabled and kwin.pointer is not None)

    def scan(self):
        if not self.enabled or self.open_device is None:
            return
        self.session_active = self.session.allowed()
        if not self.session_active:
            self.close_devices()
            return
        paths = {str(path) for path in Path('/dev/input').glob('event*')}
        for path in list(self.devices):
            if path not in paths or not os.access(path, os.R_OK):
                self.remove(path)
        self.denied = 0
        for path in sorted(paths - self.devices.keys()):
            try:
                handle = self.open_device(path, readonly=True)
            except PermissionError:
                self.denied += 1
                continue
            except OSError:
                continue
            except TypeError:
                self.error = 'Se requiere evdev 2.0 o posterior; ejecuta install.sh'
                return
            capabilities = handle.capabilities(absinfo=False)
            keys = set(capabilities.get(self.codes.EV_KEY, []))
            keyboard = bool(keys.intersection(self.positions))
            pointer = self.codes.BTN_MOUSE in keys
            if not (keyboard or pointer):
                handle.close()
                continue
            notifier = QSocketNotifier(handle.fd, QSocketNotifier.Type.Read, self)
            device = self.devices[path] = Device(handle, notifier, keyboard, pointer)
            notifier.activated.connect(lambda *_, p=path: self.read(p))
            try:
                self.reconcile(path, device)
            except OSError:
                self.remove(path)
        self.monitor.native_pointer = bool(self.pointer_count or self.pointer_from_kwin())

    def reconcile(self, path, device):
        current = set(device.handle.active_keys()).intersection(self.positions)
        for code in device.held - current:
            self.monitor.key_up(('evdev', path, code), immediate=True)
        for code in current - device.held:
            self.monitor.key_down(self.positions[code], ('evdev', path, code), initial=True)
        device.held = current

    def read(self, path):
        device = self.devices.get(path)
        if device is None or not self.enabled:
            return
        try:
            for event in device.handle.read():
                self.process(path, device, event.type, event.code, event.value)
        except BlockingIOError:
            pass
        except OSError:
            self.remove(path)

    def process(self, path, device, kind, code, value):
        e = self.codes
        if kind == e.EV_SYN and code == e.SYN_DROPPED:
            device.dropped = True
            device.motion[:] = (0., 0.)
            device.wheel.clear()
            return
        if device.dropped:
            if kind == e.EV_SYN and code == e.SYN_REPORT:
                device.dropped = False
                self.reconcile(path, device)
            return
        if kind == e.EV_KEY:
            if code in self.positions:
                identity = ('evdev', path, code)
                if value == 1:
                    device.held.add(code)
                    self.monitor.key_down(self.positions[code], identity)
                elif value == 0:
                    device.held.discard(code)
                    self.monitor.key_up(identity, immediate=True)
            elif device.pointer and e.BTN_MOUSE <= code < e.BTN_JOYSTICK and value == 1:
                self.monitor.pointer_click(context=code == e.BTN_RIGHT)
        elif kind == e.EV_REL and device.pointer:
            if code in (e.REL_X, e.REL_Y):
                device.motion[code == e.REL_Y] += value
            elif code in (e.REL_WHEEL, e.REL_HWHEEL, e.REL_WHEEL_HI_RES, e.REL_HWHEEL_HI_RES):
                device.wheel[code] = device.wheel.get(code, 0) + value
        elif kind == e.EV_SYN and code == e.SYN_REPORT:
            if not self.pointer_from_kwin():
                self.monitor.pointer_delta(*device.motion)
            device.motion[:] = (0., 0.)
            wheel = device.wheel
            dx = wheel.get(e.REL_HWHEEL_HI_RES, wheel.get(e.REL_HWHEEL, 0) * 120) / 120
            dy = wheel.get(e.REL_WHEEL_HI_RES, wheel.get(e.REL_WHEEL, 0) * 120) / 120
            self.monitor.pointer_scrolled(dx, dy)
            wheel.clear()

    def remove(self, path):
        device = self.devices.pop(path)
        device.notifier.setEnabled(False)
        device.notifier.deleteLater()
        for code in device.held:
            self.monitor.key_up(('evdev', path, code), immediate=True)
        device.handle.close()

    def close_devices(self):
        for path in list(self.devices):
            self.remove(path)
        self.monitor.native_pointer = self.pointer_from_kwin()
