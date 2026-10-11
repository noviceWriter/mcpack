"""Pack'in yerel sunucusu: hazırla/kur/başlat/durdur, canlı konsol,
oyuncular, çalışma ayarları, server.properties.

Konsol özellikleri: seviye renklendirme (INFO/WARN/ERROR + sohbet + giriş/
çıkış), seviye filtresi, vurgulamalı arama (sonraki/önceki, eşleşme sayısı),
otomatik kaydırma, satır kaydırma, kopyala/kaydet, ↑/↓ komut geçmişi,
vanilla komutları için otomatik tamamlama, hızlı komut düğmeleri. Yüksek
hacimli çıktıda arayüzü kilitlememek için satırlar 80 ms'lik partiler
halinde eklenir.
"""

from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QStringListModel, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mcpack.export.server import filter_server_mods
from mcpack.gui import pack_actions
from mcpack.gui.components import (
    Card,
    Chip,
    EmptyState,
    button,
    confirm,
    label,
    tool_button,
)
from mcpack.gui.controller import AppController
from mcpack.gui.formatting import format_duration
from mcpack.gui.theme import COLORS, mono_font
from mcpack.i18n import t
from mcpack.models import ContentKind, Pack
from mcpack.server_properties import KNOWN_PROPERTIES
from mcpack.server_runtime import (
    SYSTEM_MEMORY_RESERVE_MB,
    categorize_inventory_slot,
    get_system_memory_mb,
    max_safe_server_memory_mb,
)

CONSOLE_MAX_LINES = 10000
FLUSH_MS = 80
PLAYER_POLL_MS = 5000
GB_PRESETS = [1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32]

_LEVEL_RE = re.compile(r"(?:/|\s)(INFO|WARN|WARNING|ERROR|FATAL|SEVERE)\]")
_CHAT_RE = re.compile(r"\]:?\s*<[^>]+>")
_JOIN_RE = re.compile(r"joined the game|left the game|lost connection")

VANILLA_COMMANDS = [
    "advancement", "ban", "ban-ip", "banlist", "bossbar", "clear", "clone", "damage", "data", "datapack",
    "debug", "defaultgamemode", "deop", "difficulty", "effect", "enchant", "execute", "experience", "fill",
    "forceload", "function", "gamemode", "gamerule", "give", "help", "item", "kick", "kill", "list", "locate",
    "loot", "me", "msg", "op", "pardon", "pardon-ip", "particle", "perf", "place", "playsound", "recipe",
    "reload", "save-all", "save-off", "save-on", "say", "schedule", "scoreboard", "seed", "setblock",
    "setidletimeout", "setworldspawn", "spawnpoint", "spectate", "spreadplayers", "stop", "stopsound",
    "summon", "tag", "team", "teammsg", "teleport", "tell", "tellraw", "time set day", "time set night",
    "title", "tp", "trigger", "weather clear", "weather rain", "weather thunder", "whitelist add",
    "whitelist remove", "whitelist list", "whitelist on", "whitelist off", "worldborder", "xp",
]
QUICK_COMMANDS = [
    ("☀", "time set day"), ("☾", "time set night"), ("⛅", "weather clear"),
    ("💾", "save-all"), ("👥", "list"), ("☮", "difficulty peaceful"),
]

_FILTERS = {"all": 0, "warn": 1, "error": 2}


def _line_level(text: str) -> int:
    """0 = normal, 1 = uyarı, 2 = hata."""
    m = _LEVEL_RE.search(text)
    if m:
        lvl = m.group(1)
        if lvl in ("ERROR", "FATAL", "SEVERE"):
            return 2
        if lvl in ("WARN", "WARNING"):
            return 1
        return 0
    if text.startswith(("Exception", "Caused by", "\tat ", "java.")):
        return 2
    return 0


def _line_color(text: str) -> str | None:
    level = _line_level(text)
    if level == 2:
        return COLORS["danger"]
    if level == 1:
        return COLORS["warning"]
    if _CHAT_RE.search(text):
        return COLORS["accent_hover"]
    if _JOIN_RE.search(text):
        return COLORS["success"]
    if text.startswith("> "):
        return COLORS["info"]
    return None


class _CommandInput(QLineEdit):
    def __init__(self) -> None:
        super().__init__()
        self.history: list[str] = []
        self._index = 0
        completer = QCompleter(QStringListModel(VANILLA_COMMANDS), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.InlineCompletion)
        self.setCompleter(completer)

    def remember(self, text: str) -> None:
        if not self.history or self.history[-1] != text:
            self.history.append(text)
        self._index = len(self.history)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Up and self.history:
            self._index = max(0, self._index - 1)
            self.setText(self.history[self._index])
            return
        if event.key() == Qt.Key.Key_Down and self.history:
            self._index = min(len(self.history), self._index + 1)
            self.setText(self.history[self._index] if self._index < len(self.history) else "")
            return
        super().keyPressEvent(event)


class ConsoleView(QWidget):
    def __init__(self, panel: "ServerPanel") -> None:
        super().__init__()
        self.panel = panel
        self.lines: deque[str] = deque(maxlen=CONSOLE_MAX_LINES)
        self._pending: list[str] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(FLUSH_MS)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(t("console.filter_all"), "all")
        self.filter_combo.addItem(t("console.filter_warn"), "warn")
        self.filter_combo.addItem(t("console.filter_error"), "error")
        self.filter_combo.currentIndexChanged.connect(lambda _i: self._rerender())
        bar.addWidget(self.filter_combo)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(t("console.find_placeholder"))
        self.find_input.setClearButtonEnabled(True)
        self.find_input.returnPressed.connect(lambda: self._find(forward=True))
        self.find_input.textChanged.connect(lambda _t: self._highlight())
        bar.addWidget(self.find_input, 1)
        bar.addWidget(button("▲", variant="ghost", tooltip=t("console.find_prev"), on_click=lambda: self._find(forward=False)))
        bar.addWidget(button("▼", variant="ghost", tooltip=t("console.find_next"), on_click=lambda: self._find(forward=True)))
        self.match_label = label("", role="dim")
        bar.addWidget(self.match_label)
        self.autoscroll = QCheckBox(t("console.autoscroll"))
        self.autoscroll.setChecked(True)
        bar.addWidget(self.autoscroll)
        self.wrap = QCheckBox(t("console.wrap"))
        self.wrap.toggled.connect(
            lambda on: self.view.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.WidgetWidth if on else QPlainTextEdit.LineWrapMode.NoWrap
            )
        )
        bar.addWidget(self.wrap)
        more = tool_button("⋯", tooltip=t("console.more"))
        from PySide6.QtWidgets import QMenu

        menu = QMenu(more)
        menu.addAction(t("console.copy_all"), self._copy)
        menu.addAction(t("console.save"), self._save)
        menu.addAction(t("console.clear"), self.clear)
        more.setMenu(menu)
        bar.addWidget(more)
        outer.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setProperty("variant", "console")
        self.view.setReadOnly(True)
        self.view.setFont(mono_font(10))
        self.view.setMaximumBlockCount(CONSOLE_MAX_LINES)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setUndoRedoEnabled(False)
        outer.addWidget(self.view, 1)

        quick = QHBoxLayout()
        quick.setSpacing(4)
        quick.addWidget(label(t("console.quick"), role="dim"))
        self._quick_buttons = []
        for glyph, cmd in QUICK_COMMANDS:
            b = button(f"{glyph} {cmd}", variant="chip", on_click=lambda c=cmd: self.panel.send(c))
            self._quick_buttons.append(b)
            quick.addWidget(b)
        quick.addStretch()
        outer.addLayout(quick)

        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(8)
        prompt = label("›")
        prompt.setStyleSheet(f"color: {COLORS['accent']}; font-size: 18px; font-weight: 700;")
        cmd_row.addWidget(prompt)
        self.command = _CommandInput()
        self.command.setFont(mono_font(10))
        self.command.setPlaceholderText(t("console.command_placeholder"))
        self.command.returnPressed.connect(self._send)
        cmd_row.addWidget(self.command, 1)
        self.send_btn = button(t("console.send"), variant="primary", on_click=self._send)
        cmd_row.addWidget(self.send_btn)
        outer.addLayout(cmd_row)

    # -- içerik ----------------------------------------------------------------------

    def set_enabled_input(self, running: bool) -> None:
        self.command.setEnabled(running)
        self.send_btn.setEnabled(running)
        for b in self._quick_buttons:
            b.setEnabled(running)

    def reset(self, lines: list[str]) -> None:
        self._pending.clear()
        self.lines.clear()
        self.lines.extend(lines)
        self._rerender()

    def clear(self) -> None:
        self._pending.clear()
        self.lines.clear()
        self.view.clear()
        self.match_label.setText("")

    def append(self, line: str) -> None:
        self._pending.append(line)

    def _passes(self, line: str) -> bool:
        need = _FILTERS[self.filter_combo.currentData()]
        return need == 0 or _line_level(line) >= need

    def _write(self, lines: list[str]) -> None:
        cursor = QTextCursor(self.view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        default = QTextCharFormat()
        default.setForeground(QColor("#cfd6e4"))
        for line in lines:
            if not self._passes(line):
                continue
            color = _line_color(line)
            fmt = default
            if color:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(color))
            if not self.view.document().isEmpty():
                cursor.insertBlock()
            cursor.insertText(line, fmt)
        cursor.endEditBlock()

    def _flush(self) -> None:
        if not self._pending:
            return
        batch, self._pending = self._pending, []
        self.lines.extend(batch)
        bar = self.view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self._write(batch)
        if self.autoscroll.isChecked() and at_bottom or self.autoscroll.isChecked() and not self.isVisible():
            bar.setValue(bar.maximum())

    def _rerender(self) -> None:
        self.view.clear()
        self._write(list(self.lines))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
        self._highlight()

    # -- arama -----------------------------------------------------------------------

    def _highlight(self) -> None:
        text = self.find_input.text()
        selections = []
        if text:
            doc = self.view.document()
            cursor = QTextCursor(doc)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(COLORS["warning_soft"]))
            fmt.setForeground(QColor(COLORS["warning"]))
            count = 0
            while count < 2000:
                cursor = doc.find(text, cursor)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format = fmt
                selections.append(sel)
                count += 1
            self.match_label.setText(t("console.matches", count=count) if count < 2000 else "2000+")
        else:
            self.match_label.setText("")
        self.view.setExtraSelections(selections)

    def _find(self, *, forward: bool) -> None:
        text = self.find_input.text()
        if not text:
            return
        flags = QTextDocument.FindFlag(0) if forward else QTextDocument.FindFlag.FindBackward
        if not self.view.find(text, flags):
            cursor = self.view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start if forward else QTextCursor.MoveOperation.End)
            self.view.setTextCursor(cursor)
            self.view.find(text, flags)
        self.autoscroll.setChecked(False)

    # -- eylemler --------------------------------------------------------------------

    def _send(self) -> None:
        text = self.command.text().strip().lstrip("/")
        if not text:
            return
        self.command.remember(text)
        self.command.clear()
        self.panel.send(text)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(self.lines))
        self.panel.ctl.notify.emit("info", t("console.copied", count=len(self.lines)))

    def _save(self) -> None:
        name = f"{self.panel.pack.name if self.panel.pack else 'server'}-console-{time.strftime('%Y%m%d-%H%M%S')}.log"
        path, _ = QFileDialog.getSaveFileName(self, t("console.save"), name, "*.log *.txt")
        if path:
            Path(path).write_text("\n".join(self.lines) + "\n", encoding="utf-8")
            self.panel.ctl.notify.emit("success", t("console.saved", path=path))


class PlayersView(QWidget):
    def __init__(self, panel: "ServerPanel") -> None:
        super().__init__()
        self.panel = panel
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        left = Card(padding=12)
        left.setFixedWidth(230)
        self.count_label = label(t("players.online", count=0), role="h3")
        left.body.addWidget(self.count_label)
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._on_selected)
        left.body.addWidget(self.list, 1)
        left.body.addWidget(button(t("players.refresh"), on_click=lambda: panel.poll_players(force=True)))
        self.last_poll = label("", role="dim")
        left.body.addWidget(self.last_poll)
        outer.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right = QWidget()
        right_scroll.setWidget(right)
        col = QVBoxLayout(right)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        self.selected_label = label(t("players.select"), role="h2")
        col.addWidget(self.selected_label)

        actions = Card(padding=14)
        actions.body.addWidget(label(t("players.actions"), role="h3"))
        row1 = QHBoxLayout()
        self.action_buttons = []
        for key, variant in (("heal", None), ("feed", None), ("kill", "danger")):
            b = button(t(f"player.action.{key}"), variant=variant, on_click=lambda k=key: self._act(k))
            self.action_buttons.append(b)
            row1.addWidget(b)
        row1.addStretch()
        actions.body.addLayout(row1)
        row2 = QHBoxLayout()
        self.damage_spin = QSpinBox()
        self.damage_spin.setRange(1, 1000)
        self.damage_spin.setValue(4)
        self.damage_spin.setSuffix(" HP")
        b = button(t("player.action.damage"), on_click=lambda: self._act("damage", self.damage_spin.value()))
        self.action_buttons.append(b)
        row2.addWidget(b)
        row2.addWidget(self.damage_spin)
        row2.addSpacing(16)
        self.hunger_spin = QSpinBox()
        self.hunger_spin.setRange(5, 300)
        self.hunger_spin.setValue(30)
        self.hunger_spin.setSuffix(" s")
        b = button(t("player.action.hunger"), on_click=lambda: self._act("hunger", self.hunger_spin.value()))
        b.setToolTip(t("players.hunger_tooltip"))
        self.action_buttons.append(b)
        row2.addWidget(b)
        row2.addWidget(self.hunger_spin)
        row2.addStretch()
        actions.body.addLayout(row2)
        quick = QHBoxLayout()
        for text, template in (
            (t("players.op"), "op {p}"), (t("players.deop"), "deop {p}"),
            (t("players.gm_creative"), "gamemode creative {p}"), (t("players.gm_survival"), "gamemode survival {p}"),
            (t("players.kick"), "kick {p}"),
        ):
            b = button(text, variant="chip", on_click=lambda tpl=template: self._raw(tpl))
            self.action_buttons.append(b)
            quick.addWidget(b)
        quick.addStretch()
        actions.body.addLayout(quick)
        col.addWidget(actions)

        for which in ("inventory", "ender"):
            card = Card(padding=14)
            head = QHBoxLayout()
            head.addWidget(label(t(f"players.{which}_title"), role="h3"), 1)
            b = button(t("players.view"), on_click=lambda w=which: self._query(w))
            self.action_buttons.append(b)
            head.addWidget(b)
            card.body.addLayout(head)
            table = QTableWidget(0, 3)
            table.setHorizontalHeaderLabels([t("players.col_slot"), t("players.col_item"), t("players.col_count")])
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setMinimumHeight(170)
            card.body.addWidget(table)
            setattr(self, f"{which}_table", table)
            col.addWidget(card)
        col.addStretch()
        outer.addWidget(right_scroll, 1)
        self._update_enabled()

    def player(self) -> str | None:
        item = self.list.currentItem()
        return item.text() if item else None

    def set_players(self, names: list[str]) -> None:
        current = self.player()
        self.list.clear()
        self.list.addItems(names)
        self.count_label.setText(t("players.online", count=len(names)))
        self.last_poll.setText(t("players.updated", time=time.strftime("%H:%M:%S")))
        if current in names:
            self.list.setCurrentRow(names.index(current))
        self._update_enabled()

    def clear(self) -> None:
        self.list.clear()
        self.count_label.setText(t("players.online", count=0))
        for table in (self.inventory_table, self.ender_table):
            table.setRowCount(0)
        self._update_enabled()

    def _on_selected(self, name: str) -> None:
        self.selected_label.setText(name or t("players.select"))
        self.inventory_table.setRowCount(0)
        self.ender_table.setRowCount(0)
        self._update_enabled()

    def _update_enabled(self) -> None:
        enabled = self.player() is not None and self.panel.running
        for b in self.action_buttons:
            b.setEnabled(enabled)

    def _act(self, action: str, value: int = 0) -> None:
        player = self.player()
        if not player or self.panel.pack is None:
            return
        if action == "kill" and not confirm(self, t("players.kill_title"), t("players.kill_confirm", player=player), danger=True):
            return
        self.panel.ctl.player_action(self.panel.pack, action, player, value)

    def _raw(self, template: str) -> None:
        player = self.player()
        if player:
            self.panel.send(template.format(p=player))

    def _query(self, which: str) -> None:
        player = self.player()
        if not player or self.panel.pack is None:
            return
        table = self.inventory_table if which == "inventory" else self.ender_table

        def done(items) -> None:
            table.setRowCount(len(items))
            for row, item in enumerate(items):
                slot = categorize_inventory_slot(item.slot) if which == "inventory" else str(item.slot)
                table.setItem(row, 0, QTableWidgetItem(slot))
                table.setItem(row, 1, QTableWidgetItem(item.item_id.removeprefix("minecraft:")))
                table.setItem(row, 2, QTableWidgetItem(str(item.count)))

        self.panel.ctl.query_items(self.panel.pack.id, player, "inventory" if which == "inventory" else "ender", done)


class RuntimeSettingsView(QScrollArea):
    def __init__(self, panel: "ServerPanel") -> None:
        super().__init__()
        self.panel = panel
        self.setWidgetResizable(True)
        body = QWidget()
        self.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(12)

        card = Card(padding=16)
        card.body.addWidget(label(t("srvset.title"), role="h3"))
        form = QFormLayout()
        form.setSpacing(10)
        total = get_system_memory_mb()
        self._max_safe = max_safe_server_memory_mb(total)
        mem_row = QHBoxLayout()
        self.mem_combo = QComboBox()
        for gb in GB_PRESETS:
            if self._max_safe is None or gb * 1024 <= self._max_safe:
                self.mem_combo.addItem(f"{gb} GB", gb * 1024)
        self.mem_combo.addItem(t("srvset.memory_custom"), "custom")
        self.mem_combo.currentIndexChanged.connect(self._on_mem_preset)
        mem_row.addWidget(self.mem_combo)
        self.mem_spin = QSpinBox()
        self.mem_spin.setRange(512, self._max_safe or 131072)
        self.mem_spin.setSingleStep(256)
        self.mem_spin.setSuffix(" MB")
        self.mem_spin.editingFinished.connect(self._save)
        mem_row.addWidget(self.mem_spin)
        mem_row.addStretch()
        form.addRow(t("srvset.memory"), mem_row)
        if total and self._max_safe:
            hint = t("srvset.memory_hint", total=f"{total / 1024:.1f}", max=f"{self._max_safe / 1024:.1f}", reserve=f"{SYSTEM_MEMORY_RESERVE_MB / 1024:.0f}")
        else:
            hint = t("srvset.memory_unknown")
        form.addRow("", label(hint, role="dim", wrap=True))
        self.world_combo = QComboBox()
        self.world_combo.currentIndexChanged.connect(lambda _i: self._save())
        form.addRow(t("srvset.world"), self.world_combo)
        self.flags = QCheckBox(t("srvset.flags"))
        self.flags.setToolTip(t("srvset.flags_tooltip"))
        self.flags.toggled.connect(lambda _c: self._save())
        form.addRow("", self.flags)
        card.body.addLayout(form)
        self.saved_label = label("", role="dim")
        card.body.addWidget(self.saved_label)
        col.addWidget(card)

        eula = Card(padding=16)
        eula.body.addWidget(label("Minecraft EULA", role="h3"))
        self.eula_label = label("", role="muted", wrap=True)
        eula.body.addWidget(self.eula_label)
        row = QHBoxLayout()
        self.eula_btn = button(t("srvset.eula_accept"), variant="primary", on_click=self._accept_eula)
        row.addWidget(self.eula_btn)
        row.addWidget(button(t("srvset.eula_read"), variant="ghost", on_click=self._open_eula))
        row.addStretch()
        eula.body.addLayout(row)
        col.addWidget(eula)
        col.addStretch()
        self._loading = False

    def show_pack(self, pack: Pack) -> None:
        self._loading = True
        try:
            idx = self.mem_combo.findData(pack.server.memory_mb)
            self.mem_combo.setCurrentIndex(idx if idx >= 0 else self.mem_combo.findData("custom"))
            self.mem_spin.setValue(pack.server.memory_mb)
            self.mem_spin.setEnabled(self.mem_combo.currentData() == "custom")
            self.world_combo.clear()
            self.world_combo.addItem(t("srvset.no_world"), None)
            for w in pack.content_of(ContentKind.WORLD):
                self.world_combo.addItem(w.name, w.name)
            widx = self.world_combo.findData(pack.server.selected_world)
            self.world_combo.setCurrentIndex(widx if widx >= 0 else 0)
            self.flags.setChecked(pack.server.use_optimized_flags)
            accepted = pack.server.eula_accepted
            self.eula_label.setText(t("srvset.eula_accepted") if accepted else t("srvset.eula_pending"))
            self.eula_btn.setVisible(not accepted)
        finally:
            self._loading = False

    def _on_mem_preset(self) -> None:
        data = self.mem_combo.currentData()
        custom = data == "custom"
        self.mem_spin.setEnabled(custom)
        if not custom and data is not None:
            self.mem_spin.setValue(int(data))
            self._save()

    def _save(self) -> None:
        pack = self.panel.pack
        if self._loading or pack is None:
            return
        self.panel.ctl.update_server_config(
            pack, memory_mb=self.mem_spin.value(), selected_world=self.world_combo.currentData(),
            use_optimized_flags=self.flags.isChecked(),
        )
        self.saved_label.setText(t("srvset.saved", time=time.strftime("%H:%M:%S")))

    def _accept_eula(self) -> None:
        if self.panel.ask_eula():
            self.show_pack(self.panel.pack)

    def _open_eula(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://www.minecraft.net/eula"))


class PropertiesView(QWidget):
    def __init__(self, panel: "ServerPanel") -> None:
        super().__init__()
        self.panel = panel
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        bar = QHBoxLayout()
        self.raw_toggle = QCheckBox(t("props.raw_mode"))
        self.raw_toggle.toggled.connect(self._toggle_raw)
        bar.addWidget(self.raw_toggle)
        bar.addStretch()
        bar.addWidget(button(t("props.reload"), variant="ghost", on_click=self.load))
        bar.addWidget(button(t("props.save"), variant="primary", on_click=self.save))
        outer.addLayout(bar)
        self.note = label(t("props.note"), role="dim", wrap=True)
        outer.addWidget(self.note)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        form_body = QWidget()
        self.form = QFormLayout(form_body)
        self.form.setSpacing(10)
        self.widgets: dict[str, QWidget] = {}
        for prop in KNOWN_PROPERTIES:
            if prop.type == "bool":
                w = QCheckBox()
            elif prop.type == "choice":
                w = QComboBox()
                w.addItems(prop.choices)
            elif prop.type == "int":
                w = QSpinBox()
                w.setRange(0, 1_000_000)
            else:
                w = QLineEdit()
            self.widgets[prop.key] = w
            key_label = label(prop.key, role="dim")
            row = QVBoxLayout()
            row.setSpacing(0)
            row.addWidget(label(t(f"serverprop.{prop.key}.label")))
            row.addWidget(key_label)
            holder = QWidget()
            holder.setLayout(row)
            self.form.addRow(holder, w)
        self.form_scroll.setWidget(form_body)
        outer.addWidget(self.form_scroll, 1)

        self.raw = QPlainTextEdit()
        self.raw.setFont(mono_font(10))
        self.raw.setProperty("variant", "console")
        self.raw.hide()
        outer.addWidget(self.raw, 1)

    def _path(self) -> Path | None:
        pack = self.panel.pack
        return self.panel.ctl.manager.server_root(pack) / "server.properties" if pack else None

    def load(self) -> None:
        pack = self.panel.pack
        if pack is None:
            return
        values = self.panel.ctl.read_server_properties(pack)
        for key, w in self.widgets.items():
            v = values.get(key, "")
            if isinstance(w, QCheckBox):
                w.setChecked(v.lower() == "true")
            elif isinstance(w, QComboBox):
                w.setCurrentText(v)
            elif isinstance(w, QSpinBox):
                w.setValue(int(v) if v.lstrip("-").isdigit() else 0)
            else:
                w.setText(v)
        path = self._path()
        self.raw.setPlainText(path.read_text(encoding="utf-8") if path and path.exists() else "")

    def _toggle_raw(self, raw: bool) -> None:
        if raw:
            self.load()
        self.raw.setVisible(raw)
        self.form_scroll.setVisible(not raw)

    def save(self) -> None:
        pack = self.panel.pack
        if pack is None:
            return
        if self.raw_toggle.isChecked():
            path = self._path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.raw.toPlainText().rstrip("\n") + "\n", encoding="utf-8")
            self.panel.ctl.notify.emit("success", t("ctl.properties_saved"))
            self.load()
            return
        values = {}
        for key, w in self.widgets.items():
            if isinstance(w, QCheckBox):
                values[key] = "true" if w.isChecked() else "false"
            elif isinstance(w, QComboBox):
                values[key] = w.currentText()
            elif isinstance(w, QSpinBox):
                values[key] = str(w.value())
            else:
                values[key] = w.text()
        self.panel.ctl.save_server_properties(pack, values)


class BackupsView(QWidget):
    INTERVALS = [0, 15, 30, 60, 120, 240]

    def __init__(self, panel: "ServerPanel") -> None:
        super().__init__()
        self.panel = panel
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.backup_btn = button(t("backups.now"), variant="primary", on_click=self._backup)
        self.restore_btn = button(t("backups.restore"), on_click=self._restore)
        self.delete_btn = button(t("backups.delete"), variant="danger", on_click=self._delete)
        for b in (self.backup_btn, self.restore_btn, self.delete_btn):
            bar.addWidget(b)
        bar.addWidget(button(t("backups.open_folder"), variant="ghost", on_click=self._open_folder))
        bar.addStretch()
        self.summary = label("", role="dim")
        bar.addWidget(self.summary)
        outer.addLayout(bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([t("backups.col.date"), t("backups.col.kind"), t("backups.col.size")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 110)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        outer.addWidget(self.table, 1)
        self.empty = label(t("backups.empty"), role="muted", wrap=True)
        outer.addWidget(self.empty)

        card = Card(padding=14)
        card.body.addWidget(label(t("backups.auto_title"), role="h3"))
        form = QFormLayout()
        self.interval = QComboBox()
        for m in self.INTERVALS:
            self.interval.addItem(t("backups.interval_off") if m == 0 else t("backups.interval_minutes", n=m), m)
        self.interval.currentIndexChanged.connect(lambda _i: self._save())
        form.addRow(t("backups.interval"), self.interval)
        self.keep = QSpinBox()
        self.keep.setRange(0, 200)
        self.keep.setSpecialValueText(t("backups.keep_unlimited"))
        self.keep.editingFinished.connect(self._save)
        form.addRow(t("backups.keep"), self.keep)
        card.body.addLayout(form)
        card.body.addWidget(label(t("backups.note"), role="dim", wrap=True))
        outer.addWidget(card)

        panel.ctl.backups_changed.connect(lambda pid: panel.pack is not None and pid == panel.pack.id and self.refresh())

    def show_pack(self, pack: Pack) -> None:
        self._loading = True
        try:
            idx = self.interval.findData(pack.server.auto_backup_minutes)
            if idx < 0:
                self.interval.addItem(t("backups.interval_minutes", n=pack.server.auto_backup_minutes), pack.server.auto_backup_minutes)
                idx = self.interval.count() - 1
            self.interval.setCurrentIndex(idx)
            self.keep.setValue(pack.server.backup_keep)
        finally:
            self._loading = False
        self.refresh()

    def _directory(self) -> Path | None:
        pack = self.panel.pack
        return self.panel.ctl.manager.backups_root(pack) if pack else None

    def refresh(self) -> None:
        from mcpack.backups import list_backups
        from mcpack.gui.formatting import format_size

        directory = self._directory()
        items = list_backups(directory) if directory else []
        self._items = items
        self.table.setRowCount(len(items))
        kinds = {"manual": t("backups.kind.manual"), "auto": t("backups.kind.auto"), "before-prepare": t("backups.kind.before_prepare")}
        for r, b in enumerate(items):
            date = QTableWidgetItem(b.created.strftime("%Y-%m-%d  %H:%M:%S"))
            date.setToolTip(str(b.path))
            self.table.setItem(r, 0, date)
            self.table.setItem(r, 1, QTableWidgetItem(kinds.get(b.label, b.label or "—")))
            self.table.setItem(r, 2, QTableWidgetItem(format_size(b.size)))
        total = sum(b.size for b in items)
        self.summary.setText(t("backups.summary", count=len(items), size=format_size(total)) if items else "")
        self.table.setVisible(bool(items))
        self.empty.setVisible(not items)
        self._update_buttons()

    def _selected(self):
        row = self.table.currentRow()
        return self._items[row] if 0 <= row < len(getattr(self, "_items", [])) else None

    def _update_buttons(self) -> None:
        sel = self._selected() is not None
        self.restore_btn.setEnabled(sel and not self.panel.running)
        self.restore_btn.setToolTip(t("ctl.restore_running") if self.panel.running else "")
        self.delete_btn.setEnabled(sel)

    def _backup(self) -> None:
        if self.panel.pack is not None:
            self.panel.ctl.backup_server(self.panel.pack)

    def _restore(self) -> None:
        b = self._selected()
        if b is None or self.panel.pack is None:
            return
        if confirm(self, t("backups.restore_title"), t("backups.restore_confirm", name=b.name), ok_text=t("backups.restore"), danger=True):
            self.panel.ctl.restore_backup(self.panel.pack, b.path)

    def _delete(self) -> None:
        b = self._selected()
        if b is None or self.panel.pack is None:
            return
        if confirm(self, t("backups.delete_title"), t("backups.delete_confirm", name=b.name), ok_text=t("backups.delete"), danger=True):
            self.panel.ctl.delete_backup(self.panel.pack, b.path)

    def _open_folder(self) -> None:
        directory = self._directory()
        if directory is not None:
            pack_actions.open_folder(directory)

    def _save(self) -> None:
        pack = self.panel.pack
        if self._loading or pack is None:
            return
        self.panel.ctl.update_server_config(
            pack, auto_backup_minutes=int(self.interval.currentData() or 0), backup_keep=self.keep.value()
        )


class ServerPanel(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        self.pack: Pack | None = None
        self.running = False
        self.state = "not_prepared"
        self._started_at: float | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        head = Card(padding=14, spacing=8)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.status_chip = Chip(t("server.stopped"), "neutral", dot_color=COLORS["text_dim"])
        row.addWidget(self.status_chip)
        self.state_chip = Chip("", "neutral")
        row.addWidget(self.state_chip)
        self.uptime = label("", role="dim")
        row.addWidget(self.uptime)
        row.addStretch()
        self.prepare_btn = button(t("server.prepare"), on_click=self._prepare, tooltip=t("server.prepare_tooltip"))
        self.install_btn = button(t("server.install"), on_click=lambda: self.pack and ctl.install_server(self.pack))
        self.start_btn = button(t("server.start"), variant="primary", on_click=self._start)
        self.stop_btn = button(t("server.stop"), variant="danger", on_click=lambda: self.pack and ctl.stop_server(self.pack.id))
        more = tool_button("⋯", tooltip=t("server.more"), variant="ghost")
        from PySide6.QtWidgets import QMenu

        menu = QMenu(more)
        menu.addAction(t("server.open_folder"), lambda: self.pack and pack_actions.open_folder(ctl.manager.server_root(self.pack)))
        menu.addAction(t("server.open_logs"), lambda: self.pack and pack_actions.open_folder(ctl.manager.server_root(self.pack) / "logs"))
        menu.addSeparator()
        menu.addAction(t("server.kill"), self._kill)
        more.setMenu(menu)
        for w in (self.prepare_btn, self.install_btn, self.start_btn, self.stop_btn, more):
            row.addWidget(w)
        head.body.addLayout(row)
        self.hint = label("", role="dim", wrap=True)
        head.body.addWidget(self.hint)
        outer.addWidget(head)

        self.tabs = QTabWidget()
        self.console = ConsoleView(self)
        self.players = PlayersView(self)
        self.runtime = RuntimeSettingsView(self)
        self.properties = PropertiesView(self)
        self.mods_list = QListWidget()
        mods_holder = QWidget()
        mods_layout = QVBoxLayout(mods_holder)
        mods_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_note = label("", role="notice-info", wrap=True)
        mods_layout.addWidget(self.mods_note)
        mods_layout.addWidget(self.mods_list, 1)
        self.tabs.addTab(self.console, t("server.tab_console"))
        self.tabs.addTab(self.players, t("server.tab_players"))
        self.tabs.addTab(self.runtime, t("server.tab_settings"))
        self.tabs.addTab(self.properties, "server.properties")
        self.tabs.addTab(mods_holder, t("server.tab_mods"))
        self.backups = BackupsView(self)
        self.tabs.addTab(self.backups, t("server.tab_backups"))
        self.tabs.currentChanged.connect(self._on_tab)
        outer.addWidget(self.tabs, 1)

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._clock.start()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(PLAYER_POLL_MS)
        self._poll_timer.timeout.connect(lambda: self.poll_players(force=False))
        self._poll_timer.start()

        ctl.console_line.connect(self._on_line)
        ctl.console_reset.connect(self._on_reset)
        ctl.server_changed.connect(self._on_server_changed)
        ctl.players_updated.connect(self._on_players)

    # -- pack bağlama ----------------------------------------------------------------

    def set_pack(self, pack: Pack | None) -> None:
        switched = self.pack is None or pack is None or self.pack.id != pack.id
        self.pack = pack
        if pack is None:
            return
        self.runtime.show_pack(pack)
        self.backups.show_pack(pack)
        self._refresh_mods()
        if switched:
            info = self.ctl.server_info(pack)
            self.console.reset(info["buffer"])
            self.players.clear()
            self.properties.load()
        self.refresh_state()

    def _refresh_mods(self) -> None:
        pack = self.pack
        self.mods_list.clear()
        server_mods = filter_server_mods(pack)
        for m in server_mods:
            self.mods_list.addItem(f"{m.name or m.file_name}    —    {m.file_name}")
        excluded = len(pack.mods) - len(server_mods)
        self.mods_note.setText(t("server.mods_note", count=len(server_mods), excluded=excluded))

    def refresh_state(self) -> None:
        if self.pack is None:
            return
        info = self.ctl.server_info(self.pack)
        self.running = info["running"]
        self.state = info["state"]
        self._started_at = info["started_at"]
        if self.running:
            self.status_chip.set(t("server.running"), "success", dot_color=COLORS["success"])
        else:
            self.status_chip.set(t("server.stopped"), "neutral", dot_color=COLORS["text_dim"])
        tone = {"ready": "success", "needs_install": "warning", "not_prepared": "neutral"}[self.state]
        self.state_chip.set(t(f"server.state.{self.state}"), tone)
        self.prepare_btn.setEnabled(not self.running)
        self.install_btn.setVisible(self.state == "needs_install")
        self.install_btn.setEnabled(not self.running)
        self.start_btn.setEnabled(not self.running and self.state == "ready")
        self.stop_btn.setEnabled(self.running)
        self.console.set_enabled_input(self.running)
        hints = {
            "not_prepared": t("server.hint_not_prepared"),
            "needs_install": t("server.hint_needs_install"),
            "ready": t("server.hint_running") if self.running else t("server.hint_ready"),
        }
        self.hint.setText(hints[self.state])
        if not self.running:
            self.players.clear()
        self.players._update_enabled()
        self.backups.refresh()
        self._tick()

    def _tick(self) -> None:
        if self.running and self._started_at:
            self.uptime.setText(t("server.uptime", time=format_duration(time.time() - self._started_at)))
        else:
            self.uptime.setText("")

    # -- eylemler --------------------------------------------------------------------

    def send(self, text: str) -> None:
        if self.pack is None:
            return
        self.console.append(f"> {text}")
        self.ctl.send_command(self.pack.id, text)

    def ask_eula(self) -> bool:
        if self.pack is None:
            return False
        if confirm(self, "Minecraft EULA", t("server.eula_text"), ok_text=t("srvset.eula_accept")):
            self.ctl.update_server_config(self.pack, eula_accepted=True)
            return True
        return False

    def _prepare(self) -> None:
        if self.pack is not None:
            self.ctl.prepare_server(self.pack)

    def _start(self) -> None:
        if self.pack is None:
            return
        if not self.pack.server.eula_accepted and not self.ask_eula():
            return
        self.ctl.start_server(self.pack)

    def _kill(self) -> None:
        if self.pack is not None and self.running and confirm(
            self, t("server.kill"), t("server.kill_confirm"), danger=True
        ):
            self.ctl.kill_server(self.pack.id)

    def poll_players(self, *, force: bool) -> None:
        """Sadece Oyuncular sekmesi görünürken (ya da elle istenince) /list
        gönderilir — eskiden her 4 sn'de bir koşulsuz gönderilip konsolu
        kirletiyordu."""
        if self.pack is None or not self.running:
            return
        if force or (self.isVisible() and self.tabs.currentWidget() is self.players):
            self.ctl.poll_players(self.pack.id)

    def _on_tab(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.players:
            self.poll_players(force=True)
        elif self.tabs.currentWidget() is self.properties:
            self.properties.load()

    # -- denetleyici sinyalleri ------------------------------------------------------

    def _on_line(self, pack_id: str, line: str) -> None:
        if self.pack is not None and pack_id == self.pack.id:
            self.console.append(line)

    def _on_reset(self, pack_id: str, lines: list) -> None:
        if self.pack is not None and pack_id == self.pack.id:
            self.console.reset(lines)

    def _on_server_changed(self, pack_id: str) -> None:
        if self.pack is not None and pack_id == self.pack.id:
            self.refresh_state()

    def _on_players(self, pack_id: str, names: list) -> None:
        if self.pack is not None and pack_id == self.pack.id:
            self.players.set_players(names)


def server_empty_state() -> EmptyState:
    return EmptyState("🖥", t("server.empty_title"), t("server.empty_sub"))
