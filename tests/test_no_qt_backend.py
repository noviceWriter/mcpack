"""Backend (sunucu çalışma zamanı, web paneli, CLI) PySide6 OLMADAN
import edilebilmeli — web paneli/CLI başsız bir sunucuda Qt kurmadan
çalışabilsin diye."""

import subprocess
import sys

CODE = r"""
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name == "PySide6" or name.startswith("PySide6.") or name == "shiboken6":
            raise ImportError("PySide6 bu testte yasak")
sys.meta_path.insert(0, Block())
import mcpack.server_runtime, mcpack.webpanel.app, mcpack.cli, mcpack.importers, mcpack.backups, mcpack.packs.updates
from mcpack.logging_setup import system_info
assert "pyside6" not in system_info()
print("ok")
"""


def test_backend_imports_without_pyside6():
    out = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
