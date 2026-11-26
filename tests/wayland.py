"""Synthetic provider edges and shared rendering with isolated preferences."""

import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication
from animations import Animations
from wayland_activity import WaylandActivity
from wayland_desktop import configured_layout, kde_layout
from pet import PetWindow


def check_clock():
    a = Animations()
    # Twenty minutes of confirmed non-idle status without any local inputs.
    for now in range(1201):
        a.advance(.034, now, desktop_idle=0)
    assert not a.sleep_goal and not a.pose.relax and a.action_kind is None
    for second in range(15, 186):
        for frame in range(30):
            age = second + frame / 30
            a.advance(1/30, 1200 + age - 15, desktop_idle=age)
        if second == 65:
            assert 0 < a.pose.relax < .2
    assert a.sleeping and a.pose.zzz > .9
    a.interact()
    a.advance(1/30, 1371, desktop_idle=0)
    assert not a.sleeping and not a.pose.pressed and not a.pose.contacts
    assert a.pose.mouse_dx == a.pose.mouse_dy == 0


def check_capabilities():
    w = PetWindow()
    wl = WaylandActivity(w)
    w.wayland = wl
    session = wl.session = object()
    wl.receive(session, 'standard', (1, time.monotonic() - 22))
    assert wl.idle(time.monotonic()) >= 22
    wl.receive(session, 'mutter', (1, None))
    assert wl.selected() == ('Mutter IdleMonitor', None)
    wl.receive(session, 'standard', (2, None))
    assert 'v2' in wl.selected()[0]
    wl.receive(session, 'standard', None)
    wl.receive(session, 'mutter', None)
    assert wl.idle(time.monotonic()) is None
    wl.receive(session, 'kde', ('KDE', 'dvorak'))
    w.tick()
    assert w.keyboard.layout == 'dvorak'
    w.configure_keyboard(layout='fr')
    wl.receive(session, 'kde', ('KDE', 'de'))
    w.tick()
    assert w.keyboard.layout == 'fr'
    assert 'Wayland' in [a.text() for a in w.build_menu().actions()]
    w.native_wayland = True
    w.settings.setValue('position', QPoint(-45, 63))
    w.save_preferences()
    assert w.settings.value('position') == QPoint(-45, 63)
    wl.session = None
    wl.receive(session, 'mutter', (1, None))
    assert not wl.selected()[0]
    w.close()


def check_layouts():
    from dbus_next import Variant
    err = [('us', 'custom', 'English (programmer Dvorak)')]
    rows = [('us', 'ignored', 'English (US)'), ('us', 'us', 'English (Colemak)'), *err]
    assert [kde_layout(rows, i) for i in range(4)] == ['us', 'colemak', None, None]
    for source, result in [('us', 'us'), ('us+dvorak', 'dvorak'), ('gb', 'gb'), ('es', 'es'),
                           ('latam', 'latam'), ('fr', 'fr'), ('de', 'de'), ('us+custom', None)]:
        assert configured_layout(Variant('a(ss)', [['xkb', source]])) == result
    for rows in ([['xkb', 'us'], ['xkb', 'de']], [['ibus', 'anything']], []):
        assert configured_layout(Variant('a(ss)', rows)) is None


if __name__ == '__main__':
    app = QApplication([])
    app.setOrganizationName('miga-test')
    app.setApplicationName('wayland')
    with TemporaryDirectory() as tmp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
        check_clock()
        check_capabilities()
        check_layouts()
    print('PASS: general idle thresholds, wake without invented input, fallback, layouts and preferences.')
