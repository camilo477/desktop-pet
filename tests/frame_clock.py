"""Measure timer delivery, procedural frames and widget paints on a controlled CI desktop."""

import json
from collections import Counter
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
import time

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEventLoop, QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication
from pet import PetWindow


class Window(PetWindow):
    def __init__(self):
        self.frames = self.paints = 0
        self.render_time = 0.
        super().__init__()

    def render_frame(self, *args, **kwargs):
        start = time.perf_counter()
        super().render_frame(*args, **kwargs)
        self.render_time += time.perf_counter() - start
        self.frames += 1

    def paintEvent(self, event):
        self.paints += 1
        super().paintEvent(event)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def sample(window, mode):
    # Independent precise reference clock, with identical instrumentation in each run.
    times = []
    clock = QTimer()
    clock.setTimerType(Qt.TimerType.PreciseTimer)
    clock.timeout.connect(lambda: times.append(time.perf_counter()))
    keys = QTimer()

    def press():
        window.activity.key_down('A')
        window.activity.key_up('A', immediate=True)

    keys.timeout.connect(press)
    native_mask = window.mask_supported
    if mode == 'fixed-mask':
        window.mask_supported = False
    if mode == 'tap-off':
        window.mac_input.configure(False)
    if mode == 'clock':
        window.timer.stop()
    else:
        window.timer.start(34)
        if mode == 'hidden':
            window.hide()
        keys.start(70)
    wait(600)
    frames, paints, render = window.frames, window.paints, window.render_time
    start, cpu = time.perf_counter(), time.process_time()
    stages = Counter()
    originals = []
    def measure(obj, name):
        method = getattr(obj, name)
        def timed(*args, **kwargs):
            before = time.perf_counter()
            result = method(*args, **kwargs)
            stages[name] += time.perf_counter() - before
            return result
        originals.append((obj, name, method))
        setattr(obj, name, timed)

    measure(window.art, 'draw')
    measure(window.animations, 'advance')
    if window.mac_input:
        measure(window.mac_input, 'poll')
    if mode != 'typing':
        clock.start(34)
    wait(8000)
    elapsed = time.perf_counter() - start
    keys.stop()
    clock.stop()
    for obj, name, method in originals:
        setattr(obj, name, method)
    window.mask_supported = native_mask
    count = window.frames - frames
    gaps = sorted(1000 * (b-a) for a,b in zip(times, times[1:]))
    print(json.dumps(dict(mode=mode, reference_hz=round(len(times)/elapsed, 2) if times else None,
                          frame_hz=round(count/elapsed, 2), paint_hz=round((window.paints-paints)/elapsed, 2),
                          draw_mask_ms=round((window.render_time-render)*1000/max(1,count), 3),
                          stage_ms={k: round(v*1000/max(count, 1), 3) for k,v in stages.items()},
                          timer_p95_ms=round(gaps[int(.95*(len(gaps)-1))], 2) if gaps else None,
                          cpu=round(100*(time.process_time()-cpu)/elapsed, 2))), flush=True)
    if mode == 'hidden':
        window.show()


def sample_display_link(window):
    """Probe a window-paced clock before considering any native scheduling change."""
    import AppKit
    import objc
    from Foundation import NSObject, NSRunLoop, NSRunLoopCommonModes

    class FrameTarget(NSObject):
        @objc.typedSelector(b'v@:@')
        def frame_(self, link):
            window.tick()

    panel = objc.objc_object(c_void_p=int(window.winId())).window()
    target = FrameTarget.alloc().init()
    link = panel.displayLinkWithTarget_selector_(target, b'frame:')
    if link is None:
        print('No display link for the test window.', flush=True)
        return
    window.timer.stop()
    link.setPreferredFramesPerSecond_(30)
    link.addToRunLoop_forMode_(NSRunLoop.mainRunLoop(), NSRunLoopCommonModes)
    frames, paints = window.frames, window.paints
    start, cpu = time.perf_counter(), time.process_time()
    try:
        wait(8000)
    finally:
        link.invalidate()
    elapsed = time.perf_counter() - start
    print(json.dumps(dict(mode='display-link', frame_hz=round((window.frames-frames)/elapsed, 2),
                          paint_hz=round((window.paints-paints)/elapsed, 2),
                          cpu=round(100*(time.process_time()-cpu)/elapsed, 2),
                          visible=bool(panel.occlusionState() & AppKit.NSWindowOcclusionStateVisible))),
          flush=True)


if __name__ == '__main__':
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName('miga-tests')
    app.setApplicationName('clock')
    random.seed(57)
    with TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        QSettings().setValue('size', 300)
        window = Window()
        window.show()
        wait(250)
        modes = ['clock', 'typing', 'second-clock', 'fixed-mask', 'hidden']
        if window.mac_input:
            modes.append('tap-off')
        for mode in modes:
            sample(window, mode)
        if window.mac_input:
            sample_display_link(window)
        window.shutdown()
