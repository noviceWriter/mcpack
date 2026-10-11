"""Kütüphane: tüm pack'ler — kart ızgarası ya da liste görünümü, arama,
loader filtresi, sıralama, sağ tık menüsü."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui import pack_actions
from mcpack.gui.components import (
    Card,
    Chip,
    EmptyState,
    FlowLayout,
    SearchField,
    button,
    clear_layout,
    label,
    loader_badge,
    tool_button,
)
from mcpack.gui.controller import AppController
from mcpack.gui.dialogs import NewPackDialog
from mcpack.gui.formatting import format_relative, loader_label
from mcpack.gui.theme import COLORS
from mcpack.i18n import t
from mcpack.models import Loader, Pack

CARD_WIDTH = 300


class PackCard(Card):
    def __init__(self, ctl: AppController, pack: Pack, *, running: bool, list_mode: bool) -> None:
        super().__init__(hover=True, padding=14, spacing=10)
        self.ctl = ctl
        self.pack = pack
        if not list_mode:
            self.setFixedWidth(CARD_WIDTH)
        self.clicked.connect(lambda: ctl.navigate.emit("pack", pack.id))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: pack_actions.context_menu(self, ctl, pack).exec(self.mapToGlobal(pos))
        )

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(loader_badge(pack.loader.value, size=44))
        col = QVBoxLayout()
        col.setSpacing(1)
        name = label(pack.name, role="h3")
        name.setToolTip(pack.summary or pack.name)
        col.addWidget(name)
        loader_text = loader_label(pack.loader.value)
        if pack.loader_version:
            loader_text += f" {pack.loader_version}"
        col.addWidget(label(f"{loader_text} · MC {pack.minecraft}", role="dim"))
        top.addLayout(col, 1)
        menu_btn = tool_button("⋯", tooltip=t("library.more"))
        menu_btn.setMenu(pack_actions.context_menu(self, ctl, pack))
        top.addWidget(menu_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(top)

        if pack.summary and not list_mode:
            summary = label(pack.summary, role="muted", wrap=True)
            summary.setMaximumHeight(36)
            self.body.addWidget(summary)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(Chip(t("library.mods_chip", count=len(pack.mods)), "accent"))
        content = len(pack.content_downloads) + len(pack.content)
        if content:
            chips.addWidget(Chip(t("library.content_chip", count=content), "neutral"))
        if running:
            chips.addWidget(Chip(t("library.running_chip"), "success", dot_color=COLORS["success"]))
        chips.addStretch()
        if list_mode:
            chips.addWidget(label(t("library.updated", when=format_relative(pack.updated_at)), role="dim"))
        self.body.addLayout(chips)
        if not list_mode:
            self.body.addWidget(label(t("library.updated", when=format_relative(pack.updated_at)), role="dim"))


class LibraryPage(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        self._packs: list[Pack] = []
        self._list_mode = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(16)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(t("library.title"), role="title"))
        self.count_label = label("", role="muted")
        col.addWidget(self.count_label)
        head.addLayout(col, 1)
        head.addWidget(button(t("library.import"), on_click=lambda: pack_actions.import_modpack(self, ctl), tooltip=t("library.import_tooltip")))
        head.addWidget(button(t("library.new_pack"), variant="primary", on_click=self.new_pack))
        outer.addLayout(head)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = SearchField(t("library.search_placeholder"), delay_ms=120)
        self.search.setMinimumWidth(260)
        self.search.search.connect(lambda _q: self._render())
        bar.addWidget(self.search)
        self.loader_group = QButtonGroup(self)
        self.loader_group.setExclusive(True)
        for value, text in [("", t("library.filter_all"))] + [(l.value, loader_label(l.value)) for l in Loader]:
            chip = button(text, variant="chip", checkable=True)
            chip.setProperty("loader", value)
            chip.setChecked(value == "")
            self.loader_group.addButton(chip)
            bar.addWidget(chip)
        self.loader_group.buttonToggled.connect(lambda _b, checked: checked and self._render())
        bar.addStretch()
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(t("library.sort_updated"), "updated")
        self.sort_combo.addItem(t("library.sort_name"), "name")
        self.sort_combo.addItem(t("library.sort_mods"), "mods")
        self.sort_combo.addItem(t("library.sort_mc"), "mc")
        self.sort_combo.currentIndexChanged.connect(lambda _i: self._render())
        bar.addWidget(self.sort_combo)
        self.view_toggle = button("☰", variant="ghost", tooltip=t("library.toggle_view"), on_click=self._toggle_view)
        bar.addWidget(self.view_toggle)
        outer.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll, 1)

        self.empty = EmptyState(
            "📦", t("library.empty_title"), t("library.empty_sub"),
            actions=[button(t("library.new_pack"), variant="primary", on_click=self.new_pack)],
        )
        outer.addWidget(self.empty, 1)
        self.no_match = EmptyState("🔍", t("library.no_match_title"), t("library.no_match_sub"))
        outer.addWidget(self.no_match, 1)

        ctl.packs_changed.connect(self.refresh)
        ctl.pack_updated.connect(lambda _pid: self.refresh())
        ctl.server_changed.connect(lambda _pid: self._render())
        self.refresh()

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def new_pack(self) -> None:
        dialog = NewPackDialog(self.ctl.tasks, self)
        if dialog.exec():
            pack = self.ctl.create_pack(dialog.values())
            self.ctl.navigate.emit("pack", pack.id)

    def refresh(self) -> None:
        self._packs = self.ctl.list_packs()
        self._render()

    def _toggle_view(self) -> None:
        self._list_mode = not self._list_mode
        self.view_toggle.setText("▦" if self._list_mode else "☰")
        self._render()

    def _visible(self) -> list[Pack]:
        q = self.search.text().strip().lower()
        loader = self.loader_group.checkedButton().property("loader") if self.loader_group.checkedButton() else ""
        packs = [
            p for p in self._packs
            if (not q or q in p.name.lower() or q in p.minecraft or q in (p.summary or "").lower())
            and (not loader or p.loader.value == loader)
        ]
        key = self.sort_combo.currentData()
        if key == "name":
            packs.sort(key=lambda p: p.name.lower())
        elif key == "mods":
            packs.sort(key=lambda p: len(p.mods), reverse=True)
        elif key == "mc":
            packs.sort(key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p.minecraft.split(".")), reverse=True)
        else:
            packs.sort(key=lambda p: p.updated_at, reverse=True)
        return packs

    def _render(self) -> None:
        total = len(self._packs)
        mods = sum(len(p.mods) for p in self._packs)
        self.count_label.setText(t("library.count", count=total, mods=mods))
        visible = self._visible()
        self.empty.setVisible(total == 0)
        self.no_match.setVisible(total > 0 and not visible)
        self.scroll.setVisible(bool(visible))

        clear_layout(self.container_layout)
        running = set(self.ctl.running_server_ids())
        holder = QWidget()
        if self._list_mode:
            layout = QVBoxLayout(holder)
            layout.setContentsMargins(0, 0, 8, 0)
            layout.setSpacing(8)
        else:
            layout = FlowLayout(holder, spacing=14)
        for pack in visible:
            layout.addWidget(PackCard(self.ctl, pack, running=pack.id in running, list_mode=self._list_mode))
        self.container_layout.addWidget(holder)
        self.container_layout.addStretch()
