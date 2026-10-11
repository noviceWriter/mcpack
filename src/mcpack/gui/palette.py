"""Komut paleti (Ctrl+K): sayfalara, pack'lere ve eylemlere klavyeden
bulanık (fuzzy) arama ile hızlı erişim."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from mcpack.gui.components import label
from mcpack.gui.formatting import fuzzy_score
from mcpack.i18n import t


@dataclass
class Command:
    title: str
    run: Callable[[], None]
    group: str = ""
    hint: str = ""
    shortcut: str = ""


class _Row(QWidget):
    def __init__(self, cmd: Command) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.addWidget(label(cmd.title), 1)
        if cmd.hint:
            row.addWidget(label(cmd.hint, role="dim"))
        if cmd.group:
            row.addWidget(label(cmd.group, role="dim"))
        if cmd.shortcut:
            row.addWidget(label(cmd.shortcut, role="kbd"))


class CommandPalette(QDialog):
    def __init__(self, commands: list[Command], parent=None) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._commands = commands
        self._visible: list[Command] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("Palette")
        outer.addWidget(frame)
        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 0, 0, 8)
        col.setSpacing(0)
        self.input = QLineEdit()
        self.input.setPlaceholderText(t("palette.placeholder"))
        self.input.textChanged.connect(self._filter)
        self.input.installEventFilter(self)
        col.addWidget(self.input)
        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _i: self._run())
        self.list.itemClicked.connect(lambda _i: self._run())
        col.addWidget(self.list)
        foot = QHBoxLayout()
        foot.setContentsMargins(14, 6, 14, 0)
        foot.addWidget(label(t("palette.footer"), role="dim"))
        col.addLayout(foot)
        self.resize(620, 440)
        self._filter("")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            geo = parent.geometry()
            self.move(geo.x() + (geo.width() - self.width()) // 2, geo.y() + 90)
        self.input.setFocus()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow() + (1 if key == Qt.Key.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run()
                return True
            if key == Qt.Key.Key_Escape:
                self.reject()
                return True
        return False

    def _filter(self, text: str) -> None:
        scored = []
        for i, cmd in enumerate(self._commands):
            score = fuzzy_score(text, f"{cmd.title} {cmd.group} {cmd.hint}")
            if score is not None:
                scored.append((score, i, cmd))
        scored.sort(key=lambda x: (x[0], x[1]))
        self._visible = [c for _s, _i, c in scored[:60]]
        self.list.clear()
        for cmd in self._visible:
            item = QListWidgetItem()
            row = _Row(cmd)
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        if self._visible:
            self.list.setCurrentRow(0)

    def _run(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._visible):
            cmd = self._visible[row]
            self.accept()
            cmd.run()
