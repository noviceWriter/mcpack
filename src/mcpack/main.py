"""GUI giriş noktası."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mcpack.gui.main_window import MainWindow
from mcpack.gui.theme import DARK_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
