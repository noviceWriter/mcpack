"""Sunucu bölümünün "Oyuncular" paneli: Aternos benzeri panellerdeki gibi
çevrimiçi oyuncuları görüp üzerlerinde basit aksiyonlar (iyileştir/öldür/
hasar/doyur/açlığı azalt) uygulamak ve envanter+ender sandığı içeriğini
SALT OKUNUR görüntülemek için — komut yazmadan.

Kullanıcı netleştirdi: envanterle ilgili istek sadece GÖRÜNTÜLEME (ana
envanter + zırh/elindeki eşya + ender sandığı), DÜZENLEME değil — vanilla
Minecraft oyuncu envanterine elle NBT yazmayı zaten yasaklıyor (anti-cheat),
bu yüzden burada hiçbir "eşya ekle/slot'a sürükle" arayüzü YOK.

Diğer *Section/Panel sınıfları gibi bu widget "aptal" bir görünümdür — asıl
iş (komut gönderme, yanıt bekleme/parse etme) MainWindow'da (bkz.
main_window.py) yapılır."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.server_runtime import InventoryItem, categorize_inventory_slot


def _item_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setMaximumHeight(160)
    return table


class PlayerPanel(QWidget):
    refresh_requested = Signal()
    heal_requested = Signal(str)
    kill_requested = Signal(str)
    damage_requested = Signal(str, int)
    feed_requested = Signal(str)
    hunger_requested = Signal(str, int)
    inventory_requested = Signal(str)
    ender_chest_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.not_running_label = QLabel("Oyuncu paneli için sunucu çalışıyor olmalı.")
        self.not_running_label.setProperty("role", "muted")
        outer.addWidget(self.not_running_label)

        self.body = QWidget()
        body_layout = QHBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.addWidget(QLabel("Çevrimiçi Oyuncular:"))
        self.player_list = QListWidget()
        self.player_list.setMaximumWidth(180)
        self.player_list.currentTextChanged.connect(self._on_selection_changed)
        left.addWidget(self.player_list)
        refresh_button = QPushButton("Listeyi Yenile")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        left.addWidget(refresh_button)
        body_layout.addLayout(left)

        right = QVBoxLayout()

        actions_row1 = QHBoxLayout()
        heal_button = QPushButton("İyileştir")
        heal_button.clicked.connect(lambda: self._emit_if_selected(self.heal_requested))
        actions_row1.addWidget(heal_button)

        kill_button = QPushButton("Öldür")
        kill_button.setObjectName("danger")
        kill_button.clicked.connect(lambda: self._emit_if_selected(self.kill_requested))
        actions_row1.addWidget(kill_button)

        feed_button = QPushButton("Doyur")
        feed_button.clicked.connect(lambda: self._emit_if_selected(self.feed_requested))
        actions_row1.addWidget(feed_button)
        actions_row1.addStretch()
        right.addLayout(actions_row1)

        damage_row = QHBoxLayout()
        damage_button = QPushButton("Hasar Ver")
        self.damage_spin = QSpinBox()
        self.damage_spin.setRange(1, 1000)
        self.damage_spin.setValue(4)
        self.damage_spin.setSuffix(" HP")
        damage_button.clicked.connect(
            lambda: self._emit_if_selected_with_int(self.damage_requested, self.damage_spin.value())
        )
        damage_row.addWidget(damage_button)
        damage_row.addWidget(self.damage_spin)
        damage_row.addStretch()
        right.addLayout(damage_row)

        hunger_row = QHBoxLayout()
        hunger_button = QPushButton("Açlığı Azalt")
        hunger_button.setToolTip(
            "Vanilla Minecraft'ta açlığı ANINDA belirli bir değere ayarlamanın bir yolu yok — "
            "bu, oyuncuyu seçilen süre boyunca normalden daha hızlı acıktırır (yaklaşık bir etkidir)."
        )
        self.hunger_spin = QSpinBox()
        self.hunger_spin.setRange(5, 300)
        self.hunger_spin.setValue(30)
        self.hunger_spin.setSuffix(" sn")
        hunger_button.clicked.connect(
            lambda: self._emit_if_selected_with_int(self.hunger_requested, self.hunger_spin.value())
        )
        hunger_row.addWidget(hunger_button)
        hunger_row.addWidget(self.hunger_spin)
        hunger_row.addStretch()
        right.addLayout(hunger_row)

        inventory_box = QGroupBox("Envanter (zırh + ikinci el dahil) — salt okunur")
        inventory_layout = QVBoxLayout(inventory_box)
        view_inventory_button = QPushButton("Envanteri Görüntüle")
        view_inventory_button.clicked.connect(lambda: self._emit_if_selected(self.inventory_requested))
        inventory_layout.addWidget(view_inventory_button)
        self.inventory_table = _item_table(["Bölüm", "Eşya", "Adet"])
        inventory_layout.addWidget(self.inventory_table)
        right.addWidget(inventory_box)

        ender_box = QGroupBox("Ender Sandığı — salt okunur")
        ender_layout = QVBoxLayout(ender_box)
        view_ender_button = QPushButton("Ender Sandığını Görüntüle")
        view_ender_button.clicked.connect(lambda: self._emit_if_selected(self.ender_chest_requested))
        ender_layout.addWidget(view_ender_button)
        self.ender_table = _item_table(["Slot", "Eşya", "Adet"])
        ender_layout.addWidget(self.ender_table)
        right.addWidget(ender_box)

        body_layout.addLayout(right, 1)
        outer.addWidget(self.body)
        self.body.setVisible(False)

    # -- seçim --------------------------------------------------------------

    def _on_selection_changed(self, _text: str) -> None:
        self.inventory_table.setRowCount(0)
        self.ender_table.setRowCount(0)

    def selected_player(self) -> str | None:
        item = self.player_list.currentItem()
        return item.text() if item is not None else None

    def _emit_if_selected(self, signal: Signal) -> None:
        player = self.selected_player()
        if player:
            signal.emit(player)

    def _emit_if_selected_with_int(self, signal: Signal, value: int) -> None:
        player = self.selected_player()
        if player:
            signal.emit(player, value)

    # -- MainWindow'un çağırdığı güncelleme metodları -------------------------

    def set_running(self, running: bool) -> None:
        self.not_running_label.setVisible(not running)
        self.body.setVisible(running)
        if not running:
            self.player_list.clear()
            self.inventory_table.setRowCount(0)
            self.ender_table.setRowCount(0)

    def set_players(self, names: list[str]) -> None:
        previous = self.selected_player()
        self.player_list.clear()
        self.player_list.addItems(names)
        if previous in names:
            matches = self.player_list.findItems(previous, Qt.MatchFlag.MatchExactly)
            if matches:
                self.player_list.setCurrentItem(matches[0])

    def _fill_table(self, table: QTableWidget, items: list[InventoryItem], *, with_category: bool) -> None:
        table.setRowCount(len(items))
        for row, item in enumerate(items):
            label = categorize_inventory_slot(item.slot) if with_category else str(item.slot)
            table.setItem(row, 0, QTableWidgetItem(label))
            table.setItem(row, 1, QTableWidgetItem(item.item_id))
            table.setItem(row, 2, QTableWidgetItem(str(item.count)))

    def set_inventory(self, items: list[InventoryItem]) -> None:
        self._fill_table(self.inventory_table, items, with_category=True)

    def set_ender_chest(self, items: list[InventoryItem]) -> None:
        self._fill_table(self.ender_table, items, with_category=False)
