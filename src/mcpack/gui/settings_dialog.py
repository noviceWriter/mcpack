"""Ayarlar penceresi: CF API key, SKLauncher yolu, arama tercihi, export
hariç tutma seçenekleri (proje-amacı.md §2.1, §2.3, §6)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mcpack.config import Settings
from mcpack.gui.theme import danger_color, status_good_color
from mcpack.gui.widgets import run_async
from mcpack.i18n import t
from mcpack.sources.curseforge import CurseForgeClient
from mcpack.sources.base import SourceAPIError


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(440)
        self._settings = settings

        form = QFormLayout()

        form.addRow(_section_label(t("settings.section.language")))
        self.language_combo = QComboBox()
        self.language_combo.addItem(t("settings.language.tr"), "tr")
        self.language_combo.addItem(t("settings.language.en"), "en")
        index = self.language_combo.findData(settings.language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(t("settings.language.label"), self.language_combo)
        language_note = QLabel(t("settings.language.restart_note"))
        language_note.setWordWrap(True)
        language_note.setProperty("role", "muted")
        form.addRow("", language_note)

        form.addRow(_section_label(t("settings.section.mod_sources")))
        cf_key_row = QWidget()
        cf_key_layout = QHBoxLayout(cf_key_row)
        cf_key_layout.setContentsMargins(0, 0, 0, 0)
        self.cf_key_input = QLineEdit(settings.curseforge_api_key)
        self.cf_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cf_key_input.textChanged.connect(self._on_cf_key_changed)
        cf_key_layout.addWidget(self.cf_key_input)
        self.cf_test_button = QPushButton(t("settings.cf_test_button"))
        self.cf_test_button.setEnabled(bool(settings.curseforge_api_key))
        self.cf_test_button.clicked.connect(self._test_cf_connection)
        cf_key_layout.addWidget(self.cf_test_button)
        form.addRow(t("settings.cf_api_key_label"), cf_key_row)

        self.cf_status_label = QLabel("")
        self.cf_status_label.setWordWrap(True)
        form.addRow("", self.cf_status_label)

        self.prefer_modrinth_checkbox = QCheckBox(t("settings.prefer_modrinth"))
        self.prefer_modrinth_checkbox.setChecked(settings.prefer_modrinth)
        form.addRow(self.prefer_modrinth_checkbox)

        form.addRow(_section_label(t("settings.section.sklauncher")))
        sklauncher_row = QWidget()
        sklauncher_layout = QHBoxLayout(sklauncher_row)
        sklauncher_layout.setContentsMargins(0, 0, 0, 0)
        self.sklauncher_input = QLineEdit(settings.sklauncher_path)
        sklauncher_layout.addWidget(self.sklauncher_input)
        browse_button = QPushButton(t("settings.browse_button"))
        browse_button.clicked.connect(self._browse_sklauncher)
        sklauncher_layout.addWidget(browse_button)
        form.addRow(t("settings.sklauncher_path_label"), sklauncher_row)

        form.addRow(_section_label(t("settings.section.local_server")))
        java_row = QWidget()
        java_layout = QHBoxLayout(java_row)
        java_layout.setContentsMargins(0, 0, 0, 0)
        self.java_input = QLineEdit(settings.java_path)
        self.java_input.setPlaceholderText(t("settings.java_placeholder"))
        java_layout.addWidget(self.java_input)
        java_browse_button = QPushButton(t("settings.browse_button"))
        java_browse_button.clicked.connect(self._browse_java)
        java_layout.addWidget(java_browse_button)
        form.addRow(t("settings.java_path_label"), java_row)

        form.addRow(_section_label(t("settings.section.web_panel")))
        self.web_panel_port_input = QSpinBox()
        self.web_panel_port_input.setRange(1024, 65535)
        self.web_panel_port_input.setValue(settings.web_panel_port)
        form.addRow(t("settings.web_panel_port_label"), self.web_panel_port_input)

        self.web_panel_password_input = QLineEdit(settings.web_panel_password)
        self.web_panel_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.web_panel_password_input.setPlaceholderText(t("settings.web_panel_password_placeholder"))
        form.addRow(t("settings.web_panel_password_label"), self.web_panel_password_input)
        web_panel_note = QLabel(t("settings.web_panel_note"))
        web_panel_note.setWordWrap(True)
        web_panel_note.setProperty("role", "muted")
        form.addRow("", web_panel_note)

        form.addRow(_section_label(t("settings.section.export")))
        self.exclude_logs_checkbox = QCheckBox(t("settings.exclude_logs"))
        self.exclude_logs_checkbox.setChecked(settings.exclude_logs)
        form.addRow(self.exclude_logs_checkbox)

        self.exclude_crash_reports_checkbox = QCheckBox(t("settings.exclude_crash_reports"))
        self.exclude_crash_reports_checkbox.setChecked(settings.exclude_crash_reports)
        form.addRow(self.exclude_crash_reports_checkbox)

        self.exclude_saves_checkbox = QCheckBox(t("settings.exclude_saves"))
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
        path, _ = QFileDialog.getOpenFileName(self, t("settings.sklauncher_dialog_title"))
        if path:
            self.sklauncher_input.setText(path)

    def _browse_java(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("settings.java_dialog_title"))
        if path:
            self.java_input.setText(path)

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
        self.cf_status_label.setText(t("settings.cf_checking"))

        async def task() -> str:
            client = CurseForgeClient(api_key)
            try:
                return await client.check_connection()
            finally:
                await client.aclose()

        def on_success(game_name: str) -> None:
            self.cf_test_button.setEnabled(True)
            self.cf_status_label.setStyleSheet(f"color: {status_good_color()};")
            self.cf_status_label.setText(t("settings.cf_connected", game_name=game_name))

        def on_error(message: str) -> None:
            self.cf_test_button.setEnabled(True)
            self.cf_status_label.setStyleSheet(f"color: {danger_color()};")
            self.cf_status_label.setText(t("settings.cf_connection_failed", message=message))

        run_async(task, on_success=on_success, on_error=on_error)

    def apply_to(self, settings: Settings) -> None:
        settings.theme = "dark"
        settings.language = self.language_combo.currentData()
        settings.curseforge_api_key = self.cf_key_input.text().strip()
        settings.sklauncher_path = self.sklauncher_input.text().strip()
        settings.java_path = self.java_input.text().strip()
        settings.web_panel_port = self.web_panel_port_input.value()
        settings.web_panel_password = self.web_panel_password_input.text()
        settings.prefer_modrinth = self.prefer_modrinth_checkbox.isChecked()
        settings.exclude_logs = self.exclude_logs_checkbox.isChecked()
        settings.exclude_crash_reports = self.exclude_crash_reports_checkbox.isChecked()
        settings.exclude_saves = self.exclude_saves_checkbox.isChecked()
