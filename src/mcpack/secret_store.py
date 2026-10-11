"""Gizli ayarların (CurseForge API anahtarı, web paneli şifresi) işletim
sisteminin anahtar zincirinde saklanması.

Önceden ikisi de settings.json'da DÜZ METİN duruyordu — dosyayı okuyabilen
her program/kişi (yedekler, senkronize edilen ayar klasörleri, yanlışlıkla
paylaşılan ekran görüntüleri/destek dosyaları) anahtarı da görüyordu.

`keyring` kütüphanesi platformun yerel deposunu kullanır: Linux'ta Secret
Service (GNOME Keyring / KWallet), Windows'ta Credential Manager, macOS'ta
Keychain. Kullanılabilir bir depo yoksa (ör. masaüstü oturumu olmayan SSH,
bazı CI ortamları) `available()` False döner ve config.py düz metne (600
izinli dosya) düşer — program asla bu yüzden çalışmaz hale gelmez.

MCPACK_DISABLE_KEYRING=1 anahtar zincirini tamamen devre dışı bırakır.
"""

from __future__ import annotations

import os

from mcpack.logging_setup import get_logger

log = get_logger(__name__)

SERVICE = "mcpack"
_warned = False


def _keyring():
    if os.environ.get("MCPACK_DISABLE_KEYRING", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    try:
        import keyring
        from keyring.backends import fail
    except Exception:  # noqa: BLE001 - kütüphane yoksa düz metne düş
        return None
    try:
        backend = keyring.get_keyring()
    except Exception:  # noqa: BLE001
        return None
    if isinstance(backend, fail.Keyring) or getattr(backend, "priority", 1) <= 0:
        return None
    return keyring


def available() -> bool:
    return _keyring() is not None


def backend_name() -> str | None:
    kr = _keyring()
    if kr is None:
        return None
    backend = kr.get_keyring()
    return f"{type(backend).__module__.removeprefix('keyring.backends.')}.{type(backend).__name__}"


def _warn_once(action: str, exc: Exception) -> None:
    global _warned
    if not _warned:
        _warned = True
        log.warning("Anahtar zinciri kullanılamadı (%s): %s — gizli ayarlar düz metin olarak saklanacak", action, exc)


def get_secret(name: str) -> str | None:
    """Kayıtlı değer; kayıt yoksa "" , depo kullanılamıyorsa None."""
    kr = _keyring()
    if kr is None:
        return None
    try:
        value = kr.get_password(SERVICE, name)
    except Exception as exc:  # noqa: BLE001
        _warn_once("okuma", exc)
        return None
    return value or ""


def set_secret(name: str, value: str) -> bool:
    """Başarılıysa True. Boş değer kaydı siler."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        if value:
            kr.set_password(SERVICE, name, value)
        else:
            try:
                kr.delete_password(SERVICE, name)
            except Exception:  # noqa: BLE001 - zaten yoksa sorun değil
                pass
    except Exception as exc:  # noqa: BLE001
        _warn_once("yazma", exc)
        return False
    return True
