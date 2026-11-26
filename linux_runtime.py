"""Linux runtime location and Unix launcher."""

import os
from pathlib import Path
import stat
import tempfile

from unix_instance import instance_busy, launch, private_directory, serve, stop_instance


def runtime_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        try:
            info = Path(base).lstat()
            valid = (Path(base).is_absolute() and stat.S_ISDIR(info.st_mode)
                     and info.st_uid == os.getuid() and not info.st_mode & 0o077)
        except OSError:
            valid = False
        if not valid:
            base = None
    directory = (Path(base) / "desktop-pet" if base else
                 Path(tempfile.gettempdir()) / f"desktop-pet-{os.getuid()}")
    return private_directory(directory)
