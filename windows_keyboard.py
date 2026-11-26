"""Windows set-1 make codes mapped to Miga's layout-independent physical positions."""

def sequence(start, names):
    return dict(enumerate(names.split(), start))


BASE = {
    0x01: 'Escape', **{i: f'Digit{n}' for i, n in enumerate('1234567890', 2)},
    **sequence(0x0c, 'Minus Equal Backspace Tab'),
    **dict(enumerate('QWERTYUIOP', 0x10)),
    **sequence(0x1a, 'BracketLeft BracketRight Enter CtrlLeft'),
    **dict(enumerate('ASDFGHJKL', 0x1e)),
    **sequence(0x27, 'Semicolon Quote Backquote ShiftLeft Backslash'),
    **dict(enumerate('ZXCVBNM', 0x2c)),
    **sequence(0x33, 'Comma Period Slash ShiftRight NumpadMultiply AltLeft Space CapsLock'),
    **{0x3a + n: f'F{n}' for n in range(1, 11)},
    **sequence(0x45, 'NumLock ScrollLock Numpad7 Numpad8 Numpad9 NumpadSubtract '
                     'Numpad4 Numpad5 Numpad6 NumpadAdd Numpad1 Numpad2 Numpad3 Numpad0 NumpadDecimal'),
    0x56: 'IntlBackslash', 0x57: 'F11', 0x58: 'F12',
}
EXTENDED = {
    0x1c: 'NumpadEnter', 0x1d: 'CtrlRight', 0x35: 'NumpadDivide',
    0x37: 'PrintScreen', 0x38: 'AltRight', 0x47: 'Home', 0x48: 'ArrowUp',
    0x49: 'PageUp', 0x4b: 'ArrowLeft', 0x4d: 'ArrowRight', 0x4f: 'End',
    0x50: 'ArrowDown', 0x51: 'PageDown', 0x52: 'Insert', 0x53: 'Delete',
    **sequence(0x5b, 'MetaLeft MetaRight Menu'),
}
SIDED_VK = {'ShiftLeft': 0xa0, 'ShiftRight': 0xa1, 'CtrlLeft': 0xa2,
            'CtrlRight': 0xa3, 'AltLeft': 0xa4, 'AltRight': 0xa5}
# Published Windows keyboard identifiers (KLIDs), including the built-in Colemak.
LAYOUT_IDS = {'00000409': 'us', '00000809': 'gb', '0000080a': 'latam',
              '0000040a': 'es', '00000407': 'de', '0000040c': 'fr',
              '00010409': 'dvorak', '00060409': 'colemak'}


def physical_key(scan, flags, vk):
    if not 0 < scan < 0x80 or vk in (0, 0xff):
        return None
    if vk == 0x13 and scan in (0x1d, 0x45):
        return 'Pause'
    if flags & 4:  # Other E1 sequence components do not describe a key.
        return None
    if vk == 0x03 and flags & 2 and scan == 0x46:  # Ctrl+Break
        return 'Pause'
    if vk == 0x2c and scan == 0x54:  # Alt+Print Screen
        return 'PrintScreen'
    if vk == 0x90 and scan == 0x45:
        return 'NumLock'
    return (EXTENDED if flags & 2 else BASE).get(scan)


def foreign_layout(hkl, special_ids):
    # The low word is the language. The device in the high word can differ.
    device = (hkl >> 16) & 0xffff
    if device & 0xf000 == 0xf000:
        return special_ids.get(device & 0xfff)
    return LAYOUT_IDS.get(f'{device:08x}')
