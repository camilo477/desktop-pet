"""Seat-wide idle transitions on a separate, input-free Wayland connection."""

import asyncio
import os
import socket
import struct
import time

from animations import IDLE_ACTION_AFTER


def connect_display():
    """Open a private connection to this session, never Qt's inherited fd."""
    if os.environ.get('WAYLAND_SOCKET'):
        raise OSError('A separate named compositor connection is required')
    name = os.environ.get('WAYLAND_DISPLAY') or 'wayland-0'
    if not os.path.isabs(name):
        directory = os.environ.get('XDG_RUNTIME_DIR')
        if not directory:
            raise OSError('No Wayland runtime directory')
        name = os.path.join(directory, name)
    client = socket.socket(socket.AF_UNIX)
    try:
        client.settimeout(1)
        client.connect(name)
        client.setblocking(True)
    except OSError:
        client.close()
        raise
    return client


def compositor_pid():
    with connect_display() as client:
        credentials = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        return struct.unpack('3i', credentials)[0]


async def observe(report):
    from pywayland.client import Display
    from pywayland.protocol.ext_idle_notify_v1 import ExtIdleNotifierV1
    from pywayland.protocol.wayland import WlSeat

    with connect_display() as client:
        display = Display(client.detach())  # libwayland owns this new connection.
        display.connect()
    loop = asyncio.get_running_loop()
    failed = loop.create_future()
    registry = display.get_registry()
    advertised_features = {}
    features = {'wl_compositor', 'xdg_wm_base', 'wp_fractional_scale_manager_v1', 'zwlr_layer_shell_v1'}
    seats = {}
    watches = {}
    idle = {}
    manager = None
    manager_name = None
    version = 0

    def publish():
        # On a multi-seat desktop every seat must be idle. Use the last edge.
        if manager and watches:
            since = max(idle.values()) if len(idle) == len(watches) else None
            report('standard', (version, since))
        else:
            report('standard', None)

    def transition(name, idled):
        if name not in watches:
            return
        if idled:
            idle[name] = time.monotonic() - IDLE_ACTION_AFTER
        else:
            idle.pop(name, None)
        publish()

    def observe_seats():
        if manager:
            create = manager.get_input_idle_notification if version >= 2 else manager.get_idle_notification
            for name, seat in seats.items():
                if name not in watches:
                    watch = create(round(IDLE_ACTION_AFTER * 1000), seat)
                    watches[name] = watch
                    watch.dispatcher['idled'] = lambda _, n=name: transition(n, True)
                    watch.dispatcher['resumed'] = lambda _, n=name: transition(n, False)
        publish()

    def added(registry, name, interface, advertised):
        nonlocal manager, manager_name, version
        if interface in features:
            advertised_features[name] = interface
            report('surface', frozenset(advertised_features.values()))
        if interface == 'ext_idle_notifier_v1' and not manager:
            version = min(2, advertised, ExtIdleNotifierV1.version)
            manager = registry.bind(name, ExtIdleNotifierV1, version)
            manager_name = name
        elif interface == 'wl_seat':
            # Version 1 is enough. Never request a keyboard, pointer or touch device.
            seats[name] = registry.bind(name, WlSeat, 1)
        else:
            return
        observe_seats()

    def removed(_, name):
        nonlocal manager, manager_name
        if advertised_features.pop(name, None):
            report('surface', frozenset(advertised_features.values()))
        if name == manager_name:
            for watch in watches.values():
                watch.destroy()
            watches.clear()
            idle.clear()
            manager.destroy()
            manager = manager_name = None
        elif name in seats:
            if name in watches:
                watches.pop(name).destroy()
            idle.pop(name, None)
            # A v1 seat only needs its client-side proxy destroyed.
            seats.pop(name).destroy()
        publish()

    def ready():
        try:
            display.read()
            display.dispatch()
            display.flush()
        except (RuntimeError, OSError, ValueError) as error:
            loop.remove_reader(fd)
            if not failed.done():
                failed.set_exception(error)

    registry.dispatcher['global'] = added
    registry.dispatcher['global_remove'] = removed
    fd = display.get_fd()
    loop.add_reader(fd, ready)
    try:
        display.flush()
        await failed
    finally:
        loop.remove_reader(fd)
        display.disconnect()
