"""Read-only session D-Bus providers for desktop idle and keyboard legends."""

import asyncio
import gettext
import os
import time

from animations import IDLE_ACTION_AFTER
from keyboard_distributions import detected_layout
from wayland_idle import compositor_matches


class Unavailable(Exception):
    pass


# KWin returns the XKB short name, a user-editable label and a translated
# keymap group name. The short name alone cannot distinguish US variants.
_GROUPS = {
    ('us', 'English (US)'): 'us', ('gb', 'English (UK)'): 'gb',
    ('es', 'Spanish'): 'es', ('latam', 'Spanish (Latin American)'): 'latam',
    ('de', 'German'): 'de', ('fr', 'French'): 'fr',
    ('us', 'English (Dvorak)'): 'dvorak', ('us', 'English (Colemak)'): 'colemak',
}


def kde_layout(rows, index):
    if not 0 <= index < len(rows):
        return None
    short, _, long_name = rows[index]
    for (code, group), layout in _GROUPS.items():
        if code == short and long_name in (group, gettext.dgettext('xkeyboard-config', group)):
            return layout
    return None


def configured_layout(value):
    if value.signature != 'a(ss)' or len(value.value) != 1:
        return None
    kind, source = value.value[0]
    layout, _, variant = source.partition('+')
    return detected_layout(layout, variant) if kind == 'xkb' else None


async def service(kind, report):
    from dbus_next import Message, MessageFlag, MessageType
    from dbus_next.errors import AuthError, DBusError
    from dbus_next.aio import MessageBus

    name, path, interface = {
        'mutter': ('org.gnome.Mutter.IdleMonitor', '/org/gnome/Mutter/IdleMonitor/Core', 'org.gnome.Mutter.IdleMonitor'),
        'kde': ('org.kde.keyboard', '/Layouts', 'org.kde.KeyboardLayouts'),
        'gnome': ('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.Settings'),
    }[kind]
    address = os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')
    if not address and os.environ.get('XDG_RUNTIME_DIR'):
        address = 'unix:path=' + os.path.join(os.environ['XDG_RUNTIME_DIR'], 'bus')
    if not address or not all(part.startswith('unix:') for part in address.split(';')):
        raise Unavailable()
    bus = MessageBus(bus_address=address)
    changed = asyncio.Event()
    replaced = False
    active_watch = None

    async def call(destination, obj, iface, method, result, signature='', body=None):
        request = Message(destination=destination, path=obj, interface=iface, member=method,
                          signature=signature, body=body or [], flags=MessageFlag.NO_AUTOSTART)
        reply = await asyncio.wait_for(bus.call(request), 2)
        if reply.message_type != MessageType.METHOD_RETURN or reply.signature != result:
            raise Unavailable()
        return reply.body[0] if result else None

    def daemon(method, result, arg):
        return call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                    method, result, 's', [arg])

    def query(method, result, signature='', body=None):
        return call(owner, path, interface, method, result, signature, body)

    def signal(message):
        nonlocal replaced, active_watch
        if message.message_type != MessageType.SIGNAL:
            return
        if (message.sender == 'org.freedesktop.DBus' and message.interface == 'org.freedesktop.DBus'
                and message.member == 'NameOwnerChanged' and message.body[0] in watched_names):
            replaced = True
        elif message.sender != owner or message.path != path or message.interface != interface:
            return
        elif kind == 'mutter' and message.member == 'WatchFired' and message.signature == 'u':
            if message.body[0] == active_watch:
                active_watch = None  # One-shot watch.
        elif kind == 'kde' and (message.member, message.signature) in (('layoutChanged', 'u'), ('layoutListChanged', '')):
            pass
        elif (kind == 'gnome' and message.member == 'SettingChanged' and message.signature == 'ssv'
              and message.body[:2] == ['org.gnome.desktop.input-sources', 'sources']):
            pass
        else:
            return
        changed.set()

    def disconnected(_task):
        nonlocal replaced
        replaced = True
        changed.set()

    ended = None
    owner = None
    compositor_service = 'org.gnome.Mutter.IdleMonitor' if kind == 'gnome' else name
    watched_names = {name, compositor_service}
    try:
        await asyncio.wait_for(bus.connect(), 2)
        ended = asyncio.create_task(bus.wait_for_disconnect())
        ended.add_done_callback(disconnected)
        bus.add_message_handler(signal)
        for watched in watched_names:
            await daemon('AddMatch', '', f"type='signal',sender='org.freedesktop.DBus',member='NameOwnerChanged',arg0='{watched}'")
        # Nested compositors can share a session bus with the host desktop.
        # Its idle clock and layout would describe the wrong seat.
        compositor = await daemon('GetNameOwner', 's', compositor_service)
        pid = await daemon('GetConnectionUnixProcessID', 'u', compositor)
        if not compositor_matches(pid):
            raise Unavailable()
        owner = compositor if name == compositor_service else await daemon('GetNameOwner', 's', name)
        match = f"type='signal',sender='{owner}',path='{path}',interface='{interface}'"
        if kind == 'gnome':
            match += ",member='SettingChanged',arg0='org.gnome.desktop.input-sources',arg1='sources'"
        await daemon('AddMatch', '', match)
        if kind == 'mutter':
            await query('AddIdleWatch', 'u', 't', [round(1000 * IDLE_ACTION_AFTER)])
        while not replaced:
            changed.clear()
            if kind == 'mutter':
                milliseconds = await query('GetIdletime', 't')
                if milliseconds >= IDLE_ACTION_AFTER * 1000 and active_watch is None:
                    active_watch = await query('AddUserActiveWatch', 'u')
                    # Activity can occur before the watch registration completes.
                    milliseconds = await query('GetIdletime', 't')
                value = (1, time.monotonic() - milliseconds / 1000
                         if milliseconds >= IDLE_ACTION_AFTER * 1000 else None)
            elif kind == 'kde':
                rows = await query('getLayoutsList', 'a(sss)')
                index = await query('getLayout', 'u')
                value = ('KDE', kde_layout(rows, index))
            else:
                args = ['org.gnome.desktop.input-sources', 'sources']
                try:
                    setting = await query('ReadOne', 'v', 'ss', args)
                except Unavailable:
                    setting = await query('Read', 'v', 'ss', args)
                    if setting.signature == 'v':
                        setting = setting.value
                layout = configured_layout(setting)
                value = ('GNOME · única configurada' if layout else 'GNOME · sin fuente inequívoca', layout)
            if not replaced and not changed.is_set():
                report(kind, value)
            try:
                await asyncio.wait_for(changed.wait(), 30)  # Liveness on a quiet bus.
            except asyncio.TimeoutError:
                pass
    except (AuthError, DBusError) as error:
        raise Unavailable() from error
    finally:
        # Mutter removes watches when their private D-Bus owner disconnects.
        bus.disconnect()
        if ended is not None:
            await asyncio.gather(ended, return_exceptions=True)
