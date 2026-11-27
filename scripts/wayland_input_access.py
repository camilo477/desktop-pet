"""Explicit, reversible read permission for selected USB keyboards/mice on Linux."""

import argparse
import os
from pathlib import Path
import pwd
import re
import subprocess
import tempfile


HEADER = '# Miga: read-only access for explicitly selected input devices.\n'


def usb_id(value):
    if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{4}', value):
        raise argparse.ArgumentTypeError('Expected vendor:product, for example 0c45:672e')
    return value.lower()


def rules(uid, devices):
    lines = [HEADER.rstrip()]
    for identity in sorted(set(devices)):
        vendor, product = identity.split(':')
        for kind in ('KEYBOARD', 'MOUSE'):
            lines.append(
                f'ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", '
                f'ENV{{ID_VENDOR_ID}}=="{vendor}", ENV{{ID_MODEL_ID}}=="{product}", '
                f'ENV{{ID_INPUT_{kind}}}=="1", '
                f'RUN+="/usr/bin/setfacl -m u:{uid}:r-- $env{{DEVNAME}}"')
    return '\n'.join(lines) + '\n'


def matching_devices(identities):
    for node in sorted(Path('/dev/input').glob('event*')):
        result = subprocess.run(['/usr/bin/udevadm', 'info', '--query=property', '--name', str(node)],
                                capture_output=True, text=True, timeout=3)
        if result.returncode:
            continue
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        identity = values.get('ID_VENDOR_ID', '') + ':' + values.get('ID_MODEL_ID', '')
        if identity in identities and (values.get('ID_INPUT_KEYBOARD') == '1' or values.get('ID_INPUT_MOUSE') == '1'):
            yield node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'install', 'remove'))
    parser.add_argument('--uid', required=True, type=int)
    parser.add_argument('--device', required=True, action='append', type=usb_id)
    args = parser.parse_args()
    if args.uid <= 0:
        parser.error('Choose a normal user, not root')
    account = pwd.getpwuid(args.uid)
    path = Path('/etc/udev/rules.d') / f'99-miga-input-{args.uid}.rules'
    content = rules(args.uid, args.device)
    if args.action == 'plan':
        print(f'{path}\n{content}')
        print(f'Allows processes of {account.pw_name} to read these devices; grants no device write access.')
        return
    if os.geteuid() != 0:
        parser.error('This explicit permission change requires administrator authorization')
    if os.environ.get('PKEXEC_UID') not in (None, str(args.uid)):
        parser.error('The permission must belong to the authorizing user')
    if path.is_symlink() or path.exists() and not path.read_text().startswith(HEADER):
        parser.error(f'Refusing to replace an unmanaged file: {path}')
    nodes = list(matching_devices(set(args.device)))
    if args.action == 'install':
        if not nodes:
            parser.error('No matching keyboard or mouse is connected')
        # Keep unrelated existing ACLs; only the named user's entry is changed.
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.miga-', delete=False) as file:
            file.write(content)
            temp = Path(file.name)
        try:
            temp.chmod(0o644)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        subprocess.run(['/usr/bin/udevadm', 'control', '--reload-rules'], check=True)
        for node in nodes:
            subprocess.run(['/usr/bin/setfacl', '-m', f'u:{args.uid}:r--', str(node)], check=True)
        print(f'Read permission enabled for {account.pw_name} on {len(nodes)} selected input interfaces.')
    else:
        # Require the same selection used at installation before removing its rule.
        if path.exists() and path.read_text() != content:
            parser.error('Supply the same device selection used for installation')
        path.unlink(missing_ok=True)
        subprocess.run(['/usr/bin/udevadm', 'control', '--reload-rules'], check=True)
        for node in nodes:
            subprocess.run(['/usr/bin/setfacl', '-x', f'u:{args.uid}', str(node)], check=True)
        print('Miga input permission removed.')


if __name__ == '__main__':
    main()
