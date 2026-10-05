"""Pack detay sayfası (bir "instance"e girildiğinde açılan sayfa).

Prism Launcher'ın instance sayfasından ilham alındı: üstte pack başlığı +
eylemler, solda dikey bir bölüm listesi (Modlar / Shader / Görüntü Paketi /
Datapack / Dünya), sağda seçili bölümün içeriği. Önceden tek bir mod
tablosu + "Diğer İçerikler" adında tek bir karışık tabloya sıkıştırılmış
olan içerik burada kendi başına birer sayfaya ayrıldı (CurseForge App'te de
Resource Packs/Shader Packs kendi sekmeleridir)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.server_section import ServerSection
from mcpack.gui.theme import loader_color
from mcpack.gui.widgets import (
    _env_badge_widget,
    _environment_label,
    _mod_name_widget,
    _source_indicator_widget,
)
from mcpack.models import ContentKind, Loader, ModEntry, ModSourceType, Pack

_LOADER_ICONS = {
    "vanilla": "🌱",
    "fabric": "🧵",
    "quilt": "🧶",
    "forge": "🔨",
    "neoforge": "🔥",
}

_MOD_SORT_KEYS = {
    0: lambda m: (m.name or m.file_name).lower(),
    1: lambda m: m.source.value,
    2: lambda m: _environment_label(m.env.client.value, m.env.server.value),
}

_CONTENT_SECTIONS: list[tuple[ContentKind, str, str]] = [
    # (kind, rail etiketi, boş durum ikonu)
    (ContentKind.SHADERPACK, "✨ Shader Paketleri", "✨"),
    (ContentKind.RESOURCEPACK, "🖼 Görüntü Paketleri", "🖼"),
    (ContentKind.DATAPACK, "📦 Datapack'ler", "📦"),
]

_CHEAT_MOD_SOURCES = (ModSourceType.WURST, ModSourceType.METEOR)


def _regular_mods(pack: Pack) -> list[ModEntry]:
    """pack.mods'tan Wurst/Meteor gibi hile modlarını hariç tutar — onlar
    kendi ayrı bölümünde (bkz. CheatModsSection) gösterilir, "Modlar"
    tablosunda/sayımında TEKRAR görünmemeli (kullanıcı isteği: "ayrı bir
    bölümde sunulmalı")."""
    return [m for m in pack.mods if m.source not in _CHEAT_MOD_SOURCES]


def _style_badge(label: QLabel, icon: str, color_hex: str, *, size: int = 40) -> None:
    label.setText(icon)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text_color = "#1f2937" if QColor(color_hex).lightness() > 160 else "#ffffff"
    label.setStyleSheet(
        f"background-color: {color_hex}; color: {text_color}; border-radius: 8px; "
        f"font-size: {max(16, int(size * 0.55))}px;"
    )


def _empty_state(icon: str, title: str, sub: str, cta_text: str) -> tuple[QWidget, QPushButton]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(6)
    icon_label = QLabel(icon)
    icon_label.setStyleSheet("font-size: 36px;")
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(icon_label)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    sub_label = QLabel(sub)
    sub_label.setProperty("role", "muted")
    sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(sub_label)
    cta = QPushButton(cta_text)
    cta.setObjectName("primary")
    layout.addWidget(cta, alignment=Qt.AlignmentFlag.AlignCenter)
    return widget, cta


class ModsSection(QWidget):
    """Yüklü modların tablosu — arama, sütun başlığına tıklayarak sıralama,
    ekleme/çıkarma/env düzeltme. Vanilla pack'lerde (loader yok) tablo yerine
    bir uyarı gösterilir; shader/görüntü paketi/datapack/dünya bir loader
    gerektirmediği için onlar ayrı bölümlerde (bkz. ContentSection/WorldSection)
    her zaman erişilebilir kalır."""

    add_mod_clicked = Signal()
    remove_mod_requested = Signal(str)
    edit_env_requested = Signal(str)
    check_dependencies_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pack: Pack | None = None
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        options_row = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Yüklü modlarda ara...")
        self.filter_input.textChanged.connect(lambda _: self.show_pack(self._pack))
        options_row.addWidget(self.filter_input, 1)

        self.sort_hint = QLabel("Sıralamak için sütun başlığına tıkla ↓")
        self.sort_hint.setProperty("role", "muted")
        options_row.addWidget(self.sort_hint)

        self.show_file_names_checkbox = QCheckBox("Dosya adlarını göster")
        self.show_file_names_checkbox.toggled.connect(lambda _: self.show_pack(self._pack))
        options_row.addWidget(self.show_file_names_checkbox)
        outer.addLayout(options_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Mod", "Kaynak", "Ortam"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 220)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.table, 1)

        self.empty_state, empty_cta = _empty_state(
            "🧩", "Henüz mod eklenmemiş",
            "Modrinth ve CurseForge'ta arayıp bu pack'e mod ekleyebilirsin.",
            "+ Mod Ekle",
        )
        empty_cta.clicked.connect(self.add_mod_clicked.emit)
        outer.addWidget(self.empty_state, 1)

        self.vanilla_notice = QLabel(
            "⚠ Vanilla pack'lerde mod eklenemez — mod eklemek için bir loader "
            "(Fabric/Quilt/Forge/NeoForge) seçerek yeni bir pack oluşturun."
        )
        self.vanilla_notice.setObjectName("warningBox")
        self.vanilla_notice.setWordWrap(True)
        self.vanilla_notice.hide()
        outer.addWidget(self.vanilla_notice)

        self.filter_empty_notice = QLabel("")
        self.filter_empty_notice.setProperty("role", "muted")
        self.filter_empty_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filter_empty_notice.hide()
        outer.addWidget(self.filter_empty_notice)

        self.actions_bar = QWidget()
        button_row = QHBoxLayout(self.actions_bar)
        button_row.setContentsMargins(0, 8, 0, 0)
        add_button = QPushButton("+ Mod Ekle")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self.add_mod_clicked.emit)
        button_row.addWidget(add_button)

        remove_button = QPushButton("Seçili Modu Çıkar")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)

        env_button = QPushButton("İstemci/Sunucu Düzelt")
        env_button.clicked.connect(self._on_edit_env_clicked)
        button_row.addWidget(env_button)

        check_deps_button = QPushButton("Bağımlılıkları Kontrol Et")
        check_deps_button.clicked.connect(self.check_dependencies_clicked.emit)
        button_row.addWidget(check_deps_button)
        button_row.addStretch()
        outer.addWidget(self.actions_bar)

    def _visible_mods(self, pack: Pack) -> list[ModEntry]:
        mods = _regular_mods(pack)
        query = self.filter_input.text().strip().lower()
        if query:
            mods = [m for m in mods if query in (m.name or "").lower() or query in m.file_name.lower()]
        if self._sort_column >= 0:
            key_func = _MOD_SORT_KEYS[self._sort_column]
            mods.sort(key=key_func, reverse=self._sort_order == Qt.SortOrder.DescendingOrder)
        return mods

    def _on_header_clicked(self, column: int) -> None:
        if column not in _MOD_SORT_KEYS:
            return
        if self._sort_column == column:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(self._sort_column, self._sort_order)
        self.show_pack(self._pack)

    def show_pack(self, pack: Pack | None) -> None:
        self._pack = pack
        if pack is None:
            self.table.hide()
            self.empty_state.hide()
            self.vanilla_notice.hide()
            self.filter_empty_notice.hide()
            self.actions_bar.hide()
            return

        is_vanilla = pack.loader.value == "vanilla"
        show_controls = not is_vanilla and bool(_regular_mods(pack))
        self.actions_bar.setVisible(show_controls)
        self.filter_input.setVisible(show_controls)
        self.sort_hint.setVisible(show_controls)
        self.show_file_names_checkbox.setVisible(show_controls)
        self.vanilla_notice.setVisible(is_vanilla)

        if is_vanilla:
            self.table.hide()
            self.empty_state.hide()
            self.filter_empty_notice.hide()
            return

        if not _regular_mods(pack):
            self.table.hide()
            self.filter_empty_notice.hide()
            self.empty_state.show()
            return
        self.empty_state.hide()

        show_file_names = self.show_file_names_checkbox.isChecked()
        visible_mods = self._visible_mods(pack)
        if not visible_mods:
            query = self.filter_input.text().strip()
            self.table.hide()
            self.filter_empty_notice.setText(f'"{query}" ile eşleşen mod bulunamadı.')
            self.filter_empty_notice.show()
            return
        self.filter_empty_notice.hide()
        self.table.show()

        self.table.setRowCount(len(visible_mods))
        for row, mod in enumerate(visible_mods):
            name_item = QTableWidgetItem("")
            name_item.setData(Qt.ItemDataRole.UserRole, mod.project_id)
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(row, 0, _mod_name_widget(mod, show_file_names))

            source_item = QTableWidgetItem("")
            self.table.setItem(row, 1, source_item)
            self.table.setCellWidget(row, 1, _source_indicator_widget(mod.source.value))

            self.table.setCellWidget(row, 2, _env_badge_widget(mod.env.client.value, mod.env.server.value))
        self.table.resizeRowsToContents()

    def _on_remove_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.remove_mod_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _on_edit_env_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.edit_env_requested.emit(item.data(Qt.ItemDataRole.UserRole))


class ContentSection(QWidget):
    """Shader/görüntü paketi/datapack — üçü de Modrinth/CurseForge'ta aranıp
    eklenir (bkz. PackManager.add_content_download), export sırasında
    indirilir. Loader gerektirmediği için vanilla pack'lerde de aktiftir."""

    add_requested = Signal()
    remove_requested = Signal(str)  # project_id

    def __init__(self, kind: ContentKind, label: str, icon: str) -> None:
        super().__init__()
        self.kind = kind
        self._label = label.split(" ", 1)[-1]  # rail ikonu olmadan düz ad

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Ad", "Kaynak"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.table, 1)

        self.empty_state, empty_cta = _empty_state(
            icon, f"Henüz {self._label.lower()} eklenmemiş",
            "Bir loader gerektirmez, vanilla pack'lere de eklenebilir.",
            f"+ {self._label} Ekle",
        )
        empty_cta.clicked.connect(self.add_requested.emit)
        outer.addWidget(self.empty_state, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 8, 0, 0)
        add_button = QPushButton(f"+ {self._label} Ekle")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self.add_requested.emit)
        button_row.addWidget(add_button)

        remove_button = QPushButton("Seçiliyi Kaldır")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        self.button_row_widget = QWidget()
        self.button_row_widget.setLayout(button_row)
        outer.addWidget(self.button_row_widget)

    def show_pack(self, pack: Pack | None) -> None:
        entries = pack.content_downloads_of(self.kind) if pack is not None else []
        has_entries = bool(entries)
        self.table.setVisible(has_entries)
        self.empty_state.setVisible(not has_entries)
        self.button_row_widget.setVisible(has_entries)

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            name_item = QTableWidgetItem(entry.name or entry.file_name)
            name_item.setData(Qt.ItemDataRole.UserRole, entry.project_id)
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(row, 1, _source_indicator_widget(entry.source.value))
        self.table.resizeRowsToContents()

    def _on_remove_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.remove_requested.emit(item.data(Qt.ItemDataRole.UserRole))


class WorldSection(QWidget):
    """Dünya — indirilebilir bir Modrinth proje türü olmadığı için ya
    diskten seçilir ya da (sadece CurseForge'ta bir proje türü olarak var
    olduğu için) CurseForge'ta aranıp indirilir; ikisi de aynı listeye
    düşer (bkz. PackManager.add_content / add_world_from_download)."""

    add_local_requested = Signal()
    add_online_requested = Signal()
    remove_requested = Signal(str)  # dünya adı

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Dünya", "Kaynak"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.table, 1)

        self.empty_state, empty_cta = _empty_state(
            "🌍", "Henüz dünya yüklenmemiş",
            "Diskinden bir dünya klasörü seçebilir ya da CurseForge'ta hazır bir harita arayabilirsin.",
            "+ Dünya Klasörü Seç",
        )
        empty_cta.clicked.connect(self.add_local_requested.emit)
        # _empty_state tek bir CTA için tasarlandı ama dünyada iki farklı
        # ekleme yolu var (yerel/online) — ikinci buton olmadan pack'te hiç
        # dünya yokken kullanıcı "CurseForge'ta Ara"yı hiç göremiyordu (alt
        # buton satırı da has_entries=False iken gizli — bkz. show_pack),
        # sadece bir dünya ekledikten SONRA ortaya çıkıyordu.
        empty_online_cta = QPushButton("+ CurseForge'ta Dünya Ara")
        empty_online_cta.clicked.connect(self.add_online_requested.emit)
        self.empty_state.layout().addWidget(empty_online_cta, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.empty_state, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 8, 0, 0)
        add_local_button = QPushButton("+ Dünya Klasörü Seç")
        add_local_button.setObjectName("primary")
        add_local_button.clicked.connect(self.add_local_requested.emit)
        button_row.addWidget(add_local_button)

        add_online_button = QPushButton("+ CurseForge'ta Ara")
        add_online_button.clicked.connect(self.add_online_requested.emit)
        button_row.addWidget(add_online_button)

        remove_button = QPushButton("Seçili Dünyayı Kaldır")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        self.button_row_widget = QWidget()
        self.button_row_widget.setLayout(button_row)
        outer.addWidget(self.button_row_widget)

    def show_pack(self, pack: Pack | None) -> None:
        entries = pack.content_of(ContentKind.WORLD) if pack is not None else []
        has_entries = bool(entries)
        self.table.setVisible(has_entries)
        self.empty_state.setVisible(not has_entries)
        self.button_row_widget.setVisible(has_entries)

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            name_item = QTableWidgetItem(entry.name)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem("Yerel (diskten)"))
        self.table.resizeRowsToContents()

    def _on_remove_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.remove_requested.emit(item.text())


_CHEAT_MOD_DISCLAIMER = (
    "Wurst Client ve Meteor Client birer \"hile\" (cheat/utility) istemcisidir.\n\n"
    "• Bu modların kullanımı çoğu sunucunun kurallarına aykırıdır ve hesabınızın/"
    "karakterinizin o sunucudan banlanmasına yol açabilir.\n"
    "• Sadece izin verilen sunucularda ya da tek kişilik (singleplayer) "
    "dünyalarda, kendi sorumluluğunuzda kullanın.\n"
    "• MC Pack Manager ve geliştiricisi bu modların kullanımından doğacak "
    "hiçbir sonuçtan sorumlu değildir.\n\n"
    "Devam ederek bu şartları kabul etmiş olursunuz. İndirmek istiyor musunuz?"
)


class CheatModsSection(QWidget):
    """Wurst Client / Meteor Client — CurseForge/Modrinth'in platform
    kurallarına aykırı bularak barındırmadığı hile istemcileri, kendi resmi
    API'lerinden indirilir (bkz. sources/cheat_mods.py). SADECE Fabric
    pack'lerinde gösterilir (bkz. InstancePage.show_pack) çünkü ikisi de
    Fabric-only mod. Her indirmeden önce açık bir sorumluluk reddi + onay
    istenir — kullanıcı isteği: net uyarı metinleri, onaysız indirme yok."""

    add_requested = Signal(str)  # "wurst" | "meteor"
    remove_requested = Signal(str)  # project_id ("wurst"/"meteor")

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        warning = QLabel(
            "⚠ Bu bölüm hile istemcileri içerir. Sunucu kurallarını ihlal edip "
            "ban ile sonuçlanabilir — sorumluluk size aittir. Detaylar için "
            "eklerken çıkacak onay penceresini okuyun."
        )
        warning.setObjectName("warningBox")
        warning.setWordWrap(True)
        outer.addWidget(warning)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Mod", "Kaynak"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.table, 1)

        self.empty_state, _unused_cta = _empty_state(
            "🎯", "Henüz hile modu eklenmemiş",
            "Aşağıdaki butonlarla, onay vererek Wurst ya da Meteor Client ekleyebilirsiniz.",
            "",
        )
        _unused_cta.hide()  # tek CTA yeterli değil (iki ayrı mod) — alttaki buton satırı kullanılıyor
        outer.addWidget(self.empty_state, 1)

        button_row = QHBoxLayout()
        wurst_button = QPushButton("+ Wurst Client Ekle")
        wurst_button.clicked.connect(lambda: self._confirm_and_request("wurst"))
        button_row.addWidget(wurst_button)

        meteor_button = QPushButton("+ Meteor Client Ekle")
        meteor_button.clicked.connect(lambda: self._confirm_and_request("meteor"))
        button_row.addWidget(meteor_button)

        remove_button = QPushButton("Seçiliyi Kaldır")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        outer.addLayout(button_row)

    def _confirm_and_request(self, kind: str) -> None:
        answer = QMessageBox.warning(
            self, "Sorumluluk Reddi ve Onay", _CHEAT_MOD_DISCLAIMER,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.add_requested.emit(kind)

    def show_pack(self, pack: Pack | None) -> None:
        entries = [m for m in pack.mods if m.source in (ModSourceType.WURST, ModSourceType.METEOR)] if pack else []
        has_entries = bool(entries)
        self.table.setVisible(has_entries)
        self.empty_state.setVisible(not has_entries)

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            name_item = QTableWidgetItem(entry.name or entry.file_name)
            name_item.setData(Qt.ItemDataRole.UserRole, entry.project_id)
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(row, 1, _source_indicator_widget(entry.source.value))
        self.table.resizeRowsToContents()

    def _on_remove_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.remove_requested.emit(item.data(Qt.ItemDataRole.UserRole))


class InstancePage(QWidget):
    """Prism tarzı instance sayfası: üst başlık + eylemler, solda dikey
    bölüm listesi, sağda seçili bölümün içeriği."""

    back_requested = Signal()
    export_requested = Signal(str)
    server_pack_requested = Signal()
    run_sklauncher_requested = Signal()
    fork_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pack: Pack | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        back_button = QPushButton("← Kütüphane")
        back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(back_button)

        self.icon_badge = QLabel()
        _style_badge(self.icon_badge, "❓", "#6b7280")
        header.addWidget(self.icon_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("Pack seçilmedi")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        title_col.addWidget(self.title_label)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setProperty("role", "muted")
        title_col.addWidget(self.subtitle_label)
        header.addLayout(title_col)
        header.addStretch()

        self.format_combo = QComboBox()
        self.format_combo.addItem("Modrinth (.mrpack)", "mrpack")
        self.format_combo.addItem("CurseForge (.zip)", "curseforge")
        self.format_combo.addItem("Prism / MultiMC (.zip)", "prism")
        header.addWidget(self.format_combo)

        export_button = QPushButton("Dışa Aktar")
        export_button.setObjectName("primary")
        export_button.clicked.connect(lambda: self.export_requested.emit(self.format_combo.currentData()))
        header.addWidget(export_button)

        server_button = QPushButton("Sunucu Paketi")
        server_button.clicked.connect(self.server_pack_requested.emit)
        header.addWidget(server_button)

        sklauncher_button = QPushButton("SKLauncher ile Çalıştır")
        sklauncher_button.clicked.connect(self.run_sklauncher_requested.emit)
        header.addWidget(sklauncher_button)

        fork_button = QPushButton("Başka Sürüme Uyarla")
        fork_button.setToolTip("Bu pack'i farklı bir Minecraft versiyonu için kopyala (fork)")
        fork_button.clicked.connect(self.fork_requested.emit)
        header.addWidget(fork_button)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        outer.addLayout(body, 1)

        self.rail = QListWidget()
        self.rail.setFixedWidth(190)
        self.rail.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rail.setSpacing(2)
        body.addWidget(self.rail)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self.rail.addItem(QListWidgetItem("🧩 Modlar"))
        self.mods_section = ModsSection()
        self.stack.addWidget(self.mods_section)

        self.content_sections: dict[ContentKind, ContentSection] = {}
        for kind, label, icon in _CONTENT_SECTIONS:
            self.rail.addItem(QListWidgetItem(label))
            section = ContentSection(kind, label, icon)
            self.content_sections[kind] = section
            self.stack.addWidget(section)

        self.rail.addItem(QListWidgetItem("🌍 Dünyalar"))
        self.world_section = WorldSection()
        self.stack.addWidget(self.world_section)

        self.rail.addItem(QListWidgetItem("🖥 Sunucu"))
        self.server_section = ServerSection()
        self.stack.addWidget(self.server_section)

        # Cheat Modları: stack widget'ı HER ZAMAN burada (sabit son index),
        # ama rail satırı sadece Fabric pack'lerinde eklenir (bkz. show_pack)
        # — bu sayede rail satır index'i ile stack index'i arasındaki 1:1
        # eşleşme (currentRowChanged -> setCurrentIndex) hep korunur.
        self.cheat_mods_section = CheatModsSection()
        self.stack.addWidget(self.cheat_mods_section)
        self._cheat_rail_item: QListWidgetItem | None = None

        self.rail.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.rail.setCurrentRow(0)

    def section_index(self, kind: ContentKind) -> int:
        """ModSearchDialog'u doğru sekmede açmak için (bkz. main_window.py)."""
        if kind == ContentKind.WORLD:
            return self.stack.indexOf(self.world_section)
        return self.stack.indexOf(self.content_sections[kind])

    def show_pack(self, pack: Pack | None) -> None:
        self._pack = pack
        self.mods_section.show_pack(pack)
        for section in self.content_sections.values():
            section.show_pack(pack)
        self.world_section.show_pack(pack)
        self.server_section.show_pack(pack)
        self.cheat_mods_section.show_pack(pack)

        if pack is None:
            self.title_label.setText("Pack seçilmedi")
            self.subtitle_label.setText("")
            if self._cheat_rail_item is not None:
                self.rail.takeItem(self.rail.row(self._cheat_rail_item))
                self._cheat_rail_item = None
            return

        is_vanilla = pack.loader.value == "vanilla"
        loader_label = "Vanilla" if is_vanilla else pack.loader.value.capitalize()
        loader_version = f" {pack.loader_version}" if pack.loader_version else ""
        self.title_label.setText(pack.name)
        self.subtitle_label.setText(
            f"{loader_label}{loader_version}  ·  MC {pack.minecraft}  ·  {len(_regular_mods(pack))} mod"
        )
        icon = _LOADER_ICONS.get(pack.loader.value, "❓")
        _style_badge(self.icon_badge, icon, loader_color(pack.loader.value))

        rail_labels = ["🧩 Modlar"] + [label for _, label, _ in _CONTENT_SECTIONS] + ["🌍 Dünyalar"]
        counts = (
            [len(_regular_mods(pack))]
            + [len(pack.content_downloads_of(kind)) for kind, _, _ in _CONTENT_SECTIONS]
            + [len(pack.content_of(ContentKind.WORLD))]
        )
        for row, (label, count) in enumerate(zip(rail_labels, counts)):
            text = f"{label} ({count})" if count else label
            self.rail.item(row).setText(text)

        # Cheat Modları bölümü SADECE Fabric pack'lerinde gösterilir (Wurst/
        # Meteor Fabric-only mod) — rail'in EN SONUNA eklenir/kaldırılır ki
        # stack widget index'i (her zaman sabit, __init__'te en sona eklendi)
        # ile rail satır index'i arasındaki 1:1 eşleşme bozulmasın.
        is_fabric = pack.loader == Loader.FABRIC
        has_cheat_row = self._cheat_rail_item is not None
        if is_fabric and not has_cheat_row:
            self._cheat_rail_item = QListWidgetItem("🎯 Cheat Modları")
            self.rail.addItem(self._cheat_rail_item)
        elif not is_fabric and has_cheat_row:
            row = self.rail.row(self._cheat_rail_item)
            self.rail.takeItem(row)
            self._cheat_rail_item = None

        if self._cheat_rail_item is not None:
            cheat_count = sum(1 for m in pack.mods if m.source in _CHEAT_MOD_SOURCES)
            text = f"🎯 Cheat Modları ({cheat_count})" if cheat_count else "🎯 Cheat Modları"
            self._cheat_rail_item.setText(text)
