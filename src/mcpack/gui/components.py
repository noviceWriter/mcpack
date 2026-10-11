"""Yeniden kullanılabilir arayüz bileşenleri: kart, çip, rozet, boş durum,
istatistik kutusu, arama alanı, akış (flow) yerleşimi, toast bildirimleri,
onay penceresi. Sayfa modülleri (gui/pages/*) sadece bunları birleştirir —
renk/biçim hiçbir sayfada elle yazılmaz (bkz. theme.py)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from mcpack.gui.formatting import LOADER_GLYPHS, source_label
from mcpack.gui.icons import icons
from mcpack.gui.theme import COLORS, TONES, category_color, readable_on
from mcpack.i18n import t

# -- küçük yardımcılar ---------------------------------------------------------


def button(
    text: str,
    *,
    variant: str | None = None,
    on_click: Callable[[], None] | None = None,
    tooltip: str | None = None,
    checkable: bool = False,
) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if tooltip:
        b.setToolTip(tooltip)
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click is not None:
        b.clicked.connect(lambda _checked=False: on_click())
    return b


def tool_button(text: str, *, tooltip: str | None = None, variant: str = "ghost") -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setProperty("variant", variant)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def label(text: str = "", *, role: str | None = None, wrap: bool = False, selectable: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def separator() -> QFrame:
    line = QFrame()
    line.setProperty("separator", "true")
    return line


def hbox(*widgets, spacing: int = 8, margins: tuple[int, int, int, int] = (0, 0, 0, 0), stretch_at: int | None = None) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for i, w in enumerate(widgets):
        if stretch_at is not None and i == stretch_at:
            layout.addStretch(1)
        if w is None:
            layout.addStretch(1)
        elif isinstance(w, QLayout):
            layout.addLayout(w)
        else:
            layout.addWidget(w)
    if stretch_at is not None and stretch_at >= len(widgets):
        layout.addStretch(1)
    return layout


def repolish(widget: QWidget) -> None:
    """Dinamik özellik (setProperty) değişince QSS'in yeniden uygulanması."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class Card(QFrame):
    """Yuvarlatılmış, kenarlıklı yüzey. hover=True ise üzerine gelince
    vurgulanır (tıklanabilir kartlar için)."""

    clicked = Signal()

    def __init__(self, *, hover: bool = False, padding: int = 16, spacing: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover = hover
        self.setProperty("card", "hover" if hover else "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        if hover:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("card", "selected" if selected else ("hover" if self._hover else "true"))
        repolish(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._hover and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Chip(QLabel):
    """Küçük etiket. tone: neutral/accent/success/warning/danger/info."""

    def __init__(self, text: str = "", tone: str = "neutral", *, dot_color: str | None = None) -> None:
        super().__init__()
        self._dot = dot_color
        self.set(text, tone)

    def set(self, text: str, tone: str = "neutral", *, dot_color: str | None = None) -> None:
        if dot_color is not None:
            self._dot = dot_color
        bg, fg = TONES.get(tone, TONES["neutral"])
        prefix = f'<span style="color:{self._dot}">●</span>&nbsp;' if self._dot else ""
        self.setText(f"{prefix}{text}")
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 10px; padding: 2px 9px; font-size: 11px; font-weight: 600;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


def source_chip(source: str) -> Chip:
    return Chip(source_label(source), "neutral", dot_color=category_color(source))


class Badge(QLabel):
    """Kare, renkli rozet (loader simgesi ya da baş harf)."""

    def __init__(self, text: str, color: str, *, size: int = 40) -> None:
        super().__init__(text)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        radius = max(6, size // 4)
        self.setStyleSheet(
            f"background-color: {color}; color: {readable_on(color)}; border-radius: {radius}px; "
            f"font-size: {max(14, int(size * 0.5))}px; font-weight: 700;"
        )


def loader_badge(loader: str, *, size: int = 40) -> Badge:
    return Badge(LOADER_GLYPHS.get(loader, "❓"), category_color(loader), size=size)


class IconBox(QLabel):
    """Uzak bir ikonu (Modrinth/CurseForge) async yükleyen, yüklenene kadar
    baş harfli yer tutucu gösteren kare kutu."""

    def __init__(self, *, size: int = 44, fallback_text: str = "", color: str | None = None) -> None:
        super().__init__()
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg = color or COLORS["elevated"]
        self.setStyleSheet(
            f"background-color: {bg}; color: {COLORS['text_muted']}; border-radius: {max(6, size // 5)}px; "
            f"font-size: {max(12, size // 2.6):.0f}px; font-weight: 700;"
        )
        self._url: str | None = None
        self.setText((fallback_text or "?")[:1].upper())

    def reset(self, fallback_text: str = "") -> None:
        self._url = None
        self.clear()
        self.setText((fallback_text or "?")[:1].upper())

    def load(self, url: str | None) -> None:
        self._url = url
        if url:
            # Geç gelen eski bir ikon (kullanıcı bu arada başka öğe seçtiyse)
            # yenisinin üzerine yazılmasın.
            icons().load(url, lambda pm, u=url: self._url == u and self._set_pixmap(pm), owner=self)

    def _set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self._size, self._size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.setText("")
        self.setPixmap(scaled)


class StatTile(Card):
    def __init__(self, title: str, value: str = "—", *, hint: str = "", accent: str | None = None, clickable: bool = False) -> None:
        super().__init__(hover=clickable, padding=14, spacing=2)
        self.title_label = label(title, role="dim")
        self.value_label = label(value, role="stat")
        if accent:
            self.value_label.setStyleSheet(f"color: {accent};")
        self.hint_label = label(hint, role="dim")
        self.body.addWidget(self.title_label)
        self.body.addWidget(self.value_label)
        self.body.addWidget(self.hint_label)
        self.hint_label.setVisible(bool(hint))
        self.setMinimumWidth(150)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)
            self.hint_label.setVisible(bool(hint))


class EmptyState(QWidget):
    def __init__(self, glyph: str, title: str, subtitle: str = "", *, actions: list[QPushButton] | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)
        icon = QLabel(glyph)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 42px;")
        layout.addWidget(icon)
        self.title_label = label(title, role="h2")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, role="muted", wrap=True)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setMaximumWidth(460)
        layout.addWidget(self.subtitle_label, alignment=Qt.AlignmentFlag.AlignCenter)
        if actions:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addStretch()
            for a in actions:
                row.addWidget(a)
            row.addStretch()
            layout.addSpacing(8)
            layout.addLayout(row)


class SearchField(QLineEdit):
    """Büyüteç simgeli, debounce'lu arama alanı. `search` sinyali kullanıcı
    yazmayı bıraktıktan `delay_ms` sonra (ya da Enter'da hemen) yayılır."""

    search = Signal(str)

    def __init__(self, placeholder: str = "", *, delay_ms: int = 300) -> None:
        super().__init__()
        self.setProperty("variant", "search")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self._glass = QLabel("⌕", self)
        self._glass.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 16px; background: transparent;")
        self._glass.move(11, 5)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._emit)
        self.textChanged.connect(lambda _t: self._timer.start())
        self.returnPressed.connect(self._emit)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._glass.move(11, (self.height() - self._glass.sizeHint().height()) // 2)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self.text():
            self.clear()
            return
        super().keyPressEvent(event)

    def _emit(self) -> None:
        self._timer.stop()
        self.search.emit(self.text().strip())


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", *, actions: list[QWidget] | None = None) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title_label = label(title, role="h2")
        col.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, role="muted", wrap=True)
        self.subtitle_label.setVisible(bool(subtitle))
        col.addWidget(self.subtitle_label)
        layout.addLayout(col, 1)
        for a in actions or []:
            layout.addWidget(a)


# -- akış yerleşimi (kart ızgarası) --------------------------------------------


class FlowLayout(QLayout):
    """Qt'nin resmi "Flow Layout" örneğinin sadeleştirilmiş hali: öğeleri
    satır satır dizip genişliğe göre kaydırır (kütüphane kart ızgarası)."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = 12) -> None:
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect: QRect, *, test: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


def clear_layout(layout: QLayout) -> None:
    """Yerleşimi boşaltır. Widget'lar HEMEN gizlenip ebeveynden ayrılır —
    sadece deleteLater() çağrılırsa olay döngüsüne kadar eski kartlar
    yenilerinin altında "hayalet" olarak görünmeye devam ediyordu."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


# -- toast bildirimleri ---------------------------------------------------------

_TOAST_GLYPHS = {"info": "ℹ", "success": "✓", "warning": "⚠", "error": "✖"}
_TOAST_TONES = {"info": "info", "success": "success", "warning": "warning", "error": "danger"}


class _Toast(QFrame):
    closed = Signal(object)

    def __init__(self, level: str, message: str, *, action: tuple[str, Callable[[], None]] | None, duration_ms: int) -> None:
        super().__init__()
        self.setProperty("toast", "true")
        self.setFixedWidth(380)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 10, 12)
        layout.setSpacing(10)
        _bg, fg = TONES[_TOAST_TONES.get(level, "info")]
        glyph = QLabel(_TOAST_GLYPHS.get(level, "ℹ"))
        glyph.setStyleSheet(f"color: {fg}; font-size: 16px; font-weight: 700;")
        glyph.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(glyph)
        text = label(message, wrap=True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(text, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        close = tool_button("✕", tooltip=t("common.close"))
        close.clicked.connect(self.dismiss)
        col.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        if action is not None:
            act = button(action[0], variant="ghost")
            act.clicked.connect(lambda: (action[1](), self.dismiss()))
            col.addWidget(act)
        col.addStretch()
        layout.addLayout(col)
        self.setStyleSheet(f"QFrame[toast=\"true\"] {{ border-left: 3px solid {fg}; }}")

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._duration = duration_ms
        self._closing = False

    def appear(self) -> None:
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        if self._duration > 0:
            self._timer.start(self._duration)

    def enterEvent(self, event) -> None:  # noqa: N802 - üzerindeyken kapanmasın
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._duration > 0 and not self._closing:
            self._timer.start(1500)
        super().leaveEvent(event)

    def dismiss(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(lambda: self.closed.emit(self))
        self._anim.start()


class ToastManager(QWidget):
    """Ana pencerenin sağ alt köşesinde, üst üste dizilen bildirimler."""

    MAX_VISIBLE = 5

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self._toasts: list[_Toast] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        host.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._host and event.type() == event.Type.Resize:
            self._reposition()
        return False

    def _reposition(self) -> None:
        if not self._toasts:
            self.hide()
            return
        self.adjustSize()
        width = 380
        height = sum(tst.sizeHint().height() for tst in self._toasts) + 8 * (len(self._toasts) - 1)
        margin_bottom = 40
        self.setGeometry(self._host.width() - width - 20, self._host.height() - height - margin_bottom, width, height)
        self.raise_()
        self.show()

    def show_toast(
        self,
        level: str,
        message: str,
        *,
        action: tuple[str, Callable[[], None]] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if duration_ms is None:
            duration_ms = 8000 if level == "error" else 4500
        toast = _Toast(level, message, action=action, duration_ms=duration_ms)
        toast.closed.connect(self._remove)
        self._toasts.append(toast)
        self._layout.addWidget(toast)
        while len(self._toasts) > self.MAX_VISIBLE:
            self._remove(self._toasts[0])
        self._reposition()
        toast.appear()

    def _remove(self, toast: _Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._layout.removeWidget(toast)
            toast.deleteLater()
        QTimer.singleShot(0, self._reposition)


# -- onay pencereleri ---------------------------------------------------------------


def confirm(parent: QWidget, title: str, text: str, *, ok_text: str | None = None, danger: bool = False, default_no: bool = True) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    yes = box.addButton(ok_text or t("common.yes"), QMessageBox.ButtonRole.AcceptRole)
    no = box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
    if danger:
        yes.setProperty("variant", "danger")
    else:
        yes.setProperty("variant", "primary")
    box.setDefaultButton(no if default_no else yes)
    box.exec()
    return box.clickedButton() is yes


def info(parent: QWidget, title: str, text: str, *, warning: bool = False) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)
    box.addButton(t("common.ok"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


class FormDialog(QDialog):
    """Başlık + gövde + alt buton satırı olan standart diyalog iskeleti."""

    def __init__(self, title: str, parent: QWidget | None = None, *, width: int = 480, subtitle: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        head = label(title, role="h2")
        outer.addWidget(head)
        if subtitle:
            outer.addWidget(label(subtitle, role="muted", wrap=True))
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)
        self.error_label = label("", role="notice-danger", wrap=True)
        self.error_label.hide()
        outer.addWidget(self.error_label)
        self.buttons = QHBoxLayout()
        self.buttons.addStretch()
        self.cancel_button = button(t("common.cancel"), on_click=self.reject)
        self.ok_button = button(t("common.ok"), variant="primary", on_click=self._accept)
        self.ok_button.setDefault(True)
        self.buttons.addWidget(self.cancel_button)
        self.buttons.addWidget(self.ok_button)
        outer.addLayout(self.buttons)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def validate(self) -> str | None:
        """Alt sınıflar override eder: hata mesajı döndürürse diyalog kapanmaz."""
        return None

    def _accept(self) -> None:
        error = self.validate()
        if error:
            self.show_error(error)
            return
        self.accept()
