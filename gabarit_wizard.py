"""Wizard / Dialogue obligatoire avant toute instanciation de Canvas."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, 
    QDialogButtonBox, QVBoxLayout, QGroupBox
)
from template_model import LabelTemplate, Margins


class NewGabaritDialog(QDialog):
    """Dialogue File -> New -> New Gabarit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau Gabarit d'Étiquette")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit("Étiquette_A6_Paliers")
        form_layout.addRow("Nom du Gabarit :", self.name_input)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10.0, 500.0)
        self.width_spin.setValue(105.0)
        self.width_spin.setSuffix(" mm")

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 500.0)
        self.height_spin.setValue(148.0)
        self.height_spin.setSuffix(" mm")

        form_layout.addRow("Largeur :", self.width_spin)
        form_layout.addRow("Hauteur :", self.height_spin)

        # Marges Internes
        inner_group = QGroupBox("Marges Internes (Limite Objets)")
        inner_layout = QFormLayout(inner_group)
        self.margin_in_top = QDoubleSpinBox()
        self.margin_in_top.setValue(5.0)
        self.margin_in_left = QDoubleSpinBox()
        self.margin_in_left.setValue(5.0)
        inner_layout.addRow("Haut/Bas (mm) :", self.margin_in_top)
        inner_layout.addRow("Gauche/Droite (mm) :", self.margin_in_left)

        # Marges Externes
        outer_group = QGroupBox("Marges Externes (Débordement / Coupe)")
        outer_layout = QFormLayout(outer_group)
        self.margin_out_top = QDoubleSpinBox()
        self.margin_out_top.setValue(3.0)
        self.margin_out_left = QDoubleSpinBox()
        self.margin_out_left.setValue(3.0)
        outer_layout.addRow("Débord V (mm) :", self.margin_out_top)
        outer_layout.addRow("Débord H (mm) :", self.margin_out_left)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(inner_group)
        main_layout.addWidget(outer_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def get_template(self) -> LabelTemplate:
        return LabelTemplate(
            name=self.name_input.text(),
            width_mm=self.width_spin.value(),
            height_mm=self.height_spin.value(),
            inner_margins_mm=Margins(
                top=self.margin_in_top.value(),
                bottom=self.margin_in_top.value(),
                left=self.margin_in_left.value(),
                right=self.margin_in_left.value()
            ),
            outer_margins_mm=Margins(
                top=self.margin_out_top.value(),
                bottom=self.margin_out_top.value(),
                left=self.margin_out_left.value(),
                right=self.margin_out_left.value()
            )
        )