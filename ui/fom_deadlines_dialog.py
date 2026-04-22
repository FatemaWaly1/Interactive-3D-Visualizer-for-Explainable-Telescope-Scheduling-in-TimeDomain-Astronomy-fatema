"""Dialog: enter deadlines in one place, see FoM details in the same window after OK."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QFrame,
)
from PySide6.QtCore import Signal
import math


class FoMDeadlinesDialog(QDialog):
    """
    Single window: type deadlines, then see Expected FoM and
    the table (deadlines row + M_i row)  below.
    """

    deadlines_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculate expected Figure of Merit")
        self.resize(520, 380)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Input section
        self.prompt_label = QLabel(
            "Enter deadlines in seconds (comma-separated, e.g. 100, 200, 300):"
        )
        layout.addWidget(self.prompt_label)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("100, 200, 300")
        layout.addWidget(self.line_edit)

        btn_row = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        # Error message (hidden until set_error)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # --- Separator and results section (hidden until set_fom_results) ---
        self.results_frame = QFrame()
        self.results_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(self.results_frame)

        self.summary_label = QLabel("Expected FoM: —")
        self.summary_label.setStyleSheet("font-weight: bold;")
        results_layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setRowCount(2)
        self.table.setVerticalHeaderLabels(["Deadline (s)", "Mᵢ"])
        results_layout.addWidget(self.table)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        results_layout.addWidget(self.close_btn)

        layout.addWidget(self.results_frame)
        # Show the FoM details section immediately so the dialog always
        # looks like the “second picture”; it will be populated once
        # a valid FoM has been computed.
        self.results_frame.setVisible(True)

    def _on_ok(self):
        text = self.line_edit.text().strip()
        self.error_label.setVisible(False)
        self.deadlines_submitted.emit(text)

    def set_error(self, msg: str) -> None:
        """Show an error message in the dialog (e.g. validation failed)."""
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def set_fom_results(
        self,
        deadlines: list[float],
        merits: list[float],
        fom_value: float,
    ) -> None:
        """Show Expected FoM and the deadlines/M_i table in the same window."""
        self.error_label.setVisible(False)
        self.summary_label.setText(f"Expected FoM: {fom_value:.3f}")
        self.summary_label.setStyleSheet("color: #58a6ff;")

        self.table.setColumnCount(len(deadlines))
        self.table.setHorizontalHeaderLabels([str(i + 1) for i in range(len(deadlines))])
        for col, (d, m) in enumerate(zip(deadlines, merits)):
            d_str = "∞" if math.isinf(d) else f"{d:.1f}"
            self.table.setItem(0, col, QTableWidgetItem(d_str))
            self.table.setItem(1, col, QTableWidgetItem(f"{m:.3f}"))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.results_frame.setVisible(True)
