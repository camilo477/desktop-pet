"""Exercise direct gestures through the widget and inspect its painted output."""

from dataclasses import replace
import math
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QCursor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from activity import Activity, ActivityMonitor, KeyHint
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
    # X11 supplies a global integer QPoint even on a fractional-size drawing.
    window.global_input = True
    window.activity.pointer_moved(1, 1)
    window.activity.pointer_moved(2, 1)
    with patch.object(QCursor, 'pos', return_value=window.mapToGlobal(QPoint(105, 63))):
        window.tick()
    assert window.animations.near_face
    window.global_input = window.activity.global_input
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


def check_drag(window):
    window.timer.stop()
    # The same movement source drives manual moves and compositor position updates.
    for source in ('sleep', 'wash', 'typing'):
        a = Animations()
        a.last_activity = 0
        if source == 'sleep':
            for i in range(80):
                a.advance(.1, 200 + i / 10)
            assert a.sleeping
        elif source == 'wash':
            a.start_idle('wash')
            for i in range(52):
                a.advance(1 / 30, 20 + i / 30)
            assert a.pose.groom > .5
        else:
            for i in range(12):
                a.advance(1 / 30, i / 30, Activity(held=frozenset({'A'})))
        before = replace(a.pose)
        shell = (before.mouse_dx, before.mouse_dy)
        a.lift()
        tick = 0
        for dx, dy in ((2, 0), (35, 0), (-35, 0), (0, 42), (0, -42), (36, -32), (0, 0)):
            for i in range(23):
                tick += 1
                now = 210 + tick / 30
                # Simulate a key being tapped while the front paws are lifted.
                inputs = Activity(keyboard=now, pulses=frozenset({'P'}), latest=KeyHint('P', now),
                                  mouse=now, motion_x=dx, motion_y=dy)
                pose = a.advance(1 / 30, now, inputs, drag_delta=(dx, dy))
                assert pose.pressed == {'P'} and all(paw.goal == 'lift' for paw in a.paws)
                assert (pose.mouse_dx, pose.mouse_dy) == shell and not a.mouse_contact
            assert pose.lift > 6 and pose.left_y < 143 and pose.right_y < 143
            for component, delta in ((pose.sway_x, dx), (pose.sway_y, dy)):
                if delta:
                    assert component * delta < 0 and abs(component) < 6.3
                else:
                    assert abs(component) < .005
            frame = painted(window, pose)
            assert frame != painted(window, replace(pose, lift=0, left_y=before.left_y,
                                                   right_y=before.right_y))
            assert frame != painted(window, replace(pose, pressed=frozenset()))
        assert pose.sleep < .01 and pose.groom < .01

    # Include the last fast-motion frame, then redirect at the very next frame.
    for typing, pointer, scroll in ((True, False, False), (False, True, False),
                                    (False, False, True), (True, True, False), (False, False, False)):
        a = Animations()
        a.lift()
        for i in range(12):
            a.advance(1 / 30, i / 30, drag_delta=(45, -20))
        before = replace(a.pose)
        a.put_down(.40)
        hint = KeyHint('A', .41) if typing else KeyHint('P', .39)
        inputs = Activity(keyboard=.41 if typing else .39, pulses=frozenset({'A'}) if typing else frozenset(),
                          latest=hint, mouse=.41 if pointer else -math.inf,
                          motion_x=12 if pointer else 0, scroll=.41 if scroll else -math.inf,
                          scroll_y=int(scroll))
        pose = a.advance(1 / 30, .42, inputs)
        image = painted(window, pose)
        assert 0 < pose.lift < before.lift and pose.sway_x < 0
        assert all(paw.goal != 'P' and paw.goal != 'lift' for paw in a.paws)
        if typing:
            assert 'A' in (pose.left_key, pose.right_key)
            assert image != painted(window, replace(pose, pressed=frozenset()))
        if pointer or scroll:
            assert a.paws[0].goal == 'mouse' and pose.left_x < before.left_x
        assert image != painted(window, replace(pose, left_x=before.left_x, left_y=before.left_y,
                                                right_x=before.right_x, right_y=before.right_y))
        for i in range(40):
            pose = a.advance(1 / 30, .45 + i / 30)
        assert pose.lift == pose.sway_x == pose.sway_y == 0

    monitor = ActivityMonitor(False)
    monitor.set_enabled(True)
    monitor.pointer_moved(10, 12)
    monitor.pointer_moved(32, 42)
    monitor.set_dragging(True)
    monitor.pointer_moved(470, 120)
    monitor.key_down('A')
    state = monitor.snapshot()
    assert state.motion_x == state.motion_y == 0 and state.held == {'A'}
    monitor.set_dragging(False)
    monitor.pointer_moved(473, 119)
    state = monitor.snapshot()
    assert (state.motion_x, state.motion_y) == (3, -1)
    monitor.stop()

    window.animations = Animations()
    window.render_frame()
    window.move(120, 120)
    origin = window.pos()
    anchor = window.art.head_position.toPoint()
    window.set_paused(False)
    QTest.mousePress(window, LEFT, pos=anchor)
    QTest.mouseMove(window, anchor + QPoint(37, 18))
    QTest.qWait(220)
    assert window.pos() == origin + QPoint(37, 18)
    assert window.animations.pose.lift > 4 and window.drag_sample is not None
    QTest.mouseRelease(window, LEFT, pos=anchor)
    released = window.pos()
    QTest.qWait(650)
    assert window.pos() == released and not window.animations.carried and window.drag_sample is None
    window.set_paused(True)
    frozen = window.frame.toImage()
    QTest.mousePress(window, LEFT, pos=anchor)
    QTest.mouseMove(window, anchor + QPoint(27, -12))
    QTest.mouseRelease(window, LEFT, pos=anchor)
    assert window.pos() == released + QPoint(27, -12)
    assert window.frame.toImage() == frozen and not window.timer.isActive()


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
        check_drag(window)
        window.shutdown()
    print('PASS: painted regions at three sizes, sleeping touches, held pats, curiosity, measured drag, immediate release input and pause.')
