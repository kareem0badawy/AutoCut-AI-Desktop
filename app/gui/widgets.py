from pathlib import Path

from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
)

from app.gui.theme import get_colors


class DropZone(QWidget):
    file_selected = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str,
        icon: str = "📄",
        accept_folders: bool = False,
        file_filter: str = "All Files (*)",
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon = icon
        self._accept_folders = accept_folders
        self._file_filter = file_filter
        self._selected_path = ""
        self._hovering = False

        self.setAcceptDrops(True)
        self.setMinimumHeight(130)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("drop_zone")

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self._icon_lbl = QLabel(self._icon)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")

        self._title_lbl = QLabel(self._title)
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setStyleSheet(
            f"font-weight: 600; font-size: 13px; background: transparent;"
        )

        self._sub_lbl = QLabel(self._subtitle)
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        self._sub_lbl.setWordWrap(True)
        self._sub_lbl.setStyleSheet(
            f"font-size: 11px; background: transparent;"
        )

        self._file_lbl = QLabel("")
        self._file_lbl.setAlignment(Qt.AlignCenter)
        self._file_lbl.setWordWrap(True)
        self._file_lbl.setVisible(False)
        self._file_lbl.setStyleSheet("font-size: 11px; font-weight: 600; background: transparent;")

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._title_lbl)
        layout.addWidget(self._sub_lbl)
        layout.addWidget(self._file_lbl)

        self._apply_style()

    def _apply_style(self):
        C = get_colors()
        if self._selected_path:
            self.setObjectName("drop_zone_filled")
            self._title_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['success']}; background: transparent;")
            self._sub_lbl.setStyleSheet(f"font-size: 11px; color: {C['text_sec']}; background: transparent;")
            self._icon_lbl.setStyleSheet(f"font-size: 28px; background: transparent;")
        elif self._hovering:
            self.setObjectName("drop_zone_hover")
            self._title_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['accent_hover']}; background: transparent;")
            self._sub_lbl.setStyleSheet(f"font-size: 11px; color: {C['text_sec']}; background: transparent;")
        else:
            self.setObjectName("drop_zone")
            self._title_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['text']}; background: transparent;")
            self._sub_lbl.setStyleSheet(f"font-size: 11px; color: {C['text_dim']}; background: transparent;")

        self.style().unpolish(self)
        self.style().polish(self)

    def set_path(self, path: str):
        self._selected_path = path
        if path:
            p = Path(path)
            name = p.name if p.name else path
            self._file_lbl.setText(name)
            self._file_lbl.setVisible(True)
            self._sub_lbl.setVisible(False)
            self._icon_lbl.setText("✅")
        else:
            self._file_lbl.setVisible(False)
            self._sub_lbl.setVisible(True)
            self._icon_lbl.setText(self._icon)
        self._apply_style()

    def get_path(self) -> str:
        return self._selected_path

    def retranslate(self, title: str, subtitle: str):
        self._title = title
        self._subtitle = subtitle
        self._title_lbl.setText(title)
        if not self._selected_path:
            self._sub_lbl.setText(subtitle)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._browse()

    def _browse(self):
        if self._accept_folders:
            path = QFileDialog.getExistingDirectory(self, self._title, str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._title, str(Path.home()), self._file_filter)
        if path:
            self.set_path(path)
            self.file_selected.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self._hovering = True
            self._apply_style()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._hovering = False
        self._apply_style()

    def dropEvent(self, event: QDropEvent):
        self._hovering = False
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_path(path)
            self.file_selected.emit(path)
        self._apply_style()


def make_separator(C: dict, vertical: bool = False) -> QWidget:
    sep = QWidget()
    if vertical:
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {C['border']};")
    else:
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C['border']};")
    return sep


def make_badge(text: str, kind: str = "default", C: dict = None) -> QLabel:
    if C is None:
        C = get_colors()
    colors = {
        "success": (C['success_bg'], C['success']),
        "error":   (C['error_bg'],   C['error']),
        "warning": (C['warning_bg'], C['warning']),
        "accent":  (C['surface3'],   C['accent_hover']),
        "default": (C['surface2'],   C['text_sec']),
    }
    bg, fg = colors.get(kind, colors["default"])
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background: {bg}; color: {fg}; border-radius: 5px; "
        f"padding: 2px 8px; font-size: 11px; font-weight: 600;"
    )
    return lbl
