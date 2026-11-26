"""Start or close Miga in the current user's graphical session."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog='miga', description='Miga, tu pequeña compañía de escritorio.')
    parser.add_argument('command', nargs='?', choices=('off',), help='cerrar Miga')
    parser.add_argument('--background', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--run', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--ready-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform not in ('linux', 'win32', 'darwin'):
        print('Miga requiere Linux, Windows x64 o macOS.', file=sys.stderr)
        return 1
    try:
        if sys.platform == 'win32':
            import windows_runtime as runtime
        elif sys.platform == 'darwin':
            import macos_runtime as runtime
        else:
            import linux_runtime as runtime
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setOrganizationName('desktop-pet')
        QCoreApplication.setApplicationName('mascota')
        if sys.platform == 'darwin':
            QCoreApplication.setOrganizationDomain('camilo477.github.io')
        directory = runtime.runtime_directory()
        finder_launch = (sys.platform == 'darwin' and getattr(sys, 'frozen', False)
                         and not args.background and not args.command)
        if args.run or finder_launch:
            return runtime.serve(directory, args.ready_fd)
        app = QCoreApplication([sys.argv[0]])
        return runtime.stop_instance(directory) if args.command else runtime.launch(directory)
    except (ImportError, OSError, RuntimeError) as error:
        if sys.platform == 'darwin' and getattr(sys, 'frozen', False) and not (args.background or args.command or args.run):
            from AppKit import NSAlert
            alert = NSAlert.alloc().init()
            alert.setMessageText_('Miga')
            alert.setInformativeText_(str(error))
            alert.runModal()
        elif sys.stderr is not None:
            print(f'miga: {error}', file=sys.stderr)
        elif sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Miga', 0x10)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
