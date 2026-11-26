"""Start or close Miga in the current user's graphical session."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog='miga', description='Miga, tu pequeña compañía de escritorio.')
    parser.add_argument('command', nargs='?', choices=('off',), help='cerrar Miga')
    parser.add_argument('--run', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--ready-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform not in ('linux', 'win32'):
        print('Miga requiere Linux o Windows x64.', file=sys.stderr)
        return 1
    try:
        if sys.platform == 'win32':
            import windows_runtime as runtime
        else:
            import linux_runtime as runtime
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setOrganizationName('desktop-pet')
        QCoreApplication.setApplicationName('mascota')
        directory = runtime.runtime_directory()
        if args.run:
            return runtime.serve(directory, args.ready_fd)
        app = QCoreApplication([sys.argv[0]])
        return runtime.stop_instance(directory) if args.command else runtime.launch(directory)
    except (ImportError, OSError, RuntimeError) as error:
        if sys.stderr is not None:
            print(f'miga: {error}', file=sys.stderr)
        elif sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Miga', 0x10)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
