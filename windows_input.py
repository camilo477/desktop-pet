"""Passive Windows Raw Input on the Qt GUI thread. No text translation or hooks."""

import ctypes as C
from ctypes import wintypes as W
import winreg

from PySide6.QtGui import QCursor, QGuiApplication

from windows_keyboard import LAYOUT_IDS, SIDED_VK, foreign_layout, physical_key


class Device(C.Structure):
    _fields_ = [('page', W.USHORT), ('usage', W.USHORT), ('flags', W.DWORD), ('target', W.HWND)]


class Header(C.Structure):
    _fields_ = [('kind', W.DWORD), ('size', W.DWORD), ('device', W.HANDLE), ('param', W.WPARAM)]


class Key(C.Structure):
    _fields_ = [('scan', W.USHORT), ('flags', W.USHORT), ('reserved', W.USHORT),
                ('vk', W.USHORT), ('message', W.UINT), ('extra', W.ULONG)]


class Mouse(C.Structure):
    _fields_ = [('flags', W.USHORT), ('padding', W.USHORT), ('buttons', W.USHORT),
                ('wheel', C.c_short), ('raw_buttons', W.ULONG), ('x', W.LONG),
                ('y', W.LONG), ('extra', W.ULONG)]


class Data(C.Union):
    _fields_ = [('key', Key), ('mouse', Mouse)]


class Packet(C.Structure):
    _fields_ = [('header', Header), ('data', Data)]


def function(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args
    return fn


user = C.WinDLL('user32', use_last_error=True)
register = function(user, 'RegisterRawInputDevices', W.BOOL, C.POINTER(Device), W.UINT, W.UINT)
read_packet = function(user, 'GetRawInputData', W.UINT, W.HANDLE, W.UINT, C.c_void_p, C.POINTER(W.UINT), W.UINT)
async_state = function(user, 'GetAsyncKeyState', C.c_short, C.c_int)
foreground = function(user, 'GetForegroundWindow', W.HWND)
window_thread = function(user, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
keyboard_layout = function(user, 'GetKeyboardLayout', W.HANDLE, W.DWORD)
layout_name = function(user, 'GetKeyboardLayoutNameW', W.BOOL, W.LPWSTR)
wts = C.WinDLL('wtsapi32')
session_on = function(wts, 'WTSRegisterSessionNotification', W.BOOL, W.HWND, W.DWORD)
session_off = function(wts, 'WTSUnRegisterSessionNotification', W.BOOL, W.HWND)


def special_layouts():
    # Variant HKLs carry a device-specific number assigned at installation.
    # Accept only the known Windows drivers, never a custom layout's language.
    result = {}
    for klid, layout in LAYOUT_IDS.items():
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SYSTEM\CurrentControlSet\Control\Keyboard Layouts' + '\\' + klid) as key:
                number = int(winreg.QueryValueEx(key, 'Layout Id')[0], 16)
        except (OSError, ValueError):
            continue
        result[number] = layout
    return result


class WindowsInput:
    def __init__(self, monitor):
        self.monitor = monitor
        self.hwnd = None
        self.active = False
        self.locked = self.suspended = False
        self.held = {}
        self.screen = None
        self.layout_ids = special_layouts()
        self.next_register = self.next_layout = self.next_reconcile = 0.0
        self.packet = Packet()

    def configure(self, hwnd):
        if hwnd == self.hwnd:
            return
        if self.hwnd:
            if self.active:
                devices = (Device * 2)(Device(1, 2, 1, None), Device(1, 6, 1, None))
                register(devices, 2, C.sizeof(Device))
            session_off(self.hwnd)
        self.hwnd = hwnd
        self.active = self.monitor.native_pointer = False
        self.reset()
        if hwnd:
            session_on(hwnd, 0)
            self.register_input()

    def register_input(self):
        # INPUTSINK + DEVNOTIFY. Keep normal keyboard and mouse delivery intact.
        devices = (Device * 2)(Device(1, 2, 0x2100, self.hwnd), Device(1, 6, 0x2100, self.hwnd))
        self.active = self.monitor.native_pointer = bool(register(devices, 2, C.sizeof(Device)))
        if self.active:
            self.sync_cursor()

    def reset(self):
        self.held.clear()
        self.screen = None
        self.next_register = self.next_layout = self.next_reconcile = 0.0
        self.monitor.clear_input()

    def sync_cursor(self):
        point = QCursor.pos()
        self.screen = QGuiApplication.screenAt(point)
        self.monitor.reset_pointer_origin()
        self.monitor.pointer_moved(point.x(), point.y())

    def poll(self, now):
        if not self.hwnd or self.locked or self.suspended:
            return
        if not self.active and now >= self.next_register:
            self.next_register = now + 5
            self.register_input()
        if self.held and now >= self.next_reconcile:
            self.next_reconcile = now + .4
            for code, vk in tuple(self.held.items()):
                if not async_state(vk) & 0x8000:
                    self.release(code)
        if now >= self.next_layout:
            self.next_layout = now + 1.0
            window = foreground()
            thread = window_thread(window, None) if window else 0
            handle = keyboard_layout(thread) if thread else None
            layout = None
            if handle:
                if handle == keyboard_layout(0):
                    name = C.create_unicode_buffer(9)
                    if layout_name(name):
                        layout = LAYOUT_IDS.get(name.value.lower())
                else:
                    layout = foreign_layout(handle, self.layout_ids)
            self.monitor.set_layout(layout)

    def release(self, code):
        self.held.pop(code, None)
        self.monitor.key_up(code, immediate=True)

    def keyboard(self, device, key):
        name = physical_key(key.scan, key.flags, key.vk)
        if name is None:
            return
        code = (device, name)
        if key.flags & 1:
            self.release(code)
        else:
            self.held[code] = SIDED_VK.get(name, key.vk)
            self.monitor.key_down(name, code)
            if name == 'Pause':  # Some keyboards never send a break for Pause.
                self.release(code)

    def mouse(self, mouse):
        if mouse.x or mouse.y or mouse.flags & 1:
            # Desktop cursor movement includes Windows acceleration. Qt supplies
            # logical coordinates, including on absolute pointing devices.
            point = QCursor.pos()
            screen = QGuiApplication.screenAt(point)
            if screen != self.screen:
                self.monitor.reset_pointer_origin()
                self.screen = screen
            self.monitor.pointer_moved(point.x(), point.y())
        if mouse.buttons & 0x155:  # Left/right/middle/X1/X2 down edges.
            self.monitor.pointer_click(context=bool(mouse.buttons & 4))
        delta = mouse.wheel / 120
        if mouse.buttons & 0x400:
            self.monitor.pointer_scrolled(0, delta)
        if mouse.buttons & 0x800:
            self.monitor.pointer_scrolled(delta, 0)

    def message(self, message):
        msg = W.MSG.from_address(int(message))
        if msg.message == 0x21:  # WM_MOUSEACTIVATE: deliver click without activation.
            return True, 3
        if not self.hwnd or msg.hWnd != self.hwnd:
            return False, 0
        if msg.message == 0x02b1:  # WM_WTSSESSION_CHANGE
            if msg.wParam in (1, 2, 3, 4, 5, 6, 7, 8):
                self.locked = msg.wParam in (2, 4, 6, 7)
                self.reset()
        elif msg.message == 0x218 and msg.wParam in (4, 7, 18):  # WM_POWERBROADCAST
            self.suspended = msg.wParam == 4
            self.reset()
        elif msg.message == 0xfe and msg.wParam == 2:  # Device removal
            self.reset()
        elif msg.message == 0xff and self.active and not self.locked and not self.suspended:
            size = W.UINT(C.sizeof(Packet))
            count = read_packet(msg.lParam, 0x10000003, C.byref(self.packet),
                                C.byref(size), C.sizeof(Header))
            if count != 0xffffffff and count >= C.sizeof(Header):
                packet = self.packet
                if packet.header.kind == 1 and count >= C.sizeof(Header) + C.sizeof(Key):
                    self.keyboard(packet.header.device, packet.data.key)
                elif packet.header.kind == 0 and count >= C.sizeof(Header) + C.sizeof(Mouse):
                    self.mouse(packet.data.mouse)
        # Qt and DefWindowProc must still receive WM_INPUT.
        return False, 0
