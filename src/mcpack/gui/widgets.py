"""Paylaşılan düşük seviye GUI yardımcıları: async worker, mod/arama kartları,
SearchPanel (mod + shader/resourcepack/datapack/dünya aramasının ortak
gövdesi). Sayfa düzeyindeki bileşenler (kütüphane, instance detayı) için
bkz. library_page.py / instance_page.py."""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.icon_loader import load_icon
from mcpack.gui.theme import (
    apply_card_shadow,
    chip_colors,
    icon_placeholder_bg,
    source_color,
    status_good_color,
)
from mcpack.i18n import t
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
            # Tam traceback konsola basılır (geliştirici/log için) — GUI'ye
            # (QMessageBox popup'ı ya da bir durum etiketi) sadece kısa,
            # okunabilir hata mesajı gider. Önceden ikisi birleştirilip
            # kullanıcıya gösteriliyordu: geçici bir ağ hatasında bile
            # (ör. Modrinth bağlantısı koptuğunda) ekrana 40+ satırlık ham
            # Python traceback'i düşüyordu (kullanıcı geri bildirimi).
            traceback.print_exc()
            self.signals.error.emit(str(exc))
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


_SOURCE_LABELS = {
    "modrinth": "Modrinth",
    "curseforge": "CurseForge",
    "wurst": "Wurst Client",
    "meteor": "Meteor Client",
}


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
        return t("env.client_server")
    if client_ok:
        return t("env.client")
    if server_ok:
        return t("env.server")
    return t("env.unknown")


def _env_badge_widget(client: str, server: str) -> QWidget:
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)

    text = _environment_label(client, server)
    chip = QLabel(text)
    if text == t("env.unknown"):
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

        self.added_badge = QLabel(t("mod.already_in_pack"))
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
        title: str | None = None,
        query_placeholder: str | None = None,
        add_button_text: str | None = None,
        curseforge_only: bool = False,
    ) -> None:
        """curseforge_only: Modrinth'te karşılığı olmayan içerik türleri için
        (ör. Dünya/Harita — sadece CurseForge'ta bir proje türü olarak var)
        "Tümü"/"Modrinth" seçenekleri hiç gösterilmez, kaynak sabitçe
        CurseForge olur.

        title/query_placeholder/add_button_text None bırakılırsa varsayılan
        (genel mod arama) metinlerine düşer — t() çağrıları burada, __init__
        GÖVDESİNDE yapılır (fonksiyon imzasında DEĞİL): parametre varsayılan
        değerleri Python'da modül import edilirken BİR KERE hesaplanır, o an
        henüz set_language() çağrılmamış olabilir (bkz. main.py:main)."""
        super().__init__()
        title = title if title is not None else t("search.default_title")
        query_placeholder = (
            query_placeholder if query_placeholder is not None else t("search.query_placeholder")
        )
        add_button_text = (
            add_button_text if add_button_text is not None else t("search.add_button")
        )
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
            self.source_combo.addItem(t("search.source_all"), "both")
            # Wurst/Meteor (ModSourceType'a sonradan eklendi) burada YOK —
            # onların search()/get_versions() uygulayan bir ModSource'u yok,
            # kendi API'lerinden ayrı bir akışla eklenirler (bkz.
            # sources/cheat_mods.py, gui/instance_page.py:CheatModsSection).
            for s in (ModSourceType.MODRINTH, ModSourceType.CURSEFORGE):
                self.source_combo.addItem(_SOURCE_LABELS.get(s.value, s.value), s.value)
        self.source_combo.currentIndexChanged.connect(self._on_search_clicked)
        row.addWidget(self.source_combo)

        self.view_combo = QComboBox()
        self.view_combo.addItem(t("search.view_flat"), "all")
        self.view_combo.addItem(t("search.view_category"), "category")
        self.view_combo.currentIndexChanged.connect(self._refresh_results_view)
        row.addWidget(self.view_combo)

        search_button = QPushButton(t("search.button"))
        search_button.setObjectName("primary")
        search_button.clicked.connect(self._on_search_clicked)
        row.addWidget(search_button)
        layout.addLayout(row)

        self.results_list = QListWidget()
        self.results_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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
                for category in result.categories or [t("search.other_category")]:
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
