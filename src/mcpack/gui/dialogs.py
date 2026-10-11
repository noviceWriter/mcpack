"""Diyaloglar: yeni pack, fork, mod sürümü seçici, önerilen modlar,
istemci/sunucu ortamı düzenleyici."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.downloader import make_client
from mcpack.gameinfo import get_loader_versions, get_minecraft_versions, get_recommended_loader_version
from mcpack.gui.components import Chip, FormDialog, SearchField, label, loader_badge
from mcpack.gui.formatting import LOADER_LABELS, format_size, loader_label
from mcpack.gui.tasks import TaskManager
from mcpack.i18n import t
from mcpack.models import EnvRequirement, Loader, ModEntry, Pack
from mcpack.sources.base import ModDetail, ModVersion

# -- Minecraft + loader sürüm seçimi (yeni pack ve fork ortak) ------------------


class VersionForm(QWidget):
    """Minecraft sürümü + loader + loader sürümü seçimi. Listeler gerçek
    API'lerden çekilir; en yeni ve sağlayıcının "önerilen" build'i işaretlenir."""

    def __init__(self, tasks: TaskManager, *, fixed_loader: Loader | None = None, current_mc: str | None = None) -> None:
        super().__init__()
        self._tasks = tasks
        self._fixed_loader = fixed_loader
        self._current_mc = current_mc
        self._loader_request = 0
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(10)

        self.mc_combo = QComboBox()
        self.mc_combo.setMinimumWidth(260)
        self.mc_combo.addItem(t("common.loading"), None)
        self.mc_combo.setEnabled(False)
        self.mc_combo.currentIndexChanged.connect(self._load_loader_versions)

        self.loader_combo = QComboBox()
        for loader in Loader:
            self.loader_combo.addItem(t("newpack.loader_vanilla") if loader == Loader.VANILLA else LOADER_LABELS[loader.value], loader.value)
        if fixed_loader is not None:
            self.loader_combo.setCurrentIndex(self.loader_combo.findData(fixed_loader.value))
            self.loader_combo.setEnabled(False)
        else:
            self.loader_combo.setCurrentIndex(self.loader_combo.findData(Loader.FABRIC.value))
        self.loader_combo.currentIndexChanged.connect(self._load_loader_versions)

        self.loader_version_combo = QComboBox()
        self.loader_version_combo.setEnabled(False)
        self.only_stable = QCheckBox(t("newpack.recommended_only"))
        self.only_stable.toggled.connect(self._apply_stable_filter)
        self._loader_versions: list[str] = []
        self._recommended: str | None = None

        self.form.addRow("Minecraft", self.mc_combo)
        self.form.addRow("Loader", self.loader_combo)
        self.form.addRow(t("newpack.loader_version"), self.loader_version_combo)
        self.form.addRow("", self.only_stable)
        self.status = label("", role="dim", wrap=True)
        self.form.addRow("", self.status)
        self._load_mc_versions()

    def loader(self) -> Loader:
        return Loader(self.loader_combo.currentData())

    def minecraft(self) -> str | None:
        return self.mc_combo.currentData()

    def loader_version(self) -> str:
        return self.loader_version_combo.currentData() or ""

    def validate(self) -> str | None:
        if not self.minecraft():
            return t("newpack.error_select_mc")
        if self.loader() != Loader.VANILLA and not self.loader_version():
            return t("newpack.error_select_loader_version")
        return None

    def _load_mc_versions(self) -> None:
        async def task(ctx):
            async with make_client() as client:
                return await get_minecraft_versions(client)

        def done(versions: list[str]) -> None:
            self.mc_combo.blockSignals(True)
            self.mc_combo.clear()
            for v in versions:
                text = t("forkpack.current_suffix", version=v) if v == self._current_mc else v
                self.mc_combo.addItem(text, v)
            self.mc_combo.setEnabled(bool(versions))
            self.mc_combo.blockSignals(False)
            self._load_loader_versions()

        def failed(message: str) -> None:
            self.mc_combo.clear()
            self.mc_combo.addItem(t("newpack.load_failed"), None)
            self.status.setText(t("newpack.mc_load_failed", message=message))

        self._tasks.run(t("newpack.task_mc_versions"), task, on_success=done, on_error=failed, silent=True, category="gameinfo", owner=self)

    def _load_loader_versions(self) -> None:
        loader = self.loader()
        mc = self.minecraft()
        is_vanilla = loader == Loader.VANILLA
        self.loader_version_combo.setVisible(not is_vanilla)
        self.only_stable.setVisible(not is_vanilla)
        self.form.labelForField(self.loader_version_combo).setVisible(not is_vanilla)
        self.loader_version_combo.clear()
        self.loader_version_combo.setEnabled(False)
        if is_vanilla or not mc:
            self.status.setText("")
            return
        self.loader_version_combo.addItem(t("common.loading"), None)
        self._loader_request += 1
        request = self._loader_request

        async def task(ctx):
            async with make_client() as client:
                versions = await get_loader_versions(client, loader, mc)
                recommended = await get_recommended_loader_version(client, loader, mc)
                return versions, recommended

        def done(result) -> None:
            if request != self._loader_request:
                return  # kullanıcı bu arada başka bir sürüm seçti
            self._loader_versions, self._recommended = result
            if not self._loader_versions:
                self.loader_version_combo.clear()
                self.loader_version_combo.addItem(t("common.not_found"), None)
                self.status.setText(t("newpack.loader_versions_not_found", mc_version=mc, loader=loader.value))
                return
            self.status.setText(t("newpack.loader_versions_count", count=len(self._loader_versions)))
            self._apply_stable_filter()

        def failed(message: str) -> None:
            if request != self._loader_request:
                return
            self.loader_version_combo.clear()
            self.loader_version_combo.addItem(t("newpack.load_failed"), None)
            self.status.setText(message)

        self._tasks.run(t("newpack.task_loader_versions", loader=loader.value, mc=mc), task, on_success=done, on_error=failed, silent=True, category="gameinfo", owner=self)

    def _apply_stable_filter(self) -> None:
        if not self._loader_versions:
            return
        versions = self._loader_versions
        if self.only_stable.isChecked() and self._recommended:
            versions = [self._recommended]
        self.loader_version_combo.clear()
        default_index = 0
        for i, v in enumerate(versions):
            tags = []
            if v == self._loader_versions[0]:
                tags.append(t("newpack.tag_latest"))
            if v == self._recommended:
                tags.append(t("newpack.tag_recommended"))
                default_index = i
            text = f"{v}   ·  {' · '.join(tags)}" if tags else v
            self.loader_version_combo.addItem(text, v)
        self.loader_version_combo.setCurrentIndex(default_index)
        self.loader_version_combo.setEnabled(True)


class NewPackDialog(FormDialog):
    def __init__(self, tasks: TaskManager, parent=None) -> None:
        super().__init__(t("newpack.title"), parent, width=520, subtitle=t("newpack.subtitle"))
        self.ok_button.setText(t("newpack.create"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(t("newpack.name_placeholder"))
        self.author_input = QLineEdit()
        self.summary_input = QLineEdit()
        meta = QFormLayout()
        meta.setSpacing(10)
        meta.addRow(t("newpack.name"), self.name_input)
        self.body.addLayout(meta)
        self.versions = VersionForm(tasks)
        self.body.addWidget(self.versions)
        extra = QFormLayout()
        extra.setSpacing(10)
        extra.addRow(t("newpack.author"), self.author_input)
        extra.addRow(t("newpack.summary"), self.summary_input)
        self.body.addLayout(extra)
        self.name_input.setFocus()

    def validate(self) -> str | None:
        if not self.name_input.text().strip():
            return t("newpack.error_name_empty")
        return self.versions.validate()

    def values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "minecraft": self.versions.minecraft(),
            "loader": self.versions.loader(),
            "loader_version": self.versions.loader_version(),
            "author": self.author_input.text().strip(),
            "summary": self.summary_input.text().strip(),
        }


class ForkPackDialog(FormDialog):
    def __init__(self, tasks: TaskManager, pack: Pack, parent=None) -> None:
        super().__init__(t("forkpack.title"), parent, width=520, subtitle=t("forkpack.info", name=pack.name))
        self.ok_button.setText(t("forkpack.create"))
        self.name_input = QLineEdit(t("forkpack.name_default", name=pack.name))
        form = QFormLayout()
        form.addRow(t("newpack.name"), self.name_input)
        self.body.addLayout(form)
        self.versions = VersionForm(tasks, fixed_loader=pack.loader, current_mc=pack.minecraft)
        self.body.addWidget(self.versions)

    def validate(self) -> str | None:
        if not self.name_input.text().strip():
            return t("newpack.error_name_empty")
        return self.versions.validate()

    def values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "minecraft": self.versions.minecraft(),
            "loader_version": self.versions.loader_version(),
        }


# -- mod sürümü seçici -------------------------------------------------------------


class VersionPickerDialog(FormDialog):
    """Bir modun pack'le uyumlu tüm sürümlerini tablo halinde gösterir
    (ad, MC sürümleri, loader'lar, dosya boyutu, bağımlılık sayısı) —
    arama ve filtreyle. API en yeniden eskiye sıralı döner; en yenisi
    varsayılan seçilidir."""

    def __init__(self, title: str, versions: list[ModVersion], parent=None) -> None:
        super().__init__(t("picker.title"), parent, width=760, subtitle=t("picker.subtitle", title=title, count=len(versions)))
        self.ok_button.setText(t("picker.add"))
        self._versions = versions
        self.filter = SearchField(t("picker.filter"))
        self.filter.search.connect(self._apply_filter)
        self.body.addWidget(self.filter)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [t("picker.col.version"), "Minecraft", "Loader", t("picker.col.size"), t("picker.col.deps")]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._accept)
        self.table.setMinimumHeight(360)
        self.body.addWidget(self.table)
        for i, v in enumerate(versions):
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = f"{v.name}  ★" if i == 0 else v.name
            item = QTableWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(", ".join(v.game_versions[:6]) + (" …" if len(v.game_versions) > 6 else "")))
            self.table.setItem(row, 2, QTableWidgetItem(", ".join(v.loaders)))
            file = v.primary_file
            self.table.setItem(row, 3, QTableWidgetItem(format_size(file.size if file else None)))
            req = sum(1 for d in v.dependencies if d.dependency_type == "required")
            self.table.setItem(row, 4, QTableWidgetItem(str(req)))
        self.table.selectRow(0)

    def _apply_filter(self, text: str) -> None:
        q = text.lower()
        for row in range(self.table.rowCount()):
            hay = " ".join(self.table.item(row, c).text().lower() for c in range(3))
            self.table.setRowHidden(row, bool(q) and q not in hay)

    def validate(self) -> str | None:
        return None if self.table.currentRow() >= 0 else t("picker.error_select")

    def selected(self) -> ModVersion:
        item = self.table.item(self.table.currentRow(), 0)
        return self._versions[item.data(Qt.ItemDataRole.UserRole)]


class RecommendedModsDialog(FormDialog):
    def __init__(self, suggestions: list[tuple[ModVersion, ModDetail]], parent=None) -> None:
        super().__init__(t("recmods.title"), parent, width=480, subtitle=t("recmods.info"))
        self.ok_button.setText(t("recmods.add_selected"))
        self.cancel_button.setText(t("recmods.skip"))
        container = QWidget()
        col = QVBoxLayout(container)
        col.setSpacing(6)
        self._boxes: list[tuple[QCheckBox, ModVersion, ModDetail]] = []
        for version, detail in suggestions:
            box = QCheckBox(detail.title)
            box.setToolTip(detail.description)
            col.addWidget(box)
            self._boxes.append((box, version, detail))
        col.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        scroll.setMinimumHeight(220)
        self.body.addWidget(scroll)
        row = QHBoxLayout()
        all_btn = QPushButton(t("recmods.select_all"))
        all_btn.setProperty("variant", "ghost")
        all_btn.clicked.connect(lambda: [b.setChecked(True) for b, _v, _d in self._boxes])
        row.addWidget(all_btn)
        row.addStretch()
        self.body.addLayout(row)

    def selected(self) -> list[tuple[ModVersion, ModDetail]]:
        return [(v, d) for b, v, d in self._boxes if b.isChecked()]


class EnvEditorDialog(FormDialog):
    """Bir ya da birden çok modun istemci/sunucu gereksinimini düzeltir."""

    def __init__(self, mods: list[ModEntry], parent=None) -> None:
        names = ", ".join((m.name or m.file_name) for m in mods[:3]) + (f" +{len(mods) - 3}" if len(mods) > 3 else "")
        super().__init__(t("env.editor_title"), parent, width=460, subtitle=names)
        first = mods[0]
        self._groups: dict[str, QButtonGroup] = {}
        for side, current in (("client", first.env.client), ("server", first.env.server)):
            self.body.addWidget(label(t(f"env.editor_{side}"), role="h3"))
            row = QHBoxLayout()
            group = QButtonGroup(self)
            for req in EnvRequirement:
                radio = QRadioButton(t(f"env.req.{req.value}"))
                radio.setProperty("value", req.value)
                radio.setChecked(req == current)
                group.addButton(radio)
                row.addWidget(radio)
            row.addStretch()
            self.body.addLayout(row)
            self._groups[side] = group
        self.body.addWidget(label(t("env.editor_hint"), role="dim", wrap=True))

    def _value(self, side: str) -> EnvRequirement:
        checked = self._groups[side].checkedButton()
        return EnvRequirement(checked.property("value"))

    def values(self) -> tuple[EnvRequirement, EnvRequirement]:
        return self._value("client"), self._value("server")


class PackMetaDialog(FormDialog):
    def __init__(self, pack: Pack, parent=None) -> None:
        super().__init__(t("packmeta.title"), parent, width=480)
        head = QHBoxLayout()
        head.addWidget(loader_badge(pack.loader.value, size=36))
        head.addWidget(label(f"{loader_label(pack.loader.value)} {pack.loader_version} · MC {pack.minecraft}", role="muted"))
        head.addStretch()
        head.addWidget(Chip(pack.id[:8], "neutral"))
        self.body.addLayout(head)
        form = QFormLayout()
        form.setSpacing(10)
        self.name_input = QLineEdit(pack.name)
        self.version_input = QLineEdit(pack.version)
        self.author_input = QLineEdit(pack.author)
        self.summary_input = QLineEdit(pack.summary)
        form.addRow(t("newpack.name"), self.name_input)
        form.addRow(t("packmeta.version"), self.version_input)
        form.addRow(t("newpack.author"), self.author_input)
        form.addRow(t("newpack.summary"), self.summary_input)
        self.body.addLayout(form)

    def validate(self) -> str | None:
        return None if self.name_input.text().strip() else t("newpack.error_name_empty")

    def values(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "version": self.version_input.text().strip() or "1.0.0",
            "author": self.author_input.text().strip(),
            "summary": self.summary_input.text().strip(),
        }


class UpdatesDialog(FormDialog):
    """Bulunan güncellemeler: her satır işaretlenebilir (varsayılan: hepsi)."""

    def __init__(self, updates: list, errors: list[str], parent=None) -> None:
        super().__init__(t("updates.title"), parent, width=760, subtitle=t("updates.subtitle", count=len(updates)))
        self.ok_button.setText(t("updates.apply"))
        self._updates = updates
        self.table = QTableWidget(len(updates), 4)
        self.table.setHorizontalHeaderLabels([t("updates.col.name"), t("updates.col.current"), t("updates.col.new"), t("updates.col.source")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(320)
        for row, u in enumerate(updates):
            name = QTableWidgetItem(u.name + (f"  ({t(f'updates.kind.{u.kind.value}')})" if u.kind else ""))
            name.setFlags(name.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            name.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(u.current_file))
            self.table.setItem(row, 2, QTableWidgetItem(u.new_file))
            self.table.setItem(row, 3, QTableWidgetItem(u.source.value))
        self.body.addWidget(self.table)
        row = QHBoxLayout()
        for text, state in ((t("updates.select_all"), Qt.CheckState.Checked), (t("updates.select_none"), Qt.CheckState.Unchecked)):
            b = QPushButton(text)
            b.setProperty("variant", "ghost")
            b.clicked.connect(lambda _c=False, st=state: self._set_all(st))
            row.addWidget(b)
        row.addStretch()
        self.body.addLayout(row)
        self.body.addWidget(label(t("updates.note"), role="dim", wrap=True))
        if errors:
            box = label(t("updates.errors", count=len(errors)) + "\n" + "\n".join(f"• {e}" for e in errors[:8]), role="notice", wrap=True)
            self.body.addWidget(box)

    def _set_all(self, state) -> None:
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setCheckState(state)

    def validate(self) -> str | None:
        return None if self.selected() else t("updates.error_none")

    def selected(self) -> list:
        return [u for r, u in enumerate(self._updates) if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]
