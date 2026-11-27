"""Opt-in hardware check: reports event categories, never key identities or text."""

import argparse
import fcntl
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QObject, QTimer
from activity import ActivityMonitor
from animations import Animations
from linux_input import LinuxInput


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-seconds', type=int, default=0)
    args = parser.parse_args()
    assert 0 <= args.observe_seconds <= 60
    app = QCoreApplication([])
    pet = QObject()
    pet.kwin = None
    pet.activity = ActivityMonitor(False)
    pet.activity.set_enabled(True)
    backend = LinuxInput(pet)
    animation = Animations()
    observed = set()
    try:
        backend.configure(True)
        assert backend.session_active, 'No active unlocked login session'
        assert backend.keyboard_count > 0, 'No readable physical keyboard'
        assert backend.pointer_count > 0, 'No readable physical mouse'
        for device in backend.devices.values():
            assert fcntl.fcntl(device.handle.fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        print('PASS: active session, keyboard and mouse opened strictly read-only', flush=True)
        def tick():
            sample = pet.activity.snapshot()
            pose = animation.advance(.034, time.monotonic(), sample)
            categories = set()
            if sample.new_presses and pose.pressed:
                categories.add('keyboard -> painted key')
            if sample.motion_x or sample.motion_y:
                categories.add('mouse movement -> paw')
            if sample.scroll_x or sample.scroll_y:
                categories.add('scroll -> paw')
            for category in categories - observed:
                print('Observed:', category, flush=True)
            observed.update(categories)
        if args.observe_seconds:
            timer = QTimer()
            timer.timeout.connect(tick)
            timer.start(34)
            QTimer.singleShot(args.observe_seconds * 1000, app.quit)
            app.exec()
            print('Observation complete:', ', '.join(sorted(observed)) or 'no physical events during this interval', flush=True)
    finally:
        backend.configure(False)
        pet.activity.stop()
    assert not backend.devices and not pet.activity.snapshot().held
    print('PASS: shutdown closes all hardware handles and clears held keys', flush=True)
