"""GUI giriş noktası."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mcpack.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()  # kendi __init__'inde Settings.theme'e göre stylesheet uygular
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
