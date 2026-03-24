import sys
import os
import ctypes

XCB_CURSOR_PATH = "/nix/store/92nrp8f5bcyxy57w30wxj5ncvygz1wnx-xcb-util-cursor-0.1.5/lib/libxcb-cursor.so.0"


def _setup_linux():
    if os.path.exists(XCB_CURSOR_PATH):
        try:
            ctypes.CDLL(XCB_CURSOR_PATH)
        except OSError:
            pass
    lib_dir = os.path.dirname(XCB_CURSOR_PATH)
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    paths = [lib_dir] + [p for p in existing.split(":") if p]
    os.environ["LD_LIBRARY_PATH"] = ":".join(paths)
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"
    os.environ["QT_XCB_NO_XI2"] = "1"


def main():
    if sys.platform == "linux":
        _setup_linux()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from app.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
