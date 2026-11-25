"""Finite QWERTY key definitions shared by input, drawing and paw contacts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    identifier: str
    label: str
    scan: int
    column: float
    row: float
    width: float = 1.0

    @staticmethod
    def project(u: float, v: float) -> tuple[float, float]:
        # Rotate the keyboard on its own plane before applying floor perspective.
        u, v = 18.45 - u, 4.95 - v
        return 70 - v * 1.2 + u * (4.9 + v * .16), 151 + v * 6 + u * .035

    @property
    def contact(self) -> tuple[float, float]:
        return self.project(self.column + self.width * .5, self.row + .53)

    @property
    def polygon(self) -> tuple[tuple[float, float], ...]:
        u, v, w = self.column + .07, self.row + .07, self.width - .14
        return (self.project(u, v), self.project(u + w, v),
                self.project(u + w, v + .82), self.project(u, v + .82))

    @property
    def label_basis(self):
        u, v = self.column + self.width * .5, self.row + .53
        x, y = self.project(u, v)
        ux, uy = self.project(u + 1, v)
        vx, vy = self.project(u, v + 1)
        return x, y, (ux - x) / 5, (uy - y) / 5, (vx - x) / 6, (vy - y) / 6

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

    row(0, [("Escape", "esc", 9, 1)] +
        [("Digit" + digit, digit, scan, 1) for digit, scan in zip("1234567890", range(10, 20))] +
        [("Minus", "-", 20, 1), ("Equal", "=", 21, 1), ("Backspace", "del", 22, 2)])
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
    row(4, [("CtrlLeft", "ctrl", 37, 1.25), ("MetaLeft", "sys", 133, 1),
            ("AltLeft", "alt", 64, 1.25), ("Space", "", 65, 5.5),
            ("AltRight", "alt", 108, 1.25), ("Menu", "menu", 135, 1.25),
            ("CtrlRight", "ctrl", 105, 2)])
    keys.extend((Key("ArrowUp", "^", 111, 16.4, 3), Key("ArrowLeft", "<", 113, 15.4, 4),
                 Key("ArrowDown", "v", 116, 16.4, 4), Key("ArrowRight", ">", 114, 17.4, 4)))
    return tuple(keys)


KEYS = _definitions()
BY_ID = {key.identifier: key for key in KEYS}
BY_SCAN = {key.scan: key.identifier for key in KEYS}
KEYBOARD_CENTER = Key.project(7.5, 2.5)
BOARD = tuple(Key.project(u, v) for u, v in ((-.25, -.2), (18.7, -.2), (18.7, 5.15), (-.25, 5.15)))
SPECIAL_SYMBOLS = {0xff1b: "Escape", 0xff08: "Backspace", 0xff09: "Tab", 0xff0d: "Enter",
                   0xffe1: "ShiftLeft", 0xffe2: "ShiftRight", 0xffe3: "CtrlLeft", 0xffe4: "CtrlRight",
                   0xffe9: "AltLeft", 0xffea: "AltRight", 0xfe03: "AltRight", 0xffe5: "CapsLock",
                   0xffeb: "MetaLeft", 0xff67: "Menu", 0xff51: "ArrowLeft", 0xff52: "ArrowUp",
                   0xff53: "ArrowRight", 0xff54: "ArrowDown", 0x20: "Space"}
LABELS = {
    "es": {"Minus": "'", "Equal": "¡", "BracketLeft": "`", "BracketRight": "+",
           "Backslash": "ç", "Semicolon": "Ñ", "Quote": "´", "Slash": "-"},
    "latam": {"Minus": "'", "Equal": "¿", "BracketLeft": "´", "BracketRight": "+",
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
