"""Pack'i başka bir Minecraft versiyonuna uyarlama ("fork") diyaloğu.

Kullanıcı isteği: "fork, bir mod paketini üst/alt Minecraft sürümlerine
uyarlamak demek — o modun uygun sürümü yoksa kullanıcıya bilgi verir, modu
eklemez." Loader TÜRÜ değişmez (NewPackDialog'un aksine kullanıcı loader
seçmez) — sadece hedef Minecraft versiyonu ve o versiyon için loader
versiyonu seçilir (en-yeni/önerilen rozet mantığı NewPackDialog'dan
tekrar kullanılır, bkz. gameinfo.py)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from mcpack.downloader import make_client
from mcpack.gameinfo import get_loader_versions, get_minecraft_versions, get_recommended_loader_version
from mcpack.gui.theme import danger_color
from mcpack.gui.widgets import run_async
from mcpack.i18n import t
from mcpack.models import Loader, Pack


def _loader_labels() -> dict[Loader, str]:
    return {
        Loader.VANILLA: t("newpack.loader_vanilla"),
        Loader.FABRIC: "Fabric",
        Loader.QUILT: "Quilt",
        Loader.FORGE: "Forge",
        Loader.NEOFORGE: "NeoForge",
    }


class ForkPackDialog(QDialog):
    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(parent)
        self._loader = pack.loader
        self.setWindowTitle(t("forkpack.title"))
        self.setMinimumWidth(440)

        self.name_input = QLineEdit(t("forkpack.name_default", name=pack.name))

        loader_label = QLabel(_loader_labels().get(self._loader, self._loader.value))
        loader_label.setProperty("role", "muted")

        self.mc_version_combo = QComboBox()
        self.mc_version_combo.addItem(t("common.loading"), None)
        self.mc_version_combo.setEnabled(False)
        self.mc_version_combo.currentIndexChanged.connect(self._load_loader_versions)

        self.loader_version_combo = QComboBox()
        self.loader_version_combo.setEnabled(False)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {danger_color()};")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        info = QLabel(t("forkpack.info", name=pack.name))
        info.setWordWrap(True)
        info.setProperty("role", "muted")

        form = QFormLayout()
        form.addRow(t("forkpack.new_name_label"), self.name_input)
        form.addRow("Loader:", loader_label)
        form.addRow(t("forkpack.new_mc_version_label"), self.mc_version_combo)
        if self._loader != Loader.VANILLA:
            form.addRow(t("newpack.loader_version_label"), self.loader_version_combo)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)

        self._load_minecraft_versions(current=pack.minecraft)

    # -- veri yükleme ---------------------------------------------------

    def _load_minecraft_versions(self, *, current: str) -> None:
        async def task() -> list[str]:
            async with make_client() as client:
                return await get_minecraft_versions(client)

        def on_success(versions: list[str]) -> None:
            self.mc_version_combo.clear()
            if not versions:
                self.mc_version_combo.addItem(t("common.not_found"), None)
                return
            for v in versions:
                label = t("forkpack.current_version_suffix", version=v) if v == current else v
                self.mc_version_combo.addItem(label, v)
            self.mc_version_combo.setEnabled(True)
            self._load_loader_versions()

        def on_error(message: str) -> None:
            self.mc_version_combo.clear()
            self.mc_version_combo.addItem(t("forkpack.mc_versions_load_failed_item"), None)
            self._show_error(t("newpack.mc_versions_load_failed", message=message))

        run_async(task, on_success=on_success, on_error=on_error)

    def _load_loader_versions(self) -> None:
        if self._loader == Loader.VANILLA:
            return
        mc_version = self.mc_version_combo.currentData()
        if not mc_version:
            return

        self.loader_version_combo.clear()
        self.loader_version_combo.addItem(t("common.loading"), None)
        self.loader_version_combo.setEnabled(False)

        async def task() -> list[str]:
            async with make_client() as client:
                return await get_loader_versions(client, self._loader, mc_version)

        def on_success(versions: list[str]) -> None:
            self.loader_version_combo.clear()
            if not versions:
                self.loader_version_combo.addItem(t("common.not_found"), None)
                self._show_error(
                    t(
                        "newpack.loader_versions_not_found",
                        mc_version=mc_version,
                        loader=self._loader.value,
                    )
                )
                return
            for i, v in enumerate(versions):
                label = t("newpack.loader_version_latest", version=v) if i == 0 else v
                self.loader_version_combo.addItem(label, v)
            self.loader_version_combo.setEnabled(True)
            self._mark_recommended_loader_version(mc_version)

        def on_error(message: str) -> None:
            self.loader_version_combo.clear()
            self.loader_version_combo.addItem(t("newpack.load_failed_item"), None)
            self._show_error(message)

        run_async(task, on_success=on_success, on_error=on_error)

    def _mark_recommended_loader_version(self, mc_version: str) -> None:
        async def task() -> str | None:
            async with make_client() as client:
                return await get_recommended_loader_version(client, self._loader, mc_version)

        def on_success(recommended: str | None) -> None:
            if not recommended:
                return
            recommended_suffix = t("newpack.recommended_suffix")
            for i in range(self.loader_version_combo.count()):
                if self.loader_version_combo.itemData(i) == recommended:
                    text = self.loader_version_combo.itemText(i)
                    if recommended_suffix not in text:
                        self.loader_version_combo.setItemText(i, f"{text}  {recommended_suffix}")
                    break

        def on_error(_message: str) -> None:
            pass

        run_async(task, on_success=on_success, on_error=on_error)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    # -- onay -------------------------------------------------------------

    def _on_accept(self) -> None:
        if not self.name_input.text().strip():
            self._show_error(t("newpack.error_name_empty"))
            return
        if not self.mc_version_combo.currentData():
            self._show_error(t("newpack.error_select_mc_version"))
            return
        if self._loader != Loader.VANILLA and not self.loader_version_combo.currentData():
            self._show_error(t("newpack.error_select_loader_version"))
            return
        self.accept()

    def result_values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "minecraft": self.mc_version_combo.currentData(),
            "loader_version": self.loader_version_combo.currentData() or "",
        }
