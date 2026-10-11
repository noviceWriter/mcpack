"""GUI giriş noktası (`mcpack` komutu) — asıl kurulum gui/app.py'de."""

from __future__ import annotations

import sys


def main() -> None:
    from mcpack.gui.app import run

    sys.exit(run())


if __name__ == "__main__":
    main()
