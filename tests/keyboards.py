"""Synthetic physical keyboard, geometry and painted-contact checks."""

import math
from dataclasses import replace
import os
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from activity import Activity, ActivityMonitor, KeyHint
from animations import Animations
from character import CatArt
from keyboard_distributions import DISTRIBUTIONS, detected_layout
from keyboard_layout import FORMATS, KEY_TRAVEL, Keyboard, STANDARDS
from pet import PetWindow


def paint(art, pose, size=300):
    art.cache(size, 1)
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.scale(size / 200, size / 200)
    art.draw(p, pose)
    p.end()
    return image


def check_geometry():
    counts = {'60': 61, '65': 68, '75': 83, 'tkl': 87, '100': 104}
    art = CatArt()
    widths = {}
    for form in FORMATS:
        for standard in STANDARDS:
            kb = Keyboard(form, standard)
            assert len(kb.ids) == counts[form] + (standard == 'ISO')
            assert ('IntlBackslash' in kb.ids) == (standard == 'ISO')
            assert ('F1' in kb.ids) == (form in ('75', 'tkl', '100'))
            assert ('ArrowLeft' in kb.ids) == (form != '60')
            assert ('NumpadEnter' in kb.ids) == (form == '100')
            assert len(kb.by_id['Enter'].polygon) == (6 if standard == 'ISO' else 4)
            assert (kb.by_id['ShiftLeft'].width == 1.25) == (standard == 'ISO')
            art.set_keyboard(kb)
            paths = list(art.key_paths.values())
            for i, path in enumerate(paths):
                assert art.board_top.contains(path)
                assert all(not path.intersects(other) for other in paths[:i])
            for key in kb.by_id.values():
                assert art.key_paths[key.identifier].contains(QPointF(*key.contact))
                assert key.label_basis[2] < 0 and key.label_basis[5] < 0
            mouse = art.mouse_path.boundingRect().translated(kb.mouse_offset + 12, 0)
            assert mouse.right() < min(art.board_path.boundingRect().left(),
                                       art.renderer.boundsOnElement('hind-feet').left())
            widths[form] = art.board_path.boundingRect().width()
            for identifier in ('Escape', 'Enter', 'ShiftLeft', 'Backslash', 'CtrlRight'):
                a = Animations(kb)
                for i in range(26):
                    pose = a.advance(1 / 30, i / 30, Activity(held=frozenset({identifier})))
                paw = next(p for p in a.paws if p.goal == identifier)
                x, y = kb.by_id[identifier].contact
                assert paw.landed and math.dist((x, y + KEY_TRAVEL), (paw.x, paw.y)) < 1.05, (form, standard, identifier)
    assert widths['60'] < widths['65'] <= widths['75'] < widths['tkl'] < widths['100']


def check_distributions():
    # The same physical press follows its cap even when its printed character moves.
    samples = {
        'us': ('Q', 'Q'), 'gb': ('Backslash', '#'), 'latam': ('Quote', '{'),
        'es': ('Semicolon', 'Ñ'), 'de': ('Y', 'Z'), 'fr': ('Q', 'A'),
        'dvorak': ('Q', "'"), 'colemak': ('P', ';'),
    }
    assert samples.keys() == DISTRIBUTIONS.keys()
    assert detected_layout('us', 'colemak') == 'colemak'
    assert detected_layout('us', 'dvorak') == 'dvorak'
    assert detected_layout('us', 'colemak_dh') is None
    assert detected_layout('latam', 'dvorak') is None
    assert detected_layout('unknown', '') is None
    for layout, positions, legends in (
        ('de', ('Y', 'Z', 'BracketLeft', 'Semicolon', 'Quote'), 'ZYÜÖÄ'),
        ('fr', ('Q', 'W', 'A', 'Z', 'Digit2', 'Digit7', 'Digit9'), 'AZQWéèç'),
        ('dvorak', tuple('QWERTYASDF'), "',.PYFAOEU"),
        ('colemak', tuple('QWERTYASDF'), 'QWFPGJARST'),
        ('latam', ('Equal', 'BracketLeft', 'Semicolon', 'Quote', 'Backslash'), '¿´Ñ{}'),
        ('es', ('Equal', 'BracketLeft', 'Semicolon', 'Quote', 'Backslash'), '¡`Ñ´Ç'),
    ):
        kb = Keyboard(layout=layout)
        assert ''.join(kb.label(position) for position in positions) == legends
    for layout in ('us', 'es', 'latam', 'de', 'fr', 'dvorak'):
        assert Keyboard(layout=layout).label('IntlBackslash') == '<'
    assert Keyboard(layout='gb').label('IntlBackslash') == '\\'
    assert Keyboard(layout='colemak').label('IntlBackslash') == '-'
    for layout, (identifier, legend) in samples.items():
        kb = Keyboard('tkl', 'ISO', layout)
        assert kb.label(identifier) == legend
        art, animation = CatArt(kb), Animations(kb)
        key = kb.by_id[identifier]
        inputs = Activity(held=frozenset({identifier}), latest=KeyHint(identifier, 1))
        pose = animation.advance(1 / 30, 1, inputs)
        pressed = paint(art, pose)
        pose.pressed = frozenset()
        unpressed = paint(art, pose)
        rect = art.key_paths[identifier].boundingRect()
        assert any(pressed.pixel(x, y) != unpressed.pixel(x, y)
                   for x in range(int(rect.left()*1.5), math.ceil(rect.right()*1.5))
                   for y in range(int(rect.top()*1.5), math.ceil(rect.bottom()*1.5)))
        for i in range(20):
            animation.advance(1 / 30, 1 + (i+1)/30, inputs)
        paw = next(p for p in animation.paws if p.landed)
        assert math.dist((paw.x, paw.y), (key.contact[0], key.contact[1] + KEY_TRAVEL)) < 1.05


def check_touchpad():
    for form in FORMATS:
        for standard in STANDARDS:
            kb = Keyboard(form, standard, pointer='touchpad')
            art, a = CatArt(kb), Animations(kb)
            assert art.board_top.contains(art.touchpad_path)
            assert QRectF(0, 0, 200, 200).contains(art.board_path.boundingRect())
            assert all(art.board_top.contains(path) and not path.intersects(art.touchpad_path)
                       for path in art.key_paths.values())
            # Pointer displacement never moves the laptop's chassis or pad pixels.
            for size in (150, 200, 300):
                still = paint(art, a.pose, size)
                assert still == paint(art, replace(a.pose, mouse_dx=9, mouse_dy=1.5), size)
                assert 'mouse' not in {name for name, _ in art.hits}
                assert art.region_at(QPointF(*kb.mouse_rest)) == 'touchpad'
            for identifier in ('Escape', 'Enter', 'ShiftLeft', 'Backslash', 'CtrlRight'):
                typing = Animations(kb)
                for i in range(30):
                    typing.advance(1/30, i/30, Activity(held=frozenset({identifier})))
                paw = next(p for p in typing.paws if p.goal == identifier)
                x, y = kb.by_id[identifier].contact
                assert paw.landed and math.dist((x, y + KEY_TRAVEL), (paw.x, paw.y)) < 1.05
            # Follow large movements to each edge, reverse, scroll and click while typing.
            now = 1
            for dx, dy in ((40, 40), (-40, -40), (40, -40), (-40, 40)):
                for i in range(45):
                    now += 1/30
                    pose = a.advance(1/30, now, Activity(mouse=now, motion_x=dx, motion_y=dy,
                                      scroll=now, scroll_y=1, held=frozenset({'Q'})))
                    if a.mouse_contact:
                        assert art.touchpad_path.contains(QPointF(pose.left_x, pose.left_y))
                        assert abs(pose.mouse_dx) <= 9 and abs(pose.mouse_dy) <= 1.5
                assert a.mouse_contact and a.paws[1].goal == 'Q'
            before = pose.left_y
            pose = a.advance(.06, now + .06, Activity(scroll=now + .06, scroll_y=1, click=now))
            now += .06
            assert pose.left_y != before and pose.left_pressure > .5
            assert art.touchpad_path.contains(QPointF(pose.left_x, pose.left_y))
            clicked = paint(art, pose)
            assert clicked != paint(art, replace(pose, click=0, left_pressure=0))
            # Changing the device clears old motion, then contact follows the new surface.
            for pointer in ('mouse', 'touchpad'):
                a.set_keyboard(Keyboard(form, standard, pointer=pointer), frozenset())
                assert pose.mouse_dx == pose.mouse_dy == 0 and not a.mouse_contact
                for i in range(45):
                    now += 1/30
                    pose = a.advance(1/30, now, Activity(mouse=now))
                assert a.mouse_contact and pose.touchpad == (pointer == 'touchpad')
                assert math.dist((pose.left_x, pose.left_y), a.keyboard.mouse_rest) < .01


def check_absent():
    kb = Keyboard('60', 'ANSI')
    monitor = ActivityMonitor(False, keyboard=kb)
    monitor.set_enabled(True)
    monitor.key_down('F1', 67)
    state = monitor.snapshot()
    assert state.any_held and state.new_presses == 1 and not state.pressed and not state.latest.identifier
    a = Animations(kb)
    pose = a.advance(1/30, state.keyboard, state)
    assert not pose.pressed and all(p.goal == 'rest' for p in a.paws)
    full = Keyboard()
    held = monitor.set_keyboard(full)
    a.set_keyboard(full, held)
    state = monitor.snapshot()
    assert state.held == {'F1'} and not state.new_presses
    a.advance(1/30, state.keyboard + .04, state)
    assert any(p.goal == 'F1' for p in a.paws)
    a.set_keyboard(kb, monitor.set_keyboard(kb))
    assert not pose.pressed and not pose.contacts and all(p.key is None for p in a.paws)
    now = state.keyboard + 1
    a.advance(1/30, now, Activity(held=frozenset({'A'})))
    for i in range(40):
        a.advance(1/30, now + (i+1)/30)
    # An absent press must not revive a previous ready position.
    a.advance(1/30, now + 2, Activity(keyboard=now + 2, any_held=True))
    assert all(p.goal == 'rest' for p in a.paws)
    monitor.stop()


def check_live_menu():
    # Exercise the actual QAction callbacks with isolated preferences and synthetic input.
    config = QSettings()
    for key in ('format', 'standard', 'layout_mode', 'layout', 'pointer'):
        config.setValue(f'keyboard/{key}', 'invalid')
    w = PetWindow()
    w.show()
    origin, size = w.pos(), w.size()
    assert (w.layout_mode, w.keyboard.form, w.keyboard.standard) == ('auto', '100', 'ISO')
    assert w.keyboard.pointer == 'mouse'
    def choose(submenu, label):
        menu = w.build_menu()
        keyboards = next(a.menu() for a in menu.actions() if a.text() == 'Teclado')
        choices = next(a.menu() for a in keyboards.actions() if a.text() == submenu)
        assert sum(a.isChecked() for a in choices.actions()) == 1
        action = next(a for a in choices.actions() if a.text().startswith(label))
        action.trigger()
        assert action.isChecked()
        menu.deleteLater()

    w.activity.set_layout('de')
    w.tick()
    a = w.animations
    personality = a.personality
    stamp = a.last_activity
    layers = w.art.layers['paw'][1].cacheKey()
    for layout in ('fr', 'colemak'):
        before = w.art.keyboard.cacheKey()
        coords = w.art.key_paths
        choose('Distribución', DISTRIBUTIONS[layout])
        assert w.keyboard.layout == layout and w.art.keyboard.cacheKey() != before
        assert w.art.key_paths is coords and w.art.layers['paw'][1].cacheKey() == layers
    choose('Distribución', 'Automática')
    assert w.keyboard.layout == 'de' and a.last_activity == stamp
    w.activity.key_down('Numpad1')
    w.activity.key_down('Q')
    w.tick()
    assert a.pose.pressed == {'Q', 'Numpad1'}
    before_mask = w.last_mask
    choose('Formato', '60 %')
    assert w.last_mask != before_mask and a.pose.pressed == {'Q'}
    w.tick()
    assert 'Q' in (a.pose.left_key, a.pose.right_key)
    choose('Formato', 'TKL')
    w.activity.pointer_moved(1, 1)
    w.activity.pointer_moved(18, 20)
    w.tick()
    assert a.paws[0].goal == 'mouse'
    choose('Estándar físico', 'ANSI')
    w.tick()
    assert a.paws[0].goal == 'mouse' and a.paws[1].goal == 'Q'
    before_mask = w.last_mask
    choose('Mouse / touchpad', 'Touchpad integrado')
    assert w.keyboard.pointer == 'touchpad' and w.last_mask != before_mask
    assert a.pose.pressed == {'Q'} and a.pose.touchpad
    w.tick()
    assert a.paws[0].goal == 'mouse' and a.paws[1].goal == 'Q'
    choose('Formato', '100 %')
    assert a.pose.pressed == {'Q', 'Numpad1'} and w.keyboard.pointer == 'touchpad'
    w.activity.key_up('Numpad1')
    w.activity.key_up('Q')
    time.sleep(.23)
    w.tick()
    assert not a.pose.pressed and a.personality is personality
    w.set_reactions(False)
    choose('Distribución', DISTRIBUTIONS['dvorak'])
    choose('Formato', '75 %')
    assert not w.activity.enabled and w.keyboard.layout == 'dvorak'
    w.set_paused(True)
    before = a.time
    choose('Formato', '65 %')
    choose('Estándar físico', 'ISO')
    choose('Mouse / touchpad', 'Mouse')
    assert not a.pose.touchpad
    choose('Mouse / touchpad', 'Touchpad integrado')
    assert a.time == before and not w.timer.isActive()
    assert w.pos() == origin and w.size() == size and w.art.model is a.keyboard is w.activity.keyboard
    w.shutdown()
    restored = PetWindow()
    assert (restored.keyboard.form, restored.keyboard.standard, restored.keyboard.layout) == ('65', 'ISO', 'dvorak')
    assert restored.keyboard.pointer == 'touchpad' and restored.animations.pose.touchpad
    assert restored.paused and not restored.reactions and restored.pos() == origin
    restored.shutdown()


def check_priority():
    for rate, form, layout, pointer, scroll in (
            (3, '100', 'gb', False, False), (6, '75', 'de', False, True),
            (10, 'tkl', 'fr', True, False), (15, '60', 'dvorak', False, False)):
        kb = Keyboard(form, 'ANSI', layout)
        a = Animations(kb)
        a.last_activity = 0
        for i in range(85):
            a.advance(.1, 200 + i / 10)
        assert a.sleeping
        for i in range(60):
            now = 210 + i / 30
            edge = i * rate // 30 != (i-1) * rate // 30
            key = ('Q', 'P')[i * rate // 30 % 2]
            state = Activity(keyboard=now, new_presses=int(edge), key_interval=1/rate,
                             held=frozenset({key}), latest=KeyHint(key, now) if edge else KeyHint(),
                             mouse=now if pointer else -math.inf, scroll=now if scroll else -math.inf,
                             scroll_y=int(scroll), motion_x=int(pointer))
            pose = a.advance(1/30, now, state)
            assert pose.pressed == {key} and key in (pose.left_key, pose.right_key)
            if pointer or scroll:
                assert a.paws[0].goal == 'mouse' and a.paws[1].key == key
        assert pose.sleep < .01
        for i in range(30):
            pose = a.advance(1/30, 213+i/30)
        assert not pose.pressed and all(p.goal == 'rest' for p in a.paws)


if __name__ == '__main__':
    app = QApplication([])
    with TemporaryDirectory() as prefs:
        app.setOrganizationName('miga-tests')
        app.setApplicationName('keyboards')
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, prefs)
        check_geometry()
        check_distributions()
        check_touchpad()
        check_absent()
        check_priority()
        check_live_menu()
    print('PASS: twenty geometries, eight layouts, mouse/touchpad contact, clicks, scroll, live menu, held keys and persistence.')
