"""One physical full-size QWERTY layout for input, artwork and paw contacts."""

from dataclasses import dataclass

KEYBOARD_SCALE = .82
KEY_TRAVEL = .35 * KEYBOARD_SCALE


@dataclass(frozen=True)
class Key:
    identifier: str
    label: str
    scan: int
    column: float
    row: float
    width: float = 1.0
    height: float = 1.0

    @staticmethod
    def project(u: float, v: float) -> tuple[float, float]:
        # A half-turn on the floor plane: this is the cat's keyboard.
        u, v = 23.0 - u, 5.0 - v
        return (64 + KEYBOARD_SCALE * (u * (5.7 + v * .06) - v * .50),
                160 + KEYBOARD_SCALE * (v * 4.6 + u * .025))

    @property
    def contact(self) -> tuple[float, float]:
        return self.project(self.column + self.width * .5, self.row + self.height * .5)

    @property
    def polygon(self) -> tuple[tuple[float, float], ...]:
        u, v = self.column + .075, self.row + .075
        w, h = self.width - .15, self.height - .15
        return (self.project(u, v), self.project(u + w, v),
                self.project(u + w, v + h), self.project(u, v + h))

    @property
    def label_basis(self):
        u, v = self.column + self.width * .5, self.row + self.height * .5
        x, y = self.project(u, v)
        ux, uy = self.project(u + 1, v)
        vx, vy = self.project(u, v + 1)
        return x, y, (ux - x) / 5.7, (uy - y) / 5.7, (vx - x) / 4.6, (vy - y) / 4.6

    @property
    def preferred_paw(self):
        return 0 if self.contact[0] < KEYBOARD_CENTER[0] else 1

    @property
    def modifier(self) -> bool:
        return self.identifier.startswith(("Shift", "Ctrl", "Alt", "Meta")) or self.identifier in ("CapsLock", "Menu")


def _definitions() -> tuple[Key, ...]:
    keys = []

    def row(number, entries):
        column = 0.0
        for identifier, label, scan, width in entries:
            keys.append(Key(identifier, label, scan, column, number, width))
            column += width

    row(0, [("Backquote", "`", 49, 1)] +
        [("Digit" + digit, digit, scan, 1) for digit, scan in zip("1234567890", range(10, 20))] +
        [("Minus", "-", 20, 1), ("Equal", "=", 21, 1), ("Backspace", "bk", 22, 2)])
    row(1, [("Tab", "tab", 23, 1.5)] +
        [(letter, letter, scan, 1) for letter, scan in zip("QWERTYUIOP", range(24, 34))] +
        [("BracketLeft", "[", 34, 1), ("BracketRight", "]", 35, 1), ("Backslash", "\\", 51, 1.5)])
    row(2, [("CapsLock", "cap", 66, 1.75)] +
        [(letter, letter, scan, 1) for letter, scan in zip("ASDFGHJKL", range(38, 47))] +
        [("Semicolon", ";", 47, 1), ("Quote", "'", 48, 1), ("Enter", "ret", 36, 2.25)])
    row(3, [("ShiftLeft", "sh", 50, 1.25), ("IntlBackslash", "<", 94, 1)] +
        [(letter, letter, scan, 1) for letter, scan in zip("ZXCVBNM", range(52, 59))] +
        [("Comma", ",", 59, 1), ("Period", ".", 60, 1), ("Slash", "/", 61, 1),
         ("ShiftRight", "sh", 62, 2.75)])
    row(4, [("CtrlLeft", "ctrl", 37, 1.25), ("MetaLeft", "sys", 133, 1.25),
            ("AltLeft", "alt", 64, 1.25), ("Space", "", 65, 6.25),
            ("AltRight", "AltGr", 108, 1.25), ("MetaRight", "sys", 134, 1.25),
            ("Menu", "menu", 135, 1.25), ("CtrlRight", "ctrl", 105, 1.25)])
    keys.append(Key("Escape", "esc", 9, 0, -1.4))
    for index in range(12):
        scan = 67 + index if index < 10 else 95 + index - 10
        keys.append(Key(f"F{index + 1}", f"F{index + 1}", scan, 2 + index + (index // 4) * .5, -1.4))
    for identifier, label, scan, column in (("PrintScreen", "prt", 107, 15.5),
                                          ("ScrollLock", "scr", 78, 16.5), ("Pause", "brk", 127, 17.5)):
        keys.append(Key(identifier, label, scan, column, -1.4))
    for number, entries in ((0, (("Insert", "ins", 118), ("Home", "hm", 110), ("PageUp", "pu", 112))),
                            (1, (("Delete", "del", 119), ("End", "end", 115), ("PageDown", "pd", 117)))):
        for index, (identifier, label, scan) in enumerate(entries):
            keys.append(Key(identifier, label, scan, 15.5 + index, number))
    keys.extend((Key("ArrowUp", "^", 111, 16.5, 3), Key("ArrowLeft", "<", 113, 15.5, 4),
                 Key("ArrowDown", "v", 116, 16.5, 4), Key("ArrowRight", ">", 114, 17.5, 4)))
    for index, (identifier, label, scan) in enumerate((("NumLock", "num", 77), ("NumpadDivide", "/", 106),
                                                    ("NumpadMultiply", "*", 63), ("NumpadSubtract", "-", 82))):
        keys.append(Key(identifier, label, scan, 19 + index, 0))
    for number, digits, scans in ((1, "789", (79, 80, 81)), (2, "456", (83, 84, 85)),
                                 (3, "123", (87, 88, 89))):
        for index, (digit, scan) in enumerate(zip(digits, scans)):
            keys.append(Key("Numpad" + digit, digit, scan, 19 + index, number))
    keys.extend((Key("NumpadAdd", "+", 86, 22, 1, 1, 2),
                 Key("NumpadEnter", "ret", 104, 22, 3, 1, 2),
                 Key("Numpad0", "0", 90, 19, 4, 2), Key("NumpadDecimal", ".", 91, 21, 4)))
    return tuple(keys)


KEYBOARD_CENTER = Key.project(7.5, 2.5)
KEYS = _definitions()
BY_ID = {key.identifier: key for key in KEYS}
BY_SCAN = {key.scan: key.identifier for key in KEYS}
BOARD = tuple(Key.project(u, v) for u, v in ((-.3, -1.7), (23.3, -1.7), (23.3, 5.25), (-.3, 5.25)))
SPECIAL_SYMBOLS = {0xff1b: "Escape", 0xff08: "Backspace", 0xff09: "Tab", 0xff0d: "Enter",
                   0xffe1: "ShiftLeft", 0xffe2: "ShiftRight", 0xffe3: "CtrlLeft", 0xffe4: "CtrlRight",
                   0xffe9: "AltLeft", 0xffea: "AltRight", 0xfe03: "AltRight", 0xffe5: "CapsLock",
                   0xffeb: "MetaLeft", 0xffec: "MetaRight", 0xff67: "Menu", 0xff51: "ArrowLeft",
                   0xff52: "ArrowUp", 0xff53: "ArrowRight", 0xff54: "ArrowDown", 0x20: "Space",
                   0xff63: "Insert", 0xffff: "Delete", 0xff50: "Home", 0xff57: "End",
                   0xff55: "PageUp", 0xff56: "PageDown", 0xff61: "PrintScreen", 0xff14: "ScrollLock",
                   0xff13: "Pause", 0xff7f: "NumLock", 0xff8d: "NumpadEnter", 0xffaf: "NumpadDivide",
                   0xffaa: "NumpadMultiply", 0xffad: "NumpadSubtract", 0xffab: "NumpadAdd",
                   0xffae: "NumpadDecimal", 0xffac: "NumpadDecimal"}
SPECIAL_SYMBOLS.update({0xffbe + i: f"F{i + 1}" for i in range(12)})
SPECIAL_SYMBOLS.update({0xffb0 + i: f"Numpad{i}" for i in range(10)})
SPECIAL_SYMBOLS.update(dict(zip((0xff9e, 0xff9c, 0xff99, 0xff9b, 0xff96, 0xff9d, 0xff98, 0xff95, 0xff97, 0xff9a),
                                (f"Numpad{i}" for i in range(10)))))
SPECIAL_SYMBOLS[0xff9f] = "NumpadDecimal"
LABELS = {
    "es": {"Backquote": "º", "Minus": "'", "Equal": "¡", "BracketLeft": "`", "BracketRight": "+",
           "Backslash": "ç", "Semicolon": "Ñ", "Quote": "´", "Slash": "-"},
    "latam": {"Backquote": "|", "Minus": "'", "Equal": "¿", "BracketLeft": "´", "BracketRight": "+",
              "Backslash": "}", "Semicolon": "Ñ", "Quote": "{", "Slash": "-"},
}


def key_for_symbol(symbol: int, layout: str = "us") -> str | None:
    if symbol in SPECIAL_SYMBOLS:
        return SPECIAL_SYMBOLS[symbol]
    if ord("a") <= symbol <= ord("z") or ord("A") <= symbol <= ord("Z"):
        return chr(symbol).upper()
    if ord("0") <= symbol <= ord("9"):
        return "Digit" + chr(symbol)
    if symbol in (0xf1, 0xd1):
        return "Semicolon"
    for key in KEYS:
        label = LABELS.get(layout, {}).get(key.identifier, key.label)
        if len(label) == 1 and ord(label) == symbol:
            return key.identifier
    return None
