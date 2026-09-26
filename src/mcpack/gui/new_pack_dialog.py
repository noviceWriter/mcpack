"""Yeni Pack oluşturma diyaloğu.

Eski akış (name, minecraft, loader) serbest metin girişleri kullanıyordu —
yazım hatası yapılan bir Minecraft/loader versiyonu export'u ya da
launcher kurulumunu sessizce bozar. Burada Minecraft ve loader versiyonları
gerçek API'lerden (Modrinth, Fabric, Quilt, Forge, NeoForge) çekilip
dropdown olarak sunulur; Vanilla (loader'sız) seçeneği de eklendi.
"""

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
from mcpack.gameinfo import get_loader_versions, get_minecraft_versions
from mcpack.gui.theme import danger_color
from mcpack.gui.widgets import run_async
from mcpack.models import Loader

_LOADER_LABELS: dict[Loader, str] = {
    Loader.VANILLA: "Vanilla (loader yok)",
    Loader.FABRIC: "Fabric",
    Loader.QUILT: "Quilt",
    Loader.FORGE: "Forge",
    Loader.NEOFORGE: "NeoForge",
}


class NewPackDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Pack")
        self.setMinimumWidth(400)

        self.name_input = QLineEdit()
        self.author_input = QLineEdit()
        self.summary_input = QLineEdit()

        self.mc_version_combo = QComboBox()
        self.mc_version_combo.addItem("Yükleniyor...", None)
        self.mc_version_combo.setEnabled(False)
        self.mc_version_combo.currentIndexChanged.connect(self._on_mc_version_changed)

        self.loader_combo = QComboBox()
        for loader, label in _LOADER_LABELS.items():
            self.loader_combo.addItem(label, loader.value)
        self.loader_combo.currentIndexChanged.connect(self._on_loader_changed)

        self.loader_version_combo = QComboBox()
        self.loader_version_combo.setEnabled(False)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {danger_color()};")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QFormLayout()
        form.addRow("İsim:", self.name_input)
        form.addRow("Minecraft:", self.mc_version_combo)
        form.addRow("Loader:", self.loader_combo)
        form.addRow("Loader Versiyonu:", self.loader_version_combo)
        form.addRow("Yazar:", self.author_input)
        form.addRow("Açıklama:", self.summary_input)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)

        self._load_minecraft_versions()

    # -- veri yükleme ---------------------------------------------------

    def _load_minecraft_versions(self) -> None:
        async def task() -> list[str]:
            async with make_client() as client:
                return await get_minecraft_versions(client)

        def on_success(versions: list[str]) -> None:
            self.mc_version_combo.clear()
            if not versions:
                self.mc_version_combo.addItem("Bulunamadı", None)
                return
            for v in versions:
                self.mc_version_combo.addItem(v, v)
            self.mc_version_combo.setEnabled(True)
            self._on_mc_version_changed()

        def on_error(message: str) -> None:
            self.mc_version_combo.clear()
            self.mc_version_combo.addItem("Yüklenemedi (elle giremezsiniz, tekrar deneyin)", None)
            self._show_error(f"Minecraft versiyon listesi yüklenemedi: {message}")

        run_async(task, on_success=on_success, on_error=on_error)

    def _current_loader(self) -> Loader:
        return Loader(self.loader_combo.currentData())

    def _on_loader_changed(self) -> None:
        self._load_loader_versions()

    def _on_mc_version_changed(self) -> None:
        self._load_loader_versions()

    def _load_loader_versions(self) -> None:
        loader = self._current_loader()

        if loader == Loader.VANILLA:
            self.loader_version_combo.clear()
            self.loader_version_combo.setEnabled(False)
            return

        mc_version = self.mc_version_combo.currentData()
        if not mc_version:
            return

        self.loader_version_combo.clear()
        self.loader_version_combo.addItem("Yükleniyor...", None)
        self.loader_version_combo.setEnabled(False)

        async def task() -> list[str]:
            async with make_client() as client:
                return await get_loader_versions(client, loader, mc_version)

        def on_success(versions: list[str]) -> None:
            self.loader_version_combo.clear()
            if not versions:
                self.loader_version_combo.addItem("Bulunamadı", None)
                self._show_error(f"{mc_version} için {loader.value} versiyonu bulunamadı.")
                return
            for v in versions:
                self.loader_version_combo.addItem(v, v)
            self.loader_version_combo.setEnabled(True)

        def on_error(message: str) -> None:
            self.loader_version_combo.clear()
            self.loader_version_combo.addItem("Yüklenemedi", None)
            self._show_error(message)

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
        loader = self._current_loader()
        if loader != Loader.VANILLA and not self.loader_version_combo.currentData():
            self._show_error("Loader versiyonu seçin.")
            return
        self.accept()

    def result_values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "minecraft": self.mc_version_combo.currentData(),
            "loader": self._current_loader(),
            "loader_version": self.loader_version_combo.currentData() or "",
            "author": self.author_input.text().strip(),
            "summary": self.summary_input.text().strip(),
        }
