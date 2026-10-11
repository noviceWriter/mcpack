import json

from mcpack.config import Settings, config_dir


def test_defaults_keep_secrets():
    current = Settings(curseforge_api_key="KEY", web_panel_password="pw", web_panel_port=9000, language="en", debug_mode=True)
    fresh = Settings.defaults(keep_secrets_from=current)
    assert fresh.curseforge_api_key == "KEY"
    assert fresh.web_panel_password == "pw"
    assert fresh.web_panel_port == Settings().web_panel_port
    assert fresh.language == Settings().language
    assert fresh.debug_mode is False


def test_defaults_without_secrets_is_pristine():
    assert Settings.defaults().model_dump() == Settings().model_dump()


def test_backup_file_copies_current_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert Settings().backup_file() is None  # henüz dosya yok
    Settings(curseforge_api_key="KEY", web_panel_port=9100).save()
    backup = Settings.load().backup_file()
    assert backup is not None and backup.parent == config_dir()
    assert json.loads(backup.read_text(encoding="utf-8"))["web_panel_port"] == 9100
