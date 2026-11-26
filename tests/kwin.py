"""A native KWin instance, with synthetic layout switches in a disposable CI bus."""

import os
from pathlib import Path
import subprocess
import sys
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pet import PetWindow


def wait_for(predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        loop = QEventLoop()
        QTimer.singleShot(50, loop.quit)
        loop.exec()
    assert predicate()


if __name__ == '__main__':
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert os.environ['WAYLAND_DISPLAY'] == 'miga-ci'
    assert Path(os.environ['XDG_RUNTIME_DIR']).parent == Path(os.environ['RUNNER_TEMP'])
    app = QApplication([])
    app.setOrganizationName('miga-test')
    app.setApplicationName('kwin')
    w = PetWindow()
    w.show()
    try:
        wait_for(lambda: w.wayland.layout_source == 'KDE' and w.detected_layout == 'us')
        for index, layout in ((1, 'de'), (2, 'dvorak'), (0, 'us')):
            subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.kde.keyboard',
                            '--object-path', '/Layouts', '--method', 'org.kde.KeyboardLayouts.setLayout',
                            str(index)], check=True, stdout=subprocess.DEVNULL)
            wait_for(lambda: w.keyboard.layout == layout)
        wait_for(lambda: w.wayland.selected()[0] is not None)
        wait_for(lambda: w.wayland.idle(time.monotonic()) >= 15, timeout=20)
        print('PASS: native KWin layout changes and compositor idle edge via', w.wayland.selected()[0])
        assert not w.animations.pose.pressed and not w.animations.pose.contacts
        for size in (150, 200, 300):
            w.set_size(size)
            assert w.width() == size and not w.frame.toImage().pixelColor(0, 0).alpha()
        w.set_paused(True)
        assert not w.timer.isActive() and not w.wayland.session
        w.set_paused(False)
        wait_for(lambda: w.wayland.selected()[0] is not None)
    finally:
        w.close()
