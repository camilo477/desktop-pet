"""Keycap legends indexed by physical position (letters use their US position names)."""

DISTRIBUTIONS = {
    'us': 'Inglés (EE. UU.)', 'gb': 'Inglés (Reino Unido)',
    'latam': 'Español (Latinoamérica)', 'es': 'Español (España)',
    'de': 'Alemán (QWERTZ)', 'fr': 'Francés (AZERTY)',
    'dvorak': 'Dvorak', 'colemak': 'Colemak',
}

NUMBER_ROW = ('Backquote', *(f'Digit{n}' for n in '1234567890'), 'Minus', 'Equal')
TOP_ROW = (*'QWERTYUIOP', 'BracketLeft', 'BracketRight')
HOME_ROW = (*'ASDFGHJKL', 'Semicolon', 'Quote')
BOTTOM_ROW = (*'ZXCVBNM', 'Comma', 'Period', 'Slash')


def row(positions, legends):
    return dict(zip(positions, legends, strict=True))


LEGENDS = {
    'us': {'AltRight': 'alt'},
    'gb': {'Backslash': '#', 'IntlBackslash': '\\'},
    'es': {'Backquote': 'º', 'Minus': "'", 'Equal': '¡', 'BracketLeft': '`', 'BracketRight': '+',
           'Backslash': 'Ç', 'Semicolon': 'Ñ', 'Quote': '´', 'Slash': '-'},
    'latam': {'Backquote': '|', 'Minus': "'", 'Equal': '¿', 'BracketLeft': '´', 'BracketRight': '+',
              'Backslash': '}', 'Semicolon': 'Ñ', 'Quote': '{', 'Slash': '-'},
    'de': {'Backquote': '^', 'Minus': 'ß', 'Equal': '´', 'Y': 'Z', 'Z': 'Y',
           'BracketLeft': 'Ü', 'BracketRight': '+', 'Semicolon': 'Ö', 'Quote': 'Ä',
           'Backslash': '#', 'Slash': '-', 'NumpadDecimal': ','},
    'fr': {**row(NUMBER_ROW, """²&é"'(-è_çà)="""), **row(TOP_ROW, 'AZERTYUIOP^$'),
           **row(HOME_ROW, 'QSDFGHJKLMù'), **row(BOTTOM_ROW, 'WXCVBN,;:!'), 'Backslash': '*'},
    'dvorak': {**row(TOP_ROW, "',.PYFGCRL/="), **row(HOME_ROW, 'AOEUIDHTNS-'),
               **row(BOTTOM_ROW, ';QJKXBMWVZ'), 'Minus': '[', 'Equal': ']', 'AltRight': 'alt'},
    'colemak': {**row(TOP_ROW, 'QWFPGJLUY;[]'), **row(HOME_ROW, "ARSTDHNEIO'"),
                **row(BOTTOM_ROW, 'ZXCVBKM,./'), 'CapsLock': 'bk', 'IntlBackslash': '-'},
}


def detected_layout(layout, variant):
    if (layout, variant) in (('us', 'dvorak'), ('us', 'colemak')):
        return variant
    if layout in ('us', 'gb', 'es', 'latam', 'de', 'fr') and variant in ('', 'basic'):
        return layout
    return None
