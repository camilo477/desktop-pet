"""Controlled Apple virtual-key and scroll fixtures. No global listener."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macos_keyboard import KEYS, MODIFIERS, modifier_down, physical_key, source_layout, wheel_units

assert ''.join(KEYS[i] for i in (0, 12, 16, 6)) == 'AQYZ'
assert [KEYS[i] for i in (29,18,19,20,21,23,22,26,28,25)] == ['Digit' + str(i) for i in range(10)]
assert [physical_key(i, True) for i in (10, 50)] == ['Backquote', 'IntlBackslash']
assert [physical_key(i) for i in (36,76,51,117)] == ['Enter','NumpadEnter','Backspace','Delete']
assert physical_key(71) is None  # Apple Clear is not Num Lock.
for code, (side, other, family) in MODIFIERS.items():
    assert modifier_down(code, family | other | side, lambda _: False)
    assert not modifier_down(code, family | other, lambda _: True)
    assert modifier_down(code, family, lambda i: i == code)
assert wheel_units(-20, 10, True) == (-1., .5)
assert wheel_units(80, -1, False) == (4., -1.)
for source, layout in (('ABC', 'us'), ('British', 'gb'), ('LatinAmerican', 'latam'),
                       ('Spanish-ISO', 'es'), ('German', 'de'), ('French', 'fr'),
                       ('Dvorak', 'dvorak'), ('Colemak', 'colemak')):
    assert source_layout('com.apple.keylayout.' + source) == layout
assert source_layout('custom.US') is None
assert source_layout('com.apple.keylayout.Dvorak-QwertyCmd') is None
print('PASS: Apple physical positions, overlapping modifiers, hardware ISO swap, wheels and source IDs.')
