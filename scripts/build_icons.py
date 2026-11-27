"""Regenerate the app icons from Miga's original face, without changing the pet.

Run with Python, PySide6-Essentials and Pillow installed:
    python scripts/build_icons.py
The generated PNG, ICO and ICNS are committed so native builds need no Pillow.
"""

from io import BytesIO
import math
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

from anatomy import FaceGeometry
from animations import Pose
from appearance import Appearance
from character import CatArt


def main():
    _app = QGuiApplication.instance() or QGuiApplication([])
    art = CatArt(appearance=Appearance(coat='original'))
    pose = Pose()
    # Supersample the actual face renderer: ears, shading, eyes, nose and whiskers.
    canvas = QImage(4096, 4096, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(canvas.width() / 200, canvas.height() / 200)
    art._draw_face(painter, pose, FaceGeometry(pose))
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not canvas.save(buffer, 'PNG'):
        raise RuntimeError("Could not render Miga's icon.")
    face = Image.open(BytesIO(bytes(buffer.data()))).convert('RGBA')
    face = face.crop(face.getchannel('A').getbbox())
    # Keep the whiskers clear of the edges and center the head on a square.
    side = math.ceil(max(face.size) / .88)
    icon = Image.new('RGBA', (side, side))
    icon.alpha_composite(face, ((side - face.width) // 2, (side - face.height) // 2))
    icon = icon.resize((1024, 1024), Image.Resampling.LANCZOS)
    destination = ROOT / 'assets' / 'icons'
    destination.mkdir(parents=True, exist_ok=True)
    icon.save(destination / 'miga.png', optimize=True)
    sizes = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    icon.save(destination / 'miga.ico', sizes=sizes)
    icon.save(destination / 'miga.icns')
    print(f'Generated PNG, ICO and ICNS in {destination}')


if __name__ == '__main__':
    main()
