from mcpack.gui.widgets import _supported_environments


def test_client_only_mod():
    # Sodium: client=required, server=unsupported
    assert _supported_environments("required", "unsupported") == ["İstemci"]


def test_server_only_mod():
    assert _supported_environments("unsupported", "required") == ["Sunucu"]


def test_optional_both_sides_supports_all_three():
    # JEI: client=optional, server=optional (bkz. Modrinth "Supported environments")
    assert _supported_environments("optional", "optional") == [
        "İstemci",
        "Sunucu",
        "İstemci + Sunucu",
    ]


def test_required_both_sides_only_supports_combined():
    assert _supported_environments("required", "required") == ["İstemci + Sunucu"]


def test_required_client_optional_server():
    assert _supported_environments("required", "optional") == ["İstemci", "İstemci + Sunucu"]


def test_unsupported_both_sides_returns_empty():
    assert _supported_environments("unsupported", "unsupported") == []
