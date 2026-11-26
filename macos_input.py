"""Passive Quartz session input on Qt's main CFRunLoop."""

import ctypes as C
import time

import AppKit
import CoreFoundation as CF
from Foundation import NSOperationQueue
from Quartz import CoreGraphics as CG

from macos_keyboard import MODIFIERS, modifier_down, physical_key, source_layout, wheel_units


# HIToolbox is re-exported by Carbon. These C APIs are not part of PyObjC's
# Cocoa/Quartz wrappers. Copy returns an owned TIS object, Get a borrowed ID.
carbon = C.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
core = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')


def bind(lib, name, result, *arguments):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, arguments
    return fn


copy_source = bind(carbon, 'TISCopyCurrentKeyboardInputSource', C.c_void_p)
source_property = bind(carbon, 'TISGetInputSourceProperty', C.c_void_p, C.c_void_p, C.c_void_p)
source_id = C.c_void_p.in_dll(carbon, 'kTISPropertyInputSourceID')
get_string = bind(core, 'CFStringGetCString', C.c_bool, C.c_void_p, C.c_void_p, C.c_long, C.c_uint32)
release = bind(core, 'CFRelease', None, C.c_void_p)
secure_input = bind(carbon, 'IsSecureEventInputEnabled', C.c_bool)
hardware_layout = bind(carbon, 'KBGetLayoutType', C.c_uint32, C.c_int16)


def current_layout():
    source = copy_source()
    if not source:
        return None
    try:
        identifier = source_property(source, source_id)
        data = C.create_string_buffer(512)
        if identifier and get_string(identifier, data, len(data), 0x08000100):  # UTF-8
            return source_layout(data.value.decode('utf-8'))
        return None
    finally:
        release(source)


MOVES = (CG.kCGEventMouseMoved, CG.kCGEventLeftMouseDragged,
         CG.kCGEventRightMouseDragged, CG.kCGEventOtherMouseDragged)
CLICKS = (CG.kCGEventLeftMouseDown, CG.kCGEventRightMouseDown, CG.kCGEventOtherMouseDown)
KEY_EVENTS = (CG.kCGEventKeyDown, CG.kCGEventKeyUp, CG.kCGEventFlagsChanged)
MASK = sum(1 << kind for kind in (*MOVES, *CLICKS, *KEY_EVENTS, CG.kCGEventScrollWheel))
FIELD = CG.CGEventGetIntegerValueField


class MacInput:
    def __init__(self, monitor, status_changed):
        self.monitor = monitor
        self.status_changed = status_changed
        self.status = 'off'
        self.enabled = False
        self.held = set()
        self.tap = self.source = None
        self.next_check = self.next_reconcile = 0.
        self.inactive = set()
        self.observers = []
        self.center = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
        for name, reason, inactive in (
            (AppKit.NSWorkspaceWillSleepNotification, 'sleep', True),
            (AppKit.NSWorkspaceDidWakeNotification, 'sleep', False),
            (AppKit.NSWorkspaceSessionDidResignActiveNotification, 'session', True),
            (AppKit.NSWorkspaceSessionDidBecomeActiveNotification, 'session', False),
            (AppKit.NSWorkspaceScreensDidSleepNotification, 'screen', True),
            (AppKit.NSWorkspaceScreensDidWakeNotification, 'screen', False),
        ):
            def change(note, why=reason, block=inactive):
                if block:
                    self.inactive.add(why)
                    self.disconnect()
                else:
                    self.inactive.discard(why)
                self.next_check = 0
            token = self.center.addObserverForName_object_queue_usingBlock_(
                name, None, NSOperationQueue.mainQueue(), change)
            self.observers.append(token)

    def set_status(self, status):
        if self.status != status:
            self.status = status
            self.status_changed(status)

    def configure(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.disconnect()
            self.set_status('off')
        else:
            self.next_check = 0
            self.poll(time.monotonic())

    def disconnect(self):
        self.monitor.native_pointer = False
        if self.tap is not None:
            CG.CGEventTapEnable(self.tap, False)
            CF.CFRunLoopRemoveSource(CF.CFRunLoopGetMain(), self.source, CF.kCFRunLoopCommonModes)
            CF.CFMachPortInvalidate(self.tap)
        self.source = self.tap = None
        self.held.clear()
        self.monitor.clear_input()

    def connect(self):
        tap = CG.CGEventTapCreate(CG.kCGSessionEventTap, CG.kCGTailAppendEventTap,
                                  CG.kCGEventTapOptionListenOnly, MASK, self.event, None)
        if tap is None:
            return False
        source = CF.CFMachPortCreateRunLoopSource(None, tap, 0)
        if source is None:
            CF.CFMachPortInvalidate(tap)
            return False
        self.tap, self.source = tap, source
        CF.CFRunLoopAddSource(CF.CFRunLoopGetMain(), source, CF.kCFRunLoopCommonModes)
        CG.CGEventTapEnable(tap, True)
        self.monitor.native_pointer = True
        return True

    @staticmethod
    def key_state(code):
        return CG.CGEventSourceKeyState(CG.kCGEventSourceStateCombinedSessionState, code)

    def poll(self, now):
        if not self.enabled:
            return
        if now >= self.next_check:
            self.next_check = now + 2
            permitted = CG.CGPreflightListenEventAccess()
            if not permitted or self.inactive or secure_input():
                if self.tap is not None:
                    self.disconnect()
                self.set_status('denied' if not permitted else 'restricted')
            else:
                if self.tap is not None and (not self.monitor.native_pointer or not CG.CGEventTapIsEnabled(self.tap)):
                    self.disconnect()
                self.set_status('active' if self.tap is not None or self.connect() else 'unavailable')
            self.monitor.set_layout(current_layout())
        if self.tap is not None and self.held and now >= self.next_reconcile:
            self.next_reconcile = now + .4
            if secure_input():
                self.disconnect()
                self.set_status('restricted')
            else:
                for code in tuple(self.held):
                    if not self.key_state(code):
                        self.up(code)

    def up(self, code):
        self.held.discard(code)
        self.monitor.key_up((code,), immediate=True)

    def event(self, proxy, kind, event, context):
        if kind in (CG.kCGEventTapDisabledByTimeout, CG.kCGEventTapDisabledByUserInput):
            self.held.clear()
            self.monitor.clear_input()
            self.monitor.native_pointer = False
            self.next_check = 0
            return event
        if (not self.monitor.native_pointer or self.inactive or
                time.monotonic_ns() - CG.CGEventGetTimestamp(event) > 250_000_000):
            return event
        if kind in KEY_EVENTS:
            if secure_input():
                self.held.clear()
                self.monitor.clear_input()
                self.monitor.native_pointer = False
                self.next_check = 0
                return event
            code = FIELD(event, CG.kCGKeyboardEventKeycode)
            if kind == CG.kCGEventFlagsChanged:
                if code == 57:  # Caps Lock is latched; never leave a paw held.
                    self.monitor.key_down('CapsLock', (code,))
                    self.up(code)
                    return event
                if code not in MODIFIERS and code != 63:
                    return event
                down = modifier_down(code, CG.CGEventGetFlags(event), self.key_state)
            else:
                down = kind == CG.kCGEventKeyDown
            if down:
                iso = (code in (10, 50) and hardware_layout(FIELD(event, CG.kCGKeyboardEventKeyboardType))
                       == int.from_bytes(b'ISO ', 'big'))
                repeat = kind == CG.kCGEventKeyDown and FIELD(event, CG.kCGKeyboardEventAutorepeat)
                self.held.add(code)
                self.monitor.key_down(physical_key(code, iso), (code,), initial=bool(repeat))
            else:
                self.up(code)
        elif kind in MOVES:
            point = CG.CGEventGetLocation(event)  # Global display points, y grows down.
            self.monitor.pointer_moved(point.x, point.y)
        elif kind in CLICKS:
            self.monitor.pointer_click(context=kind == CG.kCGEventRightMouseDown)
        elif kind == CG.kCGEventScrollWheel:
            continuous = FIELD(event, CG.kCGScrollWheelEventIsContinuous)
            x, y = ((CG.kCGScrollWheelEventPointDeltaAxis2, CG.kCGScrollWheelEventPointDeltaAxis1)
                    if continuous else (CG.kCGScrollWheelEventDeltaAxis2, CG.kCGScrollWheelEventDeltaAxis1))
            self.monitor.pointer_scrolled(*wheel_units(FIELD(event, x), FIELD(event, y), continuous))
        return event

    def request_access(self):
        CG.CGRequestListenEventAccess()
        self.next_check = 0

    def close(self):
        self.configure(False)
        for token in self.observers:
            self.center.removeObserver_(token)
        self.observers.clear()
