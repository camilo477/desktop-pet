#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec "${MIGA_PYTHON:-python3}" "$project_dir/setup.py" uninstall "$@"
