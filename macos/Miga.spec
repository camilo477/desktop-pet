# Native onedir app. Build separately with each architecture's Python.
from pathlib import Path
import platform
from PyInstaller.utils.osx import macosx_version_min

root = Path(SPECPATH).parent
arch = platform.machine()
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
             datas=[(str(root / 'assets'), 'assets')],
             excludes=['windows_runtime', 'windows_input', 'linux_runtime', 'x11_input', 'pynput'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Miga', console=False,
          target_arch=arch, argv_emulation=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Miga', upx=False)
# Local Python distributions can require a newer OS than the Qt wheels.
# Inspect the thinned native binaries before signing the final bundle.
minimum = (14, 4, 0)
for binary in Path(coll.name).rglob('*'):
    if binary.is_symlink() or not binary.is_file():
        continue
    with binary.open('rb') as stream:
        if stream.read(4) == bytes.fromhex('cffaedfe'):
            minimum = max(minimum, macosx_version_min(str(binary)))
app = BUNDLE(coll, name='Miga.app', bundle_identifier='io.github.camilo477.miga',
             info_plist={'CFBundleDisplayName': 'Miga', 'LSUIElement': True,
                         'LSMinimumSystemVersion': '.'.join(map(str, minimum)),
                         'MigaProject': 'camilo477/desktop-pet'})
