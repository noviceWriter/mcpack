"""Ayarlar penceresi: CF API key, SKLauncher yolu, arama tercihi, export
hariç tutma seçenekleri (proje-amacı.md §2.1, §2.3, §6)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mcpack.config import Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(420)
        self._settings = settings

        form = QFormLayout()

        self.cf_key_input = QLineEdit(settings.curseforge_api_key)
        self.cf_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("CurseForge API Key:", self.cf_key_input)

        sklauncher_row = QWidget()
        sklauncher_layout = QHBoxLayout(sklauncher_row)
        sklauncher_layout.setContentsMargins(0, 0, 0, 0)
        self.sklauncher_input = QLineEdit(settings.sklauncher_path)
        sklauncher_layout.addWidget(self.sklauncher_input)
        browse_button = QPushButton("Gözat...")
        browse_button.clicked.connect(self._browse_sklauncher)
        sklauncher_layout.addWidget(browse_button)
        form.addRow("SKLauncher Yolu:", sklauncher_row)

        self.prefer_modrinth_checkbox = QCheckBox("Aynı mod iki kaynakta da varsa Modrinth'i tercih et")
        self.prefer_modrinth_checkbox.setChecked(settings.prefer_modrinth)
        form.addRow(self.prefer_modrinth_checkbox)

        self.exclude_logs_checkbox = QCheckBox("Export'ta logs/ klasörünü hariç tut")
        self.exclude_logs_checkbox.setChecked(settings.exclude_logs)
        form.addRow(self.exclude_logs_checkbox)

        self.exclude_crash_reports_checkbox = QCheckBox("Export'ta crash-reports/ klasörünü hariç tut")
        self.exclude_crash_reports_checkbox.setChecked(settings.exclude_crash_reports)
        form.addRow(self.exclude_crash_reports_checkbox)

        self.exclude_saves_checkbox = QCheckBox("Export'ta saves/ klasörünü hariç tut")
        self.exclude_saves_checkbox.setChecked(settings.exclude_saves)
        form.addRow(self.exclude_saves_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_sklauncher(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Portable SKLauncher Seç")
        if path:
            self.sklauncher_input.setText(path)

    def apply_to(self, settings: Settings) -> None:
        settings.curseforge_api_key = self.cf_key_input.text().strip()
        settings.sklauncher_path = self.sklauncher_input.text().strip()
        settings.prefer_modrinth = self.prefer_modrinth_checkbox.isChecked()
        settings.exclude_logs = self.exclude_logs_checkbox.isChecked()
        settings.exclude_crash_reports = self.exclude_crash_reports_checkbox.isChecked()
        settings.exclude_saves = self.exclude_saves_checkbox.isChecked()
