# Native onedir app. Build separately with each architecture's Python.
from pathlib import Path
import platform

root = Path(SPECPATH).parent
arch = platform.machine()
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
             datas=[(str(root / 'assets'), 'assets')],
             excludes=['windows_runtime', 'windows_input', 'linux_runtime', 'x11_input', 'pynput'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Miga', console=False,
          target_arch=arch, argv_emulation=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Miga', upx=False)
app = BUNDLE(coll, name='Miga.app', bundle_identifier='io.github.camilo477.miga',
             info_plist={'CFBundleDisplayName': 'Miga', 'LSUIElement': True,
                         'LSMinimumSystemVersion': '14.4',
                         'MigaProject': 'camilo477/desktop-pet',
                         'NSInputMonitoringUsageDescription':
                         'Miga anima sus patitas con posiciones físicas y movimiento. No guarda texto ni historial.'})
