"""
Minimal startup splash: dark panel, app title, tagline, static sky-map motif, progress bar.

Shown while the main window is constructed; closes automatically afterward (with a short
minimum visible time so the splash does not flash). No audio.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QElapsedTimer, Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPaintEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

# Strings aligned with ``MainWindow.setWindowTitle`` / product wording.
APP_TITLE = "GW Follow-up Telescope Scheduler"
TAGLINE = "Gravitational-wave follow-up scheduling"

# Minimum time the splash stays up when ``MainWindow()`` finishes quickly (warm cache).
_MIN_VISIBLE_MS = 1200


class HealpixMotifWidget(QWidget):
    """
    Small static graphic: disk limb, latitude arcs, meridian curves, and a coarse
    HEALPix-like band of quadrilateral “pixels” (simplified, not astronomically exact).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(168, 168)

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        cx, cy = w * 0.5, h * 0.5
        r = min(w, h) * 0.42

        line = QColor(58, 68, 92, 200)
        faint = QColor(45, 54, 72, 140)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(line, 1.0))
        painter.drawEllipse(QRectF(cx - r, cy - r, 2.0 * r, 2.0 * r))

        painter.setPen(QPen(faint, 0.8))
        for i in range(-2, 3):
            dy = (i / 2.5) * r * 0.85
            rw = math.sqrt(max(0.0, r * r - dy * dy))
            painter.drawArc(
                QRectF(cx - rw, cy + dy - rw * 0.25, 2.0 * rw, rw * 0.5),
                0,
                180 * 16,
            )

        painter.setPen(QPen(faint, 0.8))
        for i in range(-3, 4):
            dx = (i / 3.5) * r * 0.9
            rh = math.sqrt(max(0.0, r * r - dx * dx))
            painter.drawEllipse(
                QRectF(cx + dx - rh * 0.06, cy - rh, rh * 0.12, 2.0 * rh)
            )

        # HEALPix-style hint: a row of small equal-ish quadrilateral facets along the equator.
        pix = QColor(72, 90, 120, 150)
        painter.setPen(QPen(pix, 0.85))
        n = 8
        band_half = r * 0.22
        for k in range(n):
            u0, u1 = k / n, (k + 1) / n
            a0 = math.pi * (0.2 + u0 * 0.6)
            a1 = math.pi * (0.2 + u1 * 0.6)
            xa, xb = math.cos(a0) * r * 0.82, math.cos(a1) * r * 0.82
            ya, yb = math.sin(a0) * r * 0.82, math.sin(a1) * r * 0.82
            painter.drawLine(
                int(cx + xa), int(cy + ya - band_half),
                int(cx + xb), int(cy + yb - band_half),
            )
            painter.drawLine(
                int(cx + xa), int(cy + ya + band_half),
                int(cx + xb), int(cy + yb + band_half),
            )
        for k in range(n + 1):
            u = k / n
            a = math.pi * (0.2 + u * 0.6)
            xe, ye = math.cos(a) * r * 0.82, math.sin(a) * r * 0.82
            painter.drawLine(
                int(cx + xe), int(cy + ye - band_half),
                int(cx + xe), int(cy + ye + band_half),
            )


class MinimalSplashScreen(QDialog):
    """
    Frameless, border-styled dialog: title, tagline, motif, indeterminate progress.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setFixedSize(440, 300)

        self.setStyleSheet(
            """
            QDialog#MinimalSplash {
                background-color: #12141b;
                border: 1px solid #2a3142;
                border-radius: 6px;
            }
            QLabel#splashTitle {
                color: #e8eaef;
                font-size: 19px;
                font-weight: 600;
            }
            QLabel#splashTagline {
                color: #8f97a8;
                font-size: 12px;
            }
            QProgressBar {
                border: none;
                border-radius: 2px;
                background-color: #1c1f2a;
                min-height: 5px;
                max-height: 5px;
            }
            QProgressBar::chunk {
                background-color: #5b7fc7;
                border-radius: 2px;
            }
            """
        )
        self.setObjectName("MinimalSplash")

        self._title_label = QLabel(APP_TITLE)
        self._title_label.setObjectName("splashTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._tagline_label = QLabel(TAGLINE)
        self._tagline_label.setObjectName("splashTagline")
        self._tagline_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._motif = HealpixMotifWidget(self)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 28)
        layout.setSpacing(14)
        layout.addStretch(1)
        layout.addWidget(self._motif, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._title_label)
        layout.addWidget(self._tagline_label)
        layout.addSpacing(8)
        layout.addWidget(self._progress)
        layout.addStretch(1)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is not None:
            ag = screen.availableGeometry()
            g = self.frameGeometry()
            g.moveCenter(ag.center())
            self.setGeometry(g)


def show_splash_then_main(main_window_factory: Callable[[], QWidget]) -> None:
    """
    Show the splash, construct the main window on the next event-loop tick, then close.

    Keeps the splash visible for at least ``_MIN_VISIBLE_MS`` so it does not flicker when
    ``MainWindow()`` returns quickly.

    Args:
        main_window_factory: Zero-argument callable that returns the primary window widget.
    """
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication must exist before show_splash_then_main().")

    splash = MinimalSplashScreen()
    splash.show()
    app.processEvents() # Processes pending paint events so the splash appears on screen

    def load_and_reveal() -> None:
        """Constructs the heavy main window and without it,
        the splash and the main window construction would happen in the same event loop cycle,
        and the splash wouldn't get a chance to paint before the UI thread got locked up building VTK widgets"""

        timer = QElapsedTimer()
        timer.start()
        win = main_window_factory()
        elapsed = timer.elapsed()
        wait_ms = max(0, _MIN_VISIBLE_MS - elapsed)

        def reveal() -> None:
            splash.close()
            splash.deleteLater()
            win.show()

        if wait_ms > 0:
            QTimer.singleShot(wait_ms, reveal)
        else:
            reveal()

    QTimer.singleShot(0, load_and_reveal)
