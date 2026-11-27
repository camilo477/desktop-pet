"""Small Cocoa adjustments to Qt's own tool panel."""

import AppKit
import objc
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QToolTip

STATUS = {'off': 'Desactivada', 'active': 'Activa', 'denied': 'Sin permiso · modo local',
          'restricted': 'Suspendida por macOS', 'unavailable': 'No disponible · modo local'}


def prepare_panel(widget):
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    view = objc.objc_object(c_void_p=int(widget.winId()))
    panel = view.window()
    if panel is not None:
        if panel.isKindOfClass_(AppKit.NSPanel):
            panel.setStyleMask_(panel.styleMask() | AppKit.NSWindowStyleMaskNonactivatingPanel)
            panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setHasShadow_(False)
        panel.setLevel_(AppKit.NSFloatingWindowLevel if widget.always_on_top else AppKit.NSNormalWindowLevel)
        behavior = panel.collectionBehavior()
        if widget.settings.value('macos/all_spaces', True, type=bool):
            # Cocoa treats these two Spaces policies as mutually exclusive.
            behavior &= ~AppKit.NSWindowCollectionBehaviorMoveToActiveSpace
            behavior |= AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        else:
            behavior &= ~AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        panel.setCollectionBehavior_(behavior)
        widget.timer.attach(panel)


def permission_notice(widget, status):
    if status != 'denied':
        return
    key = 'privacy/input_notice_shown'
    if widget.settings.value(key, False, type=bool) and not getattr(widget, '_had_input_access', False):
        return
    widget._had_input_access = False
    widget.settings.setValue(key, True)
    def show():
        if widget.isVisible() and widget.mac_input.status == 'denied':
            QToolTip.showText(widget.mapToGlobal(widget.rect().center()),
                              'Miga está en modo local. Clic derecho → Entrada global en macOS.', widget)
    QTimer.singleShot(350, widget, show)


def window_menu(widget, parent):
    backend = widget.mac_input
    menu = parent.addMenu('Entrada global en macOS')
    menu.addAction(STATUS[backend.status]).setEnabled(False)

    def explain():
        box = QMessageBox(widget)
        box.setWindowTitle('Entrada global de Miga')
        box.setText('La monitorización de entrada permite que Miga reaccione mientras usas otras aplicaciones.')
        box.setInformativeText('Solo utiliza posiciones físicas de teclas, movimiento y rueda en memoria. '
                               'No lee texto ni guarda un historial. Puedes conceder o retirar el permiso en '
                               'Ajustes del Sistema → Privacidad y seguridad → Monitorización de entrada. '
                               'Si macOS lo indica, cierra Miga y vuelve a abrirlo. Sin permiso siguen disponibles '
                               'las caricias, los menús y las animaciones.')
        box.addButton(QMessageBox.StandardButton.Close)
        request = None
        if backend.status == 'denied':
            request = box.addButton('Solicitar permiso', QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if request is not None and box.clickedButton() == request:
            backend.request_access()

    menu.addAction('Información y permisos…', explain)

    def set_all_spaces(checked):
        widget.settings.setValue('macos/all_spaces', checked)
        widget.settings.sync()
        prepare_panel(widget)

    action = parent.addAction('En todos los escritorios')
    action.setCheckable(True)
    action.setChecked(widget.settings.value('macos/all_spaces', True, type=bool))
    action.toggled.connect(set_all_spaces)
