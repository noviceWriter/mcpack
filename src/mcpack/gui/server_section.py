"""Instance sayfasının "Sunucu" bölümü: yerel sunucuyu hazırla/kur/başlat/
durdur, canlı/renkli konsolu göster (geçmişli komut girişi, arama, temizle),
bellek (GB/MB)/dünya/performans/server.properties ayarlarını düzenle, ve
çevrimiçi oyuncuları yönet (bkz. player_panel.py).

Diğer *Section sınıfları gibi (bkz. instance_page.py:CheatModsSection) bu
widget "aptal" bir görünümdür — gerçek iş (ağ, subprocess, dosya) hiç burada
değil, MainWindow'da (bkz. main_window.py) yapılır; bu widget sadece
sinyal yayınlar ve MainWindow'un çağırdığı set_*/append_* metodlarıyla
kendini günceller."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mcpack.export.server import filter_server_mods
from mcpack.gui.player_panel import PlayerPanel
from mcpack.gui.theme import danger_color, status_good_color
from mcpack.i18n import t
from mcpack.models import ContentKind, Pack
from mcpack.server_properties import KNOWN_PROPERTIES
from mcpack.server_runtime import (
    SYSTEM_MEMORY_RESERVE_MB,
    ServerState,
    get_system_memory_mb,
    max_safe_server_memory_mb,
)


def _eula_text() -> str:
    return t("server.eula_text")


def _state_labels() -> dict[ServerState, str]:
    return {
        "not_prepared": t("server.state.not_prepared"),
        "needs_install": t("server.state.needs_install"),
        "ready": t("server.state.ready"),
    }

_GB_PRESETS = [1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32]
_CUSTOM_MB_DATA = "custom"

_LOG_LEVEL_RE = re.compile(r"\]\s*\[[^/\]]+/(INFO|WARN|ERROR)\]")


class _CommandLineEdit(QLineEdit):
    """Normal QLineEdit + terminal benzeri komut geçmişi: ↑/↓ ile daha
    önce gönderilen komutlar arasında gezinilir (proje isteği: "konsol
    kısmını baya geliştirelim")."""

    def __init__(self) -> None:
        super().__init__()
        self._history: list[str] = []
        self._history_index = 0

    def remember(self, text: str) -> None:
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._history_index = len(self._history)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.key() == Qt.Key.Key_Up:
            if self._history and self._history_index > 0:
                self._history_index -= 1
                self.setText(self._history[self._history_index])
            return
        if event.key() == Qt.Key.Key_Down:
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.setText(self._history[self._history_index])
            else:
                self._history_index = len(self._history)
                self.clear()
            return
        super().keyPressEvent(event)


class ServerSection(QWidget):
    prepare_requested = Signal()
    install_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    command_requested = Signal(str)
    eula_accepted_requested = Signal()
    settings_changed = Signal(int, object, bool)  # memory_mb, selected_world, use_optimized_flags
    properties_saved = Signal(dict)  # bilinen alanlar: key -> value (str)

    def __init__(self) -> None:
        super().__init__()
        self._pack: Pack | None = None
        self._state: ServerState = "not_prepared"
        self._running = False
        self._auto_scroll = True

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 4, 0)
        outer.setSpacing(10)

        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        status_row.addWidget(self.status_dot)
        self.status_label = QLabel(t("server.status.stopped"))
        status_row.addWidget(self.status_label)
        status_row.addSpacing(16)
        self.state_label = QLabel("")
        self.state_label.setProperty("role", "muted")
        status_row.addWidget(self.state_label)
        status_row.addStretch()
        outer.addLayout(status_row)

        button_row = QHBoxLayout()
        self.prepare_button = QPushButton(t("server.prepare_button"))
        self.prepare_button.clicked.connect(self.prepare_requested.emit)
        button_row.addWidget(self.prepare_button)

        self.install_button = QPushButton(t("server.install_button"))
        self.install_button.clicked.connect(self.install_requested.emit)
        button_row.addWidget(self.install_button)

        self.start_button = QPushButton(t("server.start_button"))
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._on_start_clicked)
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton(t("server.stop_button"))
        self.stop_button.setObjectName("danger")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        button_row.addWidget(self.stop_button)
        button_row.addStretch()
        outer.addLayout(button_row)

        self.mods_box = QGroupBox(t("server.mods_box_title"))
        mods_layout = QVBoxLayout(self.mods_box)
        self.mods_list = QListWidget()
        self.mods_list.setMaximumHeight(130)
        mods_layout.addWidget(self.mods_list)
        self.mods_excluded_label = QLabel("")
        self.mods_excluded_label.setProperty("role", "muted")
        self.mods_excluded_label.setWordWrap(True)
        mods_layout.addWidget(self.mods_excluded_label)
        outer.addWidget(self.mods_box)

        player_box = QGroupBox(t("server.players_box_title"))
        player_layout = QVBoxLayout(player_box)
        self.player_panel = PlayerPanel()
        player_layout.addWidget(self.player_panel)
        outer.addWidget(player_box)

        console_toolbar = QHBoxLayout()
        clear_console_button = QPushButton(t("server.clear_console"))
        clear_console_button.clicked.connect(self.clear_console)
        console_toolbar.addWidget(clear_console_button)

        self.console_search_input = QLineEdit()
        self.console_search_input.setPlaceholderText(t("server.console_search_placeholder"))
        self.console_search_input.returnPressed.connect(self._on_console_search)
        console_toolbar.addWidget(self.console_search_input)
        search_button = QPushButton(t("server.find_button"))
        search_button.clicked.connect(self._on_console_search)
        console_toolbar.addWidget(search_button)

        self.auto_scroll_checkbox = QCheckBox(t("server.auto_scroll"))
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.toggled.connect(self._on_auto_scroll_toggled)
        console_toolbar.addWidget(self.auto_scroll_checkbox)
        console_toolbar.addStretch()
        outer.addLayout(console_toolbar)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        self.console.setFont(QFont("monospace"))
        self.console.setMinimumHeight(260)
        outer.addWidget(self.console)

        command_row = QHBoxLayout()
        self.command_input = _CommandLineEdit()
        self.command_input.setPlaceholderText(t("server.command_placeholder"))
        self.command_input.returnPressed.connect(self._on_send_clicked)
        command_row.addWidget(self.command_input)
        send_button = QPushButton(t("server.send_button"))
        send_button.clicked.connect(self._on_send_clicked)
        command_row.addWidget(send_button)
        outer.addLayout(command_row)

        settings_box = QGroupBox(t("server.settings_box_title"))
        settings_form = QFormLayout(settings_box)

        memory_row = QWidget()
        memory_layout = QHBoxLayout(memory_row)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        self.memory_unit_combo = QComboBox()

        # Kullanıcı isteği: "16 GB RAM'i olan birinin bilgisayarı en fazla
        # 14 GB kullansın, kullanıcıya en az 2 GB bıraksın" — sisteme
        # gerçekten var olandan FAZLA bir GB seçeneği hiç GÖSTERİLMEZ
        # (seçip sonra engellemek yerine).
        total_mb = get_system_memory_mb()
        self._max_safe_memory_mb = max_safe_server_memory_mb(total_mb)
        allowed_presets = [
            gb for gb in _GB_PRESETS if self._max_safe_memory_mb is None or gb * 1024 <= self._max_safe_memory_mb
        ] or [_GB_PRESETS[0]]
        for gb in allowed_presets:
            self.memory_unit_combo.addItem(f"{gb} GB", gb * 1024)
        self.memory_unit_combo.addItem(t("server.memory_custom"), _CUSTOM_MB_DATA)
        self.memory_unit_combo.currentIndexChanged.connect(self._on_memory_unit_changed)
        memory_layout.addWidget(self.memory_unit_combo)

        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(512, self._max_safe_memory_mb or 131072)
        self.memory_spin.setSingleStep(512)
        self.memory_spin.setSuffix(" MB")
        self.memory_spin.valueChanged.connect(self._emit_settings_changed)
        memory_layout.addWidget(self.memory_spin)
        settings_form.addRow(t("server.memory_label"), memory_row)

        memory_info = QLabel(self._memory_info_text(total_mb, self._max_safe_memory_mb))
        memory_info.setProperty("role", "muted")
        memory_info.setWordWrap(True)
        settings_form.addRow("", memory_info)

        self.world_combo = QComboBox()
        self.world_combo.addItem(t("server.no_world"), None)
        self.world_combo.currentIndexChanged.connect(self._emit_settings_changed)
        settings_form.addRow(t("server.world_label"), self.world_combo)

        self.optimized_checkbox = QCheckBox(t("server.optimized_flags_checkbox"))
        self.optimized_checkbox.setToolTip(t("server.optimized_flags_tooltip"))
        self.optimized_checkbox.toggled.connect(self._emit_settings_changed)
        settings_form.addRow("", self.optimized_checkbox)

        outer.addWidget(settings_box)

        properties_box = QGroupBox("server.properties")
        properties_form = QFormLayout(properties_box)
        self._property_widgets: dict[str, QWidget] = {}
        for prop in KNOWN_PROPERTIES:
            widget = self._build_property_widget(prop)
            self._property_widgets[prop.key] = widget
            properties_form.addRow(t(f"serverprop.{prop.key}.label") + ":", widget)
        save_properties_button = QPushButton(t("server.save_properties_button"))
        save_properties_button.clicked.connect(self._on_save_properties_clicked)
        properties_form.addRow("", save_properties_button)
        outer.addWidget(properties_box)

        self._update_button_states()

    # -- bellek (GB/MB) --------------------------------------------------------

    @staticmethod
    def _memory_info_text(total_mb: int | None, max_safe_mb: int | None) -> str:
        if total_mb is None or max_safe_mb is None:
            return t("server.memory_info_unknown")
        return t(
            "server.memory_info",
            total_gb=f"{total_mb / 1024:.1f}",
            max_gb=f"{max_safe_mb / 1024:.1f}",
            reserve_gb=f"{SYSTEM_MEMORY_RESERVE_MB / 1024:.0f}",
        )

    def _on_memory_unit_changed(self) -> None:
        data = self.memory_unit_combo.currentData()
        if data == _CUSTOM_MB_DATA:
            self.memory_spin.setEnabled(True)
            return
        self.memory_spin.setEnabled(False)
        self.memory_spin.setValue(int(data))

    def _sync_memory_unit_combo(self, memory_mb: int) -> None:
        idx = self.memory_unit_combo.findData(memory_mb)
        if idx < 0:
            idx = self.memory_unit_combo.findData(_CUSTOM_MB_DATA)
        self.memory_unit_combo.blockSignals(True)
        self.memory_unit_combo.setCurrentIndex(idx)
        self.memory_spin.setEnabled(self.memory_unit_combo.currentData() == _CUSTOM_MB_DATA)
        self.memory_unit_combo.blockSignals(False)

    # -- konsol ------------------------------------------------------------

    def _color_for_line(self, text: str) -> QColor | None:
        match = _LOG_LEVEL_RE.search(text)
        if not match:
            return None
        level = match.group(1)
        if level == "ERROR":
            return QColor(danger_color())
        if level == "WARN":
            return QColor("#d97706")
        return None  # INFO: varsayılan renk, boyama yapma

    def _insert_colored_line(self, text: str) -> None:
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        color = self._color_for_line(text)
        if color is not None:
            fmt.setForeground(color)
        cursor.insertText(text + "\n", fmt)

    def append_console_line(self, text: str) -> None:
        self._insert_colored_line(text)
        if self._auto_scroll:
            bar = self.console.verticalScrollBar()
            bar.setValue(bar.maximum())

    def set_console_lines(self, lines: list[str]) -> None:
        self.console.clear()
        for line in lines:
            self._insert_colored_line(line)
        if self._auto_scroll:
            bar = self.console.verticalScrollBar()
            bar.setValue(bar.maximum())

    def clear_console(self) -> None:
        self.console.clear()

    def _on_auto_scroll_toggled(self, checked: bool) -> None:
        self._auto_scroll = checked

    def _on_console_search(self) -> None:
        text = self.console_search_input.text().strip()
        if not text:
            return
        if not self.console.find(text):
            # Bulunamadı ya da imleç sonun geçtiyse baştan dene.
            cursor = self.console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.console.setTextCursor(cursor)
            self.console.find(text)

    # -- property form yardımcıları -----------------------------------------

    def _build_property_widget(self, prop) -> QWidget:
        if prop.type == "bool":
            box = QCheckBox()
            box.setChecked(prop.default == "true")
            return box
        if prop.type == "choice":
            combo = QComboBox()
            combo.addItems(prop.choices)
            combo.setCurrentText(prop.default)
            return combo
        if prop.type == "int":
            spin = QSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setValue(int(prop.default) if prop.default.isdigit() else 0)
            return spin
        line = QLineEdit(prop.default)
        return line

    def _property_widget_value(self, widget: QWidget) -> str:
        if isinstance(widget, QCheckBox):
            return "true" if widget.isChecked() else "false"
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    def _set_property_widget_value(self, widget: QWidget, value: str) -> None:
        if isinstance(widget, QCheckBox):
            widget.setChecked(value.lower() == "true")
        elif isinstance(widget, QComboBox):
            if value:
                widget.setCurrentText(value)
        elif isinstance(widget, QSpinBox):
            try:
                widget.setValue(int(value))
            except ValueError:
                pass
        elif isinstance(widget, QLineEdit):
            widget.setText(value)

    def _on_save_properties_clicked(self) -> None:
        values = {key: self._property_widget_value(w) for key, w in self._property_widgets.items()}
        self.properties_saved.emit(values)

    def set_properties(self, values: dict[str, str]) -> None:
        for key, widget in self._property_widgets.items():
            if key in values:
                self._set_property_widget_value(widget, values[key])

    # -- EULA -----------------------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self._pack is not None and not self._pack.server.eula_accepted:
            if not self._confirm_eula():
                return
            self.eula_accepted_requested.emit()
        self.start_requested.emit()

    def _confirm_eula(self) -> bool:
        answer = QMessageBox.question(
            self, "Minecraft EULA", _eula_text(),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # -- komut ------------------------------------------------------------

    def _on_send_clicked(self) -> None:
        text = self.command_input.text().strip()
        if not text:
            return
        self.command_input.remember(text)
        self.command_requested.emit(text)
        self.command_input.clear()

    def _emit_settings_changed(self) -> None:
        self.settings_changed.emit(
            self.memory_spin.value(), self.world_combo.currentData(), self.optimized_checkbox.isChecked()
        )

    # -- MainWindow'un çağırdığı güncelleme metodları -------------------------

    def _refresh_mods_list(self, pack: Pack | None) -> None:
        """Kullanıcı isteği: "server kısmında mod falan var ise onları da
        göstersin" — Hazırla'ya basılınca server_root'a kopyalanacak
        modların AYNISI (bkz. export/server.py:filter_server_mods, hem zip
        export'ta hem burada aynı eleme mantığı) burada da listelenir."""
        self.mods_list.clear()
        if pack is None:
            self.mods_box.setTitle(t("server.mods_box_title"))
            self.mods_excluded_label.setText("")
            return
        server_mods = filter_server_mods(pack)
        self.mods_box.setTitle(t("server.mods_box_title_with_count", count=len(server_mods)))
        for mod in server_mods:
            self.mods_list.addItem(mod.name or mod.file_name)
        excluded = len(pack.mods) - len(server_mods)
        if excluded > 0:
            self.mods_excluded_label.setText(t("server.mods_excluded_note", count=excluded))
        else:
            self.mods_excluded_label.setText("")

    def show_pack(self, pack: Pack | None) -> None:
        self._pack = pack
        self._refresh_mods_list(pack)
        self.world_combo.blockSignals(True)
        self.memory_spin.blockSignals(True)
        self.optimized_checkbox.blockSignals(True)
        try:
            self.world_combo.clear()
            self.world_combo.addItem(t("server.no_world"), None)
            if pack is not None:
                for entry in pack.content_of(ContentKind.WORLD):
                    self.world_combo.addItem(entry.name, entry.name)
                idx = self.world_combo.findData(pack.server.selected_world)
                self.world_combo.setCurrentIndex(idx if idx >= 0 else 0)
                self.memory_spin.setValue(pack.server.memory_mb)
                self._sync_memory_unit_combo(pack.server.memory_mb)
                self.optimized_checkbox.setChecked(pack.server.use_optimized_flags)
        finally:
            self.world_combo.blockSignals(False)
            self.memory_spin.blockSignals(False)
            self.optimized_checkbox.blockSignals(False)
        self._update_button_states()

    def set_state(self, state: ServerState) -> None:
        self._state = state
        self.state_label.setText(_state_labels().get(state, state))
        self._update_button_states()

    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self.status_dot.setStyleSheet(f"color: {status_good_color()};")
            self.status_label.setText(t("server.status.running"))
        else:
            self.status_dot.setStyleSheet(f"color: {danger_color()};")
            self.status_label.setText(t("server.status.stopped"))
        self.player_panel.set_running(running)
        self._update_button_states()

    def _update_button_states(self) -> None:
        self.prepare_button.setEnabled(not self._running)
        self.install_button.setEnabled(not self._running and self._state == "needs_install")
        self.install_button.setVisible(self._state == "needs_install")
        self.start_button.setEnabled(not self._running and self._state == "ready")
        self.stop_button.setEnabled(self._running)
        self.command_input.setEnabled(self._running)
