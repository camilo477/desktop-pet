"""Transparent desktop window and the original layered character."""

import math
from pathlib import Path
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from animations import Animations, Pose


class CatArt:
    LAYERS = (
        "tail", "body", "ear-left", "ear-right", "head", "eyes",
        "pupil-left", "pupil-right", "eyelids", "desk-legs", "desk",
        "mouse-mat", "keyboard", "mouse", "arm-left", "arm-right",
    )

    def __init__(self) -> None:
        path = Path(__file__).resolve().parent / "assets" / "cat" / "miga.svg"
        self.renderer = QSvgRenderer(str(path))
        if not self.renderer.isValid():
            raise RuntimeError("Could not load the character artwork.")
        self.layers: dict[str, QPixmap] = {}
        self.cache_scale = 0.0
        self.eye_clip = QPainterPath()
        self.eye_clip.addEllipse(QRectF(69.5, 79.6, 16.0, 18.6))
        self.eye_clip.addEllipse(QRectF(107.5, 79.6, 16.1, 18.6))

    def cache(self, size: int, pixel_ratio: float) -> None:
        pixels = math.ceil(size * pixel_ratio)
        scale = pixels / 200.0
        if scale == self.cache_scale:
            return
        self.cache_scale = scale
        for name in self.LAYERS:
            if not self.renderer.elementExists(name):
                raise RuntimeError(f"Missing character layer: {name}")
            pixmap = QPixmap(pixels, pixels)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(scale, scale)
            self.renderer.render(painter, name, self.renderer.boundsOnElement(name))
            painter.end()
            pixmap.setDevicePixelRatio(scale)
            self.layers[name] = pixmap

    def draw(self, painter: QPainter, pose: Pose) -> None:
        def layer(name: str) -> None:
            painter.drawPixmap(0, 0, self.layers[name])

        painter.save()
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        painter.save()
        painter.translate(130, 137)
        painter.rotate(pose.tail)
        painter.translate(-130, -137)
        layer("tail")
        painter.restore()

        painter.save()
        painter.translate(0, pose.breath * 0.4)
        layer("body")
        painter.translate(97, 109)
        painter.rotate(pose.gaze_x * 2.5)
        painter.translate(-97 + pose.gaze_x * 0.6, -109 + pose.breath * 0.6)
        for name in ("ear-left", "ear-right", "head"):
            layer(name)

        painter.save()
        painter.translate(0, 89)
        painter.scale(1, max(0.025, 1.0 - pose.blink))
        painter.translate(0, -89)
        painter.setOpacity(1.0 - pose.blink ** 4)
        layer("eyes")
        painter.setClipPath(self.eye_clip)
        painter.translate(pose.gaze_x * 2.0, pose.gaze_y * 1.6)
        layer("pupil-left")
        layer("pupil-right")
        painter.restore()
        if pose.blink > 0.6:
            painter.save()
            painter.setOpacity((pose.blink - 0.6) / 0.4)
            layer("eyelids")
            painter.restore()
        painter.restore()

        for name in ("desk-legs", "desk", "mouse-mat", "keyboard", "mouse"):
            layer(name)
        for name, x, y, angle, lift in (
            ("arm-left", 77, 119, -pose.left_paw * 5.0, pose.left_paw),
            ("arm-right", 121, 120, pose.typing * 54.0 - pose.mouse * 2.5,
             pose.right_paw + pose.click * 0.6),
        ):
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            painter.translate(-x, -y - lift * 1.8)
            layer(name)
            painter.restore()
        painter.restore()


class PetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Miga")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(200, 200)
        self.art = CatArt()
        self.art.cache(self.width(), self.devicePixelRatioF())
        self.animations = Animations()
        self.last_frame = time.monotonic()
        self.press_position: QPoint | None = None
        self.press_origin = QPoint()
        self.dragging = False
        self.timer = QTimer(self)
        self.timer.setInterval(34)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 12)

    def tick(self) -> None:
        now = time.monotonic()
        self.animations.advance(min(now - self.last_frame, 0.1))
        self.last_frame = now
        self.update()

    def paintEvent(self, event) -> None:
        self.art.cache(self.width(), self.devicePixelRatioF())
        painter = QPainter(self)
        painter.scale(self.width() / 200.0, self.height() / 200.0)
        self.art.draw(painter, self.animations.pose)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition().toPoint()
            self.press_origin = self.pos()
            self.dragging = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.press_position is None:
            return
        delta = event.globalPosition().toPoint() - self.press_position
        if delta.manhattanLength() >= QApplication.startDragDistance():
            self.dragging = True
        if self.dragging:
            self.move(self.press_origin + delta)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.press_position is not None:
            if not self.dragging:
                self.animations.pet()
            self.press_position = None
            self.dragging = False

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Salir", QApplication.quit)
        menu.exec(event.globalPos())
