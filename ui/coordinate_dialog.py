"""Dialog for converting between RA/Dec, Cartesian x,y,z, and Galactic longitude/latitude."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QFormLayout, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from models.coordinates import (
    ra_dec_to_xyz,
    xyz_to_ra_dec,
    # ra_dec_to_galactic,
    # galactic_to_ra_dec,
)


class CoordinateDialog(QDialog):
    """Convert between RA/Dec (degrees) and unit-sphere x,y,z."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coordinate conversion")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        # RA/Dec -> XYZ
        g_radec = QGroupBox("RA/Dec → XYZ (unit sphere)")
        fl_radec = QFormLayout(g_radec)
        self.ra_spin = QDoubleSpinBox()
        self.ra_spin.setRange(-360, 720)
        self.ra_spin.setDecimals(4)
        self.ra_spin.setValue(0)
        self.dec_spin = QDoubleSpinBox()
        self.dec_spin.setRange(-90, 90)
        self.dec_spin.setDecimals(4)
        self.dec_spin.setValue(45)
        fl_radec.addRow("RA (°):", self.ra_spin)
        fl_radec.addRow("Dec (°):", self.dec_spin)
        self.xyz_result = QLineEdit()
        self.xyz_result.setReadOnly(True)
        self.xyz_result.setPlaceholderText("x, y, z")
        fl_radec.addRow("XYZ:", self.xyz_result)
        btn_radec = QPushButton("Convert")
        btn_radec.clicked.connect(self._convert_radec_to_xyz)
        fl_radec.addRow("", btn_radec)
        layout.addWidget(g_radec)

        # XYZ -> RA/Dec
        g_xyz = QGroupBox("XYZ → RA/Dec (unit sphere)")
        fl_xyz = QFormLayout(g_xyz)
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-2, 2)
        self.x_spin.setDecimals(4)
        self.x_spin.setValue(0.7071)
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-2, 2)
        self.y_spin.setDecimals(4)
        self.y_spin.setValue(0)
        self.z_spin = QDoubleSpinBox()
        self.z_spin.setRange(-2, 2)
        self.z_spin.setDecimals(4)
        self.z_spin.setValue(0.7071)
        fl_xyz.addRow("x:", self.x_spin)
        fl_xyz.addRow("y:", self.y_spin)
        fl_xyz.addRow("z:", self.z_spin)
        self.radec_result = QLineEdit()
        self.radec_result.setReadOnly(True)
        self.radec_result.setPlaceholderText("RA (°), Dec (°)")
        fl_xyz.addRow("RA, Dec:", self.radec_result)
        btn_xyz = QPushButton("Convert")
        btn_xyz.clicked.connect(self._convert_xyz_to_radec)
        fl_xyz.addRow("", btn_xyz)
        layout.addWidget(g_xyz)


    def _convert_radec_to_xyz(self):
        ra = self.ra_spin.value()
        dec = self.dec_spin.value()
        x, y, z = ra_dec_to_xyz(ra, dec)
        self.xyz_result.setText(f"{x:.6f}, {y:.6f}, {z:.6f}")

    def _convert_xyz_to_radec(self):
        x = self.x_spin.value()
        y = self.y_spin.value()
        z = self.z_spin.value()
        ra, dec = xyz_to_ra_dec(x, y, z)
        self.radec_result.setText(f"RA={ra:.4f}°, Dec={dec:.4f}°")

    # def _convert_radec_to_galactic(self):
    #     ra = self.ra_gal_in.value()
    #     dec = self.dec_gal_in.value()
    #     l_deg, b_deg = ra_dec_to_galactic(ra, dec)
    #     self.longlat_result.setText(f"Long={l_deg:.4f}°, Lat={b_deg:.4f}°")
    #
    # def _convert_galactic_to_radec(self):
    #     l_deg = self.long_in.value()
    #     b_deg = self.lat_in.value()
    #     ra, dec = galactic_to_ra_dec(l_deg, b_deg)
    #     self.radec_gal_result.setText(f"RA={ra:.4f}°, Dec={dec:.4f}°")
