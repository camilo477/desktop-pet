"""Essential checks: run with .venv/bin/python tests/smoke.py."""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from activity import Activity
from animations import Animations
from pet import PetWindow, visible_position


def check_window() -> None:
    pet = PetWindow()
    pet.show()
    QTest.qWait(120)
    assert pet.size() == QSize(200, 200)
    assert pet.frame.toImage().pixelColor(0, 0).alpha() == 0
    assert not pet.last_mask.contains(QPoint(0, 0))
    assert pet.last_mask.contains(QPoint(95, 95))
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pet.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    menu = pet.build_menu()
    assert [action.text() for action in menu.actions()] == [
        "Tamaño", "Siempre visible", "Reaccionar a actividad", "Pausar animaciones", "Salir",
    ]
    for size in (150, 300, 200):
        pet.set_size(size)
        assert pet.size() == QSize(size, size)
        assert pet.frame.toImage().pixelColor(0, 0).alpha() == 0
    pet.set_paused(True)
    before = pet.animations.time
    QTest.qWait(100)
    assert pet.animations.time == before and not pet.timer.isActive()
    assert not pet.activity.enabled
    assert pet.build_menu().actions()[3].text() == "Reanudar animaciones"
    pet.move(100, 100)
    start = pet.pos()
    QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(95, 95))
    QTest.mouseMove(pet, QPoint(120, 105), 30)
    QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(120, 105))
    assert pet.pos() != start
    pet.set_reactions(False)
    pet.set_always_on_top(False)
    pet.set_paused(False)
    QTest.qWait(100)
    assert pet.animations.time > before
    pet.shutdown()
    restored = PetWindow()
    assert not restored.reactions and not restored.paused and not restored.always_on_top
    assert restored.pos() == pet.pos()
    restored.shutdown()
    pet.close()
    restored.close()


def check_motion_and_screens() -> None:
    areas = [QRect(-1920, 0, 1920, 1080), QRect(0, 0, 1920, 1080)]
    assert visible_position(QPoint(5000, 5000), QSize(200, 200), areas) == QPoint(1720, 880)
    assert visible_position(QPoint(-1800, 300), QSize(200, 200), areas) == QPoint(-1800, 300)
    animation = Animations()
    for _ in range(30):
        pose = animation.advance(1 / 30, 2.0, Activity(keyboard=2.0), (4.0, -4.0))
    assert pose.typing > 0.9 and pose.left_paw > 0
    assert -1 <= pose.gaze_x <= 1 and -1 <= pose.gaze_y <= 1
    for _ in range(90):
        pose = animation.advance(1 / 30)
    assert pose.typing < 0.01 and pose.left_paw < 0.01
    animation.pet()
    assert animation.advance(0.14).blink > 0.9


if __name__ == "__main__":
    with TemporaryDirectory(prefix="desktop-pet-checks-") as directory:
        QCoreApplication.setOrganizationName("desktop-pet-checks")
        QCoreApplication.setApplicationName("smoke")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        app = QApplication([])
        check_window()
        check_motion_and_screens()
    print("PASS: rendering, mask, sizes, pause, drag, menu, preferences, animations and screen bounds.")
