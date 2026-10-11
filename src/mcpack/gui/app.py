"""Masaüstü uygulamasının giriş noktası.

Sıra önemli: önce loglama + istisna kancaları (Qt açılırken bir şey
patlarsa bile iz kalsın), sonra dil, sonra QApplication + tema + pencere.
Qt'nin kendi uyarı/hata mesajları (qWarning vb.) qInstallMessageHandler
ile aynı log akışına yönlendirilir.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from mcpack.config import Settings
from mcpack.i18n import set_language
from mcpack.logging_setup import get_logger, install_exception_hooks, setup_logging

log = get_logger("gui")


def _icon_path() -> Path:
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / "assets" / "icon.png"
    return Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def _install_qt_message_handler() -> None:
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    qt_log = get_logger("qt")
    levels = {
        QtMsgType.QtDebugMsg: 10,
        QtMsgType.QtInfoMsg: 20,
        QtMsgType.QtWarningMsg: 30,
        QtMsgType.QtCriticalMsg: 40,
        QtMsgType.QtFatalMsg: 50,
    }

    def handler(mode, context, message) -> None:
        where = f" ({context.file}:{context.line})" if context.file else ""
        qt_log.log(levels.get(mode, 30), "%s%s", message, where)

    qInstallMessageHandler(handler)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mcpack", description="MC Pack Manager")
    parser.add_argument("--debug", action="store_true", help="DEBUG seviyesinde loglama + Python konsolu")
    parser.add_argument("--open", metavar="PACK_ID", help="Açılışta bu pack'i aç")
    args, _unknown = parser.parse_known_args(argv)
    return args


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    settings = Settings.load()
    debug = True if args.debug or settings.debug_mode else None  # None -> MCPACK_DEBUG ortam değişkeni
    setup_logging(debug=debug)
    install_exception_hooks()
    set_language(settings.language)

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    _install_qt_message_handler()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MC Pack Manager")
    app.setOrganizationName("mcpack")
    icon = _icon_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    from mcpack.gui.icons import icons
    from mcpack.gui.main_window import MainWindow
    from mcpack.gui.theme import apply_theme

    apply_theme(app)
    window = MainWindow()
    window.show()
    if args.open:
        window.open_pack(args.open)
    code = app.exec()
    icons().shutdown()
    log.info("Uygulama kapandı (kod %s)", code)
    return code
