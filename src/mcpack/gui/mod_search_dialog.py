"""Mod arama/ekleme + shader/datapack/görüntü paketi arama/ekleme + dünya
yükleme penceresi.

CurseForge App ve Prism Launcher'da mod ekleme kalıcı bir yan panel değil,
kendi başına bir "gözat" akışıdır — burada da aynı yaklaşım: ana pencereyi
kalabalıklaştırmadan ayrı, taşınabilir bir pencere (modsuz — kullanıcı ana
pencereyle birlikte açık tutup birden çok mod arayıp ekleyebilir).

Shader/datapack/görüntü paketi de aynı pencerenin sol menüsünden, mod
eklemeyle BİREBİR AYNI akışla (Modrinth/CurseForge'ta arayıp ekleme) eklenir
— kullanıcı isteği: "yine mod yükler gibi". Dünya farklı: Modrinth'te
"dünya/harita" diye bir proje türü yok, sadece CurseForge'ta var (classId 17)
— bu yüzden Dünya sekmesi SADECE CurseForge'ta arar (bkz. SearchPanel
curseforge_only) ve altında ayrıca kendi bilgisayarından yükleme seçeneği de
sunar (kullanıcının kendi haritası/kayıt dosyası olabilir)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.widgets import SearchPanel
from mcpack.models import ContentKind, Loader, Pack

_SEARCHABLE_CONTENT: list[tuple[ContentKind, str, str]] = [
    # (kind, menü etiketi, arama kutusu placeholder'ı)
    (ContentKind.SHADERPACK, "Shader", "Shader adı..."),
    (ContentKind.DATAPACK, "Datapack", "Datapack adı..."),
    (ContentKind.RESOURCEPACK, "Görüntü paketi", "Görüntü paketi adı..."),
]


class ModSearchDialog(QDialog):
    world_added = Signal(str)  # seçilen dünya klasörünün yolu
    world_removed = Signal(str)  # ad (klasör adı)

    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(parent)
        self.pack = pack
        self.is_vanilla = pack.loader == Loader.VANILLA
        title_prefix = "İçerik Ekle" if self.is_vanilla else "Mod Ekle"
        self.setWindowTitle(f"{title_prefix} — {pack.name}")
        self.resize(900, 680)

        self.content_menu = QListWidget()
        self.pages = QStackedWidget()

        self.search_panel: SearchPanel | None = None
        if not self.is_vanilla:
            self.content_menu.addItem(QListWidgetItem("Modlar"))
            self.search_panel = SearchPanel()
            self.pages.addWidget(self.search_panel)

        self.content_search_panels: dict[ContentKind, SearchPanel] = {}
        for kind, label, placeholder in _SEARCHABLE_CONTENT:
            self.content_menu.addItem(QListWidgetItem(label))
            panel = SearchPanel(
                title=f"{label} Ara",
                query_placeholder=placeholder,
                add_button_text=f"Seçili {label.lower()}i Pack'e Ekle",
            )
            self.content_search_panels[kind] = panel
            self.pages.addWidget(panel)

        self._world_list = QListWidget()
        self.content_menu.addItem(QListWidgetItem("Dünya"))
        self.pages.addWidget(self._make_world_page())

        self.content_menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.content_menu.setCurrentRow(0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.content_menu, 0)
        layout.addWidget(self.pages, 1)

    def _make_world_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.world_search_panel = SearchPanel(
            title="Dünya Ara (CurseForge)",
            query_placeholder="Dünya/harita adı...",
            add_button_text="Seçili dünyayı indir ve pack'e ekle",
            curseforge_only=True,
        )
        layout.addWidget(self.world_search_panel)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        local_title = QLabel("Kendi bilgisayarından yükle")
        local_title.setProperty("role", "heading")
        layout.addWidget(local_title)
        hint = QLabel(
            "Zaten diskinde bir dünyan varsa (saves/ altındaki) klasörünü doğrudan seçip yükle. "
            "Birden fazla dünya yükleyebilirsin; sunucu paketi oluştururken hangisinin "
            "ekleneceği ayrıca sorulur."
        )
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        browse_button = QPushButton("+ Dünya Klasörü Seç ve Yükle")
        browse_button.setObjectName("primary")
        browse_button.clicked.connect(self._browse_and_add_world)
        layout.addWidget(browse_button)

        layout.addWidget(QLabel("Yüklü dünyalar:"))
        layout.addWidget(self._world_list, 1)
        self._refresh_world_list()

        remove_button = QPushButton("Seçili dünyayı kaldır")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._remove_selected_world)
        layout.addWidget(remove_button)

        return page

    def _browse_and_add_world(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Dünya Klasörü Seç")
        if not path:
            return
        self.world_added.emit(path)

    def _remove_selected_world(self) -> None:
        item = self._world_list.currentItem()
        if item is None:
            return
        self.world_removed.emit(item.text())

    def refresh_content(self, pack: Pack) -> None:
        """main_window pack.content/pack.content_downloads'ı değiştirdikten
        sonra (ekleme/kaldırma) listeleri/işaretleri güncel pack ile tazeler."""
        self.pack = pack
        self._refresh_world_list()
        for kind, panel in self.content_search_panels.items():
            panel.set_added_project_ids({c.project_id for c in pack.content_downloads_of(kind)})

    def _refresh_world_list(self) -> None:
        self._world_list.clear()
        for entry in self.pack.content_of(ContentKind.WORLD):
            self._world_list.addItem(entry.name)
