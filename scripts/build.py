"""PyInstaller ile portable paket üretimi (ileride).

Kullanım (bağımlılıklar kurulduktan sonra):
    pip install pyinstaller
    python scripts/build.py

Windows'ta tek dosyalık portable .exe, Linux'ta tek dizinlik bina üretir;
AppImage'a çevirmek için ayrıca `python-appimage` kullanılabilir.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "mcpack",
            "--onefile",
            "--windowed",
            "--add-data",
            f"{ROOT / 'data'}{';' if sys.platform == 'win32' else ':'}data",
            "--add-data",
            f"{ROOT / 'src' / 'mcpack' / 'assets'}{';' if sys.platform == 'win32' else ':'}assets",
            str(ROOT / "src" / "mcpack" / "main.py"),
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
