"""PySide6 masaüstü arayüzü.

Katmanlar:
- controller.py — tüm iş mantığı (widget yok), TaskManager ile arka plan görevleri
- pages/*      — sayfalar (Ana Sayfa, Kütüphane, Pack, Ayarlar, Geliştirici)
- components.py, theme.py, dialogs.py, palette.py — ortak arayüz parçaları
- app.py       — giriş noktası: loglama, istisna kancaları, Qt mesaj yönlendirme

Masaüstüne özgü metinler strings.py'de; import edilince mcpack.i18n.STRINGS'e eklenir.
"""

from mcpack.gui import strings as _strings  # noqa: F401  (çeviri anahtarlarını kaydeder)
