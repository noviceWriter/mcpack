"""GUI giriş noktası."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from mcpack.gui.main_window import MainWindow


def _icon_path() -> Path:
    """PyInstaller ile paketlenmişse sys._MEIPASS altındaki assets/ (bkz.
    scripts/build.py --add-data), aksi halde paketin kendi assets/ klasörü
    (known_mods.py:_data_dir ile aynı desen)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / "assets" / "icon.png"
    return Path(__file__).parent / "assets" / "icon.png"


def main() -> None:
    app = QApplication(sys.argv)
    icon_path = _icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()  # kendi __init__'inde Settings.theme'e göre stylesheet uygular
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
