"""Ayarlar sayfası: kartlar halinde gruplanmış tüm ayarlar, değişiklik
takibi (kaydedilmemiş değişiklik göstergesi), Java/CurseForge testleri,
önbellek yönetimi."""

from __future__ import annotations

import shutil

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mcpack.config import Settings, default_packs_dir
from mcpack.gui import pack_actions
from mcpack.gui.components import Card, button, info, label
from mcpack.gui.controller import AppController
from mcpack.gui.formatting import format_size
from mcpack.gui.icons import icons
from mcpack.gui.theme import COLORS
from mcpack.i18n import t
from mcpack.server_runtime import find_java, get_java_major_version
from mcpack.sources.curseforge import CurseForgeClient


def _dir_size(path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    return total


class SettingsPage(QWidget):
    def __init__(self, ctl: AppController) -> None:
        super().__init__()
        self.ctl = ctl
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(14)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(t("settings.title"), role="title"))
        self.dirty_label = label(t("settings.subtitle"), role="muted")
        col.addWidget(self.dirty_label)
        head.addLayout(col, 1)
        self.reset_btn = button(t("settings.reset"), variant="ghost", on_click=self.reset_to_defaults, tooltip=t("settings.reset_tooltip"))
        head.addWidget(self.reset_btn)
        self.revert_btn = button(t("settings.revert"), variant="ghost", on_click=self.load)
        self.save_btn = button(t("settings.save"), variant="primary", on_click=self.save)
        head.addWidget(self.revert_btn)
        head.addWidget(self.save_btn)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        self.col = QVBoxLayout(body)
        self.col.setContentsMargins(0, 0, 8, 0)
        self.col.setSpacing(14)
        root.addWidget(scroll, 1)

        # -- genel
        general = self._card(t("settings.sec_general"))
        form = self._form(general)
        self.language = QComboBox()
        self.language.addItem("Türkçe", "tr")
        self.language.addItem("English", "en")
        form.addRow(t("settings.language"), self.language)
        form.addRow("", label(t("settings.language_note"), role="dim", wrap=True))
        self.debug = QCheckBox(t("settings.debug_mode"))
        form.addRow("", self.debug)
        form.addRow("", label(t("settings.debug_note"), role="dim", wrap=True))

        # -- mod kaynakları
        sources = self._card(t("settings.sec_sources"))
        form = self._form(sources)
        key_row = QHBoxLayout()
        self.cf_key = QLineEdit()
        self.cf_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cf_key.setPlaceholderText(t("settings.cf_placeholder"))
        key_row.addWidget(self.cf_key, 1)
        self.cf_show = button("👁", variant="ghost", tooltip=t("settings.show"), checkable=True)
        self.cf_show.toggled.connect(lambda on: self.cf_key.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        key_row.addWidget(self.cf_show)
        self.cf_test = button(t("settings.test"), on_click=self._test_cf)
        key_row.addWidget(self.cf_test)
        form.addRow(t("settings.cf_key"), key_row)
        self.cf_status = label("", role="dim", wrap=True)
        form.addRow("", self.cf_status)
        form.addRow("", label(t("settings.cf_help"), role="dim", wrap=True))
        self.prefer_modrinth = QCheckBox(t("settings.prefer_modrinth"))
        form.addRow("", self.prefer_modrinth)

        # -- başlatıcı / java
        runtime = self._card(t("settings.sec_runtime"))
        form = self._form(runtime)
        self.sklauncher = QLineEdit()
        form.addRow(t("settings.sklauncher"), self._path_row(self.sklauncher, file=True))
        self.java = QLineEdit()
        self.java.setPlaceholderText(t("settings.java_placeholder"))
        java_row = self._path_row(self.java, file=True)
        java_row.addWidget(button(t("settings.detect"), on_click=self._detect_java))
        form.addRow("Java", java_row)
        self.java_status = label("", role="dim", wrap=True)
        form.addRow("", self.java_status)

        # -- web paneli
        web = self._card(t("settings.sec_web"))
        form = self._form(web)
        self.web_port = QSpinBox()
        self.web_port.setRange(1024, 65535)
        form.addRow(t("settings.web_port"), self.web_port)
        self.web_password = QLineEdit()
        self.web_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.web_password.setPlaceholderText(t("settings.web_password_placeholder"))
        form.addRow(t("settings.web_password"), self.web_password)
        form.addRow("", label(t("settings.web_note"), role="dim", wrap=True))
        web_row = QHBoxLayout()
        self.web_toggle = button("", on_click=self._toggle_web)
        web_row.addWidget(self.web_toggle)
        self.web_url = label("", role="muted", selectable=True)
        web_row.addWidget(self.web_url, 1)
        form.addRow("", web_row)

        # -- dışa aktarma
        export = self._card(t("settings.sec_export"))
        form = self._form(export)
        self.ex_logs = QCheckBox(t("settings.exclude_logs"))
        self.ex_crash = QCheckBox(t("settings.exclude_crash"))
        self.ex_saves = QCheckBox(t("settings.exclude_saves"))
        for w in (self.ex_logs, self.ex_crash, self.ex_saves):
            form.addRow("", w)

        # -- veri
        data = self._card(t("settings.sec_data"))
        form = self._form(data)
        self.packs_dir = QLineEdit()
        self.packs_dir.setPlaceholderText(str(default_packs_dir()))
        dir_row = self._path_row(self.packs_dir, file=False)
        dir_row.addWidget(button(t("settings.open"), variant="ghost", on_click=lambda: pack_actions.open_folder(ctl.settings.resolved_packs_dir())))
        form.addRow(t("settings.packs_dir"), dir_row)
        cache_row = QHBoxLayout()
        self.cache_label = label("", role="muted")
        cache_row.addWidget(self.cache_label, 1)
        cache_row.addWidget(button(t("settings.measure"), variant="ghost", on_click=self._measure_cache))
        cache_row.addWidget(button(t("settings.clear_cache"), variant="danger", on_click=self._clear_cache))
        form.addRow(t("settings.cache"), cache_row)

        self.col.addStretch()

        self._watch = [
            self.language, self.debug, self.cf_key, self.prefer_modrinth, self.sklauncher, self.java,
            self.web_port, self.web_password, self.ex_logs, self.ex_crash, self.ex_saves, self.packs_dir,
        ]
        for w in self._watch:
            if isinstance(w, QLineEdit):
                sig = w.textChanged
            elif isinstance(w, QSpinBox):
                sig = w.valueChanged
            elif isinstance(w, QComboBox):
                sig = w.currentIndexChanged
            else:
                sig = w.toggled
            sig.connect(lambda *_a: self._update_dirty())
        ctl.web_panel_changed.connect(lambda *_a: self._refresh_web())
        self.load()

    # -- yardımcılar ----------------------------------------------------------------

    def _card(self, title: str) -> Card:
        card = Card(padding=18, spacing=10)
        card.body.addWidget(label(title, role="h3"))
        self.col.addWidget(card)
        return card

    def _form(self, card: Card) -> QFormLayout:
        form = QFormLayout()
        form.setSpacing(10)
        form.setHorizontalSpacing(18)
        card.body.addLayout(form)
        return form

    def _path_row(self, edit: QLineEdit, *, file: bool) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit, 1)

        def browse() -> None:
            if file:
                path, _ = QFileDialog.getOpenFileName(self, t("settings.browse"))
            else:
                path = QFileDialog.getExistingDirectory(self, t("settings.browse"))
            if path:
                edit.setText(path)

        row.addWidget(button(t("settings.browse"), on_click=browse))
        return row

    # -- yükle / kaydet --------------------------------------------------------------

    def _collect(self) -> Settings:
        s = self.ctl.settings.model_copy()
        s.language = self.language.currentData()
        s.debug_mode = self.debug.isChecked()
        s.curseforge_api_key = self.cf_key.text().strip()
        s.prefer_modrinth = self.prefer_modrinth.isChecked()
        s.sklauncher_path = self.sklauncher.text().strip()
        s.java_path = self.java.text().strip()
        s.web_panel_port = self.web_port.value()
        s.web_panel_password = self.web_password.text()
        s.exclude_logs = self.ex_logs.isChecked()
        s.exclude_crash_reports = self.ex_crash.isChecked()
        s.exclude_saves = self.ex_saves.isChecked()
        s.packs_dir = self.packs_dir.text().strip()
        return s

    def load(self) -> None:
        s = self.ctl.settings
        self.language.setCurrentIndex(max(0, self.language.findData(s.language)))
        self.debug.setChecked(s.debug_mode)
        self.cf_key.setText(s.curseforge_api_key)
        self.prefer_modrinth.setChecked(s.prefer_modrinth)
        self.sklauncher.setText(s.sklauncher_path)
        self.java.setText(s.java_path)
        self.web_port.setValue(s.web_panel_port)
        self.web_password.setText(s.web_panel_password)
        self.ex_logs.setChecked(s.exclude_logs)
        self.ex_crash.setChecked(s.exclude_crash_reports)
        self.ex_saves.setChecked(s.exclude_saves)
        self.packs_dir.setText(s.packs_dir)
        self.cf_status.setText("")
        self._refresh_web()
        self._update_dirty()

    def is_dirty(self) -> bool:
        return self._collect().model_dump() != self.ctl.settings.model_dump()

    def _update_dirty(self) -> None:
        dirty = self.is_dirty()
        self.save_btn.setEnabled(dirty)
        self.revert_btn.setEnabled(dirty)
        self.dirty_label.setText(t("settings.unsaved") if dirty else t("settings.subtitle"))
        self.dirty_label.setStyleSheet(f"color: {COLORS['warning']};" if dirty else "")

    def save(self) -> None:
        new = self._collect()
        if self.ctl.web_panel_running and (
            new.web_panel_port != self.ctl.settings.web_panel_port or new.web_panel_password != self.ctl.settings.web_panel_password
        ):
            self.ctl.notify.emit("warning", t("settings.web_restart_needed"))
        restart = self.ctl.apply_settings(new)
        self.ctl.notify.emit("success", t("settings.saved"))
        if "language" in restart:
            info(self, t("settings.restart_title"), t("settings.language_note"))
        self._update_dirty()

    def reset_to_defaults(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(t("settings.reset_title"))
        box.setText(t("settings.reset_body"))
        keep = box.addButton(t("settings.reset_keep_secrets"), QMessageBox.ButtonRole.AcceptRole)
        everything = box.addButton(t("settings.reset_all"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (keep, everything):
            return
        current = self.ctl.settings
        backup = current.backup_file()
        fresh = Settings.defaults(keep_secrets_from=current if clicked is keep else None)
        if self.ctl.web_panel_running and (
            fresh.web_panel_port != current.web_panel_port or fresh.web_panel_password != current.web_panel_password
        ):
            self.ctl.toggle_web_panel()  # eski port/şifreyle açık kalmasın
        restart = self.ctl.apply_settings(fresh)
        self.load()
        from mcpack.logging_setup import get_logger

        get_logger(__name__).info("Ayarlar varsayılanlara sıfırlandı (yedek: %s)", backup)
        msg = t("settings.reset_done", backup=backup.name) if backup else t("settings.reset_done_nobackup")
        self.ctl.notify.emit("success", msg)
        if "language" in restart:
            info(self, t("settings.restart_title"), t("settings.language_note"))

    # -- testler ---------------------------------------------------------------------

    def _test_cf(self) -> None:
        key = self.cf_key.text().strip()
        if not key:
            self.cf_status.setText(t("settings.cf_empty"))
            return
        self.cf_test.setEnabled(False)
        self.cf_status.setStyleSheet("")
        self.cf_status.setText(t("settings.checking"))

        async def task(ctx):
            client = CurseForgeClient(key)
            try:
                return await client.check_connection()
            finally:
                await client.aclose()

        def ok(name: str) -> None:
            self.cf_test.setEnabled(True)
            self.cf_status.setStyleSheet(f"color: {COLORS['success']};")
            self.cf_status.setText(t("settings.cf_ok", game=name))

        def fail(message: str) -> None:
            self.cf_test.setEnabled(True)
            self.cf_status.setStyleSheet(f"color: {COLORS['danger']};")
            self.cf_status.setText(t("settings.cf_fail", message=message))

        self.ctl.tasks.run(t("settings.task_cf_test"), task, on_success=ok, on_error=fail, category="diagnostics", owner=self)

    def _detect_java(self) -> None:
        java = find_java(self.java.text().strip())
        if java is None:
            self.java_status.setStyleSheet(f"color: {COLORS['danger']};")
            self.java_status.setText(t("settings.java_not_found"))
            return
        self.java_status.setStyleSheet("")
        self.java_status.setText(t("settings.checking"))

        async def task(ctx):
            return await get_java_major_version(java)

        def done(major) -> None:
            self.java_status.setStyleSheet(f"color: {COLORS['success']};")
            self.java_status.setText(t("settings.java_found", path=java, version=major if major else "?"))

        self.ctl.tasks.run(t("settings.task_java"), task, on_success=done, silent=True, category="diagnostics", owner=self)

    # -- web paneli / önbellek -----------------------------------------------------

    def _refresh_web(self) -> None:
        running = self.ctl.web_panel_running
        self.web_toggle.setText(t("settings.web_stop") if running else t("settings.web_start"))
        self.web_toggle.setProperty("variant", "danger" if running else None)
        self.web_toggle.style().unpolish(self.web_toggle)
        self.web_toggle.style().polish(self.web_toggle)
        self.web_url.setText(self.ctl.web_panel_url if running else t("settings.web_off"))

    def _toggle_web(self) -> None:
        if self.is_dirty() and not self.ctl.web_panel_running:
            self.save()
        self.ctl.toggle_web_panel()

    def _cache_dirs(self):
        from mcpack.gui.icons import icon_cache_dir

        return [self.ctl.settings.resolved_packs_dir() / ".cache", icon_cache_dir()]

    def _measure_cache(self) -> None:
        dirs = self._cache_dirs()

        async def task(ctx):
            return sum(_dir_size(d) for d in dirs if d.exists())

        self.ctl.tasks.run(
            t("settings.task_measure"), task,
            on_success=lambda size: self.cache_label.setText(format_size(size)), silent=True, owner=self,
        )

    def _clear_cache(self) -> None:
        from mcpack.gui.components import confirm

        if not confirm(self, t("settings.clear_cache"), t("settings.clear_cache_confirm"), danger=True):
            return
        mod_cache = self.ctl.settings.resolved_packs_dir() / ".cache"
        shutil.rmtree(mod_cache, ignore_errors=True)
        removed = icons().clear()
        self.cache_label.setText(format_size(0))
        self.ctl.notify.emit("success", t("settings.cache_cleared", icons=removed))
