"""Pack detay sayfası: başlık + eylemler, solda bölüm rayı, sağda içerik.

Bölümler: Genel Bakış, Modlar, Keşfet, Shader, Kaynak Paketi, Datapack,
Dünyalar, Sunucu, (Fabric'te) Hile Modları.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui import pack_actions
from mcpack.gui.components import (
    Card,
    Chip,
    EmptyState,
    SearchField,
    StatTile,
    button,
    confirm,
    label,
    loader_badge,
    tool_button,
)
from mcpack.gui.controller import CHEAT_SOURCES, AppController
from mcpack.gui.dialogs import EnvEditorDialog
from mcpack.gui.formatting import (
    environment_label,
    format_relative,
    format_size,
    loader_label,
    project_url,
    source_label,
)
from mcpack.gui.pages.discover import DiscoverView
from mcpack.gui.pages.server_panel import ServerPanel
from mcpack.gui.theme import COLORS, category_color
from mcpack.i18n import t
from mcpack.models import ContentKind, Loader, ModEntry, Pack

# -- mod tablosu modeli ------------------------------------------------------------

COLS = ["name", "source", "env", "file", "size", "deps"]


class ModTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.mods: list[ModEntry] = []
        self.present: set[str] = set()

    def set_mods(self, mods: list[ModEntry], present: set[str]) -> None:
        self.beginResetModel()
        self.mods = mods
        self.present = present
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.mods)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return len(COLS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return t(f"mods.col.{COLS[section]}")
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        mod = self.mods[index.row()]
        col = COLS[index.column()]
        missing = [d for d in mod.dependencies if d not in self.present]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == "name":
                return mod.name or mod.file_name
            if col == "source":
                return source_label(mod.source.value)
            if col == "env":
                return environment_label(mod.env.client.value, mod.env.server.value)
            if col == "file":
                return mod.file_name
            if col == "size":
                return format_size(mod.file_size)
            if col == "deps":
                if missing:
                    return f"⚠ {len(missing)}/{len(mod.dependencies)}"
                return str(len(mod.dependencies)) if mod.dependencies else "—"
        if role == Qt.ItemDataRole.UserRole:
            if col == "size":
                return mod.file_size or 0
            if col == "deps":
                return len(missing) * 1000 + len(mod.dependencies)
            return (self.data(index) or "").lower()
        if role == Qt.ItemDataRole.ForegroundRole:
            from PySide6.QtGui import QColor

            if col == "source":
                return QColor(category_color(mod.source.value))
            if col == "deps" and missing:
                return QColor(COLORS["danger"])
            if col == "env" and mod.env.is_client_only:
                return QColor(COLORS["info"])
            if col in ("file", "size"):
                return QColor(COLORS["text_muted"])
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = f"{mod.name or mod.file_name}\n{mod.file_name}\nproject: {mod.project_id}\nversion: {mod.version_id}"
            tip += f"\nclient: {mod.env.client.value} · server: {mod.env.server.value}"
            if missing:
                tip += "\n" + t("mods.missing_deps_tip", ids=", ".join(missing))
            return tip
        return None


class ModFilterProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self.source = ""
        self.env = ""
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def filterAcceptsRow(self, row: int, parent) -> bool:  # noqa: N802
        mod: ModEntry = self.sourceModel().mods[row]
        if self.text:
            hay = f"{mod.name or ''} {mod.file_name} {mod.project_id} {mod.slug or ''}".lower()
            if self.text not in hay:
                return False
        if self.source and mod.source.value != self.source:
            return False
        if self.env == "client_only" and not mod.env.is_client_only:
            return False
        if self.env == "server" and not mod.env.is_server_compatible:
            return False
        if self.env == "missing":
            present = self.sourceModel().present
            if all(d in present for d in mod.dependencies):
                return False
        return True


# -- bölümler ------------------------------------------------------------------------


class OverviewTab(QScrollArea):
    def __init__(self, page: "PackPage") -> None:
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        body = QWidget()
        self.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(14)
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_mods = StatTile(t("overview.mods"))
        self.t_client = StatTile(t("overview.client_only"))
        self.t_server = StatTile(t("overview.server_mods"))
        self.t_content = StatTile(t("overview.content"))
        self.t_size = StatTile(t("overview.size"))
        for w in (self.t_mods, self.t_client, self.t_server, self.t_content, self.t_size):
            tiles.addWidget(w)
        col.addLayout(tiles)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.info_card = Card()
        self.info_card.body.addWidget(label(t("overview.info"), role="h3"))
        self.info_grid = QGridLayout()
        self.info_grid.setHorizontalSpacing(18)
        self.info_grid.setVerticalSpacing(6)
        self.info_card.body.addLayout(self.info_grid)
        self.info_card.body.addWidget(button(t("pack.edit_info"), variant="ghost", on_click=lambda: page.pack and pack_actions.edit_meta(self, page.ctl, page.pack)))
        self.info_card.body.addStretch()
        grid.addWidget(self.info_card, 0, 0)

        self.health = Card()
        self.health.body.addWidget(label(t("overview.health"), role="h3"))
        self.health_text = label("", wrap=True)
        self.health.body.addWidget(self.health_text)
        self.health_list = label("", role="muted", wrap=True, selectable=True)
        self.health.body.addWidget(self.health_list)
        row = QHBoxLayout()
        row.addWidget(button(t("overview.check_deps"), on_click=self._check_deps))
        row.addWidget(button(t("overview.show_missing"), variant="ghost", on_click=lambda: page.show_section("mods", env_filter="missing")))
        row.addStretch()
        self.health.body.addLayout(row)
        self.health.body.addStretch()
        grid.addWidget(self.health, 0, 1)

        self.sources_card = Card()
        self.sources_card.body.addWidget(label(t("overview.sources"), role="h3"))
        self.sources_text = label("", role="muted", wrap=True)
        self.sources_card.body.addWidget(self.sources_text)
        self.sources_card.body.addStretch()
        grid.addWidget(self.sources_card, 1, 0)

        actions = Card()
        actions.body.addWidget(label(t("overview.actions"), role="h3"))
        for text, fn in (
            (t("overview.add_mods"), lambda: page.show_section("discover")),
            (t("pack.server_pack"), lambda: page.pack and pack_actions.server_pack(self, page.ctl, page.pack)),
            (t("pack.fork"), lambda: page.pack and pack_actions.fork(self, page.ctl, page.pack)),
            (t("pack.duplicate"), lambda: page.pack and page.ctl.duplicate_pack(page.pack)),
        ):
            actions.body.addWidget(button(text, on_click=fn))
        actions.body.addStretch()
        grid.addWidget(actions, 1, 1)
        col.addLayout(grid)
        col.addStretch()

    def _check_deps(self) -> None:
        pack = self.page.pack
        if pack is None:
            return

        def done(lines: list[str]) -> None:
            if lines:
                self.health_text.setText(t("overview.deps_missing", count=len(lines)))
                self.health_list.setText("\n".join(lines))
            else:
                self.health_text.setText(t("overview.deps_ok"))
                self.health_list.setText("")
                self.page.ctl.notify.emit("success", t("overview.deps_ok"))

        self.page.ctl.describe_missing_dependencies(pack, done)

    def show_pack(self, pack: Pack) -> None:
        mods = pack.mods
        client_only = sum(1 for m in mods if m.env.is_client_only)
        size = sum(m.file_size or 0 for m in mods) + sum(c.file_size or 0 for c in pack.content_downloads)
        self.t_mods.set_value(str(len(mods)))
        self.t_client.set_value(str(client_only))
        self.t_server.set_value(str(len(mods) - client_only))
        self.t_content.set_value(str(len(pack.content_downloads) + len(pack.content)))
        self.t_size.set_value(format_size(size) if size else "—", t("overview.size_hint"))

        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = [
            (t("overview.f_loader"), f"{loader_label(pack.loader.value)} {pack.loader_version}".strip()),
            ("Minecraft", pack.minecraft),
            (t("packmeta.version"), pack.version),
            (t("newpack.author"), pack.author or "—"),
            (t("newpack.summary"), pack.summary or "—"),
            (t("overview.f_created"), format_relative(pack.created_at)),
            (t("overview.f_updated"), format_relative(pack.updated_at)),
            ("ID", pack.id),
        ]
        for r, (k, v) in enumerate(rows):
            self.info_grid.addWidget(label(k, role="dim"), r, 0)
            self.info_grid.addWidget(label(v, wrap=True, selectable=True), r, 1)

        missing = self.page.ctl.manager.find_missing_dependencies(pack)
        if missing:
            self.health_text.setText(t("overview.deps_missing_offline", count=len(missing)))
            self.health_text.setStyleSheet(f"color: {COLORS['warning']};")
            self.health_list.setText("\n".join(f"• {m}: {d}" for m, d in missing[:12]))
        else:
            self.health_text.setText(t("overview.deps_ok_offline"))
            self.health_text.setStyleSheet(f"color: {COLORS['success']};")
            self.health_list.setText("")

        counts: dict[str, int] = {}
        for m in mods:
            counts[m.source.value] = counts.get(m.source.value, 0) + 1
        self.sources_text.setText(
            "\n".join(f"● {source_label(k)}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])) or t("overview.no_mods")
        )


class ModsTab(QWidget):
    def __init__(self, page: "PackPage", *, cheat: bool = False) -> None:
        super().__init__()
        self.page = page
        self.cheat = cheat
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        if cheat:
            outer.addWidget(label(t("cheat.warning"), role="notice", wrap=True))

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = SearchField(t("mods.filter_placeholder"), delay_ms=120)
        self.search.search.connect(self._apply_filter)
        bar.addWidget(self.search, 1)
        self.source_filter = QComboBox()
        self.source_filter.addItem(t("mods.all_sources"), "")
        for s in ("modrinth", "curseforge", "wurst", "meteor"):
            self.source_filter.addItem(source_label(s), s)
        self.source_filter.currentIndexChanged.connect(lambda _i: self._apply_filter())
        self.env_filter = QComboBox()
        self.env_filter.addItem(t("mods.env_all"), "")
        self.env_filter.addItem(t("mods.env_client_only"), "client_only")
        self.env_filter.addItem(t("mods.env_server"), "server")
        self.env_filter.addItem(t("mods.env_missing"), "missing")
        self.env_filter.currentIndexChanged.connect(lambda _i: self._apply_filter())
        if not cheat:
            bar.addWidget(self.source_filter)
            bar.addWidget(self.env_filter)
        self.count = label("", role="dim")
        bar.addWidget(self.count)
        outer.addLayout(bar)

        self.model = ModTableModel()
        self.proxy = ModFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        for c, w in ((1, 110), (2, 140), (3, 220), (4, 80), (5, 96)):
            self.table.setColumnWidth(c, w)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(lambda _i: self._edit_env())
        self.table.selectionModel().selectionChanged.connect(lambda *_a: self._update_buttons())
        outer.addWidget(self.table, 1)
        QShortcut(QKeySequence.StandardKey.Delete, self.table, activated=self._remove)

        if cheat:
            self.empty = EmptyState("🎯", t("cheat.empty_title"), t("cheat.empty_sub"))
        else:
            self.empty = EmptyState(
                "🧩", t("mods.empty_title"), t("mods.empty_sub"),
                actions=[button(t("mods.browse"), variant="primary", on_click=lambda: page.show_section("discover"))],
            )
        outer.addWidget(self.empty, 1)
        self.vanilla_notice = label(t("mods.vanilla_notice"), role="notice", wrap=True)
        outer.addWidget(self.vanilla_notice)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        if cheat:
            actions.addWidget(button(t("cheat.add_wurst"), on_click=lambda: self._add_cheat("wurst")))
            actions.addWidget(button(t("cheat.add_meteor"), on_click=lambda: self._add_cheat("meteor")))
        else:
            actions.addWidget(button(t("mods.browse"), variant="primary", on_click=lambda: page.show_section("discover")))
        self.remove_btn = button(t("mods.remove"), variant="danger", on_click=self._remove)
        actions.addWidget(self.remove_btn)
        if not cheat:
            self.env_btn = button(t("mods.edit_env"), on_click=self._edit_env)
            actions.addWidget(self.env_btn)
            actions.addWidget(button(t("overview.check_deps"), variant="ghost", on_click=page.overview._check_deps))
        actions.addStretch()
        self.selection_label = label("", role="dim")
        actions.addWidget(self.selection_label)
        outer.addLayout(actions)

    def _mods(self, pack: Pack) -> list[ModEntry]:
        if self.cheat:
            return [m for m in pack.mods if m.source in CHEAT_SOURCES]
        return [m for m in pack.mods if m.source not in CHEAT_SOURCES]

    def show_pack(self, pack: Pack) -> None:
        mods = self._mods(pack)
        self.model.set_mods(mods, {m.project_id for m in pack.mods})
        vanilla = pack.loader == Loader.VANILLA and not self.cheat
        self.vanilla_notice.setVisible(vanilla)
        has = bool(mods)
        self.table.setVisible(has)
        self.empty.setVisible(not has and not vanilla)
        self._apply_filter()

    def set_env_filter(self, value: str) -> None:
        idx = self.env_filter.findData(value)
        if idx >= 0:
            self.env_filter.setCurrentIndex(idx)

    def _apply_filter(self, *_args) -> None:
        self.proxy.text = self.search.text().strip().lower()
        self.proxy.source = self.source_filter.currentData() or ""
        self.proxy.env = self.env_filter.currentData() or ""
        self.proxy.invalidateFilter()
        self.count.setText(t("mods.count", shown=self.proxy.rowCount(), total=self.model.rowCount()))
        self._update_buttons()

    def selected(self) -> list[ModEntry]:
        rows = {self.proxy.mapToSource(i).row() for i in self.table.selectionModel().selectedRows()}
        return [self.model.mods[r] for r in sorted(rows)]

    def _update_buttons(self) -> None:
        n = len(self.selected())
        self.remove_btn.setEnabled(n > 0)
        if not self.cheat:
            self.env_btn.setEnabled(n > 0)
        self.selection_label.setText(t("mods.selected", count=n) if n else "")

    def _remove(self) -> None:
        mods = self.selected()
        pack = self.page.pack
        if not mods or pack is None:
            return
        names = "\n".join(f"• {m.name or m.file_name}" for m in mods[:15]) + ("\n…" if len(mods) > 15 else "")
        if not confirm(self, t("mods.remove_title"), t("mods.remove_confirm", count=len(mods), list=names), ok_text=t("mods.remove"), danger=True):
            return
        dependents = [
            m.name or m.file_name for m in pack.mods
            if m not in mods and any(d in {x.project_id for x in mods} for d in m.dependencies)
        ]
        if dependents and not confirm(
            self, t("mods.dependents_title"), t("mods.dependents_body", list="\n".join(f"• {d}" for d in dependents[:15])),
            ok_text=t("mods.remove_anyway"), danger=True,
        ):
            return
        self.page.ctl.remove_mods(pack, [m.project_id for m in mods])

    def _edit_env(self) -> None:
        mods = self.selected()
        pack = self.page.pack
        if not mods or pack is None or self.cheat:
            return
        dialog = EnvEditorDialog(mods, self)
        if dialog.exec():
            client, server = dialog.values()
            self.page.ctl.set_mod_env(pack, [m.project_id for m in mods], client, server)

    def _add_cheat(self, kind: str) -> None:
        pack = self.page.pack
        if pack is not None and confirm(self, t("cheat.disclaimer_title"), t("cheat.disclaimer"), ok_text=t("cheat.accept"), danger=True):
            self.page.ctl.add_cheat_mod(pack, kind)

    def _context_menu(self, pos) -> None:
        mods = self.selected()
        if not mods:
            return
        menu = QMenu(self)
        if not self.cheat:
            menu.addAction(t("mods.edit_env"), self._edit_env)
        if len(mods) == 1:
            m = mods[0]
            url = project_url(m.source.value, m.project_id, m.slug)
            if url:
                menu.addAction(t("mods.open_page"), lambda: QDesktopServices.openUrl(QUrl(url)))
            menu.addAction(t("mods.copy_id"), lambda: QGuiApplication.clipboard().setText(m.project_id))
            menu.addAction(t("mods.copy_file"), lambda: QGuiApplication.clipboard().setText(m.file_name))
            menu.addAction(t("mods.copy_url"), lambda: QGuiApplication.clipboard().setText(m.download_url))
        menu.addSeparator()
        menu.addAction(t("mods.remove"), self._remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class ContentTab(QWidget):
    """Shader / kaynak paketi / datapack (indirilebilir içerik) ve dünyalar."""

    def __init__(self, page: "PackPage", kind: ContentKind) -> None:
        super().__init__()
        self.page = page
        self.kind = kind
        key = kind.value
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        if kind == ContentKind.DATAPACK:
            outer.addWidget(label(t("content.datapack_note"), role="notice-info", wrap=True))
        from PySide6.QtWidgets import QTableWidget

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([t("content.col.name"), t("content.col.source"), t("content.col.file")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 260)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        outer.addWidget(self.table, 1)
        QShortcut(QKeySequence.StandardKey.Delete, self.table, activated=self._remove)

        glyph = {"shaderpack": "✨", "resourcepack": "🖼", "datapack": "📦", "world": "🌍"}[key]
        actions_empty = [button(t("content.browse"), variant="primary", on_click=self._browse)]
        if kind == ContentKind.WORLD:
            actions_empty.insert(0, button(t("content.add_local_world"), variant="primary", on_click=self._add_local))
            actions_empty[1].setProperty("variant", None)
        self.empty = EmptyState(glyph, t(f"content.{key}.empty_title"), t(f"content.{key}.empty_sub"), actions=actions_empty)
        outer.addWidget(self.empty, 1)

        row = QHBoxLayout()
        if kind == ContentKind.WORLD:
            row.addWidget(button(t("content.add_local_world"), variant="primary", on_click=self._add_local))
            row.addWidget(button(t("content.browse_worlds"), on_click=self._browse))
        else:
            row.addWidget(button(t("content.browse"), variant="primary", on_click=self._browse))
        row.addWidget(button(t("content.remove"), variant="danger", on_click=self._remove))
        row.addWidget(button(t("content.open_folder"), variant="ghost", on_click=self._open_folder))
        row.addStretch()
        outer.addLayout(row)

    def show_pack(self, pack: Pack) -> None:
        self.table.setRowCount(0)
        from PySide6.QtWidgets import QTableWidgetItem

        if self.kind == ContentKind.WORLD:
            entries = [(w.name, t("content.local"), w.stored_path, w.name) for w in pack.content_of(ContentKind.WORLD)]
        else:
            entries = [
                (c.name or c.file_name, source_label(c.source.value), c.file_name, c.project_id)
                for c in pack.content_downloads_of(self.kind)
            ]
        for name, src, file, key in entries:
            r = self.table.rowCount()
            self.table.insertRow(r)
            item = QTableWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(r, 0, item)
            self.table.setItem(r, 1, QTableWidgetItem(src))
            self.table.setItem(r, 2, QTableWidgetItem(file))
        has = bool(entries)
        self.table.setVisible(has)
        self.empty.setVisible(not has)

    def _keys(self) -> list[str]:
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]

    def _browse(self) -> None:
        self.page.show_section("discover")
        self.page.discover.select_kind(self.kind.value)

    def _add_local(self) -> None:
        pack = self.page.pack
        if pack is None:
            return
        path = QFileDialog.getExistingDirectory(self, t("content.pick_world"))
        if path:
            if not (Path(path) / "level.dat").exists() and not confirm(
                self, t("content.no_level_dat_title"), t("content.no_level_dat_body")
            ):
                return
            self.page.ctl.add_local_world(pack, Path(path))

    def _remove(self) -> None:
        keys = self._keys()
        pack = self.page.pack
        if not keys or pack is None:
            return
        if not confirm(self, t("content.remove_title"), t("content.remove_confirm", count=len(keys)), ok_text=t("content.remove"), danger=True):
            return
        if self.kind == ContentKind.WORLD:
            self.page.ctl.remove_worlds(pack, keys)
        else:
            self.page.ctl.remove_content_download(pack, self.kind, keys)

    def _open_folder(self) -> None:
        pack = self.page.pack
        if pack is not None:
            sub = {"world": "worlds"}.get(self.kind.value, self.kind.value + "s")
            pack_actions.open_folder(self.page.ctl.manager.content_root(pack) / sub)


# -- sayfa ----------------------------------------------------------------------------

SECTIONS = [
    ("overview", "◉"),
    ("mods", "🧩"),
    ("discover", "🔎"),
    ("shaderpack", "✨"),
    ("resourcepack", "🖼"),
    ("datapack", "📦"),
    ("world", "🌍"),
    ("server", "🖥"),
    ("cheats", "🎯"),
]


class PackPage(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        self.pack: Pack | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 12)
        outer.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(14)
        self.back_btn = button("←", variant="ghost", tooltip=t("pack.back"), on_click=lambda: ctl.navigate.emit("library", ""))
        head.addWidget(self.back_btn)
        self.badge_holder = QHBoxLayout()
        head.addLayout(self.badge_holder)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = label("", role="title")
        col.addWidget(self.title)
        sub = QHBoxLayout()
        sub.setSpacing(8)
        self.subtitle = label("", role="muted")
        sub.addWidget(self.subtitle)
        self.server_chip = Chip("", "success", dot_color=COLORS["success"])
        sub.addWidget(self.server_chip)
        sub.addStretch()
        col.addLayout(sub)
        head.addLayout(col, 1)
        self.export_btn = tool_button(t("pack.export") + "  ▾", variant="primary")
        self.export_btn.setProperty("variant", None)
        self.export_btn.setStyleSheet(
            f"QToolButton {{ background: {COLORS['accent']}; color: white; border: 1px solid {COLORS['accent']}; font-weight: 600; padding: 7px 14px; border-radius: 8px; }}"
            f"QToolButton:hover {{ background: {COLORS['accent_hover']}; }}"
        )
        self.export_btn.setMenu(pack_actions.export_menu(self, ctl, lambda: self.pack))
        head.addWidget(self.export_btn)
        self.more_btn = tool_button("⋯", tooltip=t("library.more"))
        self.more_btn.clicked.connect(self._show_more)
        self.more_btn.setPopupMode(self.more_btn.ToolButtonPopupMode.DelayedPopup)
        head.addWidget(self.more_btn)
        outer.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(18)
        rail = QVBoxLayout()
        rail.setSpacing(2)
        self.rail_group = QButtonGroup(self)
        self.rail_buttons: dict[str, QPushButton] = {}
        for key, glyph in SECTIONS:
            b = button(f"{glyph}   {t(f'pack.section.{key}')}", variant="nav", checkable=True)
            b.setProperty("section", key)
            b.setMinimumWidth(190)
            self.rail_group.addButton(b)
            self.rail_buttons[key] = b
            rail.addWidget(b)
        rail.addStretch()
        self.rail_group.buttonClicked.connect(lambda b: self.show_section(b.property("section")))
        body.addLayout(rail)

        self.stack = QStackedWidget()
        self.overview = OverviewTab(self)
        self.mods = ModsTab(self)
        self.discover = DiscoverView(ctl)
        self.content_tabs = {k: ContentTab(self, k) for k in (ContentKind.SHADERPACK, ContentKind.RESOURCEPACK, ContentKind.DATAPACK, ContentKind.WORLD)}
        self.server = ServerPanel(ctl)
        self.cheats = ModsTab(self, cheat=True)
        self.sections: dict[str, QWidget] = {
            "overview": self.overview,
            "mods": self.mods,
            "discover": self.discover,
            "shaderpack": self.content_tabs[ContentKind.SHADERPACK],
            "resourcepack": self.content_tabs[ContentKind.RESOURCEPACK],
            "datapack": self.content_tabs[ContentKind.DATAPACK],
            "world": self.content_tabs[ContentKind.WORLD],
            "server": self.server,
            "cheats": self.cheats,
        }
        for w in self.sections.values():
            self.stack.addWidget(w)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        ctl.pack_updated.connect(self._on_pack_updated)
        ctl.server_changed.connect(lambda pid: self.pack and pid == self.pack.id and self._render_header())
        self.show_section("overview")

    def current_section(self) -> str:
        w = self.stack.currentWidget()
        return next((k for k, v in self.sections.items() if v is w), "overview")

    def show_section(self, key: str, *, env_filter: str | None = None) -> None:
        if key not in self.sections or (key == "cheats" and (self.pack is None or self.pack.loader != Loader.FABRIC)):
            key = "overview"
        self.rail_buttons[key].setChecked(True)
        self.stack.setCurrentWidget(self.sections[key])
        if key == "discover":
            self.discover.ensure_loaded()
        if env_filter:
            self.mods.set_env_filter(env_filter)

    def set_pack(self, pack: Pack) -> None:
        switched = self.pack is None or self.pack.id != pack.id
        self.pack = pack
        self._render()
        if switched:
            self.show_section("overview")

    def _on_pack_updated(self, pack_id: str) -> None:
        if self.pack is not None and pack_id == self.pack.id:
            fresh = self.ctl.load_pack(pack_id)
            if fresh is not None:
                self.pack = fresh
            self._render()

    def _render_header(self) -> None:
        pack = self.pack
        if pack is None:
            return
        while self.badge_holder.count():
            item = self.badge_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.badge_holder.addWidget(loader_badge(pack.loader.value, size=52))
        self.title.setText(pack.name)
        lv = f" {pack.loader_version}" if pack.loader_version else ""
        self.subtitle.setText(f"{loader_label(pack.loader.value)}{lv} · Minecraft {pack.minecraft} · {t('library.mods_chip', count=len(pack.mods))}")
        running = self.ctl.registry.is_running(pack.id)
        self.server_chip.set(t("library.running_chip"), "success", dot_color=COLORS["success"])
        self.server_chip.setVisible(running)

    def _render(self) -> None:
        pack = self.pack
        if pack is None:
            return
        self._render_header()
        is_fabric = pack.loader == Loader.FABRIC
        is_vanilla = pack.loader == Loader.VANILLA
        self.rail_buttons["cheats"].setVisible(is_fabric)
        counts = {
            "mods": len([m for m in pack.mods if m.source not in CHEAT_SOURCES]),
            "shaderpack": len(pack.content_downloads_of(ContentKind.SHADERPACK)),
            "resourcepack": len(pack.content_downloads_of(ContentKind.RESOURCEPACK)),
            "datapack": len(pack.content_downloads_of(ContentKind.DATAPACK)),
            "world": len(pack.content_of(ContentKind.WORLD)),
            "cheats": len([m for m in pack.mods if m.source in CHEAT_SOURCES]),
        }
        glyphs = dict(SECTIONS)
        for key, b in self.rail_buttons.items():
            text = f"{glyphs[key]}   {t(f'pack.section.{key}')}"
            if counts.get(key):
                text += f"   ·  {counts[key]}"
            b.setText(text)
        self.rail_buttons["mods"].setEnabled(not is_vanilla or counts["mods"] > 0)
        self.overview.show_pack(pack)
        self.mods.show_pack(pack)
        self.cheats.show_pack(pack)
        for tab in self.content_tabs.values():
            tab.show_pack(pack)
        self.discover.set_pack(pack)
        self.server.set_pack(pack)
        if not is_fabric and self.current_section() == "cheats":
            self.show_section("overview")

    def _show_more(self) -> None:
        if self.pack is not None:
            menu = pack_actions.context_menu(self, self.ctl, self.pack, include_open=False)
            menu.exec(self.more_btn.mapToGlobal(self.more_btn.rect().bottomLeft()))
