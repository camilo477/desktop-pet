"""Run against a disposable X server, e.g. xvfb-run -a python tests/x11_lifecycle.py."""

from pathlib import Path
import os
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from activity import ActivityMonitor


if __name__ == '__main__':
    if not os.environ.get('DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        sys.exit('This check needs an isolated X11 display.')
    monitor = ActivityMonitor(True)
    for cycle in range(12):
        monitor.set_enabled(True)
        listeners = tuple(monitor._listeners)
        assert len(listeners) == 2
        if cycle % 2:
            # Include both shutdown during startup and an established idle stream.
            deadline = time.monotonic() + 3
            while monitor._reader is None and time.monotonic() < deadline:
                time.sleep(.01)
            assert monitor._reader is not None
        monitor.stop()
        assert all(not listener.is_alive() for listener in listeners)
        assert not monitor.snapshot().pressed
    print('PASS: X11 RECORD releases both listeners without needing a final input event.')
