"""Essential checks: run with .venv/bin/python tests/smoke.py."""

import fcntl
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from activity import Activity, ActivityMonitor, KeyHint
from animations import Animations, LEFT_REST, RIGHT_REST, MOUSE_REST, SLEEP_AFTER
from keyboard_layout import BY_ID, BY_SCAN, KEYS, LABELS, key_for_symbol
from main import instance_busy
from pet import PetWindow, visible_position


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
        "Tamaño", "Siempre visible", "Reaccionar a actividad", "Pausar animaciones", "Salir",
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


def check_motion_and_screens() -> None:
    areas = [QRect(-1920, 0, 1920, 1080), QRect(0, 0, 1920, 1080)]
    assert visible_position(QPoint(5000, 5000), QSize(200, 200), areas) == QPoint(1720, 880)
    assert visible_position(QPoint(-1800, 300), QSize(200, 200), areas) == QPoint(-1800, 300)
    assert len({key.identifier for key in KEYS}) == len(KEYS)
    assert len({key.scan for key in KEYS}) == len(KEYS)
    assert len(KEYS) == 105
    for identifier in ('F1', 'F12', 'PrintScreen', 'ScrollLock', 'Pause', 'NumLock',
                       'Insert', 'Delete', 'Home', 'End', 'PageUp', 'PageDown',
                       'NumpadEnter', 'Numpad0', 'Numpad9', 'MetaRight', 'CtrlRight'):
        assert BY_SCAN[BY_ID[identifier].scan] == identifier
    assert BY_ID['NumpadEnter'].scan != BY_ID['Enter'].scan
    assert BY_ID['Numpad1'].scan != BY_ID['Digit1'].scan
    assert key_for_symbol(0xff9c) == 'Numpad1'  # Num Lock off: KP_End, not End.
    assert key_for_symbol(0xffb1) == 'Numpad1'
    assert key_for_symbol(0xff8d) == 'NumpadEnter'
    assert LABELS['latam']['Semicolon'] == 'Ñ'
    assert BY_ID['Numpad0'].contact[0] < BY_ID['ArrowDown'].contact[0]
    assert BY_ID['P'].contact[0] < BY_ID['A'].contact[0]
    assert BY_ID['Space'].contact[1] < BY_ID['Digit1'].contact[1]
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
    assert abs(pose.right_y - BY_ID['W'].contact[1] - .55) < .1
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
    # Only actual motion reserves the mouse paw; the other can reach P.
    pose = advance(.4, Activity(keyboard=now, mouse=now, held=frozenset({'P'}), latest=KeyHint('P', now)), (1, -1))
    assert pose.right_key == 'P' and pose.left_key is None
    assert pose.left_x < 45 and pose.right_x > 95
    assert -1 <= pose.gaze_x <= 1 and -1 <= pose.gaze_y <= 1
    pose = advance(1.4)
    assert pose.mouse < .01 and abs(pose.left_x - LEFT_REST[0]) < .1
    assert abs(pose.head_x) < .1  # Attention leaves a stationary cursor.
    pose = advance(.3, Activity(click=now))
    assert pose.mouse == 0 and abs(pose.left_x - LEFT_REST[0]) < .1

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
    assert animation.sleeping and pose.zzz > .99 and pose.left_y > 140
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
    assert state.motion_x == 1 and state.motion_y == 0
    monitor.pointer_moved(101, 100)
    monitor.pointer_click()
    assert monitor.snapshot().mouse == movement and monitor.snapshot().click > 0
    assert monitor.snapshot().motion_x == 0
    monitor.pointer_scrolled(0, 1)
    state = monitor.snapshot()
    assert state.scroll > 0 and state.scroll_y == 1 and state.mouse == movement
    assert monitor.snapshot().scroll_y == 0
    scroll = Animations()
    for frame in range(24):
        now_scroll = frame / 30
        pose_scroll = scroll.advance(1 / 30, now_scroll, Activity(scroll=now_scroll, scroll_y=1,
                       keyboard=now_scroll, held=frozenset({'P'}), latest=KeyHint('P', 0)))
    assert pose_scroll.mouse > .95 and pose_scroll.right_key == 'P'
    assert pose_scroll.mouse_dx == 0 and pose_scroll.mouse_dy == 0
    assert abs(pose_scroll.left_x - MOUSE_REST[0]) < .1
    monitor.key_down('W', server_time=100)
    initial = monitor.snapshot().latest
    monitor.key_up(BY_ID['W'].scan, server_time=200)
    monitor.key_down('W', server_time=200)
    assert monitor.snapshot().latest == initial and 'W' in monitor.snapshot().held
    monitor.key_up(BY_ID['W'].scan, server_time=300)
    monitor.key_down('W', server_time=301)
    assert monitor.snapshot().latest.stamp > initial.stamp
    monitor.key_up(BY_ID['W'].scan)
    QTest.qWait(35)
    state = monitor.snapshot()
    assert 'W' not in state.held and 'W' in state.pulses
    QTest.qWait(370)
    assert not monitor.snapshot().pressed and monitor._latest.identifier is None
    for identifier in ('A', 'P', 'Space'):
        monitor.key_down(identifier)
        monitor.key_up(BY_ID[identifier].scan)
    QTest.qWait(35)
    state = monitor.snapshot()
    assert not state.held and {'A', 'P', 'Space'} <= state.pulses
    monitor.key_down('A')
    monitor.set_enabled(False)
    assert not monitor.snapshot().pressed and not monitor.snapshot().any_held
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
                    pulses=frozenset({hint.identifier}), mouse=now if using_mouse else -float('inf')))
                if fresh:
                    assert hint.identifier in (pose.left_key, pose.right_key)
                if using_mouse:
                    assert pose.left_key is None and pose.right_key in (hint.identifier, None)
                    if animation.mouse_contact:
                        assert abs(pose.left_x - MOUSE_REST[0] - pose.mouse_dx) < .01
                        assert abs(pose.left_y - MOUSE_REST[1] - pose.mouse_dy) < .01
            for frame in range(9):
                pose = animation.advance(1 / 30, 3 + frame / 30)
            assert pose.left_key is None and pose.right_key is None and not pose.pressed


if __name__ == "__main__":
    with TemporaryDirectory(prefix="desktop-pet-checks-") as directory:
        QCoreApplication.setOrganizationName("desktop-pet-checks")
        QCoreApplication.setApplicationName("smoke")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        app = QApplication([])
        check_window()
        check_motion_and_screens()
        check_responsiveness()
        check_instance_lock()
    print("PASS: rendering, mask, sizes, pause, drag, menu, preferences, per-key input, holds, shared paws, grooming, sleep, screens and lock.")
