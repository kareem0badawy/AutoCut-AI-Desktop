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


def _install_exception_hook(app):
    import traceback
    from PySide6.QtWidgets import QMessageBox

    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[AutoCut UNHANDLED] {msg}")
        try:
            box = QMessageBox()
            box.setWindowTitle("AutoCut — خطأ غير متوقع")
            box.setIcon(QMessageBox.Critical)
            box.setText("حدث خطأ غير متوقع. البرنامج سيستمر في العمل.")
            box.setDetailedText(msg)
            box.exec()
        except Exception:
            pass

    sys.excepthook = handle_exception


def main():
    if sys.platform == "linux":
        _setup_linux()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from app.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    _install_exception_hook(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
