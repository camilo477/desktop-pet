"""A short, per-user Darwin socket path shared by Finder and all shells."""

import os
from pathlib import Path

from unix_instance import launch, private_directory, serve, stop_instance


def runtime_directory():
    # A shell's TMPDIR may differ from Finder's. Darwin's user temp directory
    # comes from confstr and is normally private even before we add our folder.
    base = os.confstr('CS_DARWIN_USER_TEMP_DIR') if 'CS_DARWIN_USER_TEMP_DIR' in os.confstr_names else None
    if base and len(os.fsencode(Path(base) / 'miga/control.sock')) < 104:
        return private_directory(Path(base) / 'miga')
    return private_directory(Path('/tmp') / f'miga-{os.getuid()}')
