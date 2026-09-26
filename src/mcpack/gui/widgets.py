"""GUI panelleri: pack listesi, pack detayı, mod arama, export/aksiyon paneli.

proje-amacı.md §2.6'daki 3 panelli düzen (sol: pack listesi, orta: pack
içeriği, sağ/alt: arama+export+server+launcher) burada uygulanır.
"""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.icon_loader import load_icon
from mcpack.gui.theme import (
    apply_card_shadow,
    chip_colors,
    icon_placeholder_bg,
    loader_color,
    pack_card_background,
    pack_card_stripe,
    pack_text_colors,
    source_color,
    status_good_color,
)
from mcpack.models import ModEntry, ModSourceType, Pack
from mcpack.sources.base import SearchResult

# ---------------------------------------------------------------------------
# Async yardımcı: coroutine'leri ayrı QThread'de çalıştırıp GUI'yi dondurmaz.
# ---------------------------------------------------------------------------


class _WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)


class _AsyncWorker(QThread):
    def __init__(self, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        super().__init__()
        self._coro_factory = coro_factory
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = asyncio.run(self._coro_factory())
        except Exception as exc:  # GUI'de göstermek için genel yakalama
            self.signals.error.emit(f"{exc}\n{traceback.format_exc()}")
        else:
            self.signals.result.emit(result)


_active_workers: list[_AsyncWorker] = []


def run_async(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    worker = _AsyncWorker(coro_factory)
    _active_workers.append(worker)

    def _cleanup() -> None:
        if worker in _active_workers:
            _active_workers.remove(worker)

    if on_success:
        worker.signals.result.connect(on_success)
    if on_error:
        worker.signals.error.connect(on_error)
    worker.finished.connect(_cleanup)
    worker.start()


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------


def _panel_group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    """Her paneli çerçeveli/başlıklı bir kutuya alır — düz üst üste widget
    yığını yerine gerçek bir uygulama görünümü verir (referans tasarımdaki
    gibi hafif bir yükselti/gölge ile)."""
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setSpacing(8)
    apply_card_shadow(box)
    return box, layout


def format_downloads(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


_SOURCE_LABELS = {"modrinth": "Modrinth", "curseforge": "CurseForge"}


def _mod_name_widget(mod: ModEntry, show_file_name: bool) -> QWidget:
    """Varsayılan olarak modun kullanıcı dostu adını gösterir (mod.name);
    yoksa (eski kayıtlar / detay alınamamış modlar için) dosya adına düşer.
    Kullanıcı "Dosya adlarını göster" işaretlerse, ad altına küçük/soluk
    şekilde gerçek dosya adı da eklenir."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)
    layout.setSpacing(0)

    display_name = mod.name or mod.file_name
    name_label = QLabel(display_name)
    layout.addWidget(name_label)

    if show_file_name and mod.name:
        file_label = QLabel(mod.file_name)
        file_label.setProperty("role", "muted")
        file_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(file_label)

    return container


def _environment_label(client: str, server: str) -> str:
    """Tek, birleşik ortam etiketi: sadece istemci ya da sadece sunucu ile
    çalışabiliyorsa ayrı ayrı gösterilir; ikisiyle de çalışıyorsa (client
    ve server ikisi de unsupported değilse) tek bir "İstemci + Sunucu"
    etiketi yeterli — ayrı ayrı üç rozet göstermek yerine."""
    client_ok = client != "unsupported"
    server_ok = server != "unsupported"
    if client_ok and server_ok:
        return "İstemci + Sunucu"
    if client_ok:
        return "İstemci"
    if server_ok:
        return "Sunucu"
    return "Bilinmiyor"


def _env_badge_widget(client: str, server: str) -> QWidget:
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)

    text = _environment_label(client, server)
    chip = QLabel(text)
    if text == "Bilinmiyor":
        chip.setProperty("role", "muted")
    else:
        chip_bg, chip_text = chip_colors()
        chip.setStyleSheet(
            f"background-color: {chip_bg}; color: {chip_text}; border-radius: 4px; "
            "padding: 2px 8px; font-size: 11px;"
        )
    layout.addWidget(chip)
    layout.addStretch()
    return container


def _source_indicator_widget(source_value: str) -> QWidget:
    """Kimliği (Modrinth/CurseForge) renkli METİNLE değil, yanındaki küçük
    bir noktayla taşır — metin her zaman okunabilir mürekkep rengini kullanır
    (dataviz skill kuralı: "text wears text tokens, never the series color";
    ayrıca bazı kategori renkleri beyaz zeminde tek başına metin olarak
    3:1 kontrastın altında kalıyor, nokta+etiket bu sorunu da çözer)."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)
    layout.setSpacing(6)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background-color: {source_color(source_value)}; border-radius: 4px;")
    layout.addWidget(dot)

    label = QLabel(_SOURCE_LABELS.get(source_value, source_value))
    layout.addWidget(label)
    layout.addStretch()
    return container


def _badge_label(text: str, color_hex: str, *, size: int = 36) -> QLabel:
    """Prism/CurseForge tarzı köşeli renkli rozet — loader emoji ikonu için
    (gerçek bir görsel ikon paketi olmadan, network'ten çekilemeyen pack'ler
    için de hızlı görsel kimlik sağlar)."""
    badge = QLabel(text)
    badge.setFixedSize(size, size)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text_color = "#1f2937" if QColor(color_hex).lightness() > 160 else "#ffffff"
    badge.setStyleSheet(
        f"background-color: {color_hex}; color: {text_color}; border-radius: 8px; "
        f"font-size: {max(16, int(size * 0.55))}px;"
    )
    return badge


def _icon_label(size: int = 40) -> QLabel:
    """Uzak sunucudan async yüklenecek bir mod ikonu için placeholder etiket."""
    label = QLabel()
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(f"background-color: {icon_placeholder_bg()}; border-radius: 8px;")
    return label


def _set_scaled_pixmap(label: QLabel, pixmap: QPixmap) -> None:
    size = label.width()
    scaled = pixmap.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    label.setPixmap(scaled)


# ---------------------------------------------------------------------------
# Sol panel: pack listesi (CurseForge/Prism'deki "instance kartı" ilhamı)
# ---------------------------------------------------------------------------


_LOADER_ICONS = {
    "vanilla": "🌱",
    "fabric": "🧵",
    "quilt": "🧶",
    "forge": "🔨",
    "neoforge": "🔥",
}


class _PackCard(QWidget):
    def __init__(self, pack: Pack) -> None:
        super().__init__()
        self.setStyleSheet("QLabel { background-color: transparent; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        self._name_label: QLabel
        self._subtitle_label: QLabel

        loader_label = "Vanilla" if pack.loader.value == "vanilla" else pack.loader.value.capitalize()
        icon = _LOADER_ICONS.get(pack.loader.value, "❓")
        badge = _badge_label(icon, loader_color(pack.loader.value))
        layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_label = QLabel(pack.name)
        self._name_label = name_label
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_label.setStyleSheet(
            "background: transparent; selection-background-color: transparent; "
            "font-weight: 600; font-size: 13px;"
        )
        text_col.addWidget(name_label)

        subtitle = QLabel(f"{loader_label} · MC {pack.minecraft} · {len(pack.mods)} mod")
        self._subtitle_label = subtitle
        subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        subtitle.setProperty("role", "muted")
        subtitle.setStyleSheet(
            "background: transparent; selection-background-color: transparent; "
            "font-size: 12px;"
        )
        text_col.addWidget(subtitle)

        layout.addLayout(text_col, 1)

    def set_selected(self, selected: bool) -> None:
        name_color, subtitle_color = pack_text_colors(selected)
        self.setStyleSheet(
            f"background-color: {pack_card_background(selected)}; "
            f"border-left: 3px solid {pack_card_stripe(selected)}; "
            "QLabel { background-color: transparent; }"
        )
        self._name_label.setStyleSheet(
            f"color: {name_color}; font-weight: 600; font-size: 13px;"
        )
        self._subtitle_label.setStyleSheet(
            f"background: transparent; selection-background-color: transparent; "
            f"color: {subtitle_color}; font-size: 12px;"
        )


class PackListPanel(QWidget):
    pack_selected = Signal(str)
    new_pack_requested = Signal()
    delete_pack_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._packs: list[Pack] = []
        self._cards: list[_PackCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group("Pack'ler")
        outer.addWidget(group)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSpacing(2)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

        new_button = QPushButton("+ Yeni Pack")
        new_button.setObjectName("primary")
        new_button.clicked.connect(self.new_pack_requested.emit)
        layout.addWidget(new_button)

        delete_button = QPushButton("Seçili Pack'i Sil")
        delete_button.setObjectName("danger")
        delete_button.clicked.connect(self._delete_selected)
        layout.addWidget(delete_button)

    def set_packs(self, packs: list[Pack]) -> None:
        self._packs = packs
        self._cards = []
        self.list_widget.clear()
        for pack in packs:
            item = QListWidgetItem()
            card = _PackCard(pack)
            self._cards.append(card)
            item.setSizeHint(card.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, card)
        self._update_card_selection(self.list_widget.currentRow())

    def _on_row_changed(self, row: int) -> None:
        self._update_card_selection(row)
        if 0 <= row < len(self._packs):
            self.pack_selected.emit(self._packs[row].id)

    def _update_card_selection(self, row: int) -> None:
        for index, card in enumerate(self._cards):
            card.set_selected(index == row)

    def _delete_selected(self) -> None:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self._packs):
            self.delete_pack_requested.emit(self._packs[row].id)


# ---------------------------------------------------------------------------
# Ana içerik alanı: seçili pack'in başlığı + eylem araç çubuğu + mod tablosu.
#
# CurseForge App / Prism Launcher'da mod ekleme kalıcı bir yan panel değil,
# ayrı bir "gözat" akışıdır (bkz. gui/mod_search_dialog.py); export/server/
# SKLauncher gibi eylemler de başlığın yanında kompakt bir araç çubuğunda
# durur — bu yüzden burada artık tek bir kutuya sıkışmış 4 panel yok.
# ---------------------------------------------------------------------------

_MOD_SORT_KEYS: dict[int, Callable[[ModEntry], str]] = {
    0: lambda m: (m.name or m.file_name).lower(),  # Mod
    1: lambda m: m.source.value,  # Kaynak
    2: lambda m: _environment_label(m.env.client.value, m.env.server.value),  # Ortam
}


class PackDetailPanel(QWidget):
    remove_mod_requested = Signal(str)
    edit_env_requested = Signal(str)
    """CurseForge gibi kaynaklarda client/server bilgisi güvenilir olmayabilir;
    kullanıcı bu sinyalle seçili modun env'ini elle düzeltebilir (proje-amacı.md §6)."""
    add_mod_clicked = Signal()
    export_requested = Signal(str)  # format key: mrpack/curseforge/prism
    server_pack_requested = Signal()
    run_sklauncher_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._current_pack: Pack | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("Pack seçilmedi")
        self.title_label.setStyleSheet("font-size: 19px; font-weight: 700;")
        title_col.addWidget(self.title_label)

        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(8)
        self.subtitle_label = QLabel("Soldan bir pack seçin ya da yeni oluşturun.")
        self.subtitle_label.setProperty("role", "muted")
        subtitle_row.addWidget(self.subtitle_label)
        self.mod_count_badge = QLabel("")
        self.mod_count_badge.hide()
        subtitle_row.addWidget(self.mod_count_badge)
        subtitle_row.addStretch()
        title_col.addLayout(subtitle_row)

        header.addLayout(title_col)
        header.addStretch()

        self.format_combo = QComboBox()
        self.format_combo.addItem("Modrinth (.mrpack)", "mrpack")
        self.format_combo.addItem("CurseForge (.zip)", "curseforge")
        self.format_combo.addItem("Prism / MultiMC (.zip)", "prism")
        header.addWidget(self.format_combo)

        export_button = QPushButton("Dışa Aktar")
        export_button.setObjectName("primary")
        export_button.clicked.connect(
            lambda: self.export_requested.emit(self.format_combo.currentData())
        )
        header.addWidget(export_button)

        server_button = QPushButton("Sunucu Paketi")
        server_button.clicked.connect(self.server_pack_requested.emit)
        header.addWidget(server_button)

        sklauncher_button = QPushButton("SKLauncher ile Çalıştır")
        sklauncher_button.clicked.connect(self.run_sklauncher_requested.emit)
        header.addWidget(sklauncher_button)

        outer.addLayout(header)

        table_options_row = QHBoxLayout()
        self.mod_filter_input = QLineEdit()
        self.mod_filter_input.setPlaceholderText("Yüklü modlarda ara...")
        self.mod_filter_input.textChanged.connect(self._on_filter_or_sort_changed)
        table_options_row.addWidget(self.mod_filter_input, 1)

        self.sort_hint = QLabel("Sıralamak için sütun başlığına tıkla ↓")
        self.sort_hint.setProperty("role", "muted")
        table_options_row.addWidget(self.sort_hint)

        self.show_file_names_checkbox = QCheckBox("Dosya adlarını göster")
        self.show_file_names_checkbox.toggled.connect(self._on_show_file_names_toggled)
        table_options_row.addWidget(self.show_file_names_checkbox)
        outer.addLayout(table_options_row)

        # Sıralama: ayrı bir kutu yerine "Mod / Kaynak / Ortam" başlıklarına
        # tıklanarak yapılır (kullanıcı isteği) — QTableWidget'ın kendi
        # setSortingEnabled'ı cellWidget'ları satırla birlikte taşımadığı
        # için (bilinen Qt sınırlaması), sıralamayı kendimiz uyguluyoruz.
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

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

        # Boş durum: pack'te hiç mod yoksa boş bir tablo göstermek yerine
        # "Mod Ekle" eylem çağrısı içeren bir kart gösterilir.
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)
        empty_icon = QLabel("📦")
        empty_icon.setStyleSheet("font-size: 36px;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_title = QLabel("Henüz mod eklenmemiş")
        empty_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_sub = QLabel("Modrinth ve CurseForge'ta arayıp bu pack'e mod ekleyebilirsin.")
        empty_sub.setProperty("role", "muted")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_sub)
        empty_cta = QPushButton("+ Mod Ekle")
        empty_cta.setObjectName("primary")
        empty_cta.clicked.connect(self.add_mod_clicked.emit)
        empty_layout.addWidget(empty_cta, alignment=Qt.AlignmentFlag.AlignCenter)
        self.empty_state.hide()
        outer.addWidget(self.empty_state, 1)

        # Arama/filtre hiçbir moda uymazsa (pack boş değil ama sonuç boş).
        self.filter_empty_notice = QLabel("")
        self.filter_empty_notice.setProperty("role", "muted")
        self.filter_empty_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filter_empty_notice.hide()
        outer.addWidget(self.filter_empty_notice)

        self.mod_actions_bar = QWidget()
        button_row = QHBoxLayout(self.mod_actions_bar)
        button_row.setContentsMargins(0, 0, 0, 0)
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
        button_row.addStretch()
        outer.addWidget(self.mod_actions_bar)

        self.vanilla_notice = QLabel(
            "⚠ Vanilla pack'lerde mod eklenemez — mod eklemek için bir loader (Fabric/Quilt/Forge/NeoForge) seçin.\n"
            "Shader, dünya, datapack ve görüntü paketi bir loader gerektirmez, aşağıdan eklenebilir."
        )
        self.vanilla_notice.setObjectName("warningBox")
        self.vanilla_notice.setWordWrap(True)
        self.vanilla_notice.hide()
        outer.addWidget(self.vanilla_notice)

        # Vanilla pack'lerde "+ Mod Ekle" (mod_actions_bar) gizli olduğu için
        # aynı pencereyi (Mod Ekle diyaloğu, artık shader/dünya/datapack/
        # görüntü paketi sekmelerini de içeriyor) açacak ayrı bir giriş noktası.
        self.vanilla_content_bar = QWidget()
        vanilla_content_layout = QHBoxLayout(self.vanilla_content_bar)
        vanilla_content_layout.setContentsMargins(0, 0, 0, 0)
        vanilla_content_button = QPushButton("+ Shader / Dünya / Datapack / Görüntü Paketi")
        vanilla_content_button.setObjectName("primary")
        vanilla_content_button.clicked.connect(self.add_mod_clicked.emit)
        vanilla_content_layout.addWidget(vanilla_content_button)
        vanilla_content_layout.addStretch()
        self.vanilla_content_bar.hide()
        outer.addWidget(self.vanilla_content_bar)
        outer.addStretch()  # uyarı kutusu dikey boşluğu doldurup dev bir bloğa dönüşmesin

    def _visible_mods(self, pack: Pack) -> list[ModEntry]:
        mods = list(pack.mods)

        query = self.mod_filter_input.text().strip().lower()
        if query:
            mods = [m for m in mods if query in (m.name or "").lower() or query in m.file_name.lower()]

        if self._sort_column >= 0:
            key_func = _MOD_SORT_KEYS[self._sort_column]
            mods.sort(key=key_func, reverse=self._sort_order == Qt.SortOrder.DescendingOrder)
        # _sort_column == -1 -> pack.mods sırası (eklenme sırası) korunur

        return mods

    def _on_filter_or_sort_changed(self, *_args) -> None:
        self.show_pack(self._current_pack)

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
        self.show_pack(self._current_pack)

    def show_pack(self, pack: Pack | None) -> None:
        self._current_pack = pack
        if pack is None:
            self.title_label.setText("Pack seçilmedi")
            self.subtitle_label.setText("Soldan bir pack seçin ya da yeni oluşturun.")
            self.mod_count_badge.hide()
            self.table.setRowCount(0)
            self.table.hide()
            self.empty_state.hide()
            self.filter_empty_notice.hide()
            self.mod_actions_bar.hide()
            self.mod_filter_input.hide()
            self.sort_hint.hide()
            self.show_file_names_checkbox.hide()
            self.vanilla_notice.hide()
            self.vanilla_content_bar.hide()
            return

        is_vanilla = pack.loader.value == "vanilla"
        loader_label = "Vanilla" if is_vanilla else pack.loader.value.capitalize()
        loader_version = f" {pack.loader_version}" if pack.loader_version else ""
        self.title_label.setText(pack.name)
        self.subtitle_label.setText(f"{loader_label}{loader_version}  ·  MC {pack.minecraft}")

        chip_bg, chip_text = chip_colors()
        self.mod_count_badge.setText(f"{len(pack.mods)} mod")
        self.mod_count_badge.setStyleSheet(
            f"background-color: {chip_bg}; color: {chip_text}; border-radius: 4px; "
            "padding: 1px 8px; font-size: 11px;"
        )
        self.mod_count_badge.setVisible(not is_vanilla)

        # Vanilla pack'lere mod eklenemez (loader yok) — mod tablosu ve
        # ekleme/düzenleme araç çubuğu bu durumda tamamen gizlenir. Pack'te
        # hiç mod yoksa da aynı kontroller gizlenir; onların yerini boş
        # tablo yerine gösterilen "Mod Ekle" eylem çağrısı kartı alır.
        show_table_controls = not is_vanilla and bool(pack.mods)
        self.mod_actions_bar.setVisible(show_table_controls)
        self.mod_filter_input.setVisible(show_table_controls)
        self.sort_hint.setVisible(show_table_controls)
        self.show_file_names_checkbox.setVisible(show_table_controls)
        self.vanilla_notice.setVisible(is_vanilla)
        self.vanilla_content_bar.setVisible(is_vanilla)
        if is_vanilla:
            self.table.hide()
            self.empty_state.hide()
            self.filter_empty_notice.hide()
            self.table.setRowCount(0)
            return

        # Boş durum: pack'te hiç mod yoksa tablo yerine "Mod Ekle" eylem
        # çağrısı gösterilir; filtre hiçbir sonuç vermiyorsa ayrı bir not.
        if not pack.mods:
            self.table.hide()
            self.filter_empty_notice.hide()
            self.empty_state.show()
            self.table.setRowCount(0)
            return
        self.empty_state.hide()

        show_file_names = self.show_file_names_checkbox.isChecked()
        visible_mods = self._visible_mods(pack)

        if not visible_mods:
            query = self.mod_filter_input.text().strip()
            self.table.hide()
            self.filter_empty_notice.setText(f'"{query}" ile eşleşen mod bulunamadı.')
            self.filter_empty_notice.show()
            self.table.setRowCount(0)
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

    def _on_show_file_names_toggled(self, _checked: bool) -> None:
        self.show_pack(self._current_pack)

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


# ---------------------------------------------------------------------------
# Sağ üst panel: mod arama (CurseForge/Modrinth uygulamalarındaki "mod kartı"
# görünümü ilham alındı: ikon + başlık + açıklama + kaynak rozeti + indirme)
# ---------------------------------------------------------------------------


class _ModResultCard(QWidget):
    def __init__(self, result: SearchResult, *, already_added: bool = False) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.icon_label = _icon_label(40)
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(result.title)
        title.setStyleSheet("font-weight: 600; font-size: 13px;")
        title_row.addWidget(title)

        # Kimlik rengi metinde değil küçük noktada (bkz. _source_indicator_widget
        # docstring'i) — metin okunabilir mürekkep rengini kullanır.
        source_dot = QLabel()
        source_dot.setFixedSize(7, 7)
        source_dot.setStyleSheet(
            f"background-color: {source_color(result.source.value)}; border-radius: 3px;"
        )
        title_row.addWidget(source_dot)
        source_label = QLabel(_SOURCE_LABELS.get(result.source.value, result.source.value))
        source_label.setProperty("role", "muted")
        source_label.setStyleSheet("font-size: 11px;")
        title_row.addWidget(source_label)

        self.added_badge = QLabel("✓ Pack'te")
        self.added_badge.setStyleSheet(
            f"color: {status_good_color()}; font-weight: 600; font-size: 11px;"
        )
        self.added_badge.setVisible(already_added)
        title_row.addWidget(self.added_badge)
        title_row.addStretch()

        downloads = QLabel(f"⬇ {format_downloads(result.downloads)}")
        downloads.setProperty("role", "muted")
        title_row.addWidget(downloads)
        text_col.addLayout(title_row)

        if result.description:
            desc = QLabel(result.description)
            desc.setProperty("role", "muted")
            desc.setWordWrap(True)
            desc.setMaximumHeight(32)
            text_col.addWidget(desc)

        layout.addLayout(text_col, 1)

        if result.icon_url:
            load_icon(
                result.icon_url,
                lambda pixmap: _set_scaled_pixmap(self.icon_label, pixmap),
                owner=self.icon_label,
            )

    def set_already_added(self, added: bool) -> None:
        self.added_badge.setVisible(added)


class SearchPanel(QWidget):
    search_requested = Signal(str, str, int)  # query, source, offset
    add_mod_requested = Signal(object)  # SearchResult

    PAGE_SIZE = 20
    LIVE_SEARCH_DEBOUNCE_MS = 450
    """Kullanıcı yazmayı bıraktıktan bu kadar ms sonra otomatik arama tetiklenir
    (her tuş vuruşunda değil — gereksiz API isteğini önlemek için)."""

    def __init__(
        self,
        *,
        title: str = "Mod Ara",
        query_placeholder: str = "Mod adı...",
        add_button_text: str = "Seçili Modu Pack'e Ekle",
        curseforge_only: bool = False,
    ) -> None:
        """curseforge_only: Modrinth'te karşılığı olmayan içerik türleri için
        (ör. Dünya/Harita — sadece CurseForge'ta bir proje türü olarak var)
        "Tümü"/"Modrinth" seçenekleri hiç gösterilmez, kaynak sabitçe
        CurseForge olur."""
        super().__init__()
        self._results: list[SearchResult] = []
        self._added_project_ids: set[str] = set()
        self._has_more = True
        self._loading_more = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group(title)
        outer.addWidget(group)

        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(query_placeholder)
        self.query_input.returnPressed.connect(self._on_search_clicked)
        self._live_search_timer = QTimer(self)
        self._live_search_timer.setSingleShot(True)
        self._live_search_timer.setInterval(self.LIVE_SEARCH_DEBOUNCE_MS)
        self._live_search_timer.timeout.connect(self._on_search_clicked)
        self.query_input.textEdited.connect(lambda _: self._live_search_timer.start())
        row.addWidget(self.query_input)

        self.source_combo = QComboBox()
        if curseforge_only:
            self.source_combo.addItem(
                _SOURCE_LABELS.get(ModSourceType.CURSEFORGE.value, "CurseForge"),
                ModSourceType.CURSEFORGE.value,
            )
            self.source_combo.setEnabled(False)
        else:
            self.source_combo.addItem("Tümü (Modrinth + CurseForge)", "both")
            for s in ModSourceType:
                self.source_combo.addItem(_SOURCE_LABELS.get(s.value, s.value), s.value)
        self.source_combo.currentIndexChanged.connect(self._on_search_clicked)
        row.addWidget(self.source_combo)

        self.view_combo = QComboBox()
        self.view_combo.addItem("Toplu Liste", "all")
        self.view_combo.addItem("Kategoriye Göre", "category")
        self.view_combo.currentIndexChanged.connect(self._refresh_results_view)
        row.addWidget(self.view_combo)

        search_button = QPushButton("Ara")
        search_button.setObjectName("primary")
        search_button.clicked.connect(self._on_search_clicked)
        row.addWidget(search_button)
        layout.addLayout(row)

        self.results_list = QListWidget()
        self.results_list.setSpacing(2)
        self.results_list.itemDoubleClicked.connect(self._on_add_clicked)
        # Sonsuz kaydırma: listenin sonuna yaklaşınca bir sonraki sayfayı iste
        # (CurseForge/Modrinth App'te olduğu gibi 20 sonuçla sınırlı kalmasın).
        self.results_list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.results_list)

        add_button = QPushButton(add_button_text)
        add_button.clicked.connect(self._on_add_clicked)
        layout.addWidget(add_button)

    def _on_search_clicked(self) -> None:
        # Boş sorgu da geçerli: CurseForge/Modrinth App'te olduğu gibi
        # popüler modları (indirme sayısına göre) listeler.
        self._live_search_timer.stop()
        self._has_more = True
        query = self.query_input.text().strip()
        self.search_requested.emit(query, self.source_combo.currentData(), 0)

    def _on_scroll(self, value: int) -> None:
        if not self._has_more or self._loading_more:
            return
        bar = self.results_list.verticalScrollBar()
        if value < bar.maximum() - 4:
            return
        self._loading_more = True
        query = self.query_input.text().strip()
        self.search_requested.emit(query, self.source_combo.currentData(), len(self._results))

    def set_results(self, results: list[SearchResult], *, append: bool = False) -> None:
        self._loading_more = False
        if len(results) < self.PAGE_SIZE:
            self._has_more = False

        if not append:
            self._results = []
            self.results_list.clear()

        start = len(self._results)
        self._populate(list(enumerate(results, start=start)))
        self._results.extend(results)

    def _populate(self, indexed_results: list[tuple[int, SearchResult]]) -> None:
        """indexed_results: (self._results içindeki index, sonuç) çiftleri.
        Kategoriye göre görünümde bir sonuç birden çok kategoriye ait olabilir
        ve bu yüzden birden fazla satırda görünebilir — bu yüzden kartları
        self._results ile konumsal (zip) değil, her satırın kendi index'i
        üzerinden eşleştiriyoruz (bkz. set_added_project_ids)."""
        if self.view_combo.currentData() == "category":
            grouped: dict[str, list[tuple[int, SearchResult]]] = {}
            for index, result in indexed_results:
                for category in result.categories or ["Diğer"]:
                    grouped.setdefault(category, []).append((index, result))
            for category, entries in sorted(grouped.items()):
                header = QListWidgetItem(category.capitalize())
                header.setData(Qt.ItemDataRole.UserRole, -1)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.results_list.addItem(header)
                for index, result in entries:
                    self._add_result_item(result, index)
        else:
            for index, result in indexed_results:
                self._add_result_item(result, index)

    def _add_result_item(self, result: SearchResult, index: int) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, index)
        card = _ModResultCard(result, already_added=result.project_id in self._added_project_ids)
        item.setSizeHint(card.sizeHint())
        self.results_list.addItem(item)
        self.results_list.setItemWidget(item, card)

    def _refresh_results_view(self) -> None:
        if not self._results:
            return
        self.results_list.clear()
        self._populate(list(enumerate(self._results)))

    def set_added_project_ids(self, ids: set[str]) -> None:
        """Pack'te zaten olan modları listede "✓ Pack'te" ile işaretler —
        kullanıcı aynı modu yanlışlıkla tekrar eklemeye çalışmasın diye."""
        self._added_project_ids = ids
        for row in range(self.results_list.count()):
            item = self.results_list.item(row)
            index = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(index, int) or index < 0:
                continue
            widget = self.results_list.itemWidget(item)
            if isinstance(widget, _ModResultCard):
                widget.set_already_added(self._results[index].project_id in ids)

    def _on_add_clicked(self) -> None:
        item = self.results_list.currentItem()
        if item is None:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int) and 0 <= index < len(self._results):
            self.add_mod_requested.emit(self._results[index])
