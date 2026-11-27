"""Essential checks: run with .venv/bin/python tests/smoke.py."""

import fcntl
import gc
from dataclasses import replace
import math
import os
from pathlib import Path
import random
import sys
import time
import weakref
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QCursor, QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from activity import Activity, ActivityMonitor, KeyHint
from animations import Animations, Pose, SLEEP_AFTER
from keyboard_layout import Keyboard, KEY_TRAVEL
from x11_keyboard import POSITIONS

from linux_runtime import instance_busy
from pet import PetWindow, visible_position
from anatomy import BodyGeometry, FaceGeometry, MAX_REACH
from character import CatArt
from personality import CALM, CURIOUS, EXCITED, FOCUSED, IMPATIENT, SURPRISED


DEFAULT = Keyboard()
BY_ID = DEFAULT.by_id
KEYS = tuple(BY_ID.values())
BOARD = DEFAULT.board
LEFT_REST, RIGHT_REST = DEFAULT.rest
MOUSE_REST = DEFAULT.mouse_rest


def check_window() -> None:
    cursor = QCursor.pos()
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
        "Tamaño", "Pantalla", "Teclado", "Apariencia", "Siempre visible", "Reaccionar a actividad", "Pausar animaciones", "Salir",
    ]
    for size in (150, 300, 200):
        pet.set_size(size)
        assert pet.size() == QSize(size, size)
        assert pet.frame.toImage().pixelColor(0, 0).alpha() == 0
    pet.activity.key_down('A')
    pet.animations.advance(1 / 30, 1, pet.activity.snapshot())
    assert 'A' in pet.animations.pose.pressed
    pet.set_paused(True)
    assert not pet.animations.pose.pressed and not pet.activity.snapshot().held
    before = pet.animations.time
    QTest.qWait(100)
    assert pet.animations.time == before and not pet.timer.isActive()
    assert not pet.activity.enabled
    assert pet.build_menu().actions()[6].text() == "Reanudar animaciones"
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
    # Direct head pats work even with global reactions disabled.
    QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(101, 76))
    QTest.qWait(220)
    assert pet.animations.pose.pet > .9 and pet.animations.pose.blink > .9
    pat = pet.animations.pet_start
    QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(118, 125))
    assert pet.animations.pet_start == pat
    QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(101, 76))
    QTest.mouseMove(pet, QPoint(130, 90), 30)
    QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(130, 90))
    assert pet.animations.pet_start == pat
    pet.shutdown()
    restored = PetWindow()
    assert not restored.reactions and not restored.paused and not restored.always_on_top
    assert restored.pos() == pet.pos()
    restored.shutdown()
    pet.close()
    restored.close()
    QCursor.setPos(cursor)


def check_window_lifecycle():
    pet = PetWindow()
    pet.set_reactions(True)
    now = time.monotonic()
    pet.animations.advance(.034, now - 11)
    pet.animations.last_activity = now - 220
    for i in range(100):
        pet.animations.advance(.1, now - 10 + i / 10)
    assert pet.animations.sleeping
    pet.timer.start(100)
    pet.last_frame = time.monotonic()
    pet.activity.key_down('A')
    # Deliver just the queued notice, before either the old or new timer is due.
    QApplication.processEvents()
    assert pet.animations.pose.pressed == {'A'} and pet.timer.interval() == 34
    assert any(paw.goal == 'A' for paw in pet.animations.paws)
    pet.shutdown()
    ref = weakref.ref(pet)
    del pet
    QApplication.processEvents()
    gc.collect()
    assert ref() is None, 'The application must release a closed window and its graphics'


def check_motion_and_screens() -> None:
    areas = [QRect(-1920, 0, 1920, 1080), QRect(0, 0, 1920, 1080)]
    assert visible_position(QPoint(5000, 5000), QSize(200, 200), areas) == QPoint(1720, 880)
    assert visible_position(QPoint(-1800, 300), QSize(200, 200), areas) == QPoint(-1800, 300)
    assert len({key.identifier for key in KEYS}) == len(KEYS)
    assert len(KEYS) == 105
    for identifier in ('F1', 'F12', 'PrintScreen', 'ScrollLock', 'Pause', 'NumLock',
                       'Insert', 'Delete', 'Home', 'End', 'PageUp', 'PageDown',
                       'NumpadEnter', 'Numpad0', 'Numpad9', 'MetaRight', 'CtrlRight'):
        assert identifier in POSITIONS.values()
    assert POSITIONS['KPEN'] == 'NumpadEnter' and POSITIONS['RTRN'] == 'Enter'
    assert POSITIONS['KP1'] == 'Numpad1' and POSITIONS['AE01'] == 'Digit1'
    assert Keyboard(layout='latam').label('Semicolon') == 'Ñ'
    assert BY_ID['Space'].contact[1] < BY_ID['F1'].contact[1]
    assert BY_ID['P'].preferred_paw == 0 and BY_ID['A'].preferred_paw == 1
    _, _, ux, uy, vx, vy = BY_ID['P'].label_basis
    assert ux < 0 and vy < 0 and ux * vy - uy * vx > 0  # Rotation, without reflection.
    animation = Animations()
    now = 0.0

    def advance(seconds, activity=Activity(), gaze=(0, 0)):
        nonlocal now
        for _ in range(round(seconds * 30)):
            now += 1 / 30
            pose = animation.advance(1 / 30, now, activity, gaze)
        return pose

    # A ten-second hold stays planted; autorepeat adds no motion goals.
    hold = Activity(keyboard=0, held=frozenset({'W'}), latest=KeyHint('W', 0))
    pose = advance(10, hold)
    assert pose.right_key == 'W' and 'W' in pose.pressed
    assert abs(pose.right_x - BY_ID['W'].contact[0]) < .1
    assert abs(pose.right_y - BY_ID['W'].contact[1] - KEY_TRAVEL) < .1
    assert animation.last_activity == now and pose.sleep == 0
    now += SLEEP_AFTER + 1
    pose = animation.advance(1 / 30, now, hold)
    assert animation.last_activity == now and pose.sleep == 0 and pose.right_key == 'W'
    pose = advance(1)
    assert not pose.pressed and abs(pose.right_y - RIGHT_REST[1]) < .1

    # Hand allocation follows location and preserves a held key where possible.
    chord = Activity(keyboard=now, held=frozenset({'A', 'P', 'ShiftLeft'}),
                     hints=(KeyHint('A', now), KeyHint('P', now + .001)))
    pose = advance(1, chord)
    assert {pose.left_key, pose.right_key} == {'A', 'P'}
    assert pose.pressed == chord.held
    pose = advance(1, Activity(keyboard=now, held=frozenset({'A', 'P', 'ShiftLeft'}), mouse=now))
    # Pointer activity reserves one paw; the other can reach P.
    pose = advance(.4, Activity(keyboard=now, mouse=now, held=frozenset({'P'}), latest=KeyHint('P', now)), (1, -1))
    assert pose.right_key == 'P' and pose.left_key is None
    assert animation.mouse_contact and math.dist((pose.left_x, pose.left_y), MOUSE_REST) < .1
    assert -1 <= pose.gaze_x <= 1 and -1 <= pose.gaze_y <= 1
    pose = advance(1.4)
    assert pose.mouse < .01 and abs(pose.left_x - LEFT_REST[0]) < .1
    assert abs(pose.head_x) < .1  # Attention leaves a stationary cursor.
    pose = advance(.3, Activity(click=now))
    assert animation.mouse_contact and pose.click > 0

    # A brief Space survives between frames without a queued text sequence.
    pose = advance(.13, Activity(keyboard=now, pulses=frozenset({'Space'}), latest=KeyHint('Space', now)))
    assert 'Space' in (pose.left_key, pose.right_key) and 'Space' in pose.pressed
    animation.pet()
    assert animation.advance(.09, now).blink > .95

    animation.last_activity = now - 30
    animation.start_idle('lick')
    pose = advance(1.3)
    assert pose.groom > .5 and pose.left_y < 112
    pose = advance(.5, Activity(keyboard=now, held=frozenset({'P'}), latest=KeyHint('P', now)))
    assert pose.groom < .01 and 'P' in (pose.left_key, pose.right_key)
    # Accelerate only the inactivity clock, while advancing full motion frames.
    now += SLEEP_AFTER + 1
    pose = advance(5)
    assert animation.sleeping and pose.zzz > .99
    assert math.dist((pose.left_x, pose.left_y), LEFT_REST) < .01
    assert math.dist((pose.right_x, pose.right_y), RIGHT_REST) < .01
    pose = advance(.6, Activity(keyboard=now, held=frozenset({'A'}), latest=KeyHint('A', now)))
    assert pose.sleep < .04 and pose.zzz < .03 and 'A' in pose.pressed
    animation.clear_input()
    assert not pose.pressed and pose.left_key is None and pose.right_key is None

    delayed = Animations()
    for frame in range(30):
        pose = delayed.advance(1 / 30, 5 + frame / 30, Activity(held=frozenset({'P'})))
    assert 'P' in (pose.left_key, pose.right_key) and 'P' in pose.pressed
    contact_x = pose.left_x if pose.left_key == 'P' else pose.right_x
    assert abs(contact_x - BY_ID['P'].contact[0]) < .1

    monitor = ActivityMonitor(False)
    monitor.set_enabled(True)
    monitor.pointer_moved(100, 100)
    assert monitor.snapshot().mouse == -float('inf')
    monitor.pointer_moved(101, 100)
    state = monitor.snapshot()
    movement = state.mouse
    assert state.motion_x == 1 and state.motion_y == 0 and state.pointer_distance == 1
    monitor.pointer_moved(101, 100)
    monitor.pointer_click()
    assert monitor.snapshot().mouse == movement and monitor.snapshot().click > 0
    assert monitor.snapshot().motion_x == 0
    monitor.pointer_scrolled(0, 1)
    state = monitor.snapshot()
    assert state.scroll > 0 and state.scroll_y == 1 and state.mouse == movement
    assert state.wheel_distance == 1 and state.pointer_distance == state.new_presses == 0
    assert monitor.snapshot().scroll_y == 0
    scroll = Animations()
    for frame in range(24):
        now_scroll = frame / 30
        pose_scroll = scroll.advance(1 / 30, now_scroll, Activity(scroll=now_scroll, scroll_y=1,
                       keyboard=now_scroll, held=frozenset({'P'}), latest=KeyHint('P', 0)))
    assert pose_scroll.mouse > .95 and pose_scroll.right_key == 'P'
    assert pose_scroll.mouse_dx == 0 and pose_scroll.mouse_dy == 0
    assert abs(pose_scroll.left_x - MOUSE_REST[0]) < .1
    scroll.advance(1 / 30, now_scroll + .49, Activity(scroll=now_scroll))
    assert scroll.mouse_contact
    scroll.advance(1 / 30, now_scroll + .51, Activity(scroll=now_scroll))
    assert not scroll.mouse_contact
    monitor.key_down('W', server_time=100)
    state = monitor.snapshot()
    assert state.new_presses == 1
    initial = state.latest
    monitor.key_up('W', server_time=200)
    monitor.key_down('W', server_time=200)
    state = monitor.snapshot()
    assert state.latest == initial and 'W' in state.held and state.new_presses == 0
    monitor.key_up('W', server_time=300)
    monitor.key_down('W', server_time=301)
    state = monitor.snapshot()
    assert state.latest.stamp > initial.stamp and state.new_presses == 1
    monitor.key_up('W')
    QTest.qWait(35)
    state = monitor.snapshot()
    assert 'W' not in state.held and 'W' in state.pulses
    QTest.qWait(370)
    assert not monitor.snapshot().pressed and monitor._latest.identifier is None
    for identifier in ('A', 'P', 'Space'):
        monitor.key_down(identifier)
        monitor.key_up(identifier)
    QTest.qWait(35)
    state = monitor.snapshot()
    assert not state.held and {'A', 'P', 'Space'} <= state.pulses
    monitor.key_down('A')
    monitor.set_enabled(False)
    assert not monitor.snapshot().pressed and not monitor.snapshot().any_held
    assert monitor.snapshot().new_presses == 0
    assert not monitor._down and not monitor._releases and not monitor._pulses
    monitor.stop()


def check_instance_lock() -> None:
    with TemporaryDirectory(prefix="desktop-pet-lock-") as directory:
        path = Path(directory)
        assert not instance_busy(path)
        with (path / "instance.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert instance_busy(path)
        assert not instance_busy(path)


def check_responsiveness() -> None:
    for rate in (3, 6, 10, 15):
        for using_mouse in (False, True):
            animation = Animations()
            previous = -1
            for frame in range(90):
                now = frame / 30
                press = int(now * rate + .0001)
                fresh = press != previous
                if fresh:
                    hint = KeyHint('A' if press % 2 else 'P', now)
                    previous = press
                pose = animation.advance(1 / 30, now, Activity(
                    keyboard=hint.stamp, key_interval=1 / rate, latest=hint,
                    new_presses=int(fresh),
                    pulses=frozenset({hint.identifier}), mouse=now if using_mouse else -float('inf')))
                if fresh:
                    assert hint.identifier in pose.pressed and hint.identifier in (pose.left_key, pose.right_key)
                if using_mouse:
                    assert pose.left_key is None and pose.right_key in (hint.identifier, None)
                    if animation.mouse_contact:
                        assert abs(pose.left_x - MOUSE_REST[0] - pose.mouse_dx) < .01
                        assert abs(pose.left_y - MOUSE_REST[1] - pose.mouse_dy) < .01
            for frame in range(9):
                pose = animation.advance(1 / 30, 3 + frame / 30)
            assert pose.left_key is None and pose.right_key is None and not pose.pressed


def check_personality() -> None:
    random.seed(17)
    animation = Animations()
    now = 0.0
    states = set()
    for rate, seconds in ((3, 5), (6, 6), (15, 55)):
        for frame in range(seconds * 30):
            now += 1 / 30
            edge = int((frame + 1) * rate / 30) - int(frame * rate / 30)
            pose = animation.advance(1 / 30, now, Activity(new_presses=edge, keyboard=now))
            state = animation.personality.state
            if rate == 3:
                assert state is CALM
            if rate == 15:
                states.add(state)
            assert not pose.pressed and not pose.contacts  # An expression cannot manufacture a stroke.
        assert abs(animation.personality.rate - rate) < .7
        if rate == 6:
            assert state is FOCUSED
    assert {FOCUSED, EXCITED, IMPATIENT} <= states
    for _ in range(300):
        now += 1 / 30
        pose = animation.advance(1 / 30, now, Activity(held=frozenset({'W'})))
    assert animation.personality.rate < .001 and pose.expression is CALM
    press = now + 7
    animation.advance(1 / 30, press)
    for frame in range(40):
        now = press + (frame + 1) / 30
        pose = animation.advance(1 / 30, now, Activity(mouse=now, pointer_distance=150, motion_x=10))
        if frame == 0:
            assert animation.personality.state is SURPRISED
        assert not pose.pressed and not pose.contacts
    assert animation.personality.state is CURIOUS
    for frame in range(40):
        now += 1 / 30
        pose = animation.advance(1 / 30, now)
    assert pose.expression is CALM and not animation.mouse_contact
    animation.clear_input()
    assert animation.personality.rate == animation.personality.pointer_speed == 0


def check_geometry_and_contacts() -> None:
    art = CatArt(); art.cache(200, 1)
    shell = art.renderer.boundsOnElement('mouse')
    obstacles_x = min(art.renderer.boundsOnElement('hind-feet').left(), min(x for x, _ in BOARD))
    assert shell.right() + 12 < obstacles_x

    def mouse_centroid(pose, fill='#a9b4b6'):
        image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image); art.draw(painter, pose); painter.end()
        color = QColor(fill).rgba()
        bounds = shell.translated(pose.mouse_dx, pose.mouse_dy + pose.click * .4).toAlignedRect()
        points = [(x, y) for y in range(bounds.top(), bounds.bottom() + 1)
                  for x in range(bounds.left(), bounds.right() + 1) if image.pixel(x, y) == color]
        assert points
        return tuple(sum(p[i] for p in points) / len(points) for i in (0, 1))

    origin = mouse_centroid(Pose())
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        animation = Animations()
        for frame in range(45):
            now = frame / 30
            pose = animation.advance(1 / 30, now, Activity(mouse=now, motion_x=dx * 8, motion_y=dy * 8))
            if animation.mouse_contact:
                assert math.dist((pose.left_x, pose.left_y), (MOUSE_REST[0] + pose.mouse_dx, MOUSE_REST[1] + pose.mouse_dy)) < .01
        # Test the final painted object, including the SVG and painter transforms.
        moved = mouse_centroid(Pose(mouse_dx=pose.mouse_dx, mouse_dy=pose.mouse_dy))
        assert animation.mouse_contact
        wheel_x, wheel_y = mouse_centroid(pose, '#59696e')
        forward = wheel_y - pose.left_y  # The buttons face forward from the cat, toward the viewer.
        assert forward > 0 and abs(wheel_x - pose.left_x) < .55 * forward
        assert math.dist(BodyGeometry(pose).shoulder(-1), (pose.left_x, pose.left_y)) < 60
        for i, direction in enumerate((-dx, -dy)):
            if direction:
                assert (moved[i] - origin[i]) * direction > 4
            else:
                assert abs(moved[i] - origin[i]) < .2

    # Reverse while the spring is still catching a saturated target.
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        animation = Animations()
        now = 0.0
        for frame in range(18):
            now += 1 / 30
            pose = animation.advance(1 / 30, now, Activity(mouse=now))
        assert animation.mouse_contact
        for frame in range(5):
            now += 1 / 30
            pose = animation.advance(1 / 30, now, Activity(mouse=now, motion_x=dx * 24, motion_y=dy * 24))
        for frame in range(10):
            before = pose.mouse_dx, pose.mouse_dy
            now += 1 / 30
            pose = animation.advance(1 / 30, now, Activity(mouse=now, motion_x=-dx * 6, motion_y=-dy * 6))
            for axis, direction in enumerate((dx, dy)):
                after = (pose.mouse_dx, pose.mouse_dy)[axis]
                assert (after - before[axis]) * direction >= -1e-8, 'Mouse continued against the new direction'
            assert abs(pose.mouse_dx) <= 12 and abs(pose.mouse_dy) <= 10
            assert math.dist((pose.left_x, pose.left_y), (MOUSE_REST[0] + pose.mouse_dx, MOUSE_REST[1] + pose.mouse_dy)) < .01

        # Turning onto the other axis must not replay the previous axis's reach.
        if not (dx and dy):
            before = pose.mouse_dx, pose.mouse_dy
            now += 1 / 30
            pose = animation.advance(1 / 30, now, Activity(mouse=now, motion_x=0 if dx else 6, motion_y=0 if dy else 6))
            if dx:
                assert pose.mouse_dx == before[0]
            if dy:
                assert pose.mouse_dy == before[1]

    for key in KEYS:
        animation = Animations()
        for frame in range(30):
            pose = animation.advance(1 / 30, frame / 30, Activity(held=frozenset({key.identifier}), latest=KeyHint(key.identifier, 0)))
        paw = next(paw for paw in animation.paws if paw.key == key.identifier)
        assert paw.landed, key.identifier
        assert math.dist((paw.x, paw.y), (key.contact[0], key.contact[1] + KEY_TRAVEL)) < 1.05
        assert pose.contact < .01  # Holding does not repeatedly create impacts.
        assert BodyGeometry(pose).hips == (104, 153)

    animation = Animations()
    animation.last_activity = 0
    animation.start_idle('lick')
    for frame in range(60):
        now = 25 + frame / 30
        pose = animation.advance(1 / 30, now)
        if pose.groom > .5:
            target = FaceGeometry(pose).grooming_target('lick', (animation.time - animation.action_start) / animation.action_duration)
            assert math.dist((pose.left_x, pose.left_y), target) < 2
    # Sleep is interrupted by wheel activity even without cursor movement.
    pose = animation.advance(.1, 240)
    for frame in range(60):pose = animation.advance(.1, 240 + frame / 10)
    assert animation.sleeping
    for frame in range(20):
        now = 247 + frame / 30
        pose = animation.advance(1 / 30, now, Activity(scroll=now, scroll_y=1))
    assert pose.sleep < .03 and pose.mouse > .9 and pose.mouse_dx == pose.mouse_dy == 0
    for side, point in ((-1, (pose.left_x, pose.left_y)), (1, (pose.right_x, pose.right_y))):
        assert math.dist(BodyGeometry(pose).shoulder(side), point) <= MAX_REACH + .1

    def painted(pose):
        image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image); art.draw(painter, pose); painter.end()
        return image

    def eyes_visible(image):
        head = art.head_hit_paths[-1].boundingRect().toAlignedRect()
        return any(image.pixel(x, y) == art.iris.rgba() for y in range(head.top(), head.bottom() + 1)
                   for x in range(head.left(), head.right() + 1))

    # Inspect the actual first wake frame, including the key before its paw lands.
    for source in ('keyboard', 'mouse', 'scroll'):
        animation = Animations()
        animation.last_activity = 0
        for frame in range(65):
            animation.advance(.1, 200 + frame / 10)
        assert animation.sleeping
        asleep = painted(animation.pose)
        assert not eyes_visible(asleep) and art.head_hit(art.head_position) is not None
        # From the chest to the floor, sleep uses exactly the seated drawing.
        lower_body = QRect(0, 110, 200, 90)
        seated = painted(replace(animation.pose, sleep=0, zzz=0))
        assert asleep.copy(lower_body) == seated.copy(lower_body)
        now = 207
        waking = Activity(**{source: now})
        if source == 'keyboard':
            waking = replace(waking, pulses=frozenset({'A'}), latest=KeyHint('A', now), new_presses=1)
        pose = animation.advance(.1, now, waking)
        image = painted(pose)
        assert pose.sleep > .8 and not pose.contacts and not animation.mouse_contact
        assert eyes_visible(image) and 0 < pose.zzz < 1
        if source == 'keyboard':
            key_area = art.key_paths['A'].boundingRect().adjusted(-1, -1, 1, 2).toAlignedRect()
            assert image.copy(key_area) != painted(replace(pose, pressed=frozenset())).copy(key_area)
            assert 'A' in (pose.left_key, pose.right_key)
        else:
            assert animation.paws[0].goal == 'mouse' and pose.left_x < 90 and not pose.pressed

    for kind, typing, pointer, wheel in (
            ('stretch', True, False, False), ('stretch', False, True, False),
            ('ear_rub', True, False, False), ('knead', True, False, False),
            ('knead', False, False, True), ('look', True, False, False),
            ('lick', True, True, False), ('wash', True, False, False),
            ('yawn', True, False, False), ('sleep', True, True, True)):
        animation = Animations()
        animation.last_activity = 0
        if kind == 'sleep':
            for frame in range(65):
                animation.advance(.1, 200 + frame / 10)
            assert animation.sleeping
            start = 207
        else:
            animation.start_idle(kind)
            for frame in range(46):
                pose = animation.advance(1 / 30, 25 + frame / 30)
                assert not pose.pressed and not pose.contacts and not animation.mouse_contact
            assert pose.action == kind
            start = 27

        before = replace(animation.pose)
        for frame in range(24):
            now = start + frame / 30
            event = Activity(mouse=now if pointer else -math.inf, motion_x=10 if pointer else 0,
                             scroll=now if wheel else -math.inf, scroll_y=int(wheel))
            if typing:
                # Fifteen fresh physical presses per second, with releases in between.
                key = ('P', 'A', 'L')[frame // 2 % 3]
                if frame % 2 == 0:
                    event = replace(event, keyboard=now, held=frozenset({key}),
                                    latest=KeyHint(key, now), new_presses=1, key_interval=1 / 15)
            pose = animation.advance(1 / 30, now, event)
            if event.held:
                assert key in (pose.left_key, pose.right_key)
                bounds = art.key_paths[key].boundingRect().adjusted(-1, -1, 1, 2).toAlignedRect()
                assert painted(pose).copy(bounds) != painted(replace(pose, pressed=frozenset())).copy(bounds)
            if pointer or wheel:
                assert animation.paws[0].goal == 'mouse'
                if frame == 0:
                    # The shell stays put while the painted foreleg starts its reach.
                    assert not animation.mouse_contact and pose.mouse_dx == pose.mouse_dy == 0
                    limb = QRect(14, 105, 90, 54)
                    old_paw = replace(pose, left_x=before.left_x, left_y=before.left_y)
                    assert painted(pose).copy(limb) != painted(old_paw).copy(limb)
            if frame == 0:
                assert not pose.contacts
                assert all(paw.goal in BY_ID or paw.goal in ('ready', 'mouse', 'rest') for paw in animation.paws)
        for frame in range(32):
            pose = animation.advance(1 / 30, start + 1 + frame / 30)
        assert not pose.pressed and not pose.contacts
        assert all(paw.goal == 'rest' for paw in animation.paws)

    animation = Animations()
    animation.last_activity = 0
    animation.start_idle('stretch')
    for frame in range(60):
        pose = animation.advance(1 / 30, 178 + frame / 30)
    assert pose.action == 'stretch' and pose.sleep == 0
    for frame in range(65):
        pose = animation.advance(.1, 180 + frame / 10)
    assert animation.last_activity == 0 and animation.sleeping
    assert pose.action is None and not eyes_visible(painted(pose))
    assert math.dist((pose.left_x, pose.left_y), LEFT_REST) < .01
    assert math.dist((pose.right_x, pose.right_y), RIGHT_REST) < .01


if __name__ == "__main__":
    with TemporaryDirectory(prefix="desktop-pet-checks-") as directory:
        QCoreApplication.setOrganizationName("desktop-pet-checks")
        QCoreApplication.setApplicationName("smoke")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        app = QApplication([])
        check_window()
        check_window_lifecycle()
        check_motion_and_screens()
        check_responsiveness()
        check_personality()
        check_geometry_and_contacts()
        check_instance_lock()
    print("PASS: window controls, preferences, 105 keys, physical cadence, expressions, contacts, "
          "painted mouse directions, scroll, shared paws, idle interruptions, rendered wake, screens and lock.")
