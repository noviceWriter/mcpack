"""Ana pencere kabuğu: kenar çubuğu gezinmesi + sayfa yığını + durum
çubuğu (görev göstergesi, iptal, log sayaçları, web paneli) + toast
bildirimleri + komut paleti + klavye kısayolları.

Bu dosyada iş mantığı YOKTUR — her şey AppController'dan geçer.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui import pack_actions
from mcpack.gui.components import ToastManager, button, label
from mcpack.gui.controller import AppController
from mcpack.gui.dialogs import NewPackDialog
from mcpack.gui.pages.dashboard import DashboardPage
from mcpack.gui.pages.debug import DebugPage
from mcpack.gui.pages.library import LibraryPage
from mcpack.gui.pages.pack_page import PackPage
from mcpack.gui.pages.settings import SettingsPage
from mcpack.gui.palette import Command, CommandPalette
from mcpack.gui.tasks import FAILED, Task
from mcpack.gui.theme import COLORS
from mcpack.i18n import t
from mcpack.logging_setup import EXCEPTIONS, MEMORY_HANDLER, app_version, get_logger, log_file_path, set_debug

log = get_logger(__name__)

NAV = [
    ("home", "⌂", "Ctrl+1"),
    ("library", "▤", "Ctrl+2"),
    ("pack", "◆", "Ctrl+3"),
    ("settings", "⚙", "Ctrl+,"),
    ("debug", "🐞", "F12"),
]


class MainWindow(QMainWindow):
    def __init__(self, ctl: AppController | None = None) -> None:
        super().__init__()
        self.ctl = ctl or AppController(self)
        self.setWindowTitle("MC Pack Manager")
        self.resize(1400, 880)
        self.setMinimumSize(1080, 680)
        self._current_pack_id: str | None = None

        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.home = DashboardPage(self.ctl)
        self.library = LibraryPage(self.ctl)
        self.pack_page = PackPage(self.ctl)
        self.settings_page = SettingsPage(self.ctl)
        self.debug_page = DebugPage(self.ctl)
        self.pages = {
            "home": self.home,
            "library": self.library,
            "pack": self.pack_page,
            "settings": self.settings_page,
            "debug": self.debug_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self._build_status_bar()
        self.toasts = ToastManager(root)
        self.setAcceptDrops(True)
        self._wire()
        self._shortcuts()
        self.go("home")
        log.info("Ana pencere hazır")

    # -- kurulum -------------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(232)
        col = QVBoxLayout(side)
        col.setContentsMargins(12, 16, 12, 12)
        col.setSpacing(2)
        brand = QHBoxLayout()
        logo = label("◈")
        logo.setStyleSheet(f"color: {COLORS['accent']}; font-size: 22px;")
        brand.addWidget(logo)
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        title = label("MC Pack Manager")
        title.setObjectName("SidebarBrand")
        brand_col.addWidget(title)
        brand_col.addWidget(label(f"v{app_version()}", role="dim"))
        brand.addLayout(brand_col, 1)
        col.addLayout(brand)
        col.addSpacing(10)
        search_btn = button(f"⌕   {t('nav.search')}", variant="nav", on_click=self.open_palette)
        search_btn.setToolTip("Ctrl+K")
        col.addWidget(search_btn)
        caption = label(t("nav.caption"))
        caption.setObjectName("SidebarCaption")
        col.addWidget(caption)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, glyph, shortcut in NAV:
            b = button(f"{glyph}   {t(f'nav.{key}')}", variant="nav", checkable=True)
            b.setToolTip(shortcut)
            b.clicked.connect(lambda _c=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            col.addWidget(b)
            if key == "pack":
                b.hide()
        col.addStretch()

        self.side_running = label("", role="dim", wrap=True)
        col.addWidget(self.side_running)
        self.side_web = button("", variant="nav", on_click=self.ctl.toggle_web_panel)
        col.addWidget(self.side_web)
        new_btn = button(t("library.new_pack"), variant="primary", on_click=self.new_pack)
        col.addWidget(new_btn)
        return side

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self.status_text = label(t("status.ready"), role="dim")
        bar.addWidget(self.status_text, 1)
        self.task_progress = QProgressBar()
        self.task_progress.setFixedWidth(160)
        self.task_progress.setFixedHeight(8)
        self.task_progress.hide()
        bar.addPermanentWidget(self.task_progress)
        self.task_button = QPushButton("")
        self.task_button.clicked.connect(lambda: self.go("debug", "tasks"))
        bar.addPermanentWidget(self.task_button)
        self.cancel_button = QPushButton(t("status.cancel"))
        self.cancel_button.clicked.connect(self._cancel_current)
        self.cancel_button.hide()
        bar.addPermanentWidget(self.cancel_button)
        self.log_button = QPushButton("")
        self.log_button.setToolTip(t("status.logs_tooltip"))
        self.log_button.clicked.connect(lambda: self.go("debug", "logs"))
        bar.addPermanentWidget(self.log_button)
        self.web_status = QPushButton("")
        self.web_status.clicked.connect(lambda: self.go("settings"))
        bar.addPermanentWidget(self.web_status)
        self._counter_timer = QTimer(self)
        self._counter_timer.setInterval(1500)
        self._counter_timer.timeout.connect(self._refresh_counters)
        self._counter_timer.start()
        self._refresh_tasks()
        self._refresh_counters()
        self._refresh_web()

    def _wire(self) -> None:
        c = self.ctl
        c.notify.connect(self._on_notify)
        c.status.connect(self.status_text.setText)
        c.navigate.connect(self._on_navigate)
        c.web_panel_changed.connect(lambda *_a: self._refresh_web())
        c.server_changed.connect(lambda _p: self._refresh_running())
        c.packs_changed.connect(self._on_packs_changed)
        c.pack_updated.connect(lambda pid: pid == self._current_pack_id and self._update_pack_nav())
        c.tasks.task_updated.connect(lambda _t: self._refresh_tasks())
        c.tasks.task_added.connect(lambda _t: self._refresh_tasks())
        c.tasks.task_finished.connect(self._on_task_finished)
        self._refresh_running()

    def _shortcuts(self) -> None:
        def sc(seq, fn) -> None:
            QShortcut(QKeySequence(seq), self, activated=fn)

        sc("Ctrl+K", self.open_palette)
        sc("Ctrl+P", self.open_palette)
        sc("Ctrl+1", lambda: self.go("home"))
        sc("Ctrl+2", lambda: self.go("library"))
        sc("Ctrl+3", lambda: self._current_pack_id and self.go("pack"))
        sc("Ctrl+,", lambda: self.go("settings"))
        sc("F12", lambda: self.go("debug"))
        sc("Ctrl+N", self.new_pack)
        sc("Ctrl+O", lambda: pack_actions.import_modpack(self, self.ctl))
        sc("Ctrl+F", self._focus_search)
        sc("Ctrl+Shift+D", self._toggle_debug)

    # -- gezinme -------------------------------------------------------------------

    def go(self, key: str, arg: str = "") -> None:
        if key == "pack" and not self._current_pack_id:
            key = "library"
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        if key == "debug" and arg:
            self.debug_page.show_tab(arg)
        if key == "settings" and not self.settings_page.is_dirty():
            self.settings_page.load()

    def open_pack(self, pack_id: str, section: str | None = None) -> None:
        pack = self.ctl.load_pack(pack_id)
        if pack is None:
            return
        self._current_pack_id = pack_id
        self.pack_page.set_pack(pack)
        self._update_pack_nav()
        self.go("pack")
        if section:
            self.pack_page.show_section(section)

    def _update_pack_nav(self) -> None:
        pack = self.ctl.load_pack(self._current_pack_id) if self._current_pack_id else None
        b = self.nav_buttons["pack"]
        b.setVisible(pack is not None)
        if pack is not None:
            name = pack.name if len(pack.name) <= 20 else pack.name[:19] + "…"
            b.setText(f"◆   {name}")

    def _on_navigate(self, target: str, arg: str) -> None:
        if target == "pack" and arg:
            self.open_pack(arg)
        elif target == "server" and arg:
            self.open_pack(arg, "server")
        elif target == "palette":
            self.open_palette()
        elif target in self.pages:
            self.go(target, arg)

    def _on_packs_changed(self) -> None:
        if self._current_pack_id and not any(p.id == self._current_pack_id for p in self.ctl.list_packs()):
            self._current_pack_id = None  # açık pack silindi
            if self.stack.currentWidget() is self.pack_page:
                self.go("library")
        self._update_pack_nav()

    def _focus_search(self) -> None:
        w = self.stack.currentWidget()
        if w is self.library:
            self.library.focus_search()
        elif w is self.pack_page:
            section = self.pack_page.current_section()
            if section == "discover":
                self.pack_page.discover.search.setFocus()
            elif section in ("mods", "cheats"):
                self.pack_page.sections[section].search.setFocus()

    # -- eylemler ------------------------------------------------------------------

    def new_pack(self) -> None:
        dialog = NewPackDialog(self.ctl.tasks, self)
        if dialog.exec():
            pack = self.ctl.create_pack(dialog.values())
            self.open_pack(pack.id)

    def _toggle_debug(self) -> None:
        settings = self.ctl.settings.model_copy()
        settings.debug_mode = not settings.debug_mode
        set_debug(settings.debug_mode)
        self.ctl.apply_settings(settings)
        self.toasts.show_toast("info", t("debug.mode_on") if settings.debug_mode else t("debug.mode_off"))

    def open_palette(self) -> None:
        cmds: list[Command] = []
        g_nav, g_act, g_pack = t("palette.g_nav"), t("palette.g_actions"), t("palette.g_packs")
        for key, _glyph, shortcut in NAV:
            if key == "pack" and not self._current_pack_id:
                continue
            cmds.append(Command(t(f"nav.{key}"), lambda k=key: self.go(k), g_nav, shortcut=shortcut))
        cmds += [
            Command(t("library.new_pack"), self.new_pack, g_act, shortcut="Ctrl+N"),
            Command(t("palette.import"), lambda: pack_actions.import_modpack(self, self.ctl), g_act, shortcut="Ctrl+O"),
            Command(t("palette.toggle_web"), self.ctl.toggle_web_panel, g_act),
            Command(t("palette.toggle_debug"), self._toggle_debug, g_act, shortcut="Ctrl+Shift+D"),
            Command(t("palette.run_diag"), lambda: (self.go("debug", "system"), self.debug_page.system.run_diagnostics()), g_act),
            Command(t("palette.open_logs"), lambda: pack_actions.open_folder(log_file_path().parent), g_act),
            Command(t("palette.support_bundle"), lambda: (self.go("debug", "system"), self.debug_page.system.create_bundle()), g_act),
            Command(t("palette.reset_settings"), lambda: (self.go("settings"), self.settings_page.reset_to_defaults()), g_act),
            Command(t("palette.open_data"), lambda: pack_actions.open_folder(self.ctl.settings.resolved_packs_dir()), g_act),
            Command(t("palette.view_exceptions"), lambda: self.go("debug", "exceptions"), g_act),
            Command(t("palette.view_network"), lambda: self.go("debug", "network"), g_act),
        ]
        if self._current_pack_id:
            pack = self.ctl.load_pack(self._current_pack_id)
            if pack is not None:
                for section in ("mods", "discover", "server", "world"):
                    cmds.append(Command(
                        f"{pack.name} › {t(f'pack.section.{section}')}",
                        lambda s=section: self.open_pack(pack.id, s), g_act,
                    ))
                cmds.append(Command(t("palette.export", name=pack.name), lambda: pack_actions.export(self, self.ctl, pack, "mrpack"), g_act))
        for pack in self.ctl.list_packs():
            cmds.append(Command(pack.name, lambda pid=pack.id: self.open_pack(pid), g_pack, hint=f"{pack.loader.value} · {pack.minecraft}"))
            if self.ctl.registry.is_running(pack.id):
                cmds.append(Command(t("palette.stop_server", name=pack.name), lambda pid=pack.id: self.ctl.stop_server(pid), g_act))
        CommandPalette(cmds, self).exec()

    # -- durum çubuğu ----------------------------------------------------------------

    def _visible_active(self) -> list[Task]:
        return self.ctl.tasks.active_tasks(include_silent=False)

    def _refresh_tasks(self) -> None:
        active = self._visible_active()
        if not active:
            self.task_button.setText("✓ " + t("status.no_tasks"))
            self.task_progress.hide()
            self.cancel_button.hide()
            return
        current = active[-1]
        extra = f"  (+{len(active) - 1})" if len(active) > 1 else ""
        msg = f" — {current.message}" if current.message else ""
        self.task_button.setText(f"⟳ {current.title}{msg}{extra}")
        frac = current.fraction
        self.task_progress.show()
        if frac is None:
            self.task_progress.setRange(0, 0)
        else:
            self.task_progress.setRange(0, 1000)
            self.task_progress.setValue(int(frac * 1000))
        self.cancel_button.setVisible(current.cancellable)

    def _cancel_current(self) -> None:
        cancellable = [x for x in self._visible_active() if x.cancellable]
        if cancellable:
            self.ctl.tasks.cancel(cancellable[-1].id)
            self.status_text.setText(t("status.cancelling"))

    def _on_task_finished(self, task: Task) -> None:
        self._refresh_tasks()
        if not task.silent:
            self.status_text.setText(
                t(f"status.task_{task.status}", title=task.title)
            )
        if task.status == FAILED and not task.silent:
            log.debug("Görev hatası bildirildi: %s", task.title)

    def _refresh_counters(self) -> None:
        entries = MEMORY_HANDLER.snapshot(min_level=30)
        warn = sum(1 for e in entries if e.levelno == 30)
        err = sum(1 for e in entries if e.levelno >= 40)
        exc = len(EXCEPTIONS.snapshot())
        self.log_button.setText(f"⚠ {warn}   ✖ {err}" + (f"   💥 {exc}" if exc else ""))
        color = COLORS["danger"] if err or exc else (COLORS["warning"] if warn else COLORS["text_muted"])
        self.log_button.setStyleSheet(f"color: {color};")

    def _refresh_web(self) -> None:
        if self.ctl.web_panel_running:
            self.web_status.setText(f"● {t('status.web_on')}")
            self.web_status.setStyleSheet(f"color: {COLORS['success']};")
            self.web_status.setToolTip(self.ctl.web_panel_url)
            self.side_web.setText(f"🌐   {t('nav.web_stop')}")
        else:
            self.web_status.setText(f"○ {t('status.web_off')}")
            self.web_status.setStyleSheet("")
            self.web_status.setToolTip("")
            self.side_web.setText(f"🌐   {t('nav.web_start')}")

    def _refresh_running(self) -> None:
        running = self.ctl.running_server_ids()
        if running:
            names = []
            for pid in running:
                pack = self.ctl.load_pack(pid)
                names.append(pack.name if pack else pid[:8])
            self.side_running.setText("● " + t("nav.running", count=len(running)) + "\n" + ", ".join(names))
            self.side_running.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.side_running.setText("")

    def _on_notify(self, level: str, message: str) -> None:
        action = None
        if level == "error":
            action = (t("toast.details"), lambda: self.go("debug", "exceptions" if EXCEPTIONS.snapshot() else "logs"))
            log.debug("Kullanıcıya hata gösterildi: %s", message)
        self.toasts.show_toast(level, message, action=action)
        self.status_text.setText(message.splitlines()[0][:160])

    # -- sürükle-bırak ile içe aktarma ---------------------------------------------------

    @staticmethod
    def _dropped_modpacks(event) -> list:
        from pathlib import Path

        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        return [Path(u.toLocalFile()) for u in urls if u.isLocalFile() and u.toLocalFile().lower().endswith((".mrpack", ".zip"))]

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_modpacks(event):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for path in self._dropped_modpacks(event):
            pack_actions.import_modpack(self, self.ctl, path)
        event.acceptProposedAction()

    # -- kapanış ---------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.settings_page.is_dirty():
            box = QMessageBox(self)
            box.setWindowTitle(t("close.unsaved_title"))
            box.setText(t("close.unsaved_body"))
            save = box.addButton(t("settings.save"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(t("close.discard"), QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is cancel:
                event.ignore()
                return
            if box.clickedButton() is save:
                self.settings_page.save()

        running = self.ctl.running_server_ids()
        stop = False
        if running:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(t("close.servers_title"))
            box.setText(t("close.servers_body", count=len(running)))
            stop_btn = box.addButton(t("close.stop_servers"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(t("close.leave_running"), QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(stop_btn)
            box.exec()
            if box.clickedButton() is cancel:
                event.ignore()
                return
            stop = box.clickedButton() is stop_btn

        active = self.ctl.tasks.active_tasks(include_silent=False)
        if active and not running:
            box = QMessageBox(self)
            box.setWindowTitle(t("close.tasks_title"))
            box.setText(t("close.tasks_body", count=len(active), list="\n".join(f"• {x.title}" for x in active[:6])))
            quit_btn = box.addButton(t("close.quit_anyway"), QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not quit_btn:
                event.ignore()
                return

        self.status_text.setText(t("close.shutting_down"))
        self.setEnabled(False)
        self.debug_page.shutdown()
        self.ctl.shutdown(stop_servers=stop)
        event.accept()
