import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.splash_screen import show_splash_then_main


def main() -> None:
    """
    Qt entry point: apply stylesheet, show the minimal loading splash while the main
    window is constructed, then run the event loop.
    """

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    with open("ui/theme.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    show_splash_then_main(lambda: MainWindow())

    if not app.property("_event_loop_running"):
        app.setProperty("_event_loop_running", True)
        sys.exit(app.exec())
