"""Karanlık tema QSS (proje-amacı.md §2.6)."""

DARK_STYLESHEET = """
QWidget {
    background-color: #1e1f22;
    color: #dcdcdc;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #1e1f22;
}
QListWidget, QTableWidget, QTreeWidget, QLineEdit, QTextEdit, QComboBox {
    background-color: #2b2d30;
    border: 1px solid #3a3d41;
    border-radius: 4px;
    padding: 4px;
}
QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #3d6bb3;
    color: #ffffff;
}
QPushButton {
    background-color: #3a3d41;
    border: 1px solid #4a4d51;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #46494e;
}
QPushButton:pressed {
    background-color: #3d6bb3;
}
QPushButton:disabled {
    color: #7a7a7a;
}
QHeaderView::section {
    background-color: #2b2d30;
    border: 1px solid #3a3d41;
    padding: 4px;
}
QSplitter::handle {
    background-color: #3a3d41;
}
QProgressBar {
    border: 1px solid #3a3d41;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3d6bb3;
}
QLabel[role="heading"] {
    font-weight: bold;
    font-size: 14px;
    padding: 4px 0;
}
"""
