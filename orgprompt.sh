#!/usr/bin/env bash
set -euo pipefail

dir="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$dir/.venv/bin/activate" ]; then
    source "$dir/.venv/bin/activate"
fi

exec python3 "$dir/main.py" "$@"
