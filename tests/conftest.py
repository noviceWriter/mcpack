"""Testler kullanıcının GERÇEK anahtar zincirine (GNOME Keyring vb.) asla
dokunmasın: her teste bellek içi bir keyring arka ucu verilir."""

from __future__ import annotations

import keyring
import pytest
from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


@pytest.fixture(autouse=True)
def memory_keyring(tmp_path, monkeypatch):
    backend = MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    # Ayar dosyası da gerçek ~/.config yerine geçici klasöre yazılsın.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "xdg"))
    monkeypatch.delenv("MCPACK_DISABLE_KEYRING", raising=False)
    yield backend
    keyring.set_keyring(previous)
