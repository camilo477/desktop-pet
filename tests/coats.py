"""Render coats on identical poses and exercise the real appearance menu."""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from animations import Pose
from appearance import Appearance, COATS, EYES, NOSES
from character import CatArt
from anatomy import FACE_CAMERA_DISTANCE, FACE_RX, FACE_RY, FACE_DEPTH, FaceGeometry, face_depth
from coat_patterns import FacePatch, PATTERNS, cubic_path, smooth_loop
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
             Pose(head_y=-1), Pose(head_x=-1, head_y=-1, head_tilt=-12),
             Pose(head_x=1, head_y=-1, head_tilt=12),
             Pose(head_y=-1, expression=SURPRISED),
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


def check_visible_markings():
    # A material point inside a marking and facing the camera must retain its
    # color. A straight closure between horizon crossings cut away these points.
    poses = (Pose(head_y=-1), Pose(head_y=-1, head_x=-1), Pose(head_y=-1, head_x=1),
             Pose(head_y=-1, expression=SURPRISED))
    checked = 0
    for pattern in ('piebald', 'patches', 'brindle', 'tabby'):
        for _, points in PATTERNS[pattern].face:
            source = cubic_path(smooth_loop(points))
            patch = FacePatch(points)
            samples = [(x, y, face_depth(x, y)) for x in range(-32, 33) for y in range(-27, 25)
                       if x*x/FACE_RX**2 + y*y/FACE_RY**2 < .98
                       and source.contains(QRectF(x - .3, y - .3, .6, .6))]
            for pose in poses:
                face = FaceGeometry(pose)
                projected = patch.project(face)
                camera = (-FACE_CAMERA_DISTANCE * face.sin_y,
                          -FACE_CAMERA_DISTANCE * face.sin_p / face.cos_p,
                          FACE_CAMERA_DISTANCE * face.cos_y)
                for x, y, z in samples:
                    normal = (x / FACE_RX**2, y / FACE_RY**2, z / FACE_DEPTH**2)
                    toward_camera = sum(n * (c - v) for n, c, v in zip(normal, camera, (x, y, z)))
                    if toward_camera < 2:
                        continue  # Exclude the subpixel tangent and boundary band.
                    assert projected.contains(QPointF(*face.point(x, y, z))), (pattern, pose, x, y)
                    checked += 1
    assert checked > 5000


def check_continuity():
    art = CatArt()
    for coat in ('calico', 'bicolor', 'tortie', 'ginger'):
        art.set_appearance(Appearance(coat))
        neutral_image = painted(art, Pose(), 300)
        neutral = bytes(neutral_image.constBits())
        for pitch in (-.0001, .0001):
            frame_image = painted(art, Pose(head_y=pitch), 300)
            frame = bytes(frame_image.constBits())
            # An almost stationary head must not suddenly replace large color areas.
            difference = sum(abs(a - b) for a, b in zip(neutral, frame)) / 255
            assert difference < 5, (coat, pitch, difference)


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
        check_visible_markings()
        check_continuity()
        check_preferences()
    print('PASS: eleven coats, upward-facing markings, continuous turns, eye/nose choices, hits and preferences.')
