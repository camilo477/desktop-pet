"""Read XKB physical key names and layout metadata on the existing X11 connection."""

from Xlib.protocol import rq

from keyboard_distributions import detected_layout, TOP_ROW, HOME_ROW, BOTTOM_ROW, NUMBER_ROW

# Python-Xlib exposes the core protocol and RECORD, but not these three XKB requests.
# X Keyboard Extension 1.0, UseExtension / GetState / GetNames (key names only).
CORE_KEYBOARD = 0x100
KEY_NAMES = 1 << 9


class UseExtension(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8('opcode'), rq.Opcode(0), rq.RequestLength(),
                         rq.Card16('major'), rq.Card16('minor'))
    _reply = rq.Struct(rq.Pad(1), rq.Card8('supported'), rq.Card16('sequence_number'), rq.Pad(28))


class GetState(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8('opcode'), rq.Opcode(4), rq.RequestLength(),
                         rq.Card16('device'), rq.Pad(2))
    _reply = rq.Struct(rq.Pad(2), rq.Card16('sequence_number'), rq.Pad(8),
                       rq.Card8('group'), rq.Pad(19))


class GetNames(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8('opcode'), rq.Opcode(17), rq.RequestLength(),
                         rq.Card16('device'), rq.Pad(2), rq.Card32('which'))
    _reply = rq.Struct(rq.Pad(2), rq.Card16('sequence_number'), rq.Pad(4), rq.Card32('which'),
                       rq.Pad(6), rq.Card8('first'), rq.Card8('count'), rq.Pad(12), rq.Binary('names'))


POSITIONS = {
    'TLDE': 'Backquote', 'BKSP': 'Backspace', 'TAB': 'Tab', 'RTRN': 'Enter', 'CAPS': 'CapsLock',
    'BKSL': 'Backslash', 'LSGT': 'IntlBackslash', 'LFSH': 'ShiftLeft', 'RTSH': 'ShiftRight',
    'LCTL': 'CtrlLeft', 'RCTL': 'CtrlRight', 'LALT': 'AltLeft', 'RALT': 'AltRight',
    'LWIN': 'MetaLeft', 'RWIN': 'MetaRight', 'COMP': 'Menu', 'MENU': 'Menu', 'SPCE': 'Space',
    'ESC': 'Escape', 'PRSC': 'PrintScreen', 'SCLK': 'ScrollLock', 'PAUS': 'Pause',
    'INS': 'Insert', 'HOME': 'Home', 'PGUP': 'PageUp', 'DELE': 'Delete', 'END': 'End',
    'PGDN': 'PageDown', 'UP': 'ArrowUp', 'DOWN': 'ArrowDown', 'LEFT': 'ArrowLeft',
    'RGHT': 'ArrowRight', 'NMLK': 'NumLock', 'KPDV': 'NumpadDivide', 'KPMU': 'NumpadMultiply',
    'KPSU': 'NumpadSubtract', 'KPAD': 'NumpadAdd', 'KPEN': 'NumpadEnter', 'KPDL': 'NumpadDecimal',
    **{f'KP{i}': f'Numpad{i}' for i in range(10)},
    **{f'FK{i:02}': f'F{i}' for i in range(1, 13)},
}
for prefix, row in (('AE', NUMBER_ROW[1:]), ('AD', TOP_ROW), ('AC', HOME_ROW), ('AB', BOTTOM_ROW)):
    POSITIONS.update({f'{prefix}{i:02}': identifier for i, identifier in enumerate(row, 1)})


class XkbKeyboard:
    def __init__(self, display):
        self.display = display
        extension = display.query_extension('XKEYBOARD')
        if not extension or not extension.present:
            raise ValueError('XKB unavailable')
        self.opcode = extension.major_opcode
        if not UseExtension(display=display.display, opcode=self.opcode, major=1, minor=0).supported:
            raise ValueError('XKB version unavailable')
        self.rules_atom = display.intern_atom('_XKB_RULES_NAMES')
        self.groups = ()
        self.positions = {}
        self._rules = None

    def read_positions(self):
        names = GetNames(display=self.display.display, opcode=self.opcode, device=CORE_KEYBOARD, which=KEY_NAMES)
        positions = {}
        if names.which == KEY_NAMES:
            for i in range(names.count):
                name = names.names[i*4:i*4+4].rstrip(b'\0').decode('ascii', 'replace')
                if name in POSITIONS:
                    positions[names.first + i] = POSITIONS[name]
        return positions

    def refresh(self):
        display = self.display
        prop = display.screen().root.get_full_property(self.rules_atom, 0)
        rules = bytes(prop.value) if prop else b''
        if rules != self._rules:
            fields = rules.decode('ascii', 'replace').split('\0')
            groups = []
            if len(fields) >= 4:
                variants = fields[3].split(',')
                for i, layout in enumerate(fields[2].split(',')):
                    groups.append(detected_layout(layout, variants[i] if i < len(variants) else ''))
            self.positions = self.read_positions()
            self.groups = tuple(groups)
            self._rules = rules
        state = GetState(display=display.display, opcode=self.opcode, device=CORE_KEYBOARD)
        return self.layout(state.group)

    def layout(self, group):
        # After replacing a multi-group map, X can keep the previous group locked.
        # A single configured layout still has only one possible set of legends.
        if len(self.groups) == 1:
            return self.groups[0]
        return self.groups[group] if group < len(self.groups) else None
