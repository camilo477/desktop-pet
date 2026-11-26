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

from PySide6.QtCore import QSettings, QSignalBlocker, Qt
from PySide6.QtWidgets import QApplication, QWidget

from appearance import Appearance
from pet import PetWindow
from windows_input import Device, Key, Mouse, foreground, function, user


def exercise_raw_delivery(app, pet, target):
    """Send one controlled modifier gesture to our own foreground test window."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    from PySide6.QtTest import QTest

    class KeyboardInput(C.Structure):
        _fields_ = [('vk', W.WORD), ('scan', W.WORD), ('flags', W.DWORD),
                    ('time', W.DWORD), ('extra', C.c_size_t)]

    class InputData(C.Union):
        # INPUT has a 32-byte MOUSEINPUT union member on x64.
        _fields_ = [('key', KeyboardInput), ('padding', C.c_byte * 32)]

    class Input(C.Structure):
        _fields_ = [('kind', W.DWORD), ('data', InputData)]

    send = function(user, 'SendInput', W.UINT, W.UINT, C.POINTER(Input), C.c_int)
    press = Input(1, InputData(key=KeyboardInput(scan=0x2a, flags=8)))
    release = Input(1, InputData(key=KeyboardInput(scan=0x2a, flags=10)))
    pet.timer.stop()
    app.processEvents()
    pet.activity.snapshot()
    assert foreground() == int(target.winId())
    with QSignalBlocker(pet):
        gesture = (Input * 3)(press, press, release)
        assert send(3, gesture, C.sizeof(Input)) == 3
        QTest.qWait(65)
        activity = pet.activity.snapshot()
    pet.timer.start()
    assert foreground() == int(target.winId())
    assert activity.new_presses == 1 and 'ShiftLeft' in activity.pressed
    assert not activity.any_held and target.presses and target.releases
    print('PASS: Win32 delivered synthetic make/repeat/break to Raw Input and the foreground widget.')


def hit_tests(app):
    from PySide6.QtTest import QTest
    class Target(QWidget):
        presses = releases = 0

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Shift:
                self.presses += 1

        def keyReleaseEvent(self, event):
            if event.key() == Qt.Key.Key_Shift:
                self.releases += 1

    background = Target()
    background.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    background.setGeometry(25, 25, 400, 380)
    background.show()
    background.activateWindow()
    background.setFocus()
    QTest.qWait(120)
    before = foreground()
    pet = PetWindow()
    pet.set_size(200)
    pet.move(45, 50)
    pet.show()
    QTest.qWait(120)
    hwnd = int(pet.winId())
    assert foreground() == before and before != hwnd
    hit = function(user, 'WindowFromPoint', W.HWND, W.POINT)
    to_screen = function(user, 'ClientToScreen', W.BOOL, W.HWND, C.POINTER(W.POINT))
    rect = W.RECT()
    bounds = function(user, 'GetClientRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
    assert bounds(hwnd, C.byref(rect))
    scale = rect.right / pet.width()
    assert abs(scale - pet.devicePixelRatioF()) < .01

    def target(x, y):
        point = W.POINT(round(x * scale), round(y * scale))
        assert to_screen(hwnd, C.byref(point))
        return hit(point)

    if '--dpi' not in sys.argv:
        exercise_raw_delivery(app, pet, background)
    for form, coat, paused in (('100', 'original', False), ('60', 'calico', True)):
        pet.configure_keyboard(form=form)
        pet.configure_appearance(Appearance(coat, 'auto', 'auto'))
        pet.set_paused(paused)
        QTest.qWait(90)
        head = pet.art.head_position
        assert target(head.x(), head.y()) == hwnd
        assert target(2, 2) == int(background.winId())
        assert foreground() == before
    print(f'PASS: native opaque and transparent hit targets, foreground preserved, scale {scale:g}.')
    pet.close()
    background.close()


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
    from PySide6.QtCore import QEventLoop, QTimer
    class MeasuredWindow(PetWindow):
        frames = 0

        def render_frame(self, *args, **kwargs):
            self.frames += 1
            super().render_frame(*args, **kwargs)

    pet = MeasuredWindow()
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
            loop = QEventLoop()
            QTimer.singleShot(seconds * 1000, loop.quit)
            loop.exec()
        run(1)
        cpu, start, frames = time.process_time(), time.monotonic(), pet.frames
        run(5)
        elapsed = time.monotonic() - start
        used = 100 * (time.process_time() - cpu) / elapsed
        rate = (pet.frames - frames) / elapsed
        keys.stop()
        assert (not pet.timer.isActive()) if mode == 'paused' else pet.timer.interval() == (100 if mode == 'sleep' else 34)
        rss = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
                                      f'(Get-Process -Id {os.getpid()}).WorkingSet64'], text=True)
        assert rate == 0 if mode == 'paused' else rate > (6 if mode == 'sleep' else 15)
        print(f'{mode}: {used:.2f}% one core, {int(rss.strip()) / 2**20:.1f} MiB RSS, {rate:.1f} FPS')
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
        hit_tests(app)
        QSettings().clear()
        if '--dpi' not in sys.argv:
            window_checks(app)
            QSettings().clear()
            benchmark(app)
    print('PASS: native Qt window, input registration, session messages, menu close and preferences.')
