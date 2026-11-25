#!/usr/bin/env bash
set -euo pipefail

project_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
venv_python="$project_dir/.venv/bin/python"
bin_dir="$HOME/.local/bin"
command_path="$bin_dir/mascota"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required. Install Python and its venv support first.' >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    printf '%s\n' 'Python 3.10 or newer is required.' >&2
    exit 1
fi
if [[ -e "$command_path" || -L "$command_path" ]]; then
    if [[ ! "$command_path" -ef "$project_dir/mascota" ]]; then
        printf '%s\n' 'A different ~/.local/bin/mascota already exists; move it before installing.' >&2
        exit 1
    fi
fi
if [[ -e "$project_dir/.venv" && ! -f "$project_dir/.venv/pyvenv.cfg" ]]; then
    printf '%s\n' 'The existing .venv is not a virtual environment; move it before installing.' >&2
    exit 1
fi
if [[ ! -x "$venv_python" ]]; then
    if ! python3 -m venv "$project_dir/.venv"; then
        printf '%s\n' 'Could not create the virtual environment. Check Python venv support.' >&2
        exit 1
    fi
fi
"$venv_python" -m pip install --disable-pip-version-check -r "$project_dir/requirements.txt"
chmod +x "$project_dir/mascota"
mkdir -p -- "$bin_dir"
if [[ ! -e "$command_path" && ! -L "$command_path" ]]; then
    ln -s -- "$project_dir/mascota" "$command_path"
fi

printf '\n%s\n' 'Installed. Run: mascota' 'Stop with: mascota off'
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) printf '\n%s\n' 'Add this line once to your shell configuration, then open a new terminal:' \
        'export PATH="$HOME/.local/bin:$PATH"' ;;
esac
