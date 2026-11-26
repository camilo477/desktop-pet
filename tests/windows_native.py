"""Run in a dedicated Windows session. Only synthetic activity is supplied here."""

import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from appearance import Appearance
from pet import PetWindow
from windows_input import Device, Key, Mouse, function, user


def window_checks(app):
    pet = PetWindow()
    pet.show()
    app.processEvents()
    backend = pet.windows_input
    assert backend and backend.active and backend.hwnd == int(pet.winId())
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pet.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    registered = function(user, 'GetRegisteredRawInputDevices', W.UINT,
                          C.POINTER(Device), C.POINTER(W.UINT), W.UINT)
    count = W.UINT()
    assert registered(None, C.byref(count), C.sizeof(Device)) == 0
    devices = (Device * count.value)()
    assert registered(devices, C.byref(count), C.sizeof(Device)) == count.value
    assert {d.usage for d in devices if d.target == backend.hwnd and d.page == 1} >= {2, 6}
    send = function(user, 'SendMessageW', W.LPARAM, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    assert send(backend.hwnd, 0x21, 0, 0) == 3
    key = Key(scan=0x1c, flags=2, vk=13)
    backend.keyboard(1, key)
    backend.keyboard(1, key)
    shot = pet.activity.snapshot()
    assert shot.held == {'NumpadEnter'} and shot.new_presses == 1
    backend.mouse(Mouse(buttons=0x800, wheel=-120))
    assert pet.activity.snapshot().scroll_x == -1
    send(backend.hwnd, 0x02b1, 7, 0)
    assert backend.locked and not pet.activity.snapshot().any_held
    send(backend.hwnd, 0x02b1, 8, 0)
    assert not backend.locked
    pet.configure_keyboard(form='65', standard='ANSI', layout='dvorak')
    pet.configure_appearance(Appearance('calico', 'auto', 'auto'))
    pet.set_paused(True)
    assert not backend.active and not pet.timer.isActive()
    pet.shutdown()
    restored = PetWindow()
    assert restored.keyboard.form == '65' and restored.keyboard.layout == 'dvorak'
    assert restored.art.appearance == pet.art.appearance and restored.paused
    restored.set_paused(False)
    assert restored.windows_input.active
    restored.build_menu().actions()[-1].trigger()
    assert restored._closed


def benchmark(app):
    from PySide6.QtCore import QTimer
    pet = PetWindow()
    pet.set_paused(False)
    pet.set_size(300)
    pet.show()
    app.processEvents()
    # Run with real Windows Qt painting and controlled activity in the runner.
    for mode in ('typing', 'sleep', 'paused'):
        pet.animations.last_activity = time.monotonic() - (220 if mode == 'sleep' else 0)
        if mode == 'sleep':
            pet.activity.clear_input()
        pet.set_paused(mode == 'paused')
        i = 0

        def press():
            nonlocal i
            k = 'ASDFJKL'[i % 7]
            pet.activity.key_down(k)
            pet.activity.key_up(k, immediate=True)
            i += 1

        keys = QTimer()
        keys.timeout.connect(press)
        if mode == 'typing':
            keys.start(70)
        def run(seconds):
            until = time.monotonic() + seconds
            while time.monotonic() < until:
                app.processEvents()
                time.sleep(.005)
        run(1)
        cpu, start = time.process_time(), time.monotonic()
        run(5)
        used = 100 * (time.process_time() - cpu) / (time.monotonic() - start)
        keys.stop()
        assert (not pet.timer.isActive()) if mode == 'paused' else pet.timer.interval() == (100 if mode == 'sleep' else 34)
        rss = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
                                      f'(Get-Process -Id {os.getpid()}).WorkingSet64'], text=True)
        print(f'{mode}: {used:.2f}% one core, {int(rss.strip()) / 2**20:.1f} MiB RSS')
    pet.shutdown()


if __name__ == '__main__':
    app = QApplication([])
    assert app.platformName() == 'windows'
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName('miga-test')
    app.setApplicationName('native')
    with tempfile.TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        window_checks(app)
        QSettings().clear()
        benchmark(app)
    print('PASS: native Qt window, input registration, session messages, menu close and preferences.')
