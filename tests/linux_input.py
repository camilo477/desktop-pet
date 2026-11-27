"""Physical Wayland input pipeline without reading the host's keyboard."""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evdev import ecodes as e
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication
from linux_input import Device, LinuxInput
from linux_keyboard import POSITIONS
from kwin_window import KWinWindow
from pet import PetWindow
from keyboard_layout import Keyboard


def check_pipeline(window):
    monitor = window.activity
    monitor.set_enabled(True)
    backend = LinuxInput(window)
    backend.enabled = True
    handle = SimpleNamespace(active_keys=lambda: [e.KEY_B], close=lambda: None)
    notifier = SimpleNamespace(setEnabled=lambda _: None, deleteLater=lambda: None)
    device = backend.devices['test'] = Device(handle, notifier, True, True)
    send = lambda kind, code, value: backend.process('test', device, kind, code, value)
    assert set(POSITIONS.values()) == set(Keyboard().by_id)
    send(e.EV_KEY, e.KEY_A, 1)
    send(e.EV_KEY, e.KEY_A, 2)
    activity = monitor.snapshot()
    assert activity.held == {'A'} and activity.new_presses == 1
    window.tick()
    assert window.animations.pose.pressed == {'A'}
    assert any(paw.goal == 'A' for paw in window.animations.paws)
    # The same key on two devices is released independently.
    monitor.key_down('A', ('evdev', 'second', e.KEY_A))
    send(e.EV_KEY, e.KEY_A, 0)
    assert monitor.snapshot().held == {'A'}
    monitor.key_up(('evdev', 'second', e.KEY_A), immediate=True)
    assert not monitor.snapshot().held
    # Both axes and high resolution wheels, without counting the legacy event twice.
    send(e.EV_REL, e.REL_X, 24)
    send(e.EV_REL, e.REL_Y, -10)
    send(e.EV_REL, e.REL_WHEEL, 1)
    send(e.EV_REL, e.REL_WHEEL_HI_RES, 120)
    send(e.EV_REL, e.REL_HWHEEL_HI_RES, -60)
    send(e.EV_SYN, e.SYN_REPORT, 0)
    activity = monitor.snapshot()
    assert (activity.motion_x, activity.motion_y) == (24, -10)
    assert (activity.scroll_x, activity.scroll_y) == (-.5, 1)
    # Overflow discards incomplete events and recovers only the currently held keys.
    send(e.EV_KEY, e.KEY_A, 1)
    send(e.EV_SYN, e.SYN_DROPPED, 0)
    send(e.EV_KEY, e.KEY_C, 1)
    send(e.EV_SYN, e.SYN_REPORT, 0)
    assert monitor.snapshot().held == {'B'}
    backend.remove('test')
    assert not monitor.snapshot().held
    # Loss of active-session status closes devices and releases any held keys.
    device.held = {e.KEY_A}
    monitor.key_down('A', ('evdev', 'test', e.KEY_A))
    backend.devices['test'] = device
    with patch.object(backend.session, 'allowed', return_value=False):
        backend.scan()
    assert not backend.devices and not monitor.snapshot().held
    backend.configure(False)


def check_cursor(window):
    import json
    window.activity.clear_input()
    placement = KWinWindow(window)
    window.kwin = placement
    placement.active = placement.pointer_enabled = True
    placement.position = QPoint(2400, 1500)
    payload = lambda x, y: json.dumps(dict(generation=0, x=x, y=y))
    placement.pointerMoved(payload(2600, 1550))
    placement.pointerMoved(payload(2700, 1600))
    sample = window.activity.snapshot()
    assert (sample.motion_x, sample.motion_y) == (100, 50)
    placement.pointerMoved(payload(2720, 1610))
    for _ in range(20):
        window.last_frame -= .034
        window.tick()
    assert window.animations.pose.mouse_dx or window.animations.pose.mouse_dy
    window.set_reactions(False)
    placement.pointerMoved(payload(0, 0))
    assert placement.pointer is None and not window.activity.snapshot().pointer_distance
    window.set_reactions(True)
    window.kwin = None
    placement.close()


if __name__ == '__main__':
    app = QApplication([])
    app.setOrganizationName('miga-test')
    app.setApplicationName('linux-input')
    with TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        window = PetWindow()
        try:
            check_pipeline(window)
            check_cursor(window)
        finally:
            window.shutdown()
    print('PASS: 105 physical keys, typing animation, holds, mouse axes, scroll, overflow, unplug and pause.')
