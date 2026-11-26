"""Apple virtual key positions, independent of the active input source."""

KEYS = {
    **dict(enumerate('ASDFHGZXCV')), 10: 'IntlBackslash', 11: 'B',
    **dict(enumerate('QWERYT', 12)),
    **{i: 'Digit' + n for i, n in zip((18,19,20,21,22,23,25,26,28,29), '1234659780')},
    24: 'Equal', 27: 'Minus', 30: 'BracketRight', 31: 'O', 32: 'U',
    33: 'BracketLeft', 34: 'I', 35: 'P', 36: 'Enter', 37: 'L', 38: 'J',
    39: 'Quote', 40: 'K', 41: 'Semicolon', 42: 'Backslash', 43: 'Comma',
    44: 'Slash', 45: 'N', 46: 'M', 47: 'Period', 48: 'Tab', 49: 'Space',
    50: 'Backquote', 51: 'Backspace', 53: 'Escape', 54: 'MetaRight',
    55: 'MetaLeft', 56: 'ShiftLeft', 57: 'CapsLock', 58: 'AltLeft',
    59: 'CtrlLeft', 60: 'ShiftRight', 61: 'AltRight', 62: 'CtrlRight', 63: 'Fn',
    65: 'NumpadDecimal', 67: 'NumpadMultiply', 69: 'NumpadAdd',
    75: 'NumpadDivide', 76: 'NumpadEnter', 78: 'NumpadSubtract',
    **{i: 'Numpad' + str(n) for n, i in enumerate((82,83,84,85,86,87,88,89,91,92))},
    **{i: 'F' + str(n) for n, i in enumerate((122,120,99,118,96,97,98,100,101,109,103,111), 1)},
    114: 'Insert', 115: 'Home', 116: 'PageUp', 117: 'Delete', 119: 'End',
    121: 'PageDown', 123: 'ArrowLeft', 124: 'ArrowRight', 125: 'ArrowDown', 126: 'ArrowUp',
}

# Device-dependent side bits from Apple's IOLLEvent.h, plus the aggregate
# family bit for keyboards that supply only device-independent flags.
MODIFIERS = {
    56: (0x0002, 0x0004, 1 << 17), 60: (0x0004, 0x0002, 1 << 17),
    59: (0x0001, 0x2000, 1 << 18), 62: (0x2000, 0x0001, 1 << 18),
    58: (0x0020, 0x0040, 1 << 19), 61: (0x0040, 0x0020, 1 << 19),
    55: (0x0008, 0x0010, 1 << 20), 54: (0x0010, 0x0008, 1 << 20),
}

SOURCE_IDS = {
    'US': 'us', 'ABC': 'us', 'British': 'gb', 'British-PC': 'gb',
    'LatinAmerican': 'latam', 'Spanish-ISO': 'es', 'Spanish': 'es',
    'German': 'de', 'German-DIN-2137': 'de', 'French': 'fr',
    'Dvorak': 'dvorak', 'Colemak': 'colemak',
}


def source_layout(identifier):
    prefix = 'com.apple.keylayout.'
    return SOURCE_IDS.get(identifier[len(prefix):]) if identifier.startswith(prefix) else None


def physical_key(code, iso=False):
    # The ISO hardware type exchanges the two CG virtual positions.
    if iso and code in (10, 50):
        return KEYS[50 if code == 10 else 10]
    return KEYS.get(code)


def modifier_down(code, flags, key_state):
    if code == 63:
        return bool(flags & (1 << 23))
    side, other, family = MODIFIERS[code]
    if flags & (side | other):
        return bool(flags & side)
    return bool(flags & family) and key_state(code)


def wheel_units(horizontal, vertical, continuous):
    divisor = 20.0 if continuous else 1.0
    return tuple(max(-4., min(4., n / divisor)) for n in (horizontal, vertical))
