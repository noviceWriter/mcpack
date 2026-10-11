"""Geliştirici / Hata Ayıklama sayfası.

Sekmeler:
- Loglar: canlı, seviye/kaynak/metin filtreli log akışı (logging_setup.
  MEMORY_HANDLER), duraklat, dışa aktar, debug modunu anında aç/kapat.
- Görevler: TaskManager'daki tüm arka plan görevleri — durum, ilerleme,
  süre, hata + tam traceback, iptal.
- Ağ: her HTTP isteği (yöntem, durum, süre, host, yol), istatistikler.
- İstisnalar: yakalanan/yakalanmayan tüm istisnalar (tekrar sayısıyla),
  traceback, crash raporları.
- Sistem: sürüm/ortam bilgisi, uygulama durumu, tek tıkla teşhis
  (Java, ağ erişimi, CurseForge anahtarı, disk, port...), destek paketi.
- Python konsolu (sadece debug modunda): canlı uygulama nesnelerine
  (ctl, settings, manager, registry, tasks) erişen etkileşimli yorumlayıcı.
"""

from __future__ import annotations

import code
import contextlib
import io
import json
import shutil
import socket
import time
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mcpack.config import config_dir
from mcpack.downloader import make_client
from mcpack.gui import pack_actions
from mcpack.gui.components import Card, Chip, SearchField, StatTile, button, label
from mcpack.gui.controller import AppController
from mcpack.gui.formatting import format_duration
from mcpack.gui.icons import icons
from mcpack.gui.tasks import CANCELLED, DONE, FAILED, RUNNING, Task
from mcpack.gui.theme import COLORS, LEVEL_COLORS, mono_font
from mcpack.i18n import t
from mcpack.logging_setup import (
    EXCEPTIONS,
    MEMORY_HANDLER,
    NETWORK,
    LogEntry,
    get_logger,
    is_debug,
    list_crash_reports,
    log_file_path,
    logs_dir,
    set_debug,
    system_info,
)
from mcpack.server_runtime import find_java, get_java_major_version, required_java_major

log = get_logger(__name__)

LEVELS = [("DEBUG", 10), ("INFO", 20), ("WARNING", 30), ("ERROR", 40), ("CRITICAL", 50)]
MAX_VIEW_ROWS = 20000


def _mono_view(read_only: bool = True) -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(read_only)
    view.setFont(mono_font(10))
    view.setProperty("variant", "console")
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    return view


def _table(headers: list[str], stretch: int) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(28)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    return table


# -- loglar ---------------------------------------------------------------------------


class _LogBridge(QObject):
    """MEMORY_HANDLER aboneliği HER thread'den çağrılır — kayıtlar bu
    sinyalle (QueuedConnection) GUI thread'ine taşınır."""

    entry = Signal(object)


class LogModel(QAbstractTableModel):
    HEADERS = ["time", "level", "logger", "thread", "message"]

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[LogEntry] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return t(f"debug.log.col.{self.HEADERS[section]}")
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        col = self.HEADERS[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == "time":
                return e.time_text
            if col == "level":
                return e.level
            if col == "logger":
                return e.logger.removeprefix("mcpack.")
            if col == "thread":
                return e.thread
            first = e.message.splitlines()[0] if e.message else ""
            return first + ("  ⟨traceback⟩" if e.exc_text else "")
        if role == Qt.ItemDataRole.ForegroundRole:
            if col in ("level", "message") and e.levelno >= 30:
                return QColor(LEVEL_COLORS.get(e.level, COLORS["text"]))
            if col in ("time", "thread", "logger"):
                return QColor(COLORS["text_dim"])
            if e.levelno <= 10:
                return QColor(COLORS["text_dim"])
        if role == Qt.ItemDataRole.FontRole and col in ("time", "message"):
            return mono_font(9)
        return None

    def append(self, entries: list[LogEntry]) -> None:
        if not entries:
            return
        overflow = len(self.entries) + len(entries) - MAX_VIEW_ROWS
        if overflow > 0:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self.entries[:overflow]
            self.endRemoveRows()
        start = len(self.entries)
        self.beginInsertRows(QModelIndex(), start, start + len(entries) - 1)
        self.entries.extend(entries)
        self.endInsertRows()

    def reset(self, entries: list[LogEntry]) -> None:
        self.beginResetModel()
        self.entries = list(entries)[-MAX_VIEW_ROWS:]
        self.endResetModel()


class LogFilter(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.min_level = 0
        self.text = ""
        self.logger = ""

    def filterAcceptsRow(self, row: int, parent) -> bool:  # noqa: N802
        e: LogEntry = self.sourceModel().entries[row]
        if e.levelno < self.min_level:
            return False
        if self.logger and self.logger not in e.logger.lower():
            return False
        if self.text and self.text not in e.message.lower() and self.text not in (e.exc_text or "").lower():
            return False
        return True


class LogsTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        self._pending: list[LogEntry] = []
        self._paused = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.level = QComboBox()
        for name, value in LEVELS:
            self.level.addItem(f"≥ {name}", value)
        self.level.setCurrentIndex(0 if is_debug() else 1)
        self.level.currentIndexChanged.connect(lambda _i: self._apply())
        bar.addWidget(self.level)
        self.logger_filter = QLineEdit()
        self.logger_filter.setPlaceholderText(t("debug.log.logger_filter"))
        self.logger_filter.setFixedWidth(170)
        self.logger_filter.textChanged.connect(lambda _t: self._apply())
        bar.addWidget(self.logger_filter)
        self.search = SearchField(t("debug.log.search"), delay_ms=150)
        self.search.search.connect(lambda _q: self._apply())
        bar.addWidget(self.search, 1)
        self.pause = button(t("debug.log.pause"), checkable=True, variant="ghost")
        self.pause.toggled.connect(self._on_pause)
        bar.addWidget(self.pause)
        self.autoscroll = QCheckBox(t("console.autoscroll"))
        self.autoscroll.setChecked(True)
        bar.addWidget(self.autoscroll)
        self.debug_toggle = QCheckBox(t("debug.log.debug_mode"))
        self.debug_toggle.setChecked(is_debug())
        self.debug_toggle.toggled.connect(self._toggle_debug)
        bar.addWidget(self.debug_toggle)
        outer.addLayout(bar)

        bar2 = QHBoxLayout()
        bar2.setSpacing(6)
        self.counts = label("", role="dim")
        bar2.addWidget(self.counts, 1)
        bar2.addWidget(button(t("debug.log.copy"), variant="ghost", on_click=self._copy))
        bar2.addWidget(button(t("debug.log.export"), variant="ghost", on_click=self._export))
        bar2.addWidget(button(t("debug.log.open_file"), variant="ghost", on_click=lambda: pack_actions.open_folder(logs_dir())))
        bar2.addWidget(button(t("debug.log.clear"), variant="ghost", on_click=self._clear))
        outer.addLayout(bar2)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.model = LogModel()
        self.proxy = LogFilter()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for c, w in ((0, 112), (1, 80), (2, 190), (3, 120)):
            self.table.setColumnWidth(c, w)
        self.table.selectionModel().currentRowChanged.connect(self._show_detail)
        splitter.addWidget(self.table)
        self.detail = _mono_view()
        self.detail.setPlaceholderText(t("debug.log.detail_placeholder"))
        splitter.addWidget(self.detail)
        splitter.setSizes([520, 160])
        outer.addWidget(splitter, 1)

        self._bridge = _LogBridge()
        self._bridge.entry.connect(self._on_entry, Qt.ConnectionType.QueuedConnection)
        self.model.reset(MEMORY_HANDLER.snapshot())
        MEMORY_HANDLER.subscribe(self._bridge.entry.emit)
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(150)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()
        self._apply()

    def shutdown(self) -> None:
        MEMORY_HANDLER.unsubscribe(self._bridge.entry.emit)

    @Slot(object)
    def _on_entry(self, entry: LogEntry) -> None:
        self._pending.append(entry)

    def _flush(self) -> None:
        if self._paused or not self._pending:
            return
        batch, self._pending = self._pending, []
        self.model.append(batch)
        self._update_counts()
        if self.autoscroll.isChecked():
            self.table.scrollToBottom()

    def _on_pause(self, paused: bool) -> None:
        self._paused = paused
        self.pause.setText(t("debug.log.resume") if paused else t("debug.log.pause"))
        if not paused:
            self._flush()

    def _toggle_debug(self, on: bool) -> None:
        set_debug(on)
        if on and self.level.currentData() > 10:
            self.level.setCurrentIndex(0)
        settings = self.ctl.settings.model_copy()
        settings.debug_mode = on
        self.ctl.apply_settings(settings)

    def _apply(self) -> None:
        self.proxy.min_level = self.level.currentData()
        self.proxy.text = self.search.text().strip().lower()
        self.proxy.logger = self.logger_filter.text().strip().lower()
        self.proxy.invalidateFilter()
        self._update_counts()
        if self.autoscroll.isChecked():
            self.table.scrollToBottom()

    def _update_counts(self) -> None:
        warn = sum(1 for e in self.model.entries if e.levelno == 30)
        err = sum(1 for e in self.model.entries if e.levelno >= 40)
        self.counts.setText(
            t("debug.log.counts", shown=self.proxy.rowCount(), total=len(self.model.entries), warn=warn, err=err)
            + ("  ·  " + t("debug.log.paused", n=len(self._pending)) if self._paused else "")
        )

    def _show_detail(self, current, _previous) -> None:
        if not current.isValid():
            return
        e = self.model.entries[self.proxy.mapToSource(current).row()]
        self.detail.setPlainText(e.format_line())

    def _selected_lines(self) -> list[str]:
        rows = sorted({self.proxy.mapToSource(i).row() for i in self.table.selectionModel().selectedRows()})
        if not rows:
            rows = [self.proxy.mapToSource(self.proxy.index(r, 0)).row() for r in range(self.proxy.rowCount())]
        return [self.model.entries[r].format_line() for r in rows]

    def _copy(self) -> None:
        lines = self._selected_lines()
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.ctl.notify.emit("info", t("debug.copied", count=len(lines)))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, t("debug.log.export"), f"mcpack-log-{time.strftime('%Y%m%d-%H%M%S')}.log", "*.log *.txt")
        if path:
            lines = [self.model.entries[self.proxy.mapToSource(self.proxy.index(r, 0)).row()].format_line() for r in range(self.proxy.rowCount())]
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.ctl.notify.emit("success", t("debug.saved", path=path))

    def _clear(self) -> None:
        MEMORY_HANDLER.clear()
        self.model.reset([])
        self.detail.clear()
        self._update_counts()


# -- görevler --------------------------------------------------------------------------

_STATUS_TONES = {RUNNING: COLORS["accent_hover"], DONE: COLORS["success"], FAILED: COLORS["danger"], CANCELLED: COLORS["warning"]}


class TasksTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        bar = QHBoxLayout()
        self.hide_silent = QCheckBox(t("debug.tasks.hide_silent"))
        self.hide_silent.setChecked(True)
        self.hide_silent.toggled.connect(lambda _c: self.refresh())
        bar.addWidget(self.hide_silent)
        bar.addStretch()
        self.summary = label("", role="dim")
        bar.addWidget(self.summary)
        self.cancel_btn = button(t("debug.tasks.cancel"), variant="danger", on_click=self._cancel)
        bar.addWidget(self.cancel_btn)
        bar.addWidget(button(t("debug.tasks.clear"), variant="ghost", on_click=lambda: (ctl.tasks.clear_finished(), self.refresh())))
        outer.addLayout(bar)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = _table(["#", t("debug.tasks.col.title"), t("debug.tasks.col.category"), t("debug.tasks.col.status"), t("debug.tasks.col.progress"), t("debug.tasks.col.duration")], 1)
        for c, w in ((0, 50), (2, 100), (3, 110), (4, 140), (5, 80)):
            self.table.setColumnWidth(c, w)
        self.table.currentCellChanged.connect(lambda *_a: self._show_detail())
        splitter.addWidget(self.table)
        self.detail = _mono_view()
        splitter.addWidget(self.detail)
        splitter.setSizes([480, 180])
        outer.addWidget(splitter, 1)
        ctl.tasks.task_added.connect(lambda _t: self._schedule())
        ctl.tasks.task_updated.connect(lambda _t: self._schedule())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.refresh)
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(lambda: self.isVisible() and self.ctl.tasks.active_count(include_silent=True) and self.refresh())
        self._tick.start()
        self.refresh()

    def _schedule(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def _tasks(self) -> list[Task]:
        tasks = self.ctl.tasks.tasks()
        if self.hide_silent.isChecked():
            tasks = [x for x in tasks if not x.silent or x.status == FAILED]
        return list(reversed(tasks))

    def refresh(self) -> None:
        if not self.isVisible():
            return
        tasks = self._tasks()
        current_id = self._current_id()
        self.table.setRowCount(len(tasks))
        for r, task in enumerate(tasks):
            id_item = QTableWidgetItem(str(task.id))
            id_item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(task.title + (f" — {task.message}" if task.message and task.is_active else "")))
            self.table.setItem(r, 2, QTableWidgetItem(task.category))
            st = QTableWidgetItem(t(f"debug.tasks.status.{task.status}"))
            st.setForeground(QColor(_STATUS_TONES.get(task.status, COLORS["text_muted"])))
            self.table.setItem(r, 3, st)
            frac = task.fraction
            self.table.setItem(r, 4, QTableWidgetItem(f"{task.done}/{task.total}  ({frac * 100:.0f}%)" if frac is not None else "—"))
            self.table.setItem(r, 5, QTableWidgetItem(format_duration(task.duration)))
            if task.id == current_id:
                self.table.selectRow(r)
        all_tasks = self.ctl.tasks.tasks()
        self.summary.setText(t(
            "debug.tasks.summary",
            active=sum(1 for x in all_tasks if x.is_active),
            failed=sum(1 for x in all_tasks if x.status == FAILED),
            total=len(all_tasks),
        ))
        self._show_detail()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _current(self) -> Task | None:
        tid = self._current_id()
        return next((x for x in self.ctl.tasks.tasks() if x.id == tid), None)

    def _show_detail(self) -> None:
        task = self._current()
        self.cancel_btn.setEnabled(bool(task and task.is_active and task.cancellable))
        if task is None:
            self.detail.setPlainText("")
            return
        lines = [
            f"#{task.id}  {task.title}",
            f"status: {task.status}   category: {task.category}   cancellable: {task.cancellable}   silent: {task.silent}",
            f"started: {datetime.fromtimestamp(task.started_at).isoformat(timespec='seconds') if task.started_at else '—'}"
            f"   duration: {format_duration(task.duration)}   progress: {task.done}/{task.total}",
        ]
        if task.message:
            lines.append(f"message: {task.message}")
        if task.error:
            lines += ["", f"error: {task.error}"]
        if task.traceback_text:
            lines += ["", task.traceback_text]
        self.detail.setPlainText("\n".join(lines))

    def select_task(self, task_id: int) -> None:
        self.hide_silent.setChecked(False)
        self.refresh()
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == task_id:
                self.table.selectRow(r)
                break

    def _cancel(self) -> None:
        task = self._current()
        if task:
            self.ctl.tasks.cancel(task.id)


# -- ağ --------------------------------------------------------------------------------


class NetworkTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        tiles = QHBoxLayout()
        self.t_total = StatTile(t("debug.net.total"))
        self.t_failed = StatTile(t("debug.net.failed"), accent=COLORS["danger"])
        self.t_avg = StatTile(t("debug.net.avg"))
        self.t_max = StatTile(t("debug.net.max"))
        for w in (self.t_total, self.t_failed, self.t_avg, self.t_max):
            tiles.addWidget(w)
        outer.addLayout(tiles)
        bar = QHBoxLayout()
        self.failed_only = QCheckBox(t("debug.net.failed_only"))
        self.failed_only.toggled.connect(lambda _c: self.refresh())
        bar.addWidget(self.failed_only)
        self.host_filter = QComboBox()
        self.host_filter.addItem(t("debug.net.all_hosts"), "")
        self.host_filter.currentIndexChanged.connect(lambda _i: self.refresh())
        bar.addWidget(self.host_filter)
        bar.addStretch()
        bar.addWidget(button(t("debug.net.copy_url"), variant="ghost", on_click=self._copy_url))
        bar.addWidget(button(t("debug.net.clear"), variant="ghost", on_click=lambda: (NETWORK.clear(), self.refresh())))
        outer.addLayout(bar)
        self.table = _table([t("debug.log.col.time"), t("debug.net.col.method"), t("debug.net.col.status"), "ms", "host", t("debug.net.col.path")], 5)
        for c, w in ((0, 90), (1, 70), (2, 120), (3, 70), (4, 200)):
            self.table.setColumnWidth(c, w)
        outer.addWidget(self.table, 1)
        outer.addWidget(label(t("debug.net.privacy"), role="dim", wrap=True))
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(lambda: self.isVisible() and self.refresh())
        self._timer.start()
        self._seen_seq = -1

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._seen_seq = -1
        self.refresh()

    def refresh(self) -> None:
        events = NETWORK.snapshot()
        last_seq = events[-1].seq if events else 0
        stats = NETWORK.stats()
        self.t_total.set_value(str(stats["total"]))
        self.t_failed.set_value(str(stats["failed"]))
        self.t_avg.set_value(f"{stats['avg_ms']:.0f} ms" if stats["avg_ms"] is not None else "—")
        self.t_max.set_value(f"{stats['max_ms']:.0f} ms" if stats["max_ms"] is not None else "—")
        hosts = sorted({e.host for e in events})
        current_host = self.host_filter.currentData()
        if [self.host_filter.itemData(i) for i in range(1, self.host_filter.count())] != hosts:
            self.host_filter.blockSignals(True)
            self.host_filter.clear()
            self.host_filter.addItem(t("debug.net.all_hosts"), "")
            for h in hosts:
                self.host_filter.addItem(h, h)
            self.host_filter.setCurrentIndex(max(0, self.host_filter.findData(current_host)))
            self.host_filter.blockSignals(False)
        if last_seq == self._seen_seq:
            return
        self._seen_seq = last_seq
        host = self.host_filter.currentData()
        rows = [
            e for e in reversed(events)
            if (not self.failed_only.isChecked() or e.error or (e.status or 0) >= 400) and (not host or e.host == host)
        ][:1000]
        self.table.setRowCount(len(rows))
        from urllib.parse import urlsplit

        for r, e in enumerate(rows):
            parts = urlsplit(e.url)
            path = parts.path + (f"?{parts.query}" if parts.query else "")
            status = str(e.status) if e.status is not None else (e.error or "—")
            cells = [
                datetime.fromtimestamp(e.created).strftime("%H:%M:%S"), e.method, status,
                f"{e.elapsed_ms:.0f}" if e.elapsed_ms is not None else "—", e.host, path,
            ]
            for c, v in enumerate(cells):
                item = QTableWidgetItem(v)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, e.url)
                if c == 2:
                    bad = e.error or (e.status or 0) >= 400
                    item.setForeground(QColor(COLORS["danger"] if bad else COLORS["success"]))
                    item.setToolTip(e.error or "")
                self.table.setItem(r, c, item)

    def _copy_url(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            QGuiApplication.clipboard().setText(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            self.ctl.notify.emit("info", t("debug.copied", count=1))


# -- istisnalar ------------------------------------------------------------------------


class ExceptionsTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(lambda _r: self._show())
        left.addWidget(label(t("debug.exc.recent"), role="h3"))
        left.addWidget(self.list, 2)
        left.addWidget(label(t("debug.exc.crash_reports"), role="h3"))
        self.crash_list = QListWidget()
        self.crash_list.itemDoubleClicked.connect(self._open_crash)
        left.addWidget(self.crash_list, 1)
        row = QHBoxLayout()
        row.addWidget(button(t("debug.exc.open_crash_dir"), variant="ghost", on_click=lambda: pack_actions.open_folder(logs_dir() / "crash")))
        row.addWidget(button(t("debug.exc.clear"), variant="ghost", on_click=lambda: (EXCEPTIONS.clear(), self.refresh())))
        left.addLayout(row)
        holder = QWidget()
        holder.setLayout(left)
        holder.setMaximumWidth(420)
        outer.addWidget(holder)
        right = QVBoxLayout()
        head = QHBoxLayout()
        self.title = label(t("debug.exc.none"), role="h3", wrap=True)
        head.addWidget(self.title, 1)
        head.addWidget(button(t("debug.exc.copy"), variant="ghost", on_click=self._copy))
        right.addLayout(head)
        self.meta = label("", role="dim", wrap=True)
        right.addWidget(self.meta)
        self.trace = _mono_view()
        right.addWidget(self.trace, 1)
        outer.addLayout(right, 1)
        self._events = []
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(lambda: self.isVisible() and self.refresh())
        self._timer.start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        events = list(reversed(EXCEPTIONS.snapshot()))
        signature = [(e.key, e.count) for e in events]
        if signature != [(e.key, e.count) for e in self._events]:
            current = self.list.currentRow()
            self._events = [type(e)(**{**e.__dict__}) for e in events]
            self.list.clear()
            for e in self._events:
                item = QListWidgetItem(f"{'💥' if e.crash_report else '⚠'}  {e.type_name}: {e.message[:70]}" + (f"   ×{e.count}" if e.count > 1 else ""))
                item.setToolTip(e.origin)
                self.list.addItem(item)
            if self._events:
                self.list.setCurrentRow(min(max(current, 0), len(self._events) - 1))
            else:
                self._show()
        reports = list_crash_reports()
        if self.crash_list.count() != len(reports):
            self.crash_list.clear()
            for p in reports[:50]:
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, str(p))
                self.crash_list.addItem(item)

    def _show(self) -> None:
        row = self.list.currentRow()
        if row < 0 or row >= len(self._events):
            self.title.setText(t("debug.exc.none"))
            self.meta.setText("")
            self.trace.setPlainText("")
            return
        e = self._events[row]
        self.title.setText(f"{e.type_name}: {e.message}")
        fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%H:%M:%S")  # noqa: E731
        meta = t("debug.exc.meta", origin=e.origin, count=e.count, first=fmt(e.first_seen), last=fmt(e.last_seen))
        if e.crash_report:
            meta += "\n" + t("debug.exc.report", path=e.crash_report)
        self.meta.setText(meta)
        self.trace.setPlainText(e.traceback_text)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(f"{self.title.text()}\n{self.meta.text()}\n\n{self.trace.toPlainText()}")
        self.ctl.notify.emit("info", t("debug.copied", count=1))

    def _open_crash(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.title.setText(path.name)
        self.meta.setText(str(path))
        try:
            self.trace.setPlainText(path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.trace.setPlainText(str(exc))


# -- sistem / teşhis ---------------------------------------------------------------------


class SystemTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(12)
        info_card = Card(padding=14)
        head = QHBoxLayout()
        head.addWidget(label(t("debug.sys.info"), role="h3"), 1)
        head.addWidget(button(t("debug.sys.copy"), variant="ghost", on_click=self._copy_info))
        info_card.body.addLayout(head)
        self.info_table = _table([t("debug.sys.key"), t("debug.sys.value")], 1)
        self.info_table.setColumnWidth(0, 150)
        info_card.body.addWidget(self.info_table)
        left.addWidget(info_card, 3)
        state_card = Card(padding=14)
        state_card.body.addWidget(label(t("debug.sys.state"), role="h3"))
        self.state_text = label("", role="muted", wrap=True, selectable=True)
        self.state_text.setFont(mono_font(9))
        state_card.body.addWidget(self.state_text)
        left.addWidget(state_card, 2)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(12)
        diag = Card(padding=14)
        dhead = QHBoxLayout()
        dhead.addWidget(label(t("debug.sys.diagnostics"), role="h3"), 1)
        self.run_btn = button(t("debug.sys.run"), variant="primary", on_click=self.run_diagnostics)
        dhead.addWidget(self.run_btn)
        diag.body.addLayout(dhead)
        diag.body.addWidget(label(t("debug.sys.diagnostics_hint"), role="dim", wrap=True))
        self.progress = QProgressBar()
        self.progress.hide()
        diag.body.addWidget(self.progress)
        self.results = _table(["", t("debug.sys.check"), t("debug.sys.result")], 2)
        self.results.setColumnWidth(0, 34)
        self.results.setColumnWidth(1, 200)
        diag.body.addWidget(self.results, 1)
        right.addWidget(diag, 3)
        bundle = Card(padding=14)
        bundle.body.addWidget(label(t("debug.sys.bundle"), role="h3"))
        bundle.body.addWidget(label(t("debug.sys.bundle_hint"), role="dim", wrap=True))
        brow = QHBoxLayout()
        brow.addWidget(button(t("debug.sys.bundle_create"), on_click=self.create_bundle))
        brow.addWidget(button(t("debug.sys.open_config"), variant="ghost", on_click=lambda: pack_actions.open_folder(config_dir())))
        brow.addStretch()
        bundle.body.addLayout(brow)
        right.addWidget(bundle)
        outer.addLayout(right, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(lambda: self.isVisible() and self._refresh_state())
        self._timer.start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        info = system_info()
        self.info_table.setRowCount(len(info))
        for r, (k, v) in enumerate(info.items()):
            self.info_table.setItem(r, 0, QTableWidgetItem(k))
            self.info_table.setItem(r, 1, QTableWidgetItem(v))
        self._refresh_state()

    def _refresh_state(self) -> None:
        import threading

        icon_stats = icons().stats()
        running = self.ctl.running_server_ids()
        lines = [
            f"threads      : {threading.active_count()}  ({', '.join(sorted(th.name for th in threading.enumerate())[:8])}…)",
            f"tasks        : {self.ctl.tasks.active_count(include_silent=True)} active / {len(self.ctl.tasks.tasks())} total",
            f"servers      : {len(running)} running {running if running else ''}",
            f"web panel    : {self.ctl.web_panel_url or 'off'}",
            f"icons        : mem={icon_stats['memory']} disk={icon_stats['disk']} pending={icon_stats['pending']} "
            f"dl={icon_stats['downloads']} fail={icon_stats['failures']}",
            f"log buffer   : {len(MEMORY_HANDLER.snapshot())} entries   file: {log_file_path()}",
            f"network      : {NETWORK.stats()['total']} requests ({NETWORK.stats()['failed']} failed)",
            f"exceptions   : {len(EXCEPTIONS.snapshot())}",
            f"packs dir    : {self.ctl.settings.resolved_packs_dir()}",
        ]
        self.state_text.setText("\n".join(lines))

    def _copy_info(self) -> None:
        text = "\n".join(f"{k}: {v}" for k, v in system_info().items())
        QGuiApplication.clipboard().setText(text)
        self.ctl.notify.emit("info", t("debug.copied", count=len(text.splitlines())))

    # -- teşhis -------------------------------------------------------------------

    def run_diagnostics(self) -> None:
        settings = self.ctl.settings
        packs = self.ctl.list_packs()
        self.run_btn.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 0)
        self.results.setRowCount(0)

        async def task(ctx):
            results: list[tuple[str, str, str]] = []  # (ok|warn|fail, ad, ayrıntı)

            def add(status: str, name: str, detail: str) -> None:
                results.append((status, name, detail))
                ctx.progress(len(results), 10)

            # 1) disk / klasörler
            for name, path in (("config", config_dir()), ("packs", settings.resolved_packs_dir()), ("logs", logs_dir())):
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    probe = path / ".mcpack-write-test"
                    probe.write_text("ok", encoding="utf-8")
                    probe.unlink()
                    usage = shutil.disk_usage(path)
                    free_gb = usage.free / 1024**3
                    add("ok" if free_gb > 2 else "warn", t("diag.dir", name=name), t("diag.dir_ok", path=path, free=f"{free_gb:.1f}"))
                except OSError as exc:
                    add("fail", t("diag.dir", name=name), str(exc))

            # 2) java
            java = find_java(settings.java_path)
            if java is None:
                add("fail", "Java", t("diag.java_missing"))
            else:
                major = await get_java_major_version(java)
                need = max((required_java_major(p.minecraft) for p in packs), default=17)
                if major is None:
                    add("warn", "Java", t("diag.java_unknown", path=java))
                elif major < need:
                    add("warn", "Java", t("diag.java_old", version=major, need=need, path=java))
                else:
                    add("ok", "Java", t("diag.java_ok", version=major, path=java))

            # 3) ağ erişimi
            endpoints = [
                ("Modrinth API", "https://api.modrinth.com/v2/tag/loader"),
                ("Mojang meta", "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"),
                ("Fabric meta", "https://meta.fabricmc.net/v2/versions/game"),
                ("Forge maven", "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"),
            ]
            async with make_client() as client:
                for name, url in endpoints:
                    started = time.perf_counter()
                    try:
                        resp = await client.head(url, timeout=10) if "maven" in url else await client.get(url, timeout=10)
                        ms = (time.perf_counter() - started) * 1000
                        add("ok" if resp.status_code < 400 else "fail", name, f"HTTP {resp.status_code} · {ms:.0f} ms")
                    except Exception as exc:  # noqa: BLE001
                        add("fail", name, f"{type(exc).__name__}: {exc}")

            # 4) curseforge
            if settings.curseforge_api_key:
                from mcpack.sources.curseforge import CurseForgeClient

                cf = CurseForgeClient(settings.curseforge_api_key)
                try:
                    game = await cf.check_connection()
                    add("ok", "CurseForge", t("diag.cf_ok", game=game))
                except Exception as exc:  # noqa: BLE001
                    add("fail", "CurseForge", str(exc))
                finally:
                    await cf.aclose()
            else:
                add("warn", "CurseForge", t("diag.cf_missing"))

            # 5) web paneli portu
            if self.ctl.web_panel_running:
                add("ok", t("diag.port"), t("diag.port_in_use_by_us", port=settings.web_panel_port))
            else:
                with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                    try:
                        s.bind(("127.0.0.1", settings.web_panel_port))
                        add("ok", t("diag.port"), t("diag.port_free", port=settings.web_panel_port))
                    except OSError:
                        add("warn", t("diag.port"), t("diag.port_busy", port=settings.web_panel_port))

            # 6) pack dosyaları
            from mcpack.packs import storage

            broken = []
            for path in storage.list_pack_files(settings.resolved_packs_dir()):
                try:
                    storage.load_pack(path)
                except Exception as exc:  # noqa: BLE001
                    broken.append(f"{path.name}: {exc.__class__.__name__}")
            add("fail" if broken else "ok", t("diag.packs"), "; ".join(broken[:5]) if broken else t("diag.packs_ok", count=len(packs)))
            missing = sum(len(self.ctl.manager.find_missing_dependencies(p)) for p in packs)
            add("warn" if missing else "ok", t("diag.deps"), t("diag.deps_result", count=missing))
            return results

        def done(results) -> None:
            self.run_btn.setEnabled(True)
            self.progress.hide()
            glyph = {"ok": ("✓", COLORS["success"]), "warn": ("!", COLORS["warning"]), "fail": ("✖", COLORS["danger"])}
            self.results.setRowCount(len(results))
            for r, (status, name, detail) in enumerate(results):
                g, color = glyph[status]
                gi = QTableWidgetItem(g)
                gi.setForeground(QColor(color))
                gi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results.setItem(r, 0, gi)
                self.results.setItem(r, 1, QTableWidgetItem(name))
                di = QTableWidgetItem(detail)
                di.setToolTip(detail)
                self.results.setItem(r, 2, di)
            fails = sum(1 for s, *_ in results if s == "fail")
            warns = sum(1 for s, *_ in results if s == "warn")
            log.info("Teşhis tamamlandı: %d hata, %d uyarı", fails, warns)
            self.ctl.notify.emit("error" if fails else ("warning" if warns else "success"), t("diag.summary", fails=fails, warns=warns))

        def failed(_m: str) -> None:
            self.run_btn.setEnabled(True)
            self.progress.hide()

        self.ctl.tasks.run(t("diag.task"), task, on_success=done, on_error=failed, category="diagnostics", owner=self)

    # -- destek paketi --------------------------------------------------------------

    def create_bundle(self) -> None:
        default = f"mcpack-support-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, t("debug.sys.bundle_create"), str(Path.home() / default), "*.zip")
        if not path:
            return
        settings = self.ctl.settings.model_dump()
        for secret in ("curseforge_api_key", "web_panel_password"):
            if settings.get(secret):
                settings[secret] = "***redacted***"
        tasks = [
            {"id": x.id, "title": x.title, "status": x.status, "category": x.category, "error": x.error,
             "traceback": x.traceback_text, "duration": x.duration}
            for x in self.ctl.tasks.tasks()
        ]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("system.json", json.dumps(system_info(), indent=2, ensure_ascii=False))
            zf.writestr("settings.redacted.json", json.dumps(settings, indent=2, ensure_ascii=False))
            zf.writestr("tasks.json", json.dumps(tasks, indent=2, ensure_ascii=False))
            zf.writestr("network.json", json.dumps([e.to_dict() for e in NETWORK.snapshot()], indent=2))
            zf.writestr("exceptions.json", json.dumps([e.to_dict() for e in EXCEPTIONS.snapshot()], indent=2, ensure_ascii=False))
            zf.writestr("memory-log.txt", "\n".join(e.format_line() for e in MEMORY_HANDLER.snapshot()))
            for log_file in logs_dir().glob("mcpack.log*"):
                zf.write(log_file, f"logs/{log_file.name}")
            for report in list_crash_reports()[:20]:
                zf.write(report, f"crash/{report.name}")
        log.info("Destek paketi oluşturuldu: %s", path)
        self.ctl.notify.emit("success", t("debug.sys.bundle_done", path=path))
        pack_actions.open_folder(Path(path).parent)


# -- python konsolu --------------------------------------------------------------------


class PythonConsoleTab(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        from PySide6.QtWidgets import QApplication

        self._locals = {
            "ctl": ctl, "settings": ctl.settings, "manager": ctl.manager, "registry": ctl.registry,
            "tasks": ctl.tasks, "app": QApplication.instance(), "icons": icons(), "NETWORK": NETWORK,
            "EXCEPTIONS": EXCEPTIONS, "LOGS": MEMORY_HANDLER,
        }
        self._interp = code.InteractiveInterpreter(self._locals)
        self._buffer: list[str] = []
        self._history: list[str] = []
        self._hindex = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        outer.addWidget(label(t("debug.py.warning"), role="notice", wrap=True))
        self.output = _mono_view()
        self.output.setPlainText(t("debug.py.banner", names=", ".join(sorted(self._locals))) + "\n")
        outer.addWidget(self.output, 1)
        row = QHBoxLayout()
        self.prompt = label(">>>")
        self.prompt.setFont(mono_font(10))
        row.addWidget(self.prompt)
        self.input = QLineEdit()
        self.input.setFont(mono_font(10))
        self.input.returnPressed.connect(self._run)
        self.input.installEventFilter(self)
        row.addWidget(self.input, 1)
        row.addWidget(button(t("debug.py.clear"), variant="ghost", on_click=self.output.clear))
        outer.addLayout(row)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.input and event.type() == event.Type.KeyPress and self._history:
            if event.key() == Qt.Key.Key_Up:
                self._hindex = max(0, self._hindex - 1)
                self.input.setText(self._history[self._hindex])
                return True
            if event.key() == Qt.Key.Key_Down:
                self._hindex = min(len(self._history), self._hindex + 1)
                self.input.setText(self._history[self._hindex] if self._hindex < len(self._history) else "")
                return True
        return False

    def _run(self) -> None:
        line = self.input.text()
        self.input.clear()
        if line.strip():
            self._history.append(line)
        self._hindex = len(self._history)
        self._buffer.append(line)
        self.output.appendPlainText(f"{self.prompt.text()} {line}")
        source = "\n".join(self._buffer)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            more = self._interp.runsource(source, "<mcpack-console>")
        if not more:
            self._buffer = []
            log.debug("Python konsolu: %s", source)
        self.prompt.setText("..." if more else ">>>")
        text = out.getvalue().rstrip("\n")
        if text:
            self.output.appendPlainText(text)


# -- sayfa ----------------------------------------------------------------------------


class DebugPage(QWidget):
    TABS = ["logs", "tasks", "network", "exceptions", "system", "python"]

    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(t("debug.title"), role="title"))
        col.addWidget(label(t("debug.subtitle"), role="muted"))
        head.addLayout(col, 1)
        self.debug_chip = Chip("", "warning")
        head.addWidget(self.debug_chip)
        outer.addLayout(head)
        self.tabs = QTabWidget()
        self.logs = LogsTab(ctl)
        self.tasks_tab = TasksTab(ctl)
        self.network = NetworkTab(ctl)
        self.exceptions = ExceptionsTab(ctl)
        self.system = SystemTab(ctl)
        self.python = PythonConsoleTab(ctl)
        for key, widget in zip(self.TABS, (self.logs, self.tasks_tab, self.network, self.exceptions, self.system, self.python)):
            self.tabs.addTab(widget, t(f"debug.tab.{key}"))
        outer.addWidget(self.tabs, 1)
        ctl.settings_changed.connect(self._refresh_debug_state)
        self._refresh_debug_state()

    def _refresh_debug_state(self) -> None:
        on = is_debug()
        self.debug_chip.set(t("debug.mode_on") if on else t("debug.mode_off"), "warning" if on else "neutral")
        self.tabs.setTabVisible(self.TABS.index("python"), on)
        self.logs.debug_toggle.blockSignals(True)
        self.logs.debug_toggle.setChecked(on)
        self.logs.debug_toggle.blockSignals(False)

    def show_tab(self, key: str) -> None:
        if key in self.TABS:
            if key == "python" and not is_debug():
                return
            self.tabs.setCurrentIndex(self.TABS.index(key))

    def shutdown(self) -> None:
        self.logs.shutdown()

