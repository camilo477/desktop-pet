"""Linux evdev codes mapped to physical keycaps, without decoding text."""

from evdev import ecodes


NAMES = {
    'ESC': 'Escape', 'MINUS': 'Minus', 'EQUAL': 'Equal', 'BACKSPACE': 'Backspace',
    'TAB': 'Tab', 'LEFTBRACE': 'BracketLeft', 'RIGHTBRACE': 'BracketRight',
    'ENTER': 'Enter', 'LEFTCTRL': 'CtrlLeft', 'SEMICOLON': 'Semicolon',
    'APOSTROPHE': 'Quote', 'GRAVE': 'Backquote', 'LEFTSHIFT': 'ShiftLeft',
    'BACKSLASH': 'Backslash', 'COMMA': 'Comma', 'DOT': 'Period', 'SLASH': 'Slash',
    'RIGHTSHIFT': 'ShiftRight', 'LEFTALT': 'AltLeft', 'SPACE': 'Space',
    'CAPSLOCK': 'CapsLock', 'NUMLOCK': 'NumLock', 'SCROLLLOCK': 'ScrollLock',
    '102ND': 'IntlBackslash', 'KPENTER': 'NumpadEnter', 'RIGHTCTRL': 'CtrlRight',
    'KPSLASH': 'NumpadDivide', 'SYSRQ': 'PrintScreen', 'RIGHTALT': 'AltRight',
    'HOME': 'Home', 'UP': 'ArrowUp', 'PAGEUP': 'PageUp', 'LEFT': 'ArrowLeft',
    'RIGHT': 'ArrowRight', 'END': 'End', 'DOWN': 'ArrowDown', 'PAGEDOWN': 'PageDown',
    'INSERT': 'Insert', 'DELETE': 'Delete', 'PAUSE': 'Pause',
    'LEFTMETA': 'MetaLeft', 'RIGHTMETA': 'MetaRight', 'COMPOSE': 'Menu',
    'KPASTERISK': 'NumpadMultiply', 'KPMINUS': 'NumpadSubtract', 'KPPLUS': 'NumpadAdd',
    'KPDOT': 'NumpadDecimal',
    **{letter: letter for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'},
    **{str(n): f'Digit{n}' for n in range(10)},
    **{f'KP{n}': f'Numpad{n}' for n in range(10)},
    **{f'F{n}': f'F{n}' for n in range(1, 13)},
}
POSITIONS = {getattr(ecodes, 'KEY_' + code): name for code, name in NAMES.items()}
