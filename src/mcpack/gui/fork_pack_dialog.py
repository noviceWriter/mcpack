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
from mcpack.models import Loader, Pack

_LOADER_LABELS: dict[Loader, str] = {
    Loader.VANILLA: "Vanilla (loader yok)",
    Loader.FABRIC: "Fabric",
    Loader.QUILT: "Quilt",
    Loader.FORGE: "Forge",
    Loader.NEOFORGE: "NeoForge",
}


class ForkPackDialog(QDialog):
    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(parent)
        self._loader = pack.loader
        self.setWindowTitle("Başka Sürüme Uyarla (Fork)")
        self.setMinimumWidth(440)

        self.name_input = QLineEdit(f"{pack.name} (Fork)")

        loader_label = QLabel(_LOADER_LABELS.get(self._loader, self._loader.value))
        loader_label.setProperty("role", "muted")

        self.mc_version_combo = QComboBox()
        self.mc_version_combo.addItem("Yükleniyor...", None)
        self.mc_version_combo.setEnabled(False)
        self.mc_version_combo.currentIndexChanged.connect(self._load_loader_versions)

        self.loader_version_combo = QComboBox()
        self.loader_version_combo.setEnabled(False)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {danger_color()};")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        info = QLabel(
            f"'{pack.name}' pack'indeki her mod, seçtiğiniz yeni Minecraft "
            "versiyonu için tekrar aranır. Uygun bir versiyonu bulunamayan "
            "modlar yeni pack'e eklenmez — işlem bitince hangilerinin "
            "atlandığı gösterilir."
        )
        info.setWordWrap(True)
        info.setProperty("role", "muted")

        form = QFormLayout()
        form.addRow("Yeni Pack Adı:", self.name_input)
        form.addRow("Loader:", loader_label)
        form.addRow("Yeni Minecraft Versiyonu:", self.mc_version_combo)
        if self._loader != Loader.VANILLA:
            form.addRow("Loader Versiyonu:", self.loader_version_combo)

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
                self.mc_version_combo.addItem("Bulunamadı", None)
                return
            for v in versions:
                label = f"{v}  (mevcut versiyon)" if v == current else v
                self.mc_version_combo.addItem(label, v)
            self.mc_version_combo.setEnabled(True)
            self._load_loader_versions()

        def on_error(message: str) -> None:
            self.mc_version_combo.clear()
            self.mc_version_combo.addItem("Yüklenemedi (tekrar deneyin)", None)
            self._show_error(f"Minecraft versiyon listesi yüklenemedi: {message}")

        run_async(task, on_success=on_success, on_error=on_error)

    def _load_loader_versions(self) -> None:
        if self._loader == Loader.VANILLA:
            return
        mc_version = self.mc_version_combo.currentData()
        if not mc_version:
            return

        self.loader_version_combo.clear()
        self.loader_version_combo.addItem("Yükleniyor...", None)
        self.loader_version_combo.setEnabled(False)

        async def task() -> list[str]:
            async with make_client() as client:
                return await get_loader_versions(client, self._loader, mc_version)

        def on_success(versions: list[str]) -> None:
            self.loader_version_combo.clear()
            if not versions:
                self.loader_version_combo.addItem("Bulunamadı", None)
                self._show_error(f"{mc_version} için {self._loader.value} versiyonu bulunamadı.")
                return
            for i, v in enumerate(versions):
                label = f"{v}  (en yeni)" if i == 0 else v
                self.loader_version_combo.addItem(label, v)
            self.loader_version_combo.setEnabled(True)
            self._mark_recommended_loader_version(mc_version)

        def on_error(message: str) -> None:
            self.loader_version_combo.clear()
            self.loader_version_combo.addItem("Yüklenemedi", None)
            self._show_error(message)

        run_async(task, on_success=on_success, on_error=on_error)

    def _mark_recommended_loader_version(self, mc_version: str) -> None:
        async def task() -> str | None:
            async with make_client() as client:
                return await get_recommended_loader_version(client, self._loader, mc_version)

        def on_success(recommended: str | None) -> None:
            if not recommended:
                return
            for i in range(self.loader_version_combo.count()):
                if self.loader_version_combo.itemData(i) == recommended:
                    text = self.loader_version_combo.itemText(i)
                    if "Önerilen" not in text:
                        self.loader_version_combo.setItemText(i, f"{text}  ⭐ Önerilen")
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
            self._show_error("İsim boş olamaz.")
            return
        if not self.mc_version_combo.currentData():
            self._show_error("Minecraft versiyonu seçin.")
            return
        if self._loader != Loader.VANILLA and not self.loader_version_combo.currentData():
            self._show_error("Loader versiyonu seçin.")
            return
        self.accept()

    def result_values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "minecraft": self.mc_version_combo.currentData(),
            "loader_version": self.loader_version_combo.currentData() or "",
        }
