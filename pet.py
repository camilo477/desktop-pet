"""Transparent desktop window and the original layered character."""

from dataclasses import replace
import math
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup, QBitmap, QCursor, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from keyboard_distributions import DISTRIBUTIONS
from keyboard_layout import FORMATS, STANDARDS, Keyboard
from appearance import Appearance, COATS, EYES, NOSES
from animations import Animations
from character import CatArt
from activity import Activity, ActivityMonitor, supports_global_input


SIZES = {150: "Pequeño", 200: "Mediano", 300: "Grande"}
PET_HOLD_SECONDS = .32


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
    activity_ready = Signal()

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
        self.native_mac = platform == "cocoa"
        self.mac_input = None
        # Cocoa needs a native shape for clicks to reach other windows.
        self.mask_supported = platform in ("xcb", "cocoa") or platform.startswith("wayland")
        self.native_wayland = platform.startswith("wayland")
        self.wayland = None
        self.native_windows = platform == "windows"
        self.windows_input = None
        self.global_input = supports_global_input(platform)
        self.layout_mode = self.preference('layout_mode', ('auto', 'manual'), 'auto')
        self.manual_layout = self.preference('layout', DISTRIBUTIONS, 'us')
        self.detected_layout = None
        self.keyboard = Keyboard(self.preference('format', FORMATS, '100'),
                                 self.preference('standard', STANDARDS, 'ISO'),
                                 self.effective_layout())
        self.activity = ActivityMonitor(self.global_input, self.activity_ready.emit, self.keyboard)
        self.activity_ready.connect(self.input_arrived, Qt.ConnectionType.QueuedConnection)
        self.local_gaze = (0.0, 0.0)
        self.local_pointer = None
        self.local_pointer_time = -math.inf
        self._closed = False
        self.setWindowTitle("Miga")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if platform == "xcb":
            self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus)
        if self.native_mac:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(size if size in SIZES else 200, size if size in SIZES else 200)
        look = Appearance(self.preference('coat', COATS, 'original', 'appearance'),
                          self.preference('eyes', EYES, 'auto', 'appearance'),
                          self.preference('nose', NOSES, 'auto', 'appearance'))
        self.art = CatArt(self.keyboard, look)
        self.art.cache(self.width(), self.devicePixelRatioF())
        self.animations = Animations(self.keyboard)
        self.last_frame = time.monotonic()
        self.press_position: QPoint | None = None
        self.press_region = None
        self.press_side = 0.0
        self.press_time = 0.0
        self.press_origin = QPoint()
        self.dragging = False
        self.system_drag = False
        self.native_anchor = None
        self.native_motion_time = None
        self.drag_sample = None
        self.frame = QPixmap()
        self.last_mask = QRegion()
        self.mask_time = 0.0
        self.mask_signature = None
        self.timer = QTimer(self)
        self.timer.setInterval(34)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.position_timer = QTimer(self)
        self.position_timer.setInterval(750)
        self.position_timer.timeout.connect(self.check_native_release)
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
        if self.native_wayland:
            from wayland_activity import WaylandActivity
            self.wayland = WaylandActivity(self)
            preferred = self.settings.value('wayland/screen', '', type=str)
            for screen in app.screens():
                if preferred and screen.name() == preferred:
                    self.setScreen(screen)
                    break
        if self.global_input and self.native_windows:
            from windows_input import WindowsInput
            self.windows_input = WindowsInput(self.activity)
        if self.native_mac:
            from macos_input import MacInput
            from macos_window import prepare_panel
            prepare_panel(self)
            self.mac_input = MacInput(self.activity, self.mac_status_changed)
        self.render_frame()
        self.refresh_activity()

    def mac_status_changed(self, status):
        from macos_window import permission_notice
        if status == 'active':
            self._had_input_access = True
        permission_notice(self, status)

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
        if self.wayland:
            self.wayland.configure(self.activity.enabled)
        if self.windows_input:
            self.windows_input.configure(int(self.winId()) if self.activity.enabled else None)
        if self.mac_input:
            self.mac_input.configure(self.activity.enabled)
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
        if self.windows_input:
            self.windows_input.poll(now)
        if self.mac_input:
            self.mac_input.poll(now)
        if self._menu is not None and self.animations.sleeping and self.menu_has_pointer():
            self.activity.discard_menu_pointer()
        context_target = self.cursor_on_pet if self.animations.sleeping else None
        activity = self.activity.snapshot(context_target) if self.reactions else Activity()
        if self.reactions and self.detected_layout != activity.layout:
            self.detected_layout = activity.layout
            self.keyboard.layout = self.effective_layout()
        gaze = (0.0, 0.0)
        if now - self.local_pointer_time >= 1.2:
            self.local_pointer = None
        cursor_point = self.local_pointer
        if self.reactions and now - activity.mouse < .65:
            if self.global_input and (not self.mac_input or self.activity.native_pointer):
                cursor = QCursor.pos() - self.pos()
                cursor_point = QPointF(cursor) * (200 / self.width())
                screen = self.screen() or QApplication.primaryScreen()
                if screen:
                    area = screen.geometry()
                    head = self.art.head_position * (self.width() / 200)
                    gaze = (math.tanh((cursor.x() - head.x()) / max(1, area.width() * 0.28)),
                            math.tanh((cursor.y() - head.y()) / max(1, area.height() * 0.30)))
            else:
                gaze = self.local_gaze
        if self.press_position is not None:
            self.animations.interact()
        if self.press_position is not None or self._menu is not None:
            cursor_point = None
        if (self.press_region == 'head' and not self.dragging and not self.animations.pet_held
                and now - self.press_time >= PET_HOLD_SECONDS):
            self.animations.pet(self.press_side, held=True)
        offset = None
        if cursor_point is not None:
            offset = cursor_point - self.art.head_position
            offset = (offset.x(), offset.y())
        delta = (0, 0)
        if self.drag_sample is not None:
            position = self.pos()
            motion = position - self.drag_sample
            delta = (motion.x(), motion.y())
            if self.system_drag and not motion.isNull():
                self.native_motion_time = now
            self.drag_sample = position
        self.animations.advance(min(now - self.last_frame, 0.1), now, activity, gaze, offset, delta,
                                desktop_idle=self.wayland.idle(now) if self.wayland else None)
        interval = 100 if self.animations.sleeping else 34
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.last_frame = now
        self.render_frame()

    def input_arrived(self) -> None:
        if self._closed or self.paused or not self.reactions:
            return
        if time.monotonic() - self.last_frame >= 1 / 30:
            self.tick()
            self.timer.start(34)
        elif self.timer.interval() > 34:
            self.timer.start(34)

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
        if self.native_windows:
            # Windows hit-tests the alpha surface in native resolution.
            self.update()
            return
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
                     round(pose.tail_tip * 2),
                     round(pose.tail_touch * 60),
                     round(pose.lift * 3), round(pose.sway_x * 3), round(pose.sway_y * 3),
                     round(pose.motion.curl * 30), round(pose.motion.tilt * 3),
                     round(pose.sleep * 250), round(pose.balance_x * 2), round(pose.balance_y * 2),
                     round(pose.contact * 15), round(pose.mouse_dx * 2), round(pose.mouse_dy * 2),
                     round(pose.groom * 20), round(pose.yawn * 20))
        if handle and (force_mask or signature != self.mask_signature or pose.zzz > .01 or now - self.mask_time >= 0.1):
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
        if self.native_mac:
            from macos_window import prepare_panel
            prepare_panel(self)
        self.render_frame(force_mask=True)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, "frame"):
            self.render_frame(force_mask=True)
        return super().event(event)

    def nativeEvent(self, event_type, message):
        backend = getattr(self, 'windows_input', None)
        if backend:
            handled, result = backend.message(message)
            if handled:
                return True, result
        return super().nativeEvent(event_type, message)

    def mousePressEvent(self, event) -> None:
        if self.system_drag:
            self.finish_drag()
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position() * (200 / self.width())
            self.press_region = self.art.region_at(point)
            if self.press_region is None:
                event.ignore()
                return
            self.press_position = event.globalPosition().toPoint()
            self.press_origin = self.pos()
            self.press_side = max(-1, min(1, (point.x() - self.art.head_position.x()) / 30))
            self.press_time = time.monotonic()
            self.dragging = False
            self.system_drag = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if not self.mac_input or not self.activity.native_pointer:
                self.activity.pointer_click()
            if not self.paused:
                self.animations.interact()
                if self.timer.interval() > 34:
                    self.timer.start(34)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.system_drag and not event.buttons() & Qt.MouseButton.LeftButton:
            self.finish_drag()
        position = event.globalPosition()
        self.activity.pointer_moved(position.x(), position.y(), local=True)
        if not self.paused:
            self.local_pointer = event.position() * (200 / self.width())
            self.local_pointer_time = time.monotonic()
            offset = self.local_pointer - self.art.head_position
            self.local_gaze = (offset.x() / 100, offset.y() / 100)
            if self.press_position is None and not self.reactions and offset.manhattanLength() < 58:
                self.animations.interact()
        if self.press_position is None:
            return
        delta = event.globalPosition().toPoint() - self.press_position
        if not self.dragging and delta.manhattanLength() >= QApplication.startDragDistance():
            self.dragging = True
            self.activity.set_dragging(True)
            if not self.paused:
                self.animations.lift()
                self.drag_sample = self.pos()
            if self.native_wayland and self.windowHandle():
                self.native_anchor = event.position().toPoint()
                self.native_motion_time = time.monotonic()
                started = self.windowHandle().startSystemMove()
                self.wayland.drag_accepted = started
                self.system_drag = started and self.dragging
                if self.system_drag:
                    self.position_timer.start()
        if self.dragging and not self.system_drag and not self.native_wayland:
            self.move(self.press_origin + delta)

    def wheelEvent(self, event) -> None:
        if not self.activity.global_pointer_active:
            delta = event.angleDelta()
            pixels = event.pixelDelta()
            self.activity.pointer_scrolled(delta.x() / 120 or pixels.x() / 20,
                                           delta.y() / 120 or pixels.y() / 20)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.press_position is not None:
            delta = event.globalPosition().toPoint() - self.press_position
            if (not self.dragging and delta.manhattanLength() >= QApplication.startDragDistance()):
                # A compressed final movement may first arrive with the release.
                self.dragging = True
                if self.animations.pet_held:
                    self.animations.release_pet(quick=True)
            if self.dragging and not self.system_drag and not self.native_wayland:
                self.move(self.press_origin + delta)
            if not self.dragging and not self.paused:
                if self.animations.pet_held:
                    self.animations.release_pet()
                elif self.press_region == 'head':
                    self.animations.pet(self.press_side)
                else:
                    self.animations.touch(self.press_region)
            self.finish_drag()

    def check_native_release(self) -> None:
        # Qt can clear its button state as the compositor takes the grab. Give
        # re-entry, local motion or a real release time to settle the pose.
        # Bound only our visual grip if the compositor withholds the final event.
        if (self.system_drag and self.native_anchor is not None
                and (not self.last_mask.contains(self.native_anchor)
                     or (self.native_motion_time is not None
                         and time.monotonic() - self.native_motion_time >= 6))
                and not QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self.finish_drag()

    def enterEvent(self, event) -> None:
        if self.system_drag and not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.finish_drag()
        super().enterEvent(event)

    def finish_drag(self) -> None:
        self.position_timer.stop()
        moved = self.dragging
        if moved:
            self.activity.set_dragging(False)
            if self.windows_input and self.windows_input.active:
                self.windows_input.sync_cursor()
            if self.mac_input and self.activity.native_pointer:
                self.mac_input.sync_pointer()
            self.local_pointer = None
            if self.animations.carried:
                self.animations.put_down(time.monotonic())
        self.drag_sample = None
        self.press_position = None
        self.press_origin = QPoint()
        self.press_region = None
        self.dragging = False
        self.system_drag = False
        self.native_anchor = None
        self.native_motion_time = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if moved:
            self.ensure_visible()
            self.save_preferences()

    def leaveEvent(self, event) -> None:
        self.local_gaze = (0.0, 0.0)
        self.local_pointer = None
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
        if self.windows_input and self.activity.enabled:
            self.windows_input.configure(int(self.winId()))
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
        if checked:
            self.press_region = None
            self.local_pointer = None
            if self.animations.pet_held:
                self.animations.release_pet()
            self.drag_sample = None
        self.refresh_activity()
        self.save_preferences()

    def save_preferences(self) -> None:
        if not self.native_wayland:
            self.settings.setValue("position", self.pos())
        elif self.screen() and self.screen().name():
            self.settings.setValue("wayland/screen", self.screen().name())
        for key, value in (("size", self.width()),
                           ("always_on_top", self.always_on_top),
                           ("reactions", self.reactions), ("paused", self.paused)):
            self.settings.setValue(key, value)
        self.settings.sync()

    def preference(self, name, choices, default, group='keyboard'):
        value = self.settings.value(f'{group}/{name}', default, type=str)
        return value if value in choices else default

    def effective_layout(self):
        if self.layout_mode == 'manual':
            return self.manual_layout
        return self.detected_layout or 'us'

    def configure_keyboard(self, *, layout=None, form=None, standard=None):
        form = self.keyboard.form if form is None else form
        standard = self.keyboard.standard if standard is None else standard
        if form not in FORMATS or standard not in STANDARDS:
            return
        if layout is not None:
            if layout != 'auto' and layout not in DISTRIBUTIONS:
                return
            self.layout_mode = 'auto' if layout == 'auto' else 'manual'
            self.settings.setValue('keyboard/layout_mode', self.layout_mode)
            if self.layout_mode == 'manual':
                self.manual_layout = layout
                self.settings.setValue('keyboard/layout', layout)
        changed_shape = (form, standard) != (self.keyboard.form, self.keyboard.standard)
        if changed_shape:
            self.keyboard = Keyboard(form, standard, self.effective_layout())
            held = self.activity.set_keyboard(self.keyboard)
            self.animations.set_keyboard(self.keyboard, held)
            self.art.set_keyboard(self.keyboard)
            self.settings.setValue('keyboard/format', form)
            self.settings.setValue('keyboard/standard', standard)
        else:
            self.keyboard.layout = self.effective_layout()
        self.render_frame(force_mask=changed_shape)
        self.settings.sync()

    def keyboard_menu(self, parent):
        menu = parent.addMenu('Teclado')
        auto_name = DISTRIBUTIONS.get(self.detected_layout, 'sin identificar · muestra EE. UU.')
        if self.wayland and self.detected_layout and self.wayland.layout_source:
            auto_name += f' · {self.wayland.layout_source}'
        if self.detected_layout and (self.paused or not self.reactions):
            auto_name = f'última conocida · {auto_name}'
        layouts = {'auto': f'Automática ({auto_name})', **DISTRIBUTIONS}
        selected = 'auto' if self.layout_mode == 'auto' else self.manual_layout
        for title, parameter, options, current in (
            ('Distribución', 'layout', layouts, selected),
            ('Formato', 'form', FORMATS, self.keyboard.form),
            ('Estándar físico', 'standard', {s: s for s in STANDARDS}, self.keyboard.standard),
        ):
            self.choice_menu(menu, title, options, current,
                             lambda v, k=parameter: self.configure_keyboard(**{k: v}))

    @staticmethod
    def choice_menu(parent, title, options, current, choose):
        submenu = parent.addMenu(title)
        group = QActionGroup(submenu)
        for value, label in options.items():
            action = submenu.addAction(label)
            action.setCheckable(True)
            group.addAction(action)
            action.setChecked(value == current)
            action.triggered.connect(lambda checked, v=value: choose(v))

    def configure_appearance(self, look):
        if look == self.art.appearance:
            return
        self.art.set_appearance(look)
        self.render_frame()
        for key in ('coat', 'eyes', 'nose'):
            self.settings.setValue(f'appearance/{key}', getattr(look, key))
        self.settings.sync()

    def appearance_menu(self, parent):
        menu = parent.addMenu('Apariencia')
        for title, field, choices in (
            ('Pelaje', 'coat', {k: c.name for k,c in COATS.items()}),
            ('Ojos', 'eyes', {k: c[0] for k,c in EYES.items()}),
            ('Nariz', 'nose', {k: c[0] for k,c in NOSES.items()}),
        ):
            self.choice_menu(menu, title, choices, getattr(self.art.appearance, field),
                             lambda v, k=field: self.configure_appearance(replace(self.art.appearance, **{k:v})))
        menu.addSeparator()
        menu.addAction('Restaurar apariencia original', lambda: self.configure_appearance(Appearance()))

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
        self.keyboard_menu(menu)
        self.appearance_menu(menu)
        if self.wayland:
            self.wayland.menu(menu)
        if self.mac_input:
            from macos_window import permission_menu
            permission_menu(self, menu)
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
        if self.animations.sleeping:
            self.activity.discard_menu_pointer()
        self._menu = self.build_menu()
        self._menu.aboutToHide.connect(self.clear_menu)
        self._menu.popup(event.globalPos())
        event.accept()

    def cursor_on_pet(self):
        return QApplication.widgetAt(QCursor.pos()) is self

    def menu_has_pointer(self):
        pos = QCursor.pos()
        active = QApplication.activePopupWidget()
        while isinstance(active, QMenu):
            if active.rect().contains(active.mapFromGlobal(pos)):
                return True
            active = active.parentWidget()
        return False

    def clear_menu(self) -> None:
        if self._menu is not None:
            if self.animations.sleeping and self.menu_has_pointer():
                self.activity.discard_menu_pointer()
            self._menu.deleteLater()
            self._menu = None

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self.position_timer.stop()
        if self.windows_input:
            self.windows_input.configure(None)
        if self.wayland:
            self.wayland.configure(False)
        if self.mac_input:
            self.mac_input.close()
        self.activity.stop()
        self.save_preferences()
        if self._menu is not None:
            self._menu.close()

    def closeEvent(self, event) -> None:
        self.shutdown()
        event.accept()
        QApplication.quit()
