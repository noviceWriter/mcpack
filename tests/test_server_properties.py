from pathlib import Path

from mcpack.server_properties import KNOWN_PROPERTIES, merged_with_defaults, read_properties, write_properties


def test_read_properties_parses_key_value_lines(tmp_path: Path):
    path = tmp_path / "server.properties"
    path.write_text("#Minecraft server properties\nmotd=My Server\nmax-players=10\n\n", encoding="utf-8")

    values = read_properties(path)

    assert values == {"motd": "My Server", "max-players": "10"}


def test_read_properties_missing_file_returns_empty_dict(tmp_path: Path):
    assert read_properties(tmp_path / "does-not-exist.properties") == {}


def test_write_properties_roundtrip(tmp_path: Path):
    path = tmp_path / "server.properties"
    write_properties(path, {"motd": "Hello", "pvp": "false"})

    assert read_properties(path) == {"motd": "Hello", "pvp": "false"}


def test_merged_with_defaults_fills_missing_known_keys_without_overwriting_existing():
    values = {"motd": "Custom MOTD"}

    merged = merged_with_defaults(values)

    assert merged["motd"] == "Custom MOTD"  # var olan değer korunur
    assert merged["difficulty"] == "easy"  # eksik olan varsayılanla dolar
    assert all(p.key in merged for p in KNOWN_PROPERTIES)
