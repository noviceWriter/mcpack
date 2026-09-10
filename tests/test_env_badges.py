from mcpack.gui.widgets import _environment_label


def test_client_only_mod():
    # Sodium: client=required, server=unsupported
    assert _environment_label("required", "unsupported") == "İstemci"


def test_server_only_mod():
    assert _environment_label("unsupported", "required") == "Sunucu"


def test_optional_both_sides_shows_single_combined_label():
    # JEI: client=optional, server=optional -> ayrı ayrı değil, tek birleşik etiket
    assert _environment_label("optional", "optional") == "İstemci + Sunucu"


def test_required_both_sides_shows_combined_label():
    assert _environment_label("required", "required") == "İstemci + Sunucu"


def test_required_client_optional_server_shows_combined_label():
    # Her iki taraf da unsupported değilse -> tek "İstemci + Sunucu" etiketi
    assert _environment_label("required", "optional") == "İstemci + Sunucu"


def test_unsupported_both_sides_returns_unknown():
    assert _environment_label("unsupported", "unsupported") == "Bilinmiyor"
