"""Opt-in native placement check; only disposable Miga windows are changed."""

import os
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEventLoop, QPoint, QRect, QSettings, QTimer
from PySide6.QtWidgets import QApplication
from pet import PetWindow


def wait_for(predicate, window, timeout=6):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        loop = QEventLoop()
        QTimer.singleShot(40, loop.quit)
        loop.exec()
    assert predicate(), (window.kwin.error, window.kwin.closed,
                         window.kwin.active, window.kwin.screen_name,
                         window.window_position(), window.size())


def check_placement(app):
    settings = QSettings()
    settings.setValue('size', 200)
    settings.setValue('wayland/screen', app.primaryScreen().name())
    settings.setValue('wayland/position', QPoint(60, 80))
    window = PetWindow()
    window.show()
    try:
        wait_for(lambda: window.kwin.active, window)
        wait_for(lambda: window.kwin.pointer is not None, window)
        print('KWin placement active:', window.kwin.screen_name, window.kwin.position, flush=True)
        print('Input session:', window.linux_input.session_active,
              'keyboards:', window.linux_input.keyboard_count,
              'mice:', window.linux_input.pointer_count, 'KDE pointer available', flush=True)
        wait_for(lambda: window.wayland.selected()[0] is not None, window)
        print('Activity:', window.wayland.selected()[0], 'layout:', window.wayland.layout_source, flush=True)
        primary_area = app.primaryScreen().availableGeometry()
        assert window.window_position() == primary_area.topLeft() + QPoint(60, 80)
        for screen in app.screens():
            window.move_to_screen(screen.name())
            wait_for(lambda: window.kwin.applied_generation == window.kwin.generation
                     and window.kwin.screen_name == screen.name(), window)
            print('Moved:', screen.name(), window.window_position(), 'area:', screen.availableGeometry(), flush=True)
            for size in (150, 300, 200):
                window.set_size(size)
                wait_for(lambda: window.kwin.geometry.size() == window.size()
                         and screen.availableGeometry().contains(window.kwin.geometry), window)
                # Let the compositor acknowledge the asynchronous Wayland resize.
                loop = QEventLoop()
                QTimer.singleShot(150, loop.quit)
                loop.exec()
                assert screen.availableGeometry().contains(QRect(window.window_position(), window.size()))
                assert window.frame.width() == round(size * window.devicePixelRatioF())
            print('PASS: monitor', screen.name(), screen.geometry(), 'three sizes', flush=True)
        window.set_paused(True)
        window.move_to_screen(app.primaryScreen().name())
        wait_for(lambda: window.kwin.applied_generation == window.kwin.generation
                 and window.kwin.screen_name == app.primaryScreen().name(), window)
        assert not window.timer.isActive() and window.wayland.session is None
        window.set_paused(False)
        wait_for(lambda: window.wayland.layout_source == 'KDE', window)
        position = window.window_position()
        for above in (False, True):
            window.set_always_on_top(above)
            wait_for(lambda: window.kwin.applied_generation == window.kwin.generation
                     and window.window_position() == position and window.kwin.above == above, window)
        window.save_preferences()
        assert settings.value('wayland/screen') == window.kwin.screen_name
        saved = settings.value('wayland/position')
        assert isinstance(saved, QPoint)
        window.frame.save('/tmp/miga-fedora-check.png')
        print('PASS: saved placement, stacking commands, transparent native rendering', flush=True)
    finally:
        window.close()
    # The next instance restores the actual compositor position, not Qt's (0, 0).
    restored = PetWindow()
    restored.show()
    try:
        wait_for(lambda: restored.kwin.active, restored)
        assert restored.window_position() == position
        print('PASS: position restored after closing and reopening', flush=True)
    finally:
        restored.close()


if __name__ == '__main__':
    assert '--desktop' in sys.argv, 'Pass --desktop to show temporary test windows on your KDE session'
    os.environ['QT_QPA_PLATFORM'] = 'wayland'
    app = QApplication([])
    app.setOrganizationName('miga-test')
    app.setApplicationName('kwin-desktop')
    app.setQuitOnLastWindowClosed(False)
    with TemporaryDirectory(prefix='miga-desktop-test-') as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        check_placement(app)
