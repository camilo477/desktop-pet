"""Render coats on identical poses and exercise the real appearance menu."""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from animations import Pose
from appearance import Appearance, COATS, EYES, NOSES
from character import CatArt
from personality import DROWSY, SURPRISED
from pet import PetWindow


def painted(art, pose, size):
    art.cache(size, 1)
    frame = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(Qt.GlobalColor.transparent)
    p = QPainter(frame)
    p.scale(size / 200, size / 200)
    art.draw(p, pose)
    p.end()
    return frame


def check_render():
    art = CatArt()
    poses = (Pose(), Pose(head_x=.88, head_y=-.24, head_tilt=9, expression=SURPRISED,
                          tail_touch=.6, mouse=1, left_x=38, left_y=154),
             Pose(sleep=1, blink=1, relax=1, zzz=1, time=.74, expression=DROWSY))
    for size in (150, 200, 300):
        for pose in poses:
            art.set_appearance(Appearance())
            original = painted(art, pose, size)
            hits = art.hits[:]
            coverage = original.createMaskFromColor(0, Qt.MaskMode.MaskInColor)
            seen = set()
            for coat in COATS:
                art.set_appearance(Appearance(coat))
                frame = painted(art, pose, size)
                assert hits == art.hits, (size, coat)
                assert frame.createMaskFromColor(0, Qt.MaskMode.MaskInColor) == coverage, (size, coat)
                seen.add(bytes(frame.constBits()))
            assert len(seen) == len(COATS)
            art.set_appearance(Appearance())
            assert painted(art, pose, size) == original

    for eye in EYES:
        art.set_appearance(Appearance('siamese', eye))
        frame = painted(art, Pose(), 300)
        for index, x in enumerate((133, 173)):
            assert any(frame.pixel(x+dx, y) == art.irises[index].rgba()
                       for dx in range(-10, 11) for y in range(105, 122)), eye
        assert (art.irises[0] != art.irises[1]) == (eye == 'odd')
    noses = []
    for nose in NOSES:
        art.set_appearance(Appearance('white', 'odd', nose))
        frame = painted(art, Pose(), 300)
        noses.append(bytes(frame.constBits()))
    assert len(set(noses)) == len(NOSES)


def choose(w, submenu, title):
    root = w.build_menu()
    menu = next(a.menu() for a in root.actions() if a.text() == 'Apariencia')
    if submenu:
        menu = next(a.menu() for a in menu.actions() if a.text() == submenu)
        assert sum(a.isChecked() for a in menu.actions()) == 1
    next(a for a in menu.actions() if a.text() == title).trigger()
    root.deleteLater()


def check_preferences():
    for field in ('coat', 'eyes', 'nose'):
        QSettings().setValue('appearance/' + field, 'unknown')
    w = PetWindow()
    assert w.art.appearance == Appearance()
    w.configure_keyboard(form='65', standard='ANSI', layout='fr')
    w.activity.key_down('Q')
    w.tick()
    pose = w.animations.pose
    clock = pose.time
    personality = w.animations.personality
    keyboard_cache = w.art.keyboard.cacheKey()
    location = (w.pos(), w.size())
    choose(w, 'Pelaje', 'Calicó')
    assert pose.time == clock and pose.pressed == {'Q'}
    assert w.animations.personality is personality and w.art.keyboard.cacheKey() == keyboard_cache
    paw_cache = w.art.layers['paw'][1].cacheKey()
    choose(w, 'Ojos', 'Heterocromía')
    choose(w, 'Nariz', 'Rosado')
    assert w.art.layers['paw'][1].cacheKey() == paw_cache
    assert w.activity.snapshot().held == {'Q'}
    w.activity.key_up('Q')
    w.set_reactions(False)
    now = time.monotonic()
    w.animations.advance(.034, now)
    w.animations.last_activity = now - 200
    for i in range(100):
        w.animations.advance(.1, now + i/10)
    assert w.animations.sleeping
    choose(w, 'Pelaje', 'Siamés')
    assert w.animations.sleeping and pose.blink == 1 and not w.activity.enabled
    w.set_paused(True)
    clock = w.animations.time
    old = w.frame.toImage()
    choose(w, 'Pelaje', 'Carey')
    assert not w.timer.isActive() and w.animations.time == clock and w.frame.toImage() != old
    w.shutdown()
    restored = PetWindow()
    assert restored.paused and not restored.reactions
    assert restored.art.appearance == Appearance('tortie', 'odd', 'pink')
    assert (restored.pos(), restored.size()) == location
    choose(restored, None, 'Restaurar apariencia original')
    assert restored.art.appearance == Appearance() and not restored.timer.isActive()
    assert (restored.keyboard.form, restored.keyboard.standard, restored.keyboard.layout) == ('65', 'ANSI', 'fr')
    assert (restored.pos(), restored.size()) == location
    restored.shutdown()


if __name__ == '__main__':
    app = QApplication([])
    with TemporaryDirectory() as directory:
        app.setOrganizationName('miga-tests')
        app.setApplicationName('coats')
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        check_render()
        check_preferences()
    print('PASS: eleven painted coats, eye and nose choices, anatomical hits, transparency and live preferences.')
