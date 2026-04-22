from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt

class TimelineWidget(QWidget):
    """Widget that draws dwell/slew timeline bars."""

    def __init__(self):
        super().__init__()
        self.segments = [] # Store list of (dwell, slew) per tile

    def set_segments(self, segments):
        """Set dwell/slew data & refresh"""
        self.segments = segments
        self.update()

    def paintEvent(self, event):
        """Draw dwell (blue) and slew (red) bars."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.segments:
            painter.end()
            return

        # Compute total time for scale
        total = sum(d + s for d, s in self.segments) # Sum all dwell + slew
        if total <= 0:
            painter.end()
            return

        # Layout settings
        w = self.width()
        h = self.height()
        bar_height = max(6, h // 10)  # Height of each row bar
        y = 8  # Starting y positon

        # Light background strip
        painter.setBrush(QColor(22, 27, 34))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, y-4, w, bar_height * len(self.segments) + 6 * (len(self.segments) - 1) + 8, 4, 4)

        for dwell, slew in self.segments:
            # Convert to pixel widths
            dwell_w = int((dwell / total) * w)
            slew_w = int((slew / total) * w)

            # Draw dwell bar
            painter.setBrush(QColor(88, 166, 255))
            painter.drawRect(0, y, dwell_w, bar_height) # Draw dwell

            # Draw swell bar
            painter.setBrush(QColor(248, 81, 73))
            painter.drawRect(dwell_w, y, slew_w, bar_height) # Draw swell

            # Move down for next row
            y += bar_height + 6 # Add spacing

        painter.end()

