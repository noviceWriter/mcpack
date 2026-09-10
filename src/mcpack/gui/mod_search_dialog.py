"""Mod arama/ekleme penceresi.

CurseForge App ve Prism Launcher'da mod ekleme kalıcı bir yan panel değil,
kendi başına bir "gözat" akışıdır — burada da aynı yaklaşım: ana pencereyi
kalabalıklaştırmadan ayrı, taşınabilir bir pencere (modsuz — kullanıcı ana
pencereyle birlikte açık tutup birden çok mod arayıp ekleyebilir).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout

from mcpack.gui.widgets import SearchPanel
from mcpack.models import Pack


class ModSearchDialog(QDialog):
    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(parent)
        self.pack_id = pack.id
        self.setWindowTitle(f"Mod Ekle — {pack.name}")
        self.resize(620, 680)

        self.search_panel = SearchPanel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.search_panel)
