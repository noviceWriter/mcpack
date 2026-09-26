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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    content_removed = Signal(object, str)  # ContentKind, project_id

    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(parent)
        self.pack = pack
        self.is_vanilla = pack.loader == Loader.VANILLA
        title_prefix = "İçerik Ekle" if self.is_vanilla else "Mod Ekle"
        self.setWindowTitle(f"{title_prefix} — {pack.name}")
        self.resize(900, 680)

        self.content_menu = QListWidget()
        self.content_menu.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pages = QStackedWidget()

        self.search_panel: SearchPanel | None = None
        if not self.is_vanilla:
            self.content_menu.addItem(QListWidgetItem("Modlar"))
            self.search_panel = SearchPanel()
            self.pages.addWidget(self.search_panel)

        self.content_search_panels: dict[ContentKind, SearchPanel] = {}
        self._installed_content_lists: dict[ContentKind, QListWidget] = {}
        for kind, label, placeholder in _SEARCHABLE_CONTENT:
            self.content_menu.addItem(QListWidgetItem(label))
            self.pages.addWidget(self._make_content_page(kind, label, placeholder))

        self._world_list = QListWidget()
        self._world_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.content_menu.addItem(QListWidgetItem("Dünya"))
        self.pages.addWidget(self._make_world_page())

        self.content_menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.content_menu.setCurrentRow(0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.content_menu, 0)
        layout.addWidget(self.pages, 1)

        self.refresh_content(pack)

    def _make_content_page(self, kind: ContentKind, label: str, placeholder: str) -> QWidget:
        """Shader/datapack/görüntü paketi arama sekmesi — arama sonuçlarının
        altında, o türden zaten eklenmiş olanları gösteren ve kaldırmayı
        sağlayan bir liste var (dünya sekmesindeki aynı desen — daha önce
        PackManager.remove_content_download çağıracak hiçbir GUI kontrolü
        yoktu, tek yol pack JSON'unu elle düzenlemekti)."""
        page = QWidget()
        layout = QVBoxLayout(page)

        panel = SearchPanel(
            title=f"{label} Ara",
            query_placeholder=placeholder,
            add_button_text=f"Seçili {label.lower()}i Pack'e Ekle",
        )
        self.content_search_panels[kind] = panel
        layout.addWidget(panel, 1)

        layout.addWidget(QLabel(f"Eklenmiş {label.lower()}ler:"))
        installed_list = QListWidget()
        installed_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        installed_list.setMaximumHeight(110)
        self._installed_content_lists[kind] = installed_list
        layout.addWidget(installed_list)

        remove_button = QPushButton(f"Seçili {label.lower()}i kaldır")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(lambda _checked=False, k=kind: self._remove_selected_content(k))
        layout.addWidget(remove_button)

        return page

    def _remove_selected_content(self, kind: ContentKind) -> None:
        item = self._installed_content_lists[kind].currentItem()
        if item is None:
            return
        project_id = item.data(Qt.ItemDataRole.UserRole)
        self.content_removed.emit(kind, project_id)

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
            downloads = pack.content_downloads_of(kind)
            panel.set_added_project_ids({c.project_id for c in downloads})
            installed_list = self._installed_content_lists[kind]
            installed_list.clear()
            for entry in downloads:
                item = QListWidgetItem(entry.name or entry.file_name)
                item.setData(Qt.ItemDataRole.UserRole, entry.project_id)
                installed_list.addItem(item)

    def _refresh_world_list(self) -> None:
        self._world_list.clear()
        for entry in self.pack.content_of(ContentKind.WORLD):
            self._world_list.addItem(entry.name)
