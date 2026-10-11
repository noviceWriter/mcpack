"""Keşfet: Modrinth/CurseForge'ta mod, shader, kaynak paketi, datapack ve
dünya arama + ekleme. Eski ayrı "Mod Ekle" penceresinin yerini alır; pack
sayfasının içine gömülüdür (pencere yönetimi yok, pack değişince otomatik
güncellenir).

Sol: sonsuz kaydırmalı sonuç kartları. Sağ: seçili projenin ayrıntısı +
"Sürüm seç" / "En yeniyi ekle" / "Tarayıcıda aç". Çift tıklama hızlı ekler.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QPoint, QRect, QSize, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QToolTip,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.components import (
    Card,
    Chip,
    EmptyState,
    IconBox,
    SearchField,
    button,
    info,
    label,
)
from mcpack.gui.controller import AppController
from mcpack.gui.dialogs import RecommendedModsDialog, VersionPickerDialog
from mcpack.gui.formatting import format_count, project_url, source_label
from mcpack.gui.icons import icons
from mcpack.gui.theme import COLORS, category_color
from mcpack.i18n import t
from mcpack.models import ContentKind, Loader, ModSourceType, Pack
from mcpack.sources.base import ModDetail, ModVersion, SearchResult

PAGE_SIZE = 20

# (anahtar, ContentKind | None) — None = mod
KINDS: list[tuple[str, ContentKind | None]] = [
    ("mods", None),
    ("shaderpack", ContentKind.SHADERPACK),
    ("resourcepack", ContentKind.RESOURCEPACK),
    ("datapack", ContentKind.DATAPACK),
    ("world", ContentKind.WORLD),
]


ROW_HEIGHT = 78
ICON = 46


def _wrap_two_lines(text: str, fm: QFontMetrics, width: int) -> list[str]:
    """Metni en fazla iki satıra böler; sığmayan kısım ikinci satırın
    sonunda "…" ile kısaltılır (eskiden kartlar sabit yükseklikte metni
    alttan/sağdan kırpıyordu)."""
    text = " ".join(text.split())
    if not text or width <= 10:
        return []
    if fm.horizontalAdvance(text) <= width:
        return [text]
    words = text.split(" ")
    line = ""
    for i, word in enumerate(words):
        candidate = f"{line} {word}".strip()
        if fm.horizontalAdvance(candidate) > width and line:
            rest = " ".join(words[i:])
            return [line, fm.elidedText(rest, Qt.TextElideMode.ElideRight, width)]
        line = candidate
    return [fm.elidedText(line, Qt.TextElideMode.ElideRight, width)]


def _scaled(font: QFont, factor: float) -> QFont:
    """QSS font-size piksel cinsinden verildiği için pointSize -1 olabilir."""
    f = QFont(font)
    if f.pixelSize() > 0:
        f.setPixelSize(max(8, round(f.pixelSize() * factor)))
    elif f.pointSizeF() > 0:
        f.setPointSizeF(f.pointSizeF() * factor)
    return f


class ResultDelegate(QStyledItemDelegate):
    """Arama sonuçlarını doğrudan çizer: ikon, başlık, kaynak noktası,
    "Pack'te" rozeti, indirme sayısı ve iki satırlık açıklama — hepsi
    satırın gerçek genişliğine göre kısaltılır, hiçbir şey taşmaz."""

    def __init__(self, view: "DiscoverView") -> None:
        super().__init__(view.results)
        self.view = view
        self._pixmaps: dict[str, QPixmap] = {}
        self._requested: set[str] = set()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ROW_HEIGHT)

    def _pixmap(self, url: str | None) -> QPixmap | None:
        if not url:
            return None
        pm = self._pixmaps.get(url)
        if pm is None and url not in self._requested:
            self._requested.add(url)
            view = self.view.results

            def loaded(pixmap: QPixmap, u=url) -> None:
                self._pixmaps[u] = pixmap.scaled(
                    ICON, ICON, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                view.viewport().update()

            icons().load(url, loaded, owner=view)
            pm = self._pixmaps.get(url)  # önbellekten senkron gelmiş olabilir
        return pm

    def paint(self, painter: QPainter, option, index) -> None:
        idx = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(idx, int) or idx >= len(self.view._results):
            return
        r = self.view._results[idx]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(4, 2, -4, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["selection"] if selected else COLORS["hover"]))
            painter.drawRoundedRect(rect, 8, 8)

        # ikon
        icon_rect = QRect(rect.left() + 10, rect.top() + (rect.height() - ICON) // 2, ICON, ICON)
        pm = self._pixmap(r.icon_url)
        if pm is not None:
            painter.drawPixmap(
                icon_rect.left() + (ICON - pm.width()) // 2, icon_rect.top() + (ICON - pm.height()) // 2, pm
            )
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["elevated"]))
            painter.drawRoundedRect(icon_rect, 9, 9)
            painter.setPen(QColor(COLORS["text_muted"]))
            f = _scaled(option.font, 1.3)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, (r.title or "?")[:1].upper())

        left = icon_rect.right() + 12
        right = rect.right() - 10
        base = QFont(option.font)

        # sağ üst: indirme sayısı
        small = _scaled(base, 0.88)
        fm_small = QFontMetrics(small)
        downloads = f"⬇ {format_count(r.downloads)}"
        dl_w = fm_small.horizontalAdvance(downloads)
        top = rect.top() + 10
        painter.setFont(small)
        painter.setPen(QColor(COLORS["text_dim"]))
        painter.drawText(QRect(right - dl_w, top, dl_w, fm_small.height()), Qt.AlignmentFlag.AlignRight, downloads)

        # sağ üst: "Pack'te" işareti indirme sayısının solunda
        added = r.project_id in self.view._added_cache
        reserved = dl_w
        if added:
            mark = "✓ " + t("discover.in_pack_short")
            mark_w = fm_small.horizontalAdvance(mark)
            painter.setPen(QColor(COLORS["success"]))
            painter.drawText(QRect(right - dl_w - 10 - mark_w, top, mark_w, fm_small.height()), Qt.AlignmentFlag.AlignRight, mark)
            reserved += mark_w + 10

        # kaynak: başlığın önünde renkli nokta (adı ipucunda ve ayrıntı panelinde)
        title_font = QFont(base)
        title_font.setBold(True)
        fm_title = QFontMetrics(title_font)
        dot_y = top + fm_title.height() // 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(category_color(r.source.value)))
        painter.drawEllipse(QPoint(left + 4, dot_y), 4, 4)
        title_left = left + 14
        title_space = max(30, right - reserved - 12 - title_left)
        painter.setFont(title_font)
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(
            QRect(title_left, top - 1, title_space, fm_title.height()), Qt.AlignmentFlag.AlignLeft,
            fm_title.elidedText(r.title, Qt.TextElideMode.ElideRight, title_space),
        )

        # açıklama: en fazla 2 satır, genişliğe göre "…"
        painter.setFont(base)
        fm = QFontMetrics(base)
        painter.setPen(QColor(COLORS["text_muted"]))
        y = top + fm_title.height() + 4
        for line in _wrap_two_lines(r.description or "", fm, right - left):
            painter.drawText(QRect(left, y, right - left, fm.height()), Qt.AlignmentFlag.AlignLeft, line)
            y += fm.height()
        painter.restore()

    def helpEvent(self, event, view, option, index) -> bool:  # noqa: N802
        idx = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and idx < len(self.view._results):
            r = self.view._results[idx]
            text = f"<b>{html.escape(r.title)}</b> · {html.escape(source_label(r.source.value))}<br>{html.escape(r.description or '')}"
            QToolTip.showText(event.globalPos(), text, view)
            return True
        return super().helpEvent(event, view, option, index)


class DiscoverView(QWidget):
    added = Signal()

    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        self.pack: Pack | None = None
        self.kind_key = "mods"
        self._results: list[SearchResult] = []
        self._has_more = True
        self._loading = False
        self._request = 0
        self._last_query: tuple | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        kinds = QHBoxLayout()
        kinds.setSpacing(6)
        self.kind_group = QButtonGroup(self)
        self.kind_buttons: dict[str, object] = {}
        for key, _kind in KINDS:
            chip = button(t(f"discover.kind.{key}"), variant="chip", checkable=True)
            chip.setProperty("kind", key)
            self.kind_group.addButton(chip)
            self.kind_buttons[key] = chip
            kinds.addWidget(chip)
        self.kind_group.buttonToggled.connect(self._on_kind_toggled)
        kinds.addStretch()
        outer.addLayout(kinds)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = SearchField(t("discover.search_placeholder"), delay_ms=400)
        self.search.search.connect(lambda _q: self.run_search())
        bar.addWidget(self.search, 1)
        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(lambda _i: self.run_search())
        bar.addWidget(self.source_combo)
        self.count_label = label("", role="dim")
        bar.addWidget(self.count_label)
        outer.addLayout(bar)

        self.notice = label("", role="notice-info", wrap=True)
        self.notice.hide()
        outer.addWidget(self.notice)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.results = QListWidget()
        self.results.setUniformItemSizes(True)
        self.results.setMouseTracking(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._added_cache: set[str] = set()
        self.results.setItemDelegate(ResultDelegate(self))
        self.results.currentRowChanged.connect(self._on_selected)
        self.results.itemDoubleClicked.connect(lambda _i: self.add_selected(quick=True))
        self.results.verticalScrollBar().valueChanged.connect(self._on_scroll)
        left_layout.addWidget(self.results)
        self.empty = EmptyState("🔍", t("discover.empty_title"), t("discover.empty_sub"))
        self.empty.hide()
        left_layout.addWidget(self.empty)
        self.loading_label = label(t("discover.loading"), role="dim")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()
        left_layout.addWidget(self.loading_label)
        splitter.addWidget(left)

        self.detail = Card(padding=18, spacing=10)
        self.detail.setMinimumWidth(300)
        self.detail.setMaximumWidth(400)
        head = QHBoxLayout()
        self.detail_icon = IconBox(size=64)
        head.addWidget(self.detail_icon)
        dcol = QVBoxLayout()
        dcol.setSpacing(3)
        self.detail_title = label("", role="h2", wrap=True)
        dcol.addWidget(self.detail_title)
        self.detail_meta = label("", role="dim")
        dcol.addWidget(self.detail_meta)
        head.addLayout(dcol, 1)
        self.detail.body.addLayout(head)
        self.detail_desc = label("", role="muted", wrap=True, selectable=True)
        self.detail.body.addWidget(self.detail_desc)
        self.detail_cats = QHBoxLayout()
        self.detail_cats.setSpacing(4)
        self.detail.body.addLayout(self.detail_cats)
        self.detail.body.addStretch()
        self.add_latest_btn = button(t("discover.add_latest"), variant="primary", on_click=lambda: self.add_selected(quick=True))
        self.pick_btn = button(t("discover.pick_version"), on_click=lambda: self.add_selected(quick=False))
        self.open_btn = button(t("discover.open_browser"), variant="ghost", on_click=self._open_in_browser)
        for b in (self.add_latest_btn, self.pick_btn, self.open_btn):
            self.detail.body.addWidget(b)
        self.detail_hint = label(t("discover.hint"), role="dim", wrap=True)
        self.detail.body.addWidget(self.detail_hint)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)
        self._show_detail(None)

    # -- durum ----------------------------------------------------------------------

    @property
    def kind(self) -> ContentKind | None:
        return dict(KINDS)[self.kind_key]

    def set_pack(self, pack: Pack | None) -> None:
        changed = self.pack is None or pack is None or pack.id != self.pack.id
        self.pack = pack
        if pack is None:
            return
        is_vanilla = pack.loader == Loader.VANILLA
        self.kind_buttons["mods"].setVisible(not is_vanilla)
        if changed:
            self._results = []
            self.results.clear()
            self._last_query = None
            self.select_kind("shaderpack" if is_vanilla and self.kind_key == "mods" else self.kind_key, search=False)
        else:
            self._refresh_added_markers()

    def select_kind(self, key: str, *, search: bool = True) -> None:
        if self.pack is not None and self.pack.loader == Loader.VANILLA and key == "mods":
            key = "shaderpack"
        self.kind_key = key
        btn = self.kind_buttons[key]
        self.kind_group.blockSignals(True)
        btn.setChecked(True)
        self.kind_group.blockSignals(False)
        self._configure_sources()
        if search:
            self.run_search(force=True)

    def ensure_loaded(self) -> None:
        """Sekme ilk görünür olduğunda popüler sonuçları getirir."""
        if not self._results and not self._loading:
            self.run_search(force=True)

    def _on_kind_toggled(self, btn, checked: bool) -> None:
        if checked:
            self.kind_key = btn.property("kind")
            self._configure_sources()
            self.run_search(force=True)

    def _configure_sources(self) -> None:
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        world = self.kind == ContentKind.WORLD
        if world:
            self.source_combo.addItem("CurseForge", ModSourceType.CURSEFORGE.value)
        else:
            self.source_combo.addItem(t("discover.source_all"), "both")
            self.source_combo.addItem("Modrinth", ModSourceType.MODRINTH.value)
            self.source_combo.addItem("CurseForge", ModSourceType.CURSEFORGE.value)
        self.source_combo.blockSignals(False)
        notice = ""
        if world and not self.ctl.has_curseforge():
            notice = t("discover.world_needs_cf")
        elif not world and not self.ctl.has_curseforge():
            notice = t("discover.cf_not_configured")
        self.notice.setText(notice)
        self.notice.setVisible(bool(notice))

    # -- arama -----------------------------------------------------------------------

    def run_search(self, *, force: bool = False, offset: int = 0) -> None:
        if self.pack is None:
            return
        source = self.source_combo.currentData() or "both"
        query = self.search.text().strip()
        key = (self.pack.id, self.kind_key, source, query)
        if offset == 0 and not force and key == self._last_query:
            return
        if source == ModSourceType.CURSEFORGE.value and not self.ctl.has_curseforge():
            self._set_results([], append=False)
            self.empty.title_label.setText(t("discover.cf_required_title"))
            self.empty.subtitle_label.setText(t("discover.cf_required_sub"))
            return
        self._last_query = key
        self._request += 1
        request = self._request
        self._loading = True
        self.loading_label.setVisible(True)
        if offset == 0:
            self.count_label.setText(t("discover.searching"))

        def done(results: list[SearchResult]) -> None:
            if request != self._request:
                return  # daha yeni bir arama başladı
            self._loading = False
            self.loading_label.hide()
            self._set_results(results, append=offset > 0)

        def failed(message: str) -> None:
            if request != self._request:
                return
            self._loading = False
            self.loading_label.hide()
            self.count_label.setText(t("discover.failed"))

        self.ctl.search(self.pack, self.kind, query, source, offset, done, failed)

    def _on_scroll(self, value: int) -> None:
        bar = self.results.verticalScrollBar()
        if self._has_more and not self._loading and value >= bar.maximum() - 40 and self._results:
            self.run_search(offset=len(self._results))

    def _added_ids(self) -> set[str]:
        if self.pack is None:
            return set()
        if self.kind is None:
            return {m.project_id for m in self.pack.mods}
        if self.kind == ContentKind.WORLD:
            return set()
        return {c.project_id for c in self.pack.content_downloads_of(self.kind)}

    def _set_results(self, results: list[SearchResult], *, append: bool) -> None:
        self._has_more = len(results) >= PAGE_SIZE // 2
        if not append:
            self._results = []
            self.results.clear()
        self._added_cache = self._added_ids()
        known = {(r.source, r.project_id) for r in self._results}
        for r in results:
            if (r.source, r.project_id) in known:
                continue
            known.add((r.source, r.project_id))
            self._results.append(r)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            item.setData(Qt.ItemDataRole.UserRole, len(self._results) - 1)
            self.results.addItem(item)
        self.count_label.setText(t("discover.count", count=len(self._results)) + ("+" if self._has_more else ""))
        has = bool(self._results)
        self.results.setVisible(has)
        self.empty.setVisible(not has)
        if not has:
            self.empty.title_label.setText(t("discover.empty_title"))
            self.empty.subtitle_label.setText(t("discover.empty_sub"))
        if not append and has:
            self.results.setCurrentRow(0)

    def _refresh_added_markers(self) -> None:
        self._added_cache = self._added_ids()
        self.results.viewport().update()
        self._on_selected(self.results.currentRow())

    # -- ayrıntı paneli -------------------------------------------------------------

    def _current(self) -> SearchResult | None:
        item = self.results.currentItem()
        if item is None:
            return None
        idx = item.data(Qt.ItemDataRole.UserRole)
        return self._results[idx] if isinstance(idx, int) and idx < len(self._results) else None

    def _on_selected(self, _row: int) -> None:
        self._show_detail(self._current())

    def _show_detail(self, result: SearchResult | None) -> None:
        for w in (self.add_latest_btn, self.pick_btn, self.open_btn):
            w.setEnabled(result is not None)
        while self.detail_cats.count():
            item = self.detail_cats.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if result is None:
            self.detail_title.setText(t("discover.no_selection"))
            self.detail_meta.setText("")
            self.detail_desc.setText(t("discover.no_selection_sub"))
            return
        self.detail_icon.reset(result.title)
        self.detail_icon.load(result.icon_url)
        self.detail_title.setText(result.title)
        self.detail_meta.setText(f"{source_label(result.source.value)} · ⬇ {format_count(result.downloads)} · {result.slug}")
        self.detail_desc.setText(result.description or "—")
        for cat in result.categories[:6]:
            self.detail_cats.addWidget(Chip(cat, "neutral"))
        self.detail_cats.addStretch()
        in_pack = result.project_id in self._added_ids()
        self.add_latest_btn.setText(t("discover.reinstall") if in_pack else t("discover.add_latest"))
        self.pick_btn.setVisible(self.kind != ContentKind.WORLD)

    def _open_in_browser(self) -> None:
        r = self._current()
        if r is not None:
            url = project_url(r.source.value, r.project_id, r.slug)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    # -- ekleme ----------------------------------------------------------------------

    def add_selected(self, *, quick: bool) -> None:
        result = self._current()
        pack = self.pack
        if result is None or pack is None:
            return
        kind = self.kind
        if kind is None and pack.find_mod(result.project_id) is not None and quick:
            self.ctl.notify.emit("info", t("discover.already_added", title=result.title))
            return

        def fetched(detail: ModDetail, versions: list[ModVersion]) -> None:
            if not versions:
                self.ctl.notify.emit(
                    "error",
                    t("discover.no_compatible", title=result.title, minecraft=pack.minecraft,
                      loader=pack.loader.value if kind is None else "—"),
                )
                return
            chosen = versions[0]
            if not quick and len(versions) > 1:
                dialog = VersionPickerDialog(result.title, versions, self)
                if not dialog.exec():
                    return
                chosen = dialog.selected()
            if kind is None:
                self.ctl.add_mod_version(pack, chosen, detail, on_done=self._after_mod_added)
            elif kind == ContentKind.WORLD:
                self.ctl.add_world_download(pack, chosen, detail)
            else:
                self.ctl.add_content_download(pack, kind, chosen, detail)
            self.added.emit()

        self.ctl.fetch_versions(pack, result, kind, fetched)

    def _after_mod_added(self, suggestions: list[tuple[ModVersion, ModDetail]], failed: list[str]) -> None:
        pack = self.pack
        if pack is None:
            return
        if failed:
            info(
                self, t("deps.unresolved_title"),
                t("deps.unresolved_body", minecraft=pack.minecraft, loader=pack.loader.value,
                  list="\n".join(f"• {n}" for n in failed)),
                warning=True,
            )
        if suggestions:
            dialog = RecommendedModsDialog(suggestions, self)
            if dialog.exec():
                self.ctl.add_mod_versions(pack, dialog.selected())
