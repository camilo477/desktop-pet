"""Synthetic physical keyboard, geometry and painted-contact checks."""

import math
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from activity import Activity, ActivityMonitor, KeyHint
from animations import Animations
from character import CatArt
from keyboard_distributions import DISTRIBUTIONS, detected_layout
from keyboard_layout import FORMATS, KEY_TRAVEL, Keyboard, STANDARDS


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
    assert detected_layout('us', 'colemak_dh') is None and detected_layout('de', 'dvorak') is None


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
    monitor.stop()


if __name__ == '__main__':
    app = QApplication([])
    check_geometry()
    check_distributions()
    check_absent()
    print('PASS: ten physical geometries, eight distributions, painted key presses, paw contacts and absent keys.')
