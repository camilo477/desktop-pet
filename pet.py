"""Transparent desktop window and the original layered character."""

import math
import time

from PySide6.QtCore import QEvent, QPoint, QRect, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QActionGroup, QBitmap, QCursor, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from animations import Animations
from character import CatArt
from activity import Activity, ActivityMonitor, supports_global_input


SIZES = {150: "Pequeño", 200: "Mediano", 300: "Grande"}


def visible_position(position: QPoint, size: QSize, areas: list[QRect]) -> QPoint:
    if not areas:
        return position
    window = QRect(position, size)

    def score(area: QRect) -> tuple[int, int]:
        overlap = area.intersected(window)
        return (overlap.width() * overlap.height(),
                -(area.center() - window.center()).manhattanLength())

    area = max(areas, key=score)
    return QPoint(
        max(area.left(), min(position.x(), max(area.left(), area.right() - size.width() + 1))),
        max(area.top(), min(position.y(), max(area.top(), area.bottom() - size.height() + 1))),
    )


class PetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings()
        try:
            size = self.settings.value("size", 200, type=int)
        except (TypeError, ValueError):
            size = 200
        self.always_on_top = self.settings.value("always_on_top", True, type=bool)
        self.reactions = self.settings.value("reactions", True, type=bool)
        self.paused = self.settings.value("paused", False, type=bool)
        platform = QApplication.platformName().lower()
        self.mask_supported = platform == "xcb" or platform.startswith("wayland")
        self.native_wayland = platform.startswith("wayland")
        self.global_input = supports_global_input(platform)
        self.activity = ActivityMonitor(self.global_input)
        self.local_gaze = (0.0, 0.0)
        self._closed = False
        self.setWindowTitle("Miga")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(size if size in SIZES else 200, size if size in SIZES else 200)
        self.art = CatArt()
        self.art.cache(self.width(), self.devicePixelRatioF())
        self.animations = Animations()
        self.last_frame = time.monotonic()
        self.press_position: QPoint | None = None
        self.head_press: float | None = None
        self.press_origin = QPoint()
        self.dragging = False
        self.system_drag = False
        self.frame = QPixmap()
        self.last_mask = QRegion()
        self.mask_time = 0.0
        self.mask_signature = None
        self.timer = QTimer(self)
        self.timer.setInterval(34)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.setInterval(300)
        self.position_timer.timeout.connect(self.finish_drag)
        self._menu = None
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            default = QPoint(area.right() - self.width() - 24, area.bottom() - self.height() - 12)
            position = self.settings.value("position", default)
            if not isinstance(position, QPoint):
                position = default
            if not self.native_wayland:
                self.move(self.clamp_position(position))
        app = QApplication.instance()
        app.screenAdded.connect(self.watch_screen)
        app.screenRemoved.connect(lambda screen: QTimer.singleShot(0, self.ensure_visible))
        for screen in app.screens():
            self.watch_screen(screen)
        self.render_frame()
        self.refresh_activity()

    def clamp_position(self, position: QPoint) -> QPoint:
        return visible_position(position, self.size(),
                                [screen.availableGeometry() for screen in QApplication.screens()])

    def ensure_visible(self) -> None:
        if not self.native_wayland and not self._closed:
            self.move(self.clamp_position(self.pos()))

    def watch_screen(self, screen) -> None:
        screen.availableGeometryChanged.connect(self.ensure_visible)
        QTimer.singleShot(0, self.ensure_visible)

    def refresh_activity(self) -> None:
        self.activity.set_enabled(self.reactions and not self.paused)
        if not self.reactions or self.paused:
            self.animations.clear_input()
            self.render_frame()
        self.last_frame = time.monotonic()
        if self.paused:
            self.timer.stop()
        else:
            self.timer.start()

    def tick(self) -> None:
        now = time.monotonic()
        activity = self.activity.snapshot() if self.reactions else Activity()
        self.art.set_layout(activity.layout)
        gaze = (0.0, 0.0)
        if self.reactions and now - activity.mouse < .65:
            if self.global_input:
                cursor = QCursor.pos() - self.pos()
                screen = self.screen() or QApplication.primaryScreen()
                if screen:
                    area = screen.geometry()
                    gaze = (math.tanh((cursor.x() - self.width() * 0.505) / max(1, area.width() * 0.28)),
                            math.tanh((cursor.y() - self.height() * 0.38) / max(1, area.height() * 0.30)))
            else:
                gaze = self.local_gaze
        self.animations.advance(min(now - self.last_frame, 0.1), now, activity, gaze)
        interval = 100 if self.animations.sleeping else 34
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.last_frame = now
        self.render_frame()

    def render_frame(self, force_mask: bool = False) -> None:
        ratio = self.devicePixelRatioF()
        self.art.cache(self.width(), ratio)
        pixels = math.ceil(self.width() * ratio)
        if self.frame.width() != pixels or self.frame.devicePixelRatio() != ratio:
            self.frame = QPixmap(pixels, pixels)
            self.frame.setDevicePixelRatio(ratio)
        self.frame.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.frame)
        painter.scale(self.width() / 200.0, self.height() / 200.0)
        self.art.draw(painter, self.animations.pose)
        painter.end()
        now = time.monotonic()
        handle = self.windowHandle()
        pose = self.animations.pose
        signature = (round(pose.left_x * 2), round(pose.left_y * 2),
                     round(pose.right_x * 2), round(pose.right_y * 2),
                     round(pose.head_x * 20), round(pose.head_y * 20),
                     round(pose.head_tilt * 3), round(pose.pet * 30),
                     round(pose.ear_left * 2), round(pose.ear_right * 2),
                     round(pose.tail * math.sin(pose.tail_phase) * 20),
                     round(pose.tail * math.cos(pose.tail_phase) * 20),
                     round(pose.sleep * 250), round(pose.balance_x * 2), round(pose.balance_y * 2),
                     round(pose.groom * 20), round(pose.yawn * 20))
        if handle and (force_mask or signature != self.mask_signature or now - self.mask_time >= 0.1):
            # Native masks use logical pixels; keep antialiased edges inside the mask.
            image = self.frame.toImage().scaled(self.size())
            image.setDevicePixelRatio(1)
            base = QRegion(QBitmap.fromImage(image.createMaskFromColor(0, Qt.MaskMode.MaskInColor)))
            region = base
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                region = region.united(base.translated(dx, dy))
            if force_mask or region != self.last_mask:
                if self.mask_supported:
                    handle.setMask(region)
                self.last_mask = region
            self.mask_time = now
            self.mask_signature = signature
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.frame)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.render_frame(force_mask=True)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, "frame"):
            self.render_frame(force_mask=True)
        return super().event(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition().toPoint()
            self.press_origin = self.pos()
            self.head_press = self.art.head_hit(event.position() * (200 / self.width()))
            self.dragging = False
            self.system_drag = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.activity.pointer_click()
            if not self.paused:
                self.animations.interact()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        position = event.globalPosition()
        self.activity.pointer_moved(position.x(), position.y(), local=True)
        if self.reactions and not self.paused:
            self.local_gaze = ((event.position().x() / self.width() - 0.505) * 2.0,
                               (event.position().y() / self.height() - 0.38) * 2.0)
        if self.press_position is None:
            return
        delta = event.globalPosition().toPoint() - self.press_position
        if not self.dragging and delta.manhattanLength() >= QApplication.startDragDistance():
            self.dragging = True
            if self.native_wayland and self.windowHandle():
                self.system_drag = self.windowHandle().startSystemMove()
        if self.dragging and not self.system_drag:
            self.move(self.press_origin + delta)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.press_position is not None:
            if not self.dragging and not self.paused:
                if self.head_press is not None and self.art.head_hit(event.position() * (200 / self.width())) is not None:
                    self.animations.pet(self.head_press)
                else:
                    self.animations.interact()
            self.finish_drag()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.native_wayland and hasattr(self, "position_timer"):
            self.position_timer.start()

    def finish_drag(self) -> None:
        self.position_timer.stop()
        self.press_position = None
        self.head_press = None
        self.dragging = False
        self.system_drag = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.ensure_visible()
        self.save_preferences()

    def leaveEvent(self, event) -> None:
        self.local_gaze = (0.0, 0.0)
        super().leaveEvent(event)

    def set_size(self, size: int) -> None:
        if size not in SIZES:
            return
        bottom = self.pos() + QPoint(self.width() // 2, self.height())
        self.setFixedSize(size, size)
        if not self.native_wayland:
            self.move(self.clamp_position(bottom - QPoint(size // 2, size)))
        self.render_frame(force_mask=True)
        self.save_preferences()

    def set_always_on_top(self, checked: bool) -> None:
        self.always_on_top = checked
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()
        self.ensure_visible()
        self.render_frame(force_mask=True)
        self.save_preferences()

    def set_reactions(self, checked: bool) -> None:
        self.reactions = checked
        self.local_gaze = (0.0, 0.0)
        self.refresh_activity()
        self.save_preferences()

    def set_paused(self, checked: bool) -> None:
        self.paused = checked
        self.refresh_activity()
        self.save_preferences()

    def save_preferences(self) -> None:
        for key, value in (("position", self.pos()), ("size", self.width()),
                           ("always_on_top", self.always_on_top),
                           ("reactions", self.reactions), ("paused", self.paused)):
            self.settings.setValue(key, value)
        self.settings.sync()

    def build_menu(self) -> QMenu:
        menu = QMenu(self)
        size_menu = menu.addMenu("Tamaño")
        sizes = QActionGroup(size_menu)
        sizes.setExclusive(True)
        for size, title in SIZES.items():
            action = size_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(self.width() == size)
            sizes.addAction(action)
            action.triggered.connect(lambda checked, value=size: self.set_size(value))
        for label, checked, callback in (
            ("Siempre visible", self.always_on_top, self.set_always_on_top),
            ("Reaccionar a actividad", self.reactions, self.set_reactions),
            ("Reanudar animaciones" if self.paused else "Pausar animaciones",
             self.paused, self.set_paused),
        ):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(checked)
            action.toggled.connect(callback)
        menu.addAction("Salir", self.close)
        return menu

    def contextMenuEvent(self, event) -> None:
        if self._menu is not None:
            return
        if not self.paused:
            self.animations.interact()
        self._menu = self.build_menu()
        self._menu.aboutToHide.connect(self.clear_menu)
        self._menu.popup(event.globalPos())
        event.accept()

    def clear_menu(self) -> None:
        if self._menu is not None:
            self._menu.deleteLater()
            self._menu = None

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self.position_timer.stop()
        self.activity.stop()
        self.save_preferences()
        if self._menu is not None:
            self._menu.close()

    def closeEvent(self, event) -> None:
        self.shutdown()
        event.accept()
        QApplication.quit()
