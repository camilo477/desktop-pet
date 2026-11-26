"""Native Aqua checks. Session delivery uses our own foreground test window in CI."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import traceback
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import AppKit
import objc
from Quartz import CoreGraphics as CG
from PySide6.QtCore import QEventLoop, QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget
from appearance import Appearance
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


def desktop_checks(w):
    # The only foreground target is this runner's own test window.
    class Target(QWidget):
        received = False
        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_A:
                self.received = True
    target = Target()
    target.setGeometry(60, 60, 400, 360)
    target.show()
    w.move(85, 90)
    w.show()
    wait(150)
    window = objc.objc_object(c_void_p=int(w.winId())).window()
    behind = objc.objc_object(c_void_p=int(target.winId())).window()
    view = window.contentView()

    def hit(x, y):
        point = view.convertPoint_toView_((x, y if view.isFlipped() else w.height() - y), None)
        screen = window.convertPointToScreen_(point)
        return AppKit.NSWindow.windowNumberAtPoint_belowWindowWithWindowNumber_(screen, 0)

    for size, coat, form in ((150, 'white', '60'), (300, 'calico', '75'), (200, 'original', '100')):
        w.set_size(size)
        w.configure_appearance(Appearance(coat))
        w.configure_keyboard(form=form)
        w.move(85, 90)
        wait(80)
        head = w.art.head_position * (size / 200)
        assert hit(head.x(), head.y()) == window.windowNumber(), 'Opaque head must receive hits'
        assert hit(2, 2) == behind.windowNumber(), 'Transparent corner must expose the window below'
    if (os.environ.get('GITHUB_ACTIONS') == 'true' and w.mac_input.status == 'active'
            and CG.CGPreflightPostEventAccess()):
        app = AppKit.NSApplication.sharedApplication()
        target.activateWindow()
        app.activateIgnoringOtherApps_(True)
        behind.makeKeyAndOrderFront_(None)
        wait(150)
        if app.isActive() and app.keyWindow() == behind:
            w.timer.stop()
            QApplication.processEvents()
            w.activity.snapshot()
            from PySide6.QtCore import QSignalBlocker
            with QSignalBlocker(w):
                for down in (True, False):
                    event = CG.CGEventCreateKeyboardEvent(None, 0, down)
                    CG.CGEventSetTimestamp(event, time.monotonic_ns())
                    assert app.isActive() and app.keyWindow() == behind
                    CG.CGEventPost(CG.kCGSessionEventTap, event)
                wait(80)
                state = w.activity.snapshot()
            assert target.received and state.new_presses == 1 and not state.any_held, (
                target.received, state.new_presses, state.any_held)
            print('PASS: synthetic session events reached the real listen-only tap and our foreground window.')
            w.timer.start(34)
        else:
            print('Session delivery untested: the runner did not foreground the controlled target.')
    target.close()
    print('PASS: native WindowServer hit targets on the cat and behind its transparent corner.')


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
    desktop_checks(w)

    # Native permission query above. Model denial/revocation without changing TCC.
    with patch.object(CG, 'CGPreflightListenEventAccess', return_value=False):
        if backend.tap is not None:
            w.activity.key_down('X', (7,))
            backend.held.add(7)
            backend.next_check = 0
            backend.poll(time.monotonic())
            assert backend.tap is None and not w.activity.snapshot().any_held
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
                CG.CGEventSetTimestamp(event, time.monotonic_ns())
                CG.CGEventSetIntegerValueField(event, CG.kCGKeyboardEventAutorepeat, int(repeat))
                backend.event(None, CG.kCGEventKeyDown if down else CG.kCGEventKeyUp, event, None)
            wheel = CG.CGEventCreateScrollWheelEvent(None, CG.kCGScrollEventUnitLine, 2, 1, -2)
            CG.CGEventSetTimestamp(wheel, time.monotonic_ns())
            backend.event(None, CG.kCGEventScrollWheel, wheel, None)
        state = w.activity.snapshot()
        assert (state.scroll_x, state.scroll_y) == (-2, 1)
        assert ('A' in state.pulses, state.new_presses, state.any_held) == (True, 1, False), (
            'A' in state.pulses, state.new_presses, state.any_held, bool(backend.inactive), w.activity.enabled)
        with patch('macos_input.secure_input', return_value=False):
            caps = CG.CGEventCreateKeyboardEvent(None, 57, True)
            for flags in (CG.kCGEventFlagMaskAlphaShift, CG.kCGEventFlagMaskAlphaShift, 0):
                CG.CGEventSetTimestamp(caps, time.monotonic_ns())
                CG.CGEventSetFlags(caps, flags)
                backend.event(None, CG.kCGEventFlagsChanged, caps, None)
            state = w.activity.snapshot()
            assert state.new_presses == 2 and not state.any_held
        backend.configure(False)
        assert not w.activity.native_pointer and not w.activity.snapshot().pressed
    print('PASS: Cocoa panel, current source, local interaction, simulated denial and Quartz fixtures.')


def samples(w):
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
            yield 800
        elif mode == 'sleep':
            w.animations.last_activity = time.monotonic() - 215
            for _ in range(10):
                yield 800
                if w.animations.sleeping:
                    break
            assert w.animations.sleeping
        wall, cpu, frames = time.monotonic(), time.process_time(), w.frames
        yield 5000
        elapsed = time.monotonic() - wall
        used = 100 * (time.process_time() - cpu) / elapsed
        keys.stop()
        rss = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())]))
        fps = (w.frames - frames) / elapsed
        assert fps == 0 if mode == 'pause' else fps > 5
        print(f'{mode}: {used:.2f}% one core, {rss/1024:.1f} MiB RSS, {fps:.1f} FPS')


def benchmark(w):
    measurements = samples(w)
    def advance():
        try:
            delay = next(measurements)
        except StopIteration:
            print('PASS: all three native frame samples.', flush=True)
            w.shutdown()
            QApplication.quit()
        except Exception:
            traceback.print_exc()
            QApplication.exit(1)
        else:
            QTimer.singleShot(delay, advance)
    QTimer.singleShot(0, advance)
    return QApplication.instance().exec()


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
        sys.exit(benchmark(w))
