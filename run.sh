#!/usr/bin/env bash
# Programı (GUI) çalıştırır — proje kökünden `./run.sh` ile.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
    echo "venv bulunamadı, oluşturuluyor..."
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
fi

source .venv/bin/activate
exec mcpack
