"""Lifetime and capability state for Miga's optional Wayland observers."""

import asyncio
import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox

from wayland_desktop import Unavailable, service
from wayland_idle import observe


class DesktopSession:
    """One interruptible I/O loop. All painting and animation stay on Qt's thread."""

    def __init__(self, notify):
        self.notify = notify
        self.loop = asyncio.new_event_loop()
        self.stop = asyncio.Event()
        self.thread = threading.Thread(target=self.run, name='Wayland desktop', daemon=True)
        self.thread.start()

    async def retry(self, kind):
        while True:
            try:
                if kind == 'standard':
                    await observe(self.report)
                else:
                    await service(kind, self.report)
            except ImportError:
                return  # Each optional binding can operate without the other.
            except (OSError, ValueError, RuntimeError, EOFError, asyncio.TimeoutError, Unavailable):
                pass
            self.report(kind, None)
            if kind == 'standard':
                self.report('surface', None)
            await asyncio.sleep(12)

    def report(self, kind, value):
        self.notify(self, kind, value)

    async def watch(self):
        desktops = set(os.environ.get('XDG_CURRENT_DESKTOP', '').upper().split(':'))
        kinds = ['standard']
        # A desktop name selects probes only. A successful protocol reply
        # establishes the capability. Avoid consulting a different desktop's settings.
        if 'KDE' in desktops or not any(desktops):
            kinds.append('kde')
        if 'GNOME' in desktops or not any(desktops):
            kinds.extend(('mutter', 'gnome'))
        tasks = [asyncio.create_task(self.retry(kind)) for kind in kinds]
        try:
            await self.stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.watch())
        finally:
            self.loop.close()

    def close(self):
        self.loop.call_soon_threadsafe(self.stop.set)


class WaylandActivity(QObject):
    updated = Signal(object, str, object)

    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.session = None
        self.sources = {}
        self.layouts = {}
        self.surface = frozenset()
        self.layout_source = None
        self.drag_accepted = None
        self.updated.connect(self.receive, Qt.ConnectionType.QueuedConnection)

    def configure(self, enabled):
        if enabled == bool(self.session):
            return
        if enabled:
            self.session = DesktopSession(self.updated.emit)
        else:
            session, self.session = self.session, None
            session.close()
            self.sources.clear()
            self.layouts.clear()
            self.layout_source = None
            self.surface = frozenset()

    def selected(self):
        standard = self.sources.get('standard')
        if standard and standard[0] >= 2:
            return 'ext-idle-notify v2 · entrada', standard[1]
        if self.sources.get('mutter'):
            return 'Mutter IdleMonitor', self.sources['mutter'][1]
        if standard:
            return 'ext-idle-notify v1 · respeta inhibidores', standard[1]
        return None, None

    def idle(self, now):
        source, since = self.selected()
        if not source:
            return None
        return 0. if since is None else max(0., now - since)

    def receive(self, session, kind, value):
        if session is not self.session or session is None:
            return  # A completion from before pause/restart.
        if kind == 'surface':
            self.surface = value or frozenset()
        elif kind in ('kde', 'gnome'):
            self.layouts[kind] = value
            source = self.layouts.get('kde') or self.layouts.get('gnome')
            self.layout_source, layout = source or (None, None)
            self.pet.activity.set_layout(layout)
        else:
            previous, before = self.selected()
            self.sources[kind] = value
            current, after = self.selected()
            if current and after is None and (before is not None or (not previous and self.pet.animations.sleeping)):
                self.pet.animations.interact()
                self.pet.input_arrived()

    def menu(self, parent):
        menu = parent.addMenu('Wayland')
        source, _ = self.selected()
        hardware = self.pet.linux_input
        placement = self.pet.kwin
        mode = ('Entrada física' if hardware and hardware.keyboard_count else
                'Actividad general' if source else 'Local')
        if not self.session:
            mode += ' · observación desactivada'
        keyboard = f'{hardware.keyboard_count} dispositivo(s)' if hardware and hardware.keyboard_count else 'sin permiso de lectura'
        pointer = 'KDE' if placement and placement.active and placement.pointer_enabled else 'local'
        scroll = 'activo' if hardware and hardware.pointer_count else 'local'
        for label in (f'Modo · {mode}', f'Teclado físico · {keyboard}',
                      f'Puntero · {pointer} · Scroll · {scroll}',
                      f'Inactividad · {source or "sin observador activo"}',
                      f'Distribución · {self.layout_source or "sin fuente disponible"}'):
            menu.addAction(label).setEnabled(False)
        if hardware and hardware.error:
            menu.addAction(hardware.error).setEnabled(False)
        if placement and placement.active:
            menu.addAction(f'Ubicación · KDE · {placement.screen_name}').setEnabled(False)
        def details():
            drag = {True: 'aceptado', False: 'rechazado', None: 'sin probar'}.get(self.drag_accepted)
            shape = 'anunciadas' if 'wl_compositor' in self.surface else 'gestionadas por Qt'
            scale = ('El compositor anuncia escala fraccional. '
                     if 'wp_fractional_scale_manager_v1' in self.surface else '')
            layer = ('Ofrece capas, pero Miga utiliza una ventana móvil. '
                     if 'zwlr_layer_shell_v1' in self.surface else '')
            placement_info = ('La integración con KDE guarda la posición, permite elegir pantalla '
                              'y aplica Siempre visible. '
                              if placement and placement.active else
                              'El compositor decide la ubicación y si mantiene la ventana encima. ')
            QMessageBox.information(self.pet, 'Miga en Wayland',
                f'Arrastre nativo {drag}. Regiones de entrada {shape}. {scale}{layer}'
                + placement_info +
                'Las caricias, los pelajes y el teclado manual siguen disponibles. '
                'La entrada física autorizada anima las teclas, el ratón y el scroll. '
                'Sin permiso de lectura, la actividad general regula el sueño. '
                'En modo local, Miga cuenta la actividad que recibe en su ventana.')
        menu.addAction('Información…', details)
