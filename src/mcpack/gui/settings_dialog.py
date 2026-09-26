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
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mcpack.config import Settings
from mcpack.gui.theme import danger_color, status_good_color
from mcpack.gui.widgets import run_async
from mcpack.sources.curseforge import CurseForgeClient
from mcpack.sources.base import SourceAPIError


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(440)
        self._settings = settings

        form = QFormLayout()

        form.addRow(_section_label("Mod Kaynakları"))
        cf_key_row = QWidget()
        cf_key_layout = QHBoxLayout(cf_key_row)
        cf_key_layout.setContentsMargins(0, 0, 0, 0)
        self.cf_key_input = QLineEdit(settings.curseforge_api_key)
        self.cf_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cf_key_input.textChanged.connect(self._on_cf_key_changed)
        cf_key_layout.addWidget(self.cf_key_input)
        self.cf_test_button = QPushButton("Bağlantıyı Test Et")
        self.cf_test_button.setEnabled(bool(settings.curseforge_api_key))
        self.cf_test_button.clicked.connect(self._test_cf_connection)
        cf_key_layout.addWidget(self.cf_test_button)
        form.addRow("CurseForge API Key:", cf_key_row)

        self.cf_status_label = QLabel("")
        self.cf_status_label.setWordWrap(True)
        form.addRow("", self.cf_status_label)

        self.prefer_modrinth_checkbox = QCheckBox("Aynı mod iki kaynakta da varsa Modrinth'i tercih et")
        self.prefer_modrinth_checkbox.setChecked(settings.prefer_modrinth)
        form.addRow(self.prefer_modrinth_checkbox)

        form.addRow(_section_label("SKLauncher"))
        sklauncher_row = QWidget()
        sklauncher_layout = QHBoxLayout(sklauncher_row)
        sklauncher_layout.setContentsMargins(0, 0, 0, 0)
        self.sklauncher_input = QLineEdit(settings.sklauncher_path)
        sklauncher_layout.addWidget(self.sklauncher_input)
        browse_button = QPushButton("Gözat...")
        browse_button.clicked.connect(self._browse_sklauncher)
        sklauncher_layout.addWidget(browse_button)
        form.addRow("Taşınabilir Yol:", sklauncher_row)

        form.addRow(_section_label("Dışa Aktarma"))
        self.exclude_logs_checkbox = QCheckBox("Dışa aktarımda logs/ klasörünü hariç tut")
        self.exclude_logs_checkbox.setChecked(settings.exclude_logs)
        form.addRow(self.exclude_logs_checkbox)

        self.exclude_crash_reports_checkbox = QCheckBox("Dışa aktarımda crash-reports/ klasörünü hariç tut")
        self.exclude_crash_reports_checkbox.setChecked(settings.exclude_crash_reports)
        form.addRow(self.exclude_crash_reports_checkbox)

        self.exclude_saves_checkbox = QCheckBox("Dışa aktarımda saves/ klasörünü hariç tut")
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
        path, _ = QFileDialog.getOpenFileName(self, "Taşınabilir SKLauncher Seç")
        if path:
            self.sklauncher_input.setText(path)

    def _on_cf_key_changed(self, text: str) -> None:
        self.cf_test_button.setEnabled(bool(text.strip()))
        self.cf_status_label.setText("")

    def _test_cf_connection(self) -> None:
        """CurseForge API'sine gerçekten bağlanılabiliyor mu — key doğru mu,
        ağ/CDN engeli var mı — export sırasında sürpriz bir hatayla
        karşılaşmadan önce kullanıcının kendi kontrol edebilmesi için."""
        api_key = self.cf_key_input.text().strip()
        if not api_key:
            return

        self.cf_test_button.setEnabled(False)
        self.cf_status_label.setStyleSheet("")
        self.cf_status_label.setText("Kontrol ediliyor...")

        async def task() -> str:
            client = CurseForgeClient(api_key)
            try:
                return await client.check_connection()
            finally:
                await client.aclose()

        def on_success(game_name: str) -> None:
            self.cf_test_button.setEnabled(True)
            self.cf_status_label.setStyleSheet(f"color: {status_good_color()};")
            self.cf_status_label.setText(f"✓ Bağlandı ({game_name})")

        def on_error(message: str) -> None:
            self.cf_test_button.setEnabled(True)
            self.cf_status_label.setStyleSheet(f"color: {danger_color()};")
            self.cf_status_label.setText(f"✗ Bağlanamadı: {message}")

        run_async(task, on_success=on_success, on_error=on_error)

    def apply_to(self, settings: Settings) -> None:
        settings.theme = "dark"
        settings.curseforge_api_key = self.cf_key_input.text().strip()
        settings.sklauncher_path = self.sklauncher_input.text().strip()
        settings.prefer_modrinth = self.prefer_modrinth_checkbox.isChecked()
        settings.exclude_logs = self.exclude_logs_checkbox.isChecked()
        settings.exclude_crash_reports = self.exclude_crash_reports_checkbox.isChecked()
        settings.exclude_saves = self.exclude_saves_checkbox.isChecked()
