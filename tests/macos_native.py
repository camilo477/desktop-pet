"""Checks on a disposable Aqua session. Never request TCC or post an event."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import AppKit
import objc
from Quartz import CoreGraphics as CG
from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtWidgets import QApplication
from macos_input import current_layout
from pet import PetWindow


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class Window(PetWindow):
    frames = 0

    def render_frame(self, *args, **kwargs):
        self.frames += 1
        super().render_frame(*args, **kwargs)


def checks(w):
    backend = w.mac_input
    print('Native preflight:', bool(CG.CGPreflightListenEventAccess()), 'backend:', backend.status,
          'known input source:', current_layout(), flush=True)
    assert w.keyboard.label('MetaLeft') == '⌘'
    ns = objc.objc_object(c_void_p=int(w.winId())).window()
    assert not ns.isOpaque() and not ns.canBecomeKeyWindow()
    assert ns.styleMask() & AppKit.NSWindowStyleMaskNonactivatingPanel
    assert AppKit.NSApp().activationPolicy() == AppKit.NSApplicationActivationPolicyAccessory
    assert w.frame.toImage().pixelColor(0, 0).alpha() == 0
    w.set_always_on_top(False)
    assert ns.level() == AppKit.NSNormalWindowLevel
    w.set_always_on_top(True)
    assert ns.level() == AppKit.NSFloatingWindowLevel

    # Native permission query above. Model denial/revocation without changing TCC.
    with patch.object(CG, 'CGPreflightListenEventAccess', return_value=False):
        backend.configure(False)
        backend.configure(True)
        assert backend.status == 'denied' and not w.activity.native_pointer
        assert w.timer.isActive()
        w.animations.pet(0)
        wait(100)
        assert w.animations.pose.pet > 0
        # Feed synthetic in-memory Quartz objects directly to the adapter, never
        # post them to macOS. This checks decoding independently of TCC delivery.
        w.activity.native_pointer = True
        with patch('macos_input.secure_input', return_value=False):
            for down, repeat in ((True, False), (True, True), (False, False)):
                event = CG.CGEventCreateKeyboardEvent(None, 0, down)
                CG.CGEventSetIntegerValueField(event, CG.kCGKeyboardEventAutorepeat, int(repeat))
                backend.event(None, CG.kCGEventKeyDown if down else CG.kCGEventKeyUp, event, None)
        state = w.activity.snapshot()
        assert 'A' in state.pulses and state.new_presses == 1 and not state.any_held
        backend.configure(False)
        assert not w.activity.native_pointer and not w.activity.snapshot().pressed
    print('PASS: Cocoa panel, current source, local interaction, simulated denial and Quartz fixtures.')


def benchmark(w):
    w.set_size(300)
    for mode in ('typing', 'sleep', 'pause'):
        w.set_paused(mode == 'pause')
        w.activity.clear_input()
        keys = QTimer()
        def press():
            w.activity.key_down('A')
            w.activity.key_up('A', immediate=True)
        keys.timeout.connect(press)
        if mode == 'typing':
            keys.start(70)
        elif mode == 'sleep':
            w.animations.last_activity = time.monotonic() - 215
            for _ in range(10):
                wait(800)
                if w.animations.sleeping:
                    break
            assert w.animations.sleeping
        wall, cpu, frames = time.monotonic(), time.process_time(), w.frames
        wait(5000)
        elapsed = time.monotonic() - wall
        used = 100 * (time.process_time() - cpu) / elapsed
        keys.stop()
        rss = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())]))
        fps = (w.frames - frames) / elapsed
        assert fps == 0 if mode == 'pause' else fps > 5
        print(f'{mode}: {used:.2f}% one core, {rss/1024:.1f} MiB RSS, {fps:.1f} FPS')


if __name__ == '__main__':
    app = QApplication([])
    assert app.platformName() == 'cocoa'
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName('miga-tests')
    app.setApplicationName('macos')
    with TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        w = Window()
        w.show()
        wait(300)
        checks(w)
        benchmark(w)
        w.shutdown()
