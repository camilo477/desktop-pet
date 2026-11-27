"""Monitor placement and KWin wrapper regressions, without a desktop session."""

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QRect, QSettings, QSize
from PySide6.QtQml import QJSEngine
from PySide6.QtWidgets import QApplication
from pet import PetWindow, visible_position
from wayland_idle import compositor_matches

ROOT = Path(__file__).resolve().parents[1]


def check_compositor():
    def executable(path, **kwargs):
        assert str(path) == '/proc/40/exe'  # Never require access to privileged KWin's exe.
        return Path('/usr/bin/kwin_wayland_wrapper')

    with patch('wayland_idle.compositor_pid', return_value=40):
        assert compositor_matches(40)
        assert not compositor_matches(0)
        with patch.object(Path, 'resolve', executable), patch.object(Path, 'read_text', return_value='PPid:\t40\n'):
            assert compositor_matches(41)
        with patch.object(Path, 'resolve', executable), patch.object(Path, 'read_text', return_value='PPid:\t99\n'):
            assert not compositor_matches(41)  # A nested compositor on the host's session bus.
        with patch.object(Path, 'resolve', return_value=Path('/usr/bin/other-launcher')):
            assert not compositor_matches(41)
        with patch.object(Path, 'resolve', side_effect=PermissionError):
            assert not compositor_matches(41)
    with patch('wayland_idle.compositor_pid', return_value=0):
        assert not compositor_matches(0)


MOCK = r'''
function signal() {
    const slots = [];
    return {connect: f => slots.push(f), emit: function () { slots.forEach(f => f()); }};
}
function assert(ok, message) { if (!ok) throw new Error(message); }
const outputs = [
    {name: 'DP-3', area: {x: 0, y: 0, width: 1080, height: 1862}},
    {name: 'HDMI-A-1', area: {x: 1080, y: 1052, width: 1920, height: 1080}}
];
function window(pid, caption) {
    const value = {pid: pid, caption: caption, captionNormal: caption, output: outputs[1],
        transient: false, keepAbove: false, move: false,
        frameGeometryChanged: signal(), interactiveMoveResizeFinished: signal()};
    // Model Qt's live QRectF reference, including mutation after a getter call.
    const geometry = {x: 1200, y: 1100, width: 200, height: 200};
    Object.defineProperty(value, 'frameGeometry', {
        get: () => geometry,
        set: r => { Object.assign(geometry, r); value.frameGeometryChanged.emit(); }
    });
    return value;
}
const own = window(42, 'Miga');
const unrelated = window(43, 'Miga');
const menu = window(42, 'Miga'); menu.transient = true;
const messages = [];
const replies = [];
function callDBus(service, path, iface, method, payload, reply) {
    messages.push(JSON.parse(payload));
    if (reply) replies.push(reply);
}
function flush() {
    let remaining = 100;
    while (replies.length && remaining--) replies.shift()();
    assert(remaining > 0, 'Placement must not loop');
}
const KWin = {MaximizeArea: 0};
const workspace = {
    screens: outputs.slice(), currentDesktop: {},
    windowAdded: signal(), windowRemoved: signal(), screensChanged: signal(),
    virtualScreenGeometryChanged: signal(),
    cursorPosChanged: signal(), cursorPos: {x: 100, y: 100},
    windowList: () => [unrelated, menu, own],
    clientArea: (kind, target) => (target.output || target).area,
    sendClientToScreen: (client, output) => { client.output = output; }
};
'''


def check_script():
    engine = QJSEngine()
    config = dict(pid=42, service='test', interface='test', generation=1,
                  action='restore', screen='DP-3', primary='HDMI-A-1',
                  position=[700, 1500], above=True)
    source = MOCK + '\nconst config = ' + json.dumps(config) + ';\n'
    source += (ROOT / 'kwin_window.js').read_text()
    source += r'''
flush();
assert(own.output.name === 'DP-3' && own.frameGeometry.x === 700 && own.frameGeometry.y === 1500,
       'Restore screen-relative position');
assert(own.keepAbove && !unrelated.keepAbove && !menu.keepAbove, 'Only our toplevel is affected');
own.frameGeometry = {x: 1000, y: 1800, width: 300, height: 300};
flush();
assert(own.frameGeometry.x <= 780 && own.frameGeometry.y <= 1562, 'Resize stays inside portrait work area');
own.move = true;
own.frameGeometry = {x: 2850, y: 2000, width: 300, height: 300};
own.output = outputs[1];
flush();
assert(own.frameGeometry.x === 2850, 'Do not clamp during a cross-monitor drag');
own.move = false;
own.interactiveMoveResizeFinished.emit();
flush();
assert(own.frameGeometry.x === 2700 && own.frameGeometry.y === 1832, 'Clamp on release');
assert(messages[messages.length - 1].released, 'Release reaches the animation controller');
workspace.screens = [outputs[0]];
workspace.screensChanged.emit();
flush();
assert(own.output === outputs[0] && own.frameGeometry.x === 780, 'Recover after output removal');
outputs[0].area = {x: -1080, y: -500, width: 1080, height: 1862};
workspace.virtualScreenGeometryChanged.emit();
flush();
assert(own.frameGeometry.x === -300 && own.frameGeometry.y <= 1062, 'Negative origins and rotation');
assert(unrelated.frameGeometry.x === 1200 && menu.frameGeometry.x === 1200, 'Other windows unchanged');
'''
    result = engine.evaluate(source, 'kwin-placement-regression.js')
    assert not result.isError(), result.toString() + '\n' + result.property('stack').toString()


def check_qt():
    areas = [QRect(0, 0, 1080, 1920), QRect(1080, 1052, 1920, 1080)]
    assert visible_position(QPoint(2000, 100), QSize(300, 300), areas) == QPoint(2000, 1052)
    assert visible_position(QPoint(900, 500), QSize(300, 300), areas) == QPoint(780, 500)
    assert visible_position(QPoint(3000, 2100), QSize(300, 300), areas) == QPoint(2700, 1832)
    window = PetWindow()
    try:
        menu = window.build_menu()
        screen_menu = next(action.menu() for action in menu.actions() if action.text() == 'Pantalla')
        screen_menu.actions()[0].trigger()
        assert window.screen().availableGeometry().contains(window.geometry())
        before = window.pos()
        window.move_to_screen('disconnected-output')
        assert window.pos() == before
    finally:
        window.shutdown()


if __name__ == '__main__':
    app = QApplication([])
    app.setOrganizationName('miga-test')
    app.setApplicationName('screens')
    with TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        check_compositor()
        check_script()
        check_qt()
    print('PASS: KWin wrapper, portrait/offset/negative outputs, resize, drag, hotplug and monitor menu.')
