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
curseforge_only). Kendi bilgisayarından dünya klasörü seçme artık bu
pencerede DEĞİL, doğrudan InstancePage'in "Dünyalar" bölümünde (bkz.
instance_page.py:WorldSection) — burada tekrar bir "Dünya Klasörü Seç"
butonu göstermek kullanıcıyı "CurseForge'ta ara" ile "diskten yükle"
arasında hangi ekranda olduğu konusunda karıştırıyordu."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
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
from mcpack.i18n import t
from mcpack.models import ContentKind, Loader, Pack


def _searchable_content() -> list[tuple[ContentKind, str]]:
    # (kind, i18n anahtar öneki — bkz. i18n.py "content.<prefix>.*")
    return [
        (ContentKind.SHADERPACK, "content.shader"),
        (ContentKind.DATAPACK, "content.datapack"),
        (ContentKind.RESOURCEPACK, "content.resourcepack"),
    ]


class ModSearchDialog(QDialog):
    world_removed = Signal(str)  # ad (klasör adı) — bkz. _remove_selected_world
    content_removed = Signal(object, str)  # ContentKind, project_id

    def __init__(self, pack: Pack, parent=None, *, initial_kind: ContentKind | None = None) -> None:
        """initial_kind: InstancePage'in belirli bir bölümündeki "+ Ekle"
        butonuna tıklandığında pencere doğrudan o türün sekmesinde açılsın
        diye (ör. Shader bölümünden açılırsa Modlar'da değil Shader
        sekmesinde başlar) — verilmezse (ana araç çubuğundan açılış) ilk
        sekmede (Modlar, ya da vanilla'da ilk içerik türünde) başlar."""
        super().__init__(parent)
        self.pack = pack
        self._initial_kind = initial_kind
        self.is_vanilla = pack.loader == Loader.VANILLA
        title_prefix = t("modsearch.title_content") if self.is_vanilla else t("modsearch.title_mod")
        self.setWindowTitle(f"{title_prefix} — {pack.name}")
        self.resize(900, 680)

        self.content_menu = QListWidget()
        self.content_menu.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pages = QStackedWidget()

        self.search_panel: SearchPanel | None = None
        if not self.is_vanilla:
            self.content_menu.addItem(QListWidgetItem(t("modsearch.menu_mods")))
            self.search_panel = SearchPanel()
            self.pages.addWidget(self.search_panel)

        self.content_search_panels: dict[ContentKind, SearchPanel] = {}
        self._installed_content_lists: dict[ContentKind, QListWidget] = {}
        self._kind_rows: dict[ContentKind, int] = {}
        for kind, key_prefix in _searchable_content():
            self._kind_rows[kind] = self.content_menu.count()
            self.content_menu.addItem(QListWidgetItem(t(f"{key_prefix}.label")))
            self.pages.addWidget(self._make_content_page(kind, key_prefix))

        self._world_list = QListWidget()
        self._world_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._kind_rows[ContentKind.WORLD] = self.content_menu.count()
        self.content_menu.addItem(QListWidgetItem(t("modsearch.menu_world")))
        self.pages.addWidget(self._make_world_page())

        self.content_menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        initial_row = self._kind_rows.get(initial_kind, 0) if initial_kind is not None else 0
        self.content_menu.setCurrentRow(initial_row)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.content_menu, 0)
        layout.addWidget(self.pages, 1)

        self.refresh_content(pack)

    def _make_content_page(self, kind: ContentKind, key_prefix: str) -> QWidget:
        """Shader/datapack/görüntü paketi arama sekmesi — arama sonuçlarının
        altında, o türden zaten eklenmiş olanları gösteren ve kaldırmayı
        sağlayan bir liste var (dünya sekmesindeki aynı desen — daha önce
        PackManager.remove_content_download çağıracak hiçbir GUI kontrolü
        yoktu, tek yol pack JSON'unu elle düzenlemekti)."""
        page = QWidget()
        layout = QVBoxLayout(page)

        panel = SearchPanel(
            title=t(f"{key_prefix}.search_title"),
            query_placeholder=t(f"{key_prefix}.placeholder"),
            add_button_text=t(f"{key_prefix}.add_button"),
        )
        self.content_search_panels[kind] = panel
        layout.addWidget(panel, 1)

        layout.addWidget(QLabel(t(f"{key_prefix}.installed_label")))
        installed_list = QListWidget()
        installed_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        installed_list.setMaximumHeight(110)
        self._installed_content_lists[kind] = installed_list
        layout.addWidget(installed_list)

        remove_button = QPushButton(t(f"{key_prefix}.remove_button"))
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
        """Sadece CurseForge'ta arama — diskten yükleme artık burada değil
        (bkz. modül docstring'i). "Yüklü dünyalar" listesi burada hâlâ var
        ki bu pencere açıkken az önce indirilen bir dünya anında görülüp
        gerekirse kaldırılabilsin (diğer içerik sekmelerindeki "Eklenmiş
        X'ler" deseniyle tutarlı)."""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.world_search_panel = SearchPanel(
            title=t("modsearch.world_search_title"),
            query_placeholder=t("modsearch.world_placeholder"),
            add_button_text=t("modsearch.world_add_button"),
            curseforge_only=True,
        )
        layout.addWidget(self.world_search_panel, 1)

        layout.addWidget(QLabel(t("modsearch.world_installed_label")))
        layout.addWidget(self._world_list)
        self._world_list.setMaximumHeight(110)
        self._refresh_world_list()

        remove_button = QPushButton(t("modsearch.world_remove_button"))
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._remove_selected_world)
        layout.addWidget(remove_button)

        return page

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
