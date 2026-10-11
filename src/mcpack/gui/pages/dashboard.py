"""Ana Sayfa: genel durum özeti — istatistikler, son düzenlenen pack'ler,
çalışan sunucular, sistem sağlığı ve hızlı eylemler."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from mcpack.gui.components import (
    Card,
    Chip,
    StatTile,
    button,
    clear_layout,
    label,
    loader_badge,
)
from mcpack.gui.controller import AppController
from mcpack.gui.dialogs import NewPackDialog
from mcpack.gui.formatting import format_duration, format_relative, loader_label
from mcpack.gui.theme import COLORS
from mcpack.i18n import t
from mcpack.logging_setup import EXCEPTIONS, MEMORY_HANDLER, NETWORK
from mcpack.server_runtime import find_java


class DashboardPage(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(t("dash.title"), role="title"))
        col.addWidget(label(t("dash.subtitle"), role="muted"))
        head.addLayout(col, 1)
        head.addWidget(button(t("dash.open_palette"), variant="ghost", on_click=lambda: ctl.navigate.emit("palette", "")))
        head.addWidget(button(t("library.new_pack"), variant="primary", on_click=self._new_pack))
        outer.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tile_packs = StatTile(t("dash.tile_packs"))
        self.tile_mods = StatTile(t("dash.tile_mods"))
        self.tile_servers = StatTile(t("dash.tile_servers"), accent=COLORS["success"])
        self.tile_tasks = StatTile(t("dash.tile_tasks"))
        self.tile_errors = StatTile(t("dash.tile_errors"), clickable=True)
        for tile in (self.tile_packs, self.tile_mods, self.tile_servers, self.tile_tasks, self.tile_errors):
            tiles.addWidget(tile)
        self.tile_errors.clicked.connect(lambda: ctl.navigate.emit("debug", "exceptions"))
        outer.addLayout(tiles)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        self.recent_card = Card()
        self.recent_card.body.addWidget(label(t("dash.recent"), role="h3"))
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(6)
        self.recent_card.body.addLayout(self.recent_list)
        self.recent_card.body.addStretch()
        grid.addWidget(self.recent_card, 0, 0, 2, 1)

        self.servers_card = Card()
        self.servers_card.body.addWidget(label(t("dash.running_servers"), role="h3"))
        self.servers_list = QVBoxLayout()
        self.servers_list.setSpacing(6)
        self.servers_card.body.addLayout(self.servers_list)
        self.servers_card.body.addStretch()
        grid.addWidget(self.servers_card, 0, 1)

        self.health_card = Card()
        self.health_card.body.addWidget(label(t("dash.health"), role="h3"))
        self.health_list = QVBoxLayout()
        self.health_list.setSpacing(6)
        self.health_card.body.addLayout(self.health_list)
        self.health_card.body.addWidget(
            button(t("dash.run_diagnostics"), variant="ghost", on_click=lambda: ctl.navigate.emit("debug", "system"))
        )
        grid.addWidget(self.health_card, 1, 1)

        quick = Card()
        quick.body.addWidget(label(t("dash.quick"), role="h3"))
        qrow = QHBoxLayout()
        qrow.setSpacing(8)
        qrow.addWidget(button(t("dash.quick_library"), on_click=lambda: ctl.navigate.emit("library", "")))
        qrow.addWidget(button(t("dash.quick_settings"), on_click=lambda: ctl.navigate.emit("settings", "")))
        self.web_btn = button(t("dash.quick_web_panel"), on_click=ctl.toggle_web_panel)
        qrow.addWidget(self.web_btn)
        qrow.addWidget(button(t("dash.quick_debug"), on_click=lambda: ctl.navigate.emit("debug", "")))
        qrow.addStretch()
        quick.body.addLayout(qrow)
        grid.addWidget(quick, 2, 0, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        outer.addLayout(grid)
        outer.addStretch()

        ctl.packs_changed.connect(self.refresh)
        ctl.pack_updated.connect(lambda _p: self.refresh())
        ctl.server_changed.connect(lambda _p: self.refresh())
        ctl.settings_changed.connect(self.refresh)
        ctl.web_panel_changed.connect(lambda *_a: self._refresh_web_btn())
        ctl.tasks.active_count_changed.connect(lambda _n: self._refresh_counters())
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.refresh()

    def _new_pack(self) -> None:
        dialog = NewPackDialog(self.ctl.tasks, self)
        if dialog.exec():
            pack = self.ctl.create_pack(dialog.values())
            self.ctl.navigate.emit("pack", pack.id)

    def _tick(self) -> None:
        if self.isVisible():
            self._refresh_counters()
            self._refresh_servers()

    def _refresh_web_btn(self) -> None:
        self.web_btn.setText(t("dash.quick_web_panel_stop") if self.ctl.web_panel_running else t("dash.quick_web_panel"))

    def _refresh_counters(self) -> None:
        active = self.ctl.tasks.active_count()
        self.tile_tasks.set_value(str(active), t("dash.tasks_hint", total=len(self.ctl.tasks.tasks())))
        exc = EXCEPTIONS.snapshot()
        errors = len(MEMORY_HANDLER.snapshot(min_level=40))
        self.tile_errors.set_value(str(len(exc)), t("dash.errors_hint", logs=errors, net=NETWORK.stats()["failed"]))
        self.tile_errors.value_label.setStyleSheet(f"color: {COLORS['danger'] if exc else COLORS['text']};")

    def refresh(self) -> None:
        packs = self.ctl.list_packs()
        self.tile_packs.set_value(str(len(packs)))
        self.tile_mods.set_value(str(sum(len(p.mods) for p in packs)))
        self._refresh_counters()
        self._refresh_web_btn()

        clear_layout(self.recent_list)
        recent = sorted(packs, key=lambda p: p.updated_at, reverse=True)[:6]
        if not recent:
            self.recent_list.addWidget(label(t("dash.no_packs"), role="muted"))
        for pack in recent:
            row = Card(hover=True, padding=10, spacing=0)
            line = QHBoxLayout()
            line.setSpacing(10)
            line.addWidget(loader_badge(pack.loader.value, size=32))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(pack.name, role="h3"))
            col.addWidget(label(f"{loader_label(pack.loader.value)} · MC {pack.minecraft} · {t('library.mods_chip', count=len(pack.mods))}", role="dim"))
            line.addLayout(col, 1)
            line.addWidget(label(format_relative(pack.updated_at), role="dim"))
            row.body.addLayout(line)
            row.clicked.connect(lambda pid=pack.id: self.ctl.navigate.emit("pack", pid))
            self.recent_list.addWidget(row)
        self._refresh_servers()
        self._refresh_health()

    def _refresh_servers(self) -> None:
        running = self.ctl.running_server_ids()
        self.tile_servers.set_value(str(len(running)))
        clear_layout(self.servers_list)
        if not running:
            self.servers_list.addWidget(label(t("dash.no_running_servers"), role="muted", wrap=True))
            return
        for pid in running:
            pack = self.ctl.load_pack(pid)
            if pack is None:
                continue
            started = self.ctl.server_started_at.get(pid)
            row = QHBoxLayout()
            row.addWidget(Chip("", "success", dot_color=COLORS["success"]))
            row.addWidget(label(pack.name, role="h3"), 1)
            row.addWidget(label(format_duration(time.time() - started) if started else "", role="dim"))
            row.addWidget(button(t("dash.open"), variant="ghost", on_click=lambda p=pid: self.ctl.navigate.emit("server", p)))
            row.addWidget(button(t("server.stop"), variant="danger", on_click=lambda p=pid: self.ctl.stop_server(p)))
            self.servers_list.addLayout(row)

    def _refresh_health(self) -> None:
        clear_layout(self.health_list)
        java = find_java(self.ctl.settings.java_path)
        checks = [
            (bool(java), t("dash.health_java_ok", path=java) if java else t("dash.health_java_missing")),
            (self.ctl.has_curseforge(), t("dash.health_cf_ok") if self.ctl.has_curseforge() else t("dash.health_cf_missing")),
            (bool(self.ctl.settings.sklauncher_path), t("dash.health_sk_ok") if self.ctl.settings.sklauncher_path else t("dash.health_sk_missing")),
        ]
        for ok, text in checks:
            row = QHBoxLayout()
            dot = label("●")
            dot.setStyleSheet(f"color: {COLORS['success'] if ok else COLORS['warning']};")
            row.addWidget(dot)
            row.addWidget(label(text, role="muted", wrap=True), 1)
            self.health_list.addLayout(row)
