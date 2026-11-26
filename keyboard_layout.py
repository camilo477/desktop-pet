"""Physical key positions and their common projection onto the cat's floor plane."""

from dataclasses import dataclass
from keyboard_distributions import LEGENDS, TOP_ROW, HOME_ROW, BOTTOM_ROW, NUMBER_ROW

FORMATS = {'60': '60 %', '65': '65 %', '75': '75 %', 'tkl': 'TKL', '100': '100 %'}
STANDARDS = ('ANSI', 'ISO')
KEYBOARD_SCALE = .82
KEY_TRAVEL = .35 * KEYBOARD_SCALE
MOUSE_ANCHOR = (36.5, 153.5)  # Palm end of the original SVG mouse.
REST = ((91., 157.), (115., 157.))

BASE_LABELS = {
    **dict(zip(NUMBER_ROW, '`1234567890-=', strict=True)),
    'Backspace': 'bk', 'Enter': 'ret', 'Tab': 'tab', 'CapsLock': 'cap', 'Space': '',
    'ShiftLeft': 'sh', 'ShiftRight': 'sh', 'CtrlLeft': 'ctrl', 'CtrlRight': 'ctrl',
    'AltLeft': 'alt', 'AltRight': 'AltGr', 'MetaLeft': 'sys', 'MetaRight': 'sys',
    'Menu': 'menu', 'Escape': 'esc',
    'BracketLeft': '[', 'BracketRight': ']', 'Backslash': '\\', 'Semicolon': ';',
    'IntlBackslash': '<', 'Quote': "'", 'Comma': ',', 'Period': '.', 'Slash': '/',
    'PrintScreen': 'prt', 'ScrollLock': 'scr', 'Pause': 'brk', 'Insert': 'ins', 'Home': 'hm',
    'PageUp': 'pu', 'Delete': 'del', 'End': 'end', 'PageDown': 'pd', 'ArrowUp': '^',
    'ArrowLeft': '<', 'ArrowDown': 'v', 'ArrowRight': '>', 'NumLock': 'num',
    'NumpadDivide': '/', 'NumpadMultiply': '*', 'NumpadSubtract': '-', 'NumpadAdd': '+',
    'NumpadEnter': 'ret', 'NumpadDecimal': '.', **{f'Numpad{n}': str(n) for n in range(10)},
}


def placements(form, standard):
    compact = form in ('65', '75')
    function_row = form not in ('60', '65')
    keys = []

    def add(identifier, column, line, width=1., height=1.):
        keys.append((identifier, column, line, width, height))

    def row(line, entries):
        column = 0.
        for entry in entries:
            identifier, width = (entry, 1.) if isinstance(entry, str) else entry
            add(identifier, column, line, width)
            column += width

    row(0, [NUMBER_ROW[0] if function_row else 'Escape', *NUMBER_ROW[1:], ('Backspace', 2)])
    row(1, [('Tab', 1.5), *TOP_ROW])
    row(2, [('CapsLock', 1.75), *HOME_ROW])
    if standard == 'ISO':
        add('Backslash', 12.75, 2)
        add('Enter', 13.5, 1, 1.5, 2)
        left_shift = [('ShiftLeft', 1.25), 'IntlBackslash']
    else:
        add('Backslash', 13.5, 1, 1.5)
        add('Enter', 12.75, 2, 2.25)
        left_shift = [('ShiftLeft', 2.25)]
    row(3, [*left_shift, *BOTTOM_ROW, ('ShiftRight', 1.75 if compact else 2.75)])
    bottom = [('CtrlLeft', 1.25), ('MetaLeft', 1.25), ('AltLeft', 1.25), ('Space', 6.25)]
    if compact:
        row(4, [*bottom, 'AltRight', 'Fn', 'CtrlRight', 'ArrowLeft', 'ArrowDown', 'ArrowRight'])
        add('ArrowUp', 14, 3)
        navigation = ('Delete', 'Home', 'PageUp', 'PageDown') if form == '65' else ('Home', 'End', 'PageUp', 'PageDown')
        for line, identifier in enumerate(navigation):
            add(identifier, 15, line)
    else:
        right = ('AltRight', 'Fn' if form == '60' else 'MetaRight', 'Menu', 'CtrlRight')
        row(4, [*bottom, *((identifier, 1.25) for identifier in right)])

    if function_row:
        line = -1.1 if compact else -1.4
        add('Escape', 0, line)
        for i in range(12):
            add(f'F{i+1}', 1.5 + i if compact else 2 + i + (i // 4) * .5, line)
        if compact:
            add('PrintScreen', 14, line)
            add('Delete', 15, line)
        else:
            for line, ids in ((-1.4, ('PrintScreen', 'ScrollLock', 'Pause')),
                              (0, ('Insert', 'Home', 'PageUp')), (1, ('Delete', 'End', 'PageDown')),
                              (4, ('ArrowLeft', 'ArrowDown', 'ArrowRight'))):
                for i, identifier in enumerate(ids):
                    add(identifier, 15.5 + i, line)
            add('ArrowUp', 16.5, 3)
    if form == '100':
        for i, identifier in enumerate(('NumLock', 'NumpadDivide', 'NumpadMultiply', 'NumpadSubtract')):
            add(identifier, 19 + i, 0)
        for line, digits in enumerate(('789', '456', '123'), 1):
            for i, digit in enumerate(digits):
                add('Numpad' + digit, 19 + i, line)
        add('NumpadAdd', 22, 1, 1, 2)
        add('NumpadEnter', 22, 3, 1, 2)
        add('Numpad0', 19, 4, 2)
        add('NumpadDecimal', 21, 4)
    return keys


@dataclass(frozen=True, slots=True)
class Key:
    identifier: str
    width: float
    polygon: tuple
    contact: tuple
    label_basis: tuple
    preferred_paw: int

    @property
    def modifier(self):
        return self.identifier.startswith(('Shift', 'Ctrl', 'Alt', 'Meta')) or self.identifier in ('CapsLock', 'Menu')


class Keyboard:
    def __init__(self, form='100', standard='ISO', layout='us'):
        if form not in FORMATS or standard not in STANDARDS or layout not in LEGENDS:
            raise ValueError('Unsupported keyboard configuration')
        self.form, self.standard, self.layout = form, standard, layout
        positions = placements(form, standard)
        self.columns = max(col + w for _, col, _, w, _ in positions)
        reduction = 23 - self.columns
        self.origin_x = 64 + 1.9 * reduction
        self.mouse_offset = min(3., reduction * .5)
        self.mouse_rest = (MOUSE_ANCHOR[0] + self.mouse_offset, MOUSE_ANCHOR[1])
        self.rest = ((REST[0][0] + .24 * reduction, REST[0][1]),
                     (REST[1][0] - .16 * reduction, REST[1][1]))
        self.center = self.project(self.columns / 2, 2.5)
        split = self.project(7.5, 2.5)[0]
        far = min(line for _, _, line, _, _ in positions) - .3
        self.board = tuple(self.project(u, v) for u, v in (
            (-.3, far), (self.columns + .3, far), (self.columns + .3, 5.25), (-.3, 5.25)))
        self.by_id = {}
        for identifier, col, line, w, h in positions:
            l, r, t, b = col + .075, col + w - .075, line + .075, line + h - .075
            outline = ((l, t), (r, t), (r, b), (l, b))
            u, v = col + w / 2, line + h / 2
            if identifier == 'Enter' and standard == 'ISO':
                step = line + 1 - .075
                outline = ((l, t), (r, t), (r, b), (l + .25, b), (l + .25, step), (l, step))
                u += .125
            x, y = self.project(u, v)
            ux, uy = self.project(u + 1, v)
            vx, vy = self.project(u, v + 1)
            basis = (x, y, (ux-x)/5.7, (uy-y)/5.7, (vx-x)/4.6, (vy-y)/4.6)
            self.by_id[identifier] = Key(identifier, w, tuple(self.project(*pt) for pt in outline),
                                         (x, y), basis, int(x >= split))

        self.ids = frozenset(self.by_id)

    def project(self, u, v):
        # Half-turn about the floor plane: the number pad is on the viewer's left.
        u, v = self.columns - u, 5 - v
        return (self.origin_x + KEYBOARD_SCALE * (u * (5.7 + v * .06) - v * .50),
                160 + KEYBOARD_SCALE * (v * 4.6 + u * .025))

    def label(self, identifier):
        return LEGENDS[self.layout].get(identifier, BASE_LABELS.get(identifier, identifier))
