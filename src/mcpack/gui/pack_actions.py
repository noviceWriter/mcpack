"""Hem Kütüphane kartlarından hem Pack sayfasından erişilen ortak pack
eylemleri (bilgi düzenle, kopyala, fork, klasörü aç, sil, dışa aktar).
Diyalog + onay burada; asıl iş AppController'da."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QWidget

from mcpack.gui.components import confirm, info
from mcpack.gui.controller import EXPORT_LABELS, EXPORTERS, AppController
from mcpack.gui.dialogs import ForkPackDialog, PackMetaDialog
from mcpack.i18n import t
from mcpack.models import ContentKind, Pack


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def edit_meta(parent: QWidget, ctl: AppController, pack: Pack) -> None:
    dialog = PackMetaDialog(pack, parent)
    if dialog.exec():
        ctl.update_pack_meta(pack, **dialog.values())


def fork(parent: QWidget, ctl: AppController, pack: Pack) -> None:
    dialog = ForkPackDialog(ctl.tasks, pack, parent)
    if not dialog.exec():
        return

    def done(new_pack: Pack, failed: list[str]) -> None:
        if failed:
            info(
                parent, t("fork.skipped_title"),
                t("fork.skipped_body", name=new_pack.name, minecraft=new_pack.minecraft,
                  list="\n".join(f"• {n}" for n in failed)),
                warning=True,
            )

    ctl.fork_pack(pack, dialog.values(), done)


def delete(parent: QWidget, ctl: AppController, pack: Pack) -> bool:
    if not confirm(
        parent, t("pack.delete_title"), t("pack.delete_confirm", name=pack.name, mods=len(pack.mods)),
        ok_text=t("pack.delete"), danger=True,
    ):
        return False
    return ctl.delete_pack(pack.id)


def _pick_source_dir(parent: QWidget) -> Path | None:
    """Overrides (config/, kubejs/ ...) kaynağı. Vazgeçilirse None — eskiden
    sessizce çalışma dizinine (Path.cwd()) düşüyordu, bu da proje klasörünün
    yanlışlıkla pakete girmesine yol açabiliyordu."""
    chosen = QFileDialog.getExistingDirectory(parent, t("export.pick_source_dir"))
    return Path(chosen) if chosen else None


def _ask_overrides(parent: QWidget) -> Path | None | bool:
    """True -> overrides istenmiyor (boş klasör), Path -> seçilen, False -> iptal."""
    choice, ok = QInputDialog.getItem(
        parent, t("export.overrides_title"), t("export.overrides_body"),
        [t("export.overrides_none"), t("export.overrides_pick")], 0, False,
    )
    if not ok:
        return False
    if choice == t("export.overrides_none"):
        return True
    picked = _pick_source_dir(parent)
    return picked if picked is not None else False


def _empty_dir(ctl: AppController, pack: Pack) -> Path:
    path = ctl.cache_dir(pack) / "empty-overrides"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _with_dependency_gate(parent: QWidget, ctl: AppController, pack: Pack, proceed) -> None:
    """Dışa aktarma öncesi sert kontrol: eksik zorunlu bağımlılık varsa
    kullanıcıya gösterip açık onay ister."""

    def checked(lines: list[str]) -> None:
        if not lines:
            proceed()
            return
        if confirm(
            parent, t("deps.missing_title"), t("deps.missing_confirm", list="\n".join(lines)),
            ok_text=t("deps.continue_anyway"), danger=True,
        ):
            proceed()

    ctl.describe_missing_dependencies(pack, checked)


def export(parent: QWidget, ctl: AppController, pack: Pack, fmt: str) -> None:
    exporter_cls = EXPORTERS[fmt]

    def proceed() -> None:
        output, _ = QFileDialog.getSaveFileName(
            parent, t("export.save_title", fmt=EXPORT_LABELS[fmt]),
            f"{pack.name}{exporter_cls.file_extension}", f"*{exporter_cls.file_extension}",
        )
        if not output:
            return
        overrides = _ask_overrides(parent)
        if overrides is False:
            return
        source = _empty_dir(ctl, pack) if overrides is True else overrides
        ctl.export(pack, fmt, Path(output), source, on_done=lambda p: _offer_reveal(parent, p))

    _with_dependency_gate(parent, ctl, pack, proceed)


def server_pack(parent: QWidget, ctl: AppController, pack: Pack) -> None:
    def proceed() -> None:
        world = None
        worlds = [w.name for w in pack.content_of(ContentKind.WORLD)]
        if worlds:
            options = [t("serverpack.no_world"), *worlds]
            choice, ok = QInputDialog.getItem(parent, t("serverpack.world_title"), t("serverpack.world_body"), options, 0, False)
            if not ok:
                return
            world = None if choice == options[0] else choice
        output, _ = QFileDialog.getSaveFileName(parent, t("serverpack.save_title"), f"{pack.name}-server.zip", "*.zip")
        if not output:
            return
        overrides = _ask_overrides(parent)
        if overrides is False:
            return
        source = _empty_dir(ctl, pack) if overrides is True else overrides

        def done(path: Path, missing_notice: bool) -> None:
            if missing_notice:
                from mcpack.export.server import SERVER_FILE_MISSING_NOTICE_NAME

                info(parent, t("serverpack.missing_file_title"), t("serverpack.missing_file_body", notice=SERVER_FILE_MISSING_NOTICE_NAME), warning=True)
            _offer_reveal(parent, path)

        ctl.server_pack(pack, Path(output), source, world, on_done=done)

    _with_dependency_gate(parent, ctl, pack, proceed)


def sklauncher(parent: QWidget, ctl: AppController, pack: Pack) -> None:
    if not ctl.settings.sklauncher_path:
        info(parent, t("sklauncher.missing_title"), t("ctl.sklauncher_missing"), warning=True)
        ctl.navigate.emit("settings", "")
        return

    def proceed() -> None:
        overrides = _ask_overrides(parent)
        if overrides is False:
            return
        ctl.run_sklauncher(pack, _empty_dir(ctl, pack) if overrides is True else overrides)

    _with_dependency_gate(parent, ctl, pack, proceed)


def _offer_reveal(parent: QWidget, path: Path) -> None:
    open_folder(path.parent)


def export_menu(parent: QWidget, ctl: AppController, pack_getter) -> QMenu:
    menu = QMenu(parent)
    for fmt, text in EXPORT_LABELS.items():
        menu.addAction(text, lambda f=fmt: (p := pack_getter()) and export(parent, ctl, p, f))
    menu.addSeparator()
    menu.addAction(t("pack.server_pack"), lambda: (p := pack_getter()) and server_pack(parent, ctl, p))
    menu.addAction(t("pack.sklauncher"), lambda: (p := pack_getter()) and sklauncher(parent, ctl, p))
    return menu


def context_menu(parent: QWidget, ctl: AppController, pack: Pack, *, include_open: bool = True) -> QMenu:
    menu = QMenu(parent)
    if include_open:
        menu.addAction(t("pack.open"), lambda: ctl.navigate.emit("pack", pack.id))
    menu.addAction(t("pack.edit_info"), lambda: edit_meta(parent, ctl, pack))
    menu.addAction(t("pack.duplicate"), lambda: ctl.duplicate_pack(pack))
    menu.addAction(t("pack.fork"), lambda: fork(parent, ctl, pack))
    export_sub = export_menu(parent, ctl, lambda: pack)
    export_sub.setTitle(t("pack.export"))
    menu.addMenu(export_sub)
    menu.addSeparator()
    menu.addAction(t("pack.open_content_folder"), lambda: open_folder(ctl.manager.content_root(pack)))
    menu.addAction(t("pack.open_server_folder"), lambda: open_folder(ctl.manager.server_root(pack)))
    menu.addSeparator()
    menu.addAction(t("pack.delete"), lambda: delete(parent, ctl, pack))
    return menu
