"""Placement of Miga's own Wayland window through the current KWin session."""

import json
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import ClassInfo, QObject, QPoint, QRect, QTimer, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage

from wayland_idle import compositor_matches


INTERFACE = 'io.github.camilo477.Miga.Placement'


@ClassInfo(**{'D-Bus Interface': INTERFACE})
class KWinWindow(QObject):
    """A temporary, PID-scoped script; no installed rules or desktop changes."""

    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.bus = QDBusConnection.sessionBus()
        self.service = f'{INTERFACE}.p{os.getpid()}'
        self.plugin = f'miga-placement-{os.getpid()}'
        self.directory = None
        self.active = False
        self.position = None
        self.pointer = None
        self.pointer_enabled = False
        self.geometry = QRect()
        self.above = None
        self.screen_name = ''
        self.generation = 0
        self.applied_generation = 0
        self.closed = False
        self.error = None
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(pet.save_preferences)

    def call(self, path, interface, method, *args):
        message = QDBusMessage.createMethodCall('org.kde.KWin', path, interface, method)
        message.setAutoStartService(False)
        message.setArguments(list(args))
        reply = self.bus.call(message, timeout=1000)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            raise RuntimeError(reply.errorMessage())
        return reply.arguments()

    def start(self):
        if self.closed or not self.bus.isConnected():
            return
        try:
            # Never control the host desktop from a nested Wayland session.
            owner = self.bus.interface().servicePid('org.kde.KWin')
            if not owner.isValid() or not compositor_matches(owner.value()):
                self.error = 'KWin does not own this Wayland connection'
                return
            if not self.bus.registerService(self.service):
                self.error = self.bus.lastError().message()
                return
            if not self.bus.registerObject('/Placement', self,
                    QDBusConnection.RegisterOption.ExportAllSlots):
                self.bus.unregisterService(self.service)
                self.error = self.bus.lastError().message()
                return
            self.directory = tempfile.TemporaryDirectory(prefix='miga-kwin-')
            self.apply('restore')
        except (OSError, RuntimeError) as error:
            self.error = str(error)
            self.close()

    def apply(self, action='keep', screen=''):
        if self.closed or self.directory is None:
            return
        settings = self.pet.settings
        saved = settings.value('wayland/position')
        self.generation += 1
        config = dict(pid=os.getpid(), service=self.service, interface=INTERFACE,
                      generation=self.generation, action=action,
                      screen=screen or settings.value('wayland/screen', '', type=str),
                      primary=self.pet.primary_screen_name(),
                      position=[saved.x(), saved.y()] if isinstance(saved, QPoint) else None,
                      input=self.pointer_enabled,
                      above=self.pet.always_on_top)
        try:
            self.call('/Scripting', 'org.kde.kwin.Scripting', 'unloadScript', self.plugin)
            path = Path(self.directory.name) / 'placement.js'
            source = Path(__file__).with_name('kwin_window.js').read_text()
            path.write_text('const config = ' + json.dumps(config) + ';\n' + source)
            result = self.call('/Scripting', 'org.kde.kwin.Scripting', 'loadScript', str(path), self.plugin)
            if not result or result[0] < 0:
                raise RuntimeError('KWin did not load the placement script')
            self.call(f'/Scripting/Script{result[0]}', 'org.kde.kwin.Script', 'run')
        except (OSError, RuntimeError) as error:
            self.error = str(error)
            self.close()

    def configure_pointer(self, enabled):
        if enabled == self.pointer_enabled:
            return
        self.pointer_enabled = enabled
        self.pointer = None
        self.pet.activity.reset_pointer_origin()
        self.apply()

    @Slot(str)
    def pointerMoved(self, payload):
        if self.closed or not self.pointer_enabled or not self.pet.activity.enabled:
            return
        try:
            state = json.loads(payload)
            if state['generation'] != self.generation:
                return
            x, y = state['x'], state['y']
            if not all(isinstance(v, (int, float)) and abs(v) < 1000000 for v in (x, y)):
                return
            self.pointer = QPoint(round(x), round(y))
        except (ValueError, TypeError, KeyError, OverflowError):
            return
        self.pet.activity.native_pointer = True
        self.pet.activity.pointer_moved(x, y)

    @Slot(str)
    def report(self, payload):
        if self.closed:
            return
        try:
            state = json.loads(payload)
            if state['generation'] != self.generation:
                return
            x, y = state['x'], state['y']
            if not all(isinstance(v, (int, float)) and abs(v) < 1000000 for v in (x, y)):
                return
            self.position = QPoint(round(x), round(y))
            self.geometry = QRect(round(x), round(y), round(state['width']), round(state['height']))
            self.screen_name = str(state['screen'])
            offset = QPoint(round(state['offsetX']), round(state['offsetY']))
        except (ValueError, TypeError, KeyError, OverflowError):
            return
        self.active = True
        self.above = state.get('above')
        self.applied_generation = self.generation
        self.pet.settings.setValue('wayland/screen', self.screen_name)
        self.pet.settings.setValue('wayland/position', offset)
        if self.pet.drag_sample is not None:
            import time
            self.pet.sample_drag(time.monotonic())
        if state.get('released') and self.pet.system_drag:
            self.pet.finish_drag()
        self.save_timer.start()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.active = False
        self.pointer = None
        self.save_timer.stop()
        if self.directory is not None:
            try:
                self.call('/Scripting', 'org.kde.kwin.Scripting', 'unloadScript', self.plugin)
            except RuntimeError:
                pass
            self.directory.cleanup()
            self.directory = None
        self.bus.unregisterObject('/Placement')
        self.bus.unregisterService(self.service)
