from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDoubleSpinBox,
    QHBoxLayout
)
from PySide6.QtCore import Signal, Qt

class TelescopeDialog(QDialog):
    """Modal dialog for entering telescope settings."""

    # Emit dict with telescope data
    telescope_saved = Signal(dict) # save to file
    telescope_applied = Signal() # apply to active

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Telescope Settings")
        self.setModal(True)  # Block main window until dialog is closed
        self._build_ui()

    def _build_ui(self):
        """Build telescope input panel layout."""

        layout = QVBoxLayout(self) # Main vertical layout

        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        # Name
        self.name_label = QLabel("Name")
        self.name_input = QLineEdit() # Text box
        self.name_input.setPlaceholderText("e.g. LIGO, ZTF, Custom")
        form.addWidget(self.name_label, 0, 0)
        form.addWidget(self.name_input, 0, 1)

        # Slew speed
        self.slew_speed_label = QLabel("Slew Speed (°/s)")
        self.speed_input = QDoubleSpinBox()
        self.speed_input.setRange(0.01, 10000)
        self.speed_input.setDecimals(3)
        self.speed_input.setSuffix(" deg/s")
        self.speed_input.setValue(5.0)
        form.addWidget(self.slew_speed_label, 1, 0)
        form.addWidget(self.speed_input, 1, 1)

        # Dwell time
        self.dwell_time_label = QLabel("Dwell Time (s)")
        self.dwell_time_input = QDoubleSpinBox()
        self.dwell_time_input.setRange(0.01, 100000)
        self.dwell_time_input.setDecimals(1)
        self.dwell_time_input.setSuffix(" s")
        self.dwell_time_input.setValue(60.0)
        form.addWidget(self.dwell_time_label, 2, 0)
        form.addWidget(self.dwell_time_input, 2, 1)

        layout.addLayout(form)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_button)

        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(self._on_apply)
        btn_row.addWidget(self.apply_button)

        layout.addLayout(btn_row)

    def _on_save(self):
        """Emit telescope data for saving to file."""
        data = {
            "name": self.name_input.text().strip(),
            "slew_speed": float(self.speed_input.value()), # didn't add strip() as float already ignores surrounding spaces
            "dwell_time": float(self.dwell_time_input.value()),
        }
        self.telescope_saved.emit(data) # Emit save request

    def _on_apply(self):
        """Emit apply request without changing telescope fields."""
        self.telescope_applied.emit()









