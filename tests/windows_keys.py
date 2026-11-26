"""Portable set-1 fixtures. No OS input or user preferences are used."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from activity import ActivityMonitor
from keyboard_layout import Keyboard
from windows_keyboard import BASE, EXTENDED, LAYOUT_IDS, foreign_layout, physical_key


def main():
    expected = Keyboard('100', 'ISO').ids
    assert set(BASE.values()) | set(EXTENDED.values()) | {'Pause'} == set(expected)
    for scan, vk, flags, name in (
        (0x2a, 0x10, 0, 'ShiftLeft'), (0x36, 0x10, 0, 'ShiftRight'),
        (0x1d, 0x11, 0, 'CtrlLeft'), (0x1d, 0x11, 2, 'CtrlRight'),
        (0x38, 0x12, 2, 'AltRight'), (0x38, 0x12, 0, 'AltLeft'),
        (0x1c, 13, 0, 'Enter'), (0x1c, 13, 2, 'NumpadEnter'),
        (0x47, 0x24, 0, 'Numpad7'), (0x47, 0x24, 2, 'Home'),
        (0x56, 0xe2, 0, 'IntlBackslash'), (0x45, 0x90, 2, 'NumLock'),
        (0x1d, 0x13, 4, 'Pause'), (0x46, 3, 2, 'Pause'),
        (0x37, 0x2c, 2, 'PrintScreen'), (0x54, 0x2c, 0, 'PrintScreen'),
        (0x2a, 0xff, 2, None), (0x2a, 0x10, 2, None), (0xff, 0xff, 0, None),
        (0x10, 0x41, 0, 'Q'), (0x15, 0x5a, 0, 'Y'),
    ):
        assert physical_key(scan, flags, vk) == physical_key(scan, flags | 1, vk) == name
    assert len(set(LAYOUT_IDS.values())) == 8
    assert foreign_layout(0x080a0409, {}) == 'latam'
    assert foreign_layout(0xf0020409, {2: 'dvorak'}) == 'dvorak'
    assert foreign_layout(0xf0990409, {}) is None
    monitor = ActivityMonitor(False)
    monitor.set_enabled(True)
    for _ in range(150):
        monitor.key_down('Q', (1, 'Q'))
    monitor.key_down('Q', (2, 'Q'))
    assert monitor.snapshot().new_presses == 2
    monitor.key_up((1, 'Q'), immediate=True)
    assert monitor.snapshot().held == {'Q'}
    monitor.set_keyboard(Keyboard('60', 'ANSI', 'fr'))
    monitor.key_down('NumpadEnter', (1, 'NumpadEnter'))
    assert monitor.snapshot().held == {'Q'}
    monitor.key_up((2, 'Q'), immediate=True)
    monitor.key_up((1, 'NumpadEnter'), immediate=True)
    assert not monitor.snapshot().any_held
    print('PASS: 105 physical positions, extended keys, layouts, repeat, multiple devices and compact formats.')


if __name__ == '__main__':
    main()
