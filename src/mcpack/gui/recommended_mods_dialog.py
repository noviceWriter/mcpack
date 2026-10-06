"""Bir mod eklenirken bulunan opsiyonel (zorunlu olmayan) bağımlılıkları
kullanıcıya seçtirmek için diyalog.

Required bağımlılıklar otomatik eklenir (bkz. PackManager.resolve_dependencies);
optional olanlar burada listelenir, kullanıcı hangilerini istediğini işaretler.
"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from mcpack.i18n import t
from mcpack.sources.base import ModDetail, ModVersion


class RecommendedModsDialog(QDialog):
    def __init__(self, suggestions: list[tuple[ModVersion, ModDetail]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("recmods.title"))
        self.resize(420, 420)

        layout = QVBoxLayout(self)
        info = QLabel(t("recmods.info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        self._checkboxes: list[tuple[QCheckBox, ModVersion, ModDetail]] = []
        for version, detail in suggestions:
            checkbox = QCheckBox(detail.title)
            scroll_layout.addWidget(checkbox)
            self._checkboxes.append((checkbox, version, detail))
        scroll_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("recmods.add_selected"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("recmods.skip"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> list[tuple[ModVersion, ModDetail]]:
        return [(version, detail) for checkbox, version, detail in self._checkboxes if checkbox.isChecked()]
