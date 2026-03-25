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


def _install_exception_hook(log):
    import traceback
    from PySide6.QtWidgets import QMessageBox

    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical(f"UNHANDLED EXCEPTION:\n{msg}")
        try:
            box = QMessageBox()
            box.setWindowTitle("AutoCut — خطأ")
            box.setIcon(QMessageBox.Critical)
            box.setText("حدث خطأ غير متوقع. تم حفظ التفاصيل في autocut.log")
            box.setDetailedText(msg)
            box.exec()
        except Exception:
            pass

    sys.excepthook = handle_exception


def main():
    from app.logger import logger
    logger.info("=" * 60)
    logger.info("AutoCut starting up")
    logger.info(f"Python {sys.version}")
    logger.info(f"Platform: {sys.platform}")

    if sys.platform == "linux":
        _setup_linux()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from app.gui.main_window import MainWindow

    _install_exception_hook(logger)

    app = QApplication(sys.argv)

    # Load Cairo Bold from bundled assets
    import os
    from PySide6.QtGui import QFontDatabase
    _font_path = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Cairo-Bold.ttf")
    if os.path.exists(_font_path):
        _fid = QFontDatabase.addApplicationFont(_font_path)
        if _fid >= 0:
            _families = QFontDatabase.applicationFontFamilies(_fid)
            logger.info(f"Cairo font loaded — families: {_families}")
            app.setFont(QFont("Cairo", 11, QFont.Bold))
        else:
            logger.warning("Cairo font file found but failed to load — using fallback")
            app.setFont(QFont("Segoe UI", 11))
    else:
        logger.warning(f"Cairo font not found at {_font_path} — using fallback")
        app.setFont(QFont("Segoe UI", 11))

    logger.info("Creating main window...")
    try:
        window = MainWindow()
        window.show()
        logger.info("Main window shown — entering event loop")
        code = app.exec()
        logger.info(f"Event loop exited with code {code}")
        sys.exit(code)
    except Exception as e:
        import traceback
        logger.critical(f"Fatal error during startup:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
