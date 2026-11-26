"""Exercise direct gestures through the widget and inspect its painted output."""

from dataclasses import replace
import math
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from activity import Activity
from animations import Animations, Pose
from pet import PetWindow

LEFT = Qt.MouseButton.LeftButton


def painted(window, pose):
    image = QImage(window.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.scale(window.width() / 200, window.height() / 200)
    window.art.draw(painter, pose)
    painter.end()
    return image


def visible_point(window, region):
    # Find an interior pixel of the requested topmost painted region.
    scale = window.width() / 200
    image = window.frame.toImage()
    for name, path in reversed(window.art.hits):
        if name != region:
            continue
        bounds = path.boundingRect().toAlignedRect()
        for y in range(bounds.top(), bounds.bottom() + 1):
            for x in range(bounds.left(), bounds.right() + 1):
                px = QPoint(round(x * scale), round(y * scale))
                point = QPointF(px) / scale
                if all(window.art.region_at(point + offset) == region for offset in
                       (QPointF(), QPointF(-1, 0), QPointF(1, 0), QPointF(0, 1), QPointF(0, -1))):
                    assert image.pixelColor(px).alpha() > 100
                    return px
    raise AssertionError(f'No visible {region} at {window.width()} px')


def check_touch(window):
    window.set_reactions(False)
    window.timer.stop()
    for size, yaw in ((150, -.9), (200, 0), (300, .9)):
        window.set_size(size)
        window.animations.pose = Pose(head_x=yaw, head_tilt=yaw * 8, tail=.9, tail_phase=2,
                                      tail_touch=.35, balance_x=yaw * 8)
        window.render_frame()
        for region in ('head', 'ear-left', 'ear-right', 'torso', 'tail', 'paw', 'keyboard', 'mouse'):
            visible_point(window, region)
        assert window.art.region_at(QPointF(3, 3)) is None

    window.set_size(200)
    for region in ('ear-left', 'ear-right', 'tail', 'head'):
        animation = window.animations = Animations()
        animation.last_activity = 0
        for i in range(80):
            animation.advance(.1, 200 + i * .1)
        window.render_frame()
        point = visible_point(window, region)
        QTest.mouseClick(window, LEFT, pos=point)
        QTest.mouseClick(window, LEFT, pos=point)
        for i in range(4):
            pose = animation.advance(1 / 30, 209 + i / 30)
        assert pose.sleep < .9
        actual = painted(window, pose)
        if region == 'head':
            assert pose.pet > .9 and pose.blink > .9
        elif region == 'tail':
            assert 0 < pose.tail_touch < 1 and pose.pet == 0
            assert actual != painted(window, replace(pose, tail_touch=0))
        else:
            field = 'ear_left' if region == 'ear-left' else 'ear_right'
            assert abs(getattr(pose, field)) > 3 and pose.pet == 0
            assert actual != painted(window, replace(pose, **{field: 0}))

    animation = window.animations = Animations()
    window.render_frame()
    point = window.art.head_position.toPoint()
    window.set_paused(False)
    QTest.mousePress(window, LEFT, pos=point)
    QTest.qWait(720)
    assert animation.pet_held and animation.pose.blink > .88
    onset = animation.pet_start
    QTest.qWait(350)
    assert animation.pet_start == onset and animation.pose.pet > .85
    QTest.mouseRelease(window, LEFT, pos=point)
    assert not animation.pet_held and animation.pose.pet > .85
    QTest.qWait(850)
    assert animation.pose.pet == 0 and not window.activity.enabled

    QTest.mousePress(window, LEFT, pos=point)
    QTest.qWait(620)
    assert animation.pet_held
    QTest.mouseMove(window, point + QPoint(QApplication.startDragDistance() + 2, 3))
    assert window.dragging and not animation.pet_held
    QTest.mouseRelease(window, LEFT, pos=point)
    assert not window.dragging and animation.pet_start != animation.time

    animation = Animations()
    for x, expected in ((70, False), (46, True), (54, True), (65, False)):
        pose = animation.advance(.04, animation.time, face_offset=(x, -8))
        assert animation.near_face == expected
    for i in range(35):
        pose = animation.advance(1 / 30, 2 + i / 30, face_offset=(-25, -12))
    assert pose.gaze_x < -.4 and pose.expression.pupil > 3 and pose.mouse == 0
    for i in range(15):
        now = 4 + i / 30
        pose = animation.advance(1 / 30, now, Activity(keyboard=now, held=frozenset({'A'})),
                                 face_offset=(-25, -12))
    assert pose.gaze_y > .85 and pose.mouse == 0


if __name__ == '__main__':
    with TemporaryDirectory(prefix='miga-touch-') as directory:
        app = QApplication([])
        app.setOrganizationName('miga-tests')
        app.setApplicationName('direct')
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        window = PetWindow()
        window.show()
        check_touch(window)
        window.shutdown()
    print('PASS: painted regions at three sizes, sleeping touches, held pats, drag threshold and proximity.')
