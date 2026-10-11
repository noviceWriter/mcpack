import json
import os
import stat

from mcpack.config import SETTINGS_FILE, Settings, config_dir


def _raw() -> dict:
    return json.loads((config_dir() / SETTINGS_FILE).read_text(encoding="utf-8"))


def test_secrets_go_to_keyring_not_file(memory_keyring):
    Settings(curseforge_api_key="CFKEY", web_panel_password="pw").save()
    raw = _raw()
    assert raw["curseforge_api_key"] == "" and raw["web_panel_password"] == ""
    assert raw["secrets_in_keyring"] is True
    assert memory_keyring.store[("mcpack", "curseforge_api_key")] == "CFKEY"
    loaded = Settings.load()
    assert loaded.curseforge_api_key == "CFKEY" and loaded.web_panel_password == "pw"


def test_plaintext_secrets_are_migrated_on_load(memory_keyring):
    path = config_dir() / SETTINGS_FILE
    path.write_text(json.dumps({"curseforge_api_key": "OLD", "web_panel_password": "x"}), encoding="utf-8")
    loaded = Settings.load()
    assert loaded.curseforge_api_key == "OLD"
    assert _raw()["curseforge_api_key"] == ""  # dosyadan silindi
    assert memory_keyring.store[("mcpack", "curseforge_api_key")] == "OLD"


def test_clearing_secret_deletes_keyring_entry(memory_keyring):
    Settings(curseforge_api_key="CFKEY").save()
    Settings(curseforge_api_key="").save()
    assert ("mcpack", "curseforge_api_key") not in memory_keyring.store


def test_falls_back_to_plaintext_when_keyring_disabled(monkeypatch):
    monkeypatch.setenv("MCPACK_DISABLE_KEYRING", "1")
    Settings(curseforge_api_key="CFKEY").save()
    raw = _raw()
    assert raw["curseforge_api_key"] == "CFKEY" and raw["secrets_in_keyring"] is False
    assert Settings.load().curseforge_api_key == "CFKEY"


def test_settings_file_is_private():
    Settings().save()
    if os.name != "nt":
        mode = stat.S_IMODE((config_dir() / SETTINGS_FILE).stat().st_mode)
        assert mode == 0o600
