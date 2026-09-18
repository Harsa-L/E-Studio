"""Wizard lightweight for creating a new labelling template document."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models.template_model import LabelTemplate, Margins


class NewGabaritDialog(QDialog):
    """Create a new label workspace using an Office-like, step-by-step flow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau gabarit")
        self.resize(780, 640)
        self.setMinimumWidth(620)
        self.setObjectName("newGabaritDialog")

        self.step_cards = []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        side = QWidget(self)
        side.setMinimumWidth(200)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(10)

        title = QLabel("Créer")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        side_layout.addWidget(title)

        for index, label in enumerate(("Document", "Marges", "Référence")):
            card = QFrame(side)
            card.setFrameShape(QFrame.StyledPanel)
            card.setFrameShadow(QFrame.Raised)
            card.setProperty("active", index == 0)
            card.setStyleSheet(
                "QFrame { border: 1px solid palette(mid); border-radius: 8px; } "
                "QFrame[active=true] { border: 2px solid palette(highlight); }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_label = QLabel(f"{index + 1}. {label}")
            card_label.setWordWrap(True)
            card_layout.addWidget(card_label)
            side_layout.addWidget(card)
            self.step_cards.append(card)

        side_layout.addStretch()
        outer.addWidget(side)

        form_panel = QWidget(self)
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(12)

        header = QLabel("Nouveau gabarit d'étiquette")
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 17px; font-weight: 600;")
        form_layout.addWidget(header)

        fields = QGroupBox("Document")
        fields_layout = QFormLayout(fields)
        fields_layout.setSpacing(8)

        self.name_input = QLineEdit("Étiquette_A6_Paliers")
        self.name_input.textChanged.connect(self._refresh_summary)
        fields_layout.addRow("Nom du gabarit :", self.name_input)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10.0, 500.0)
        self.width_spin.setValue(105.0)
        self.width_spin.setSuffix(" mm")
        self.width_spin.valueChanged.connect(self._refresh_summary)
        fields_layout.addRow("Largeur :", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 500.0)
        self.height_spin.setValue(148.0)
        self.height_spin.setSuffix(" mm")
        self.height_spin.valueChanged.connect(self._refresh_summary)
        fields_layout.addRow("Hauteur :", self.height_spin)
        form_layout.addWidget(fields)

        margins_panel = QGroupBox("Marges")
        margins_layout = QFormLayout(margins_panel)
        margins_layout.setSpacing(8)

        self.margin_in_top = QDoubleSpinBox()
        self.margin_in_top.setRange(0.0, 500.0)
        self.margin_in_top.setValue(5.0)
        self.margin_in_top.valueChanged.connect(self._refresh_summary)
        self.margin_in_left = QDoubleSpinBox()
        self.margin_in_left.setRange(0.0, 500.0)
        self.margin_in_left.setValue(5.0)
        self.margin_in_left.valueChanged.connect(self._refresh_summary)
        margins_layout.addRow("Marges internes H/B (mm) :", self.margin_in_top)
        margins_layout.addRow("Marges internes G/D (mm) :", self.margin_in_left)

        self.margin_out_top = QDoubleSpinBox()
        self.margin_out_top.setRange(0.0, 500.0)
        self.margin_out_top.setValue(3.0)
        self.margin_out_top.valueChanged.connect(self._refresh_summary)
        self.margin_out_left = QDoubleSpinBox()
        self.margin_out_left.setRange(0.0, 500.0)
        self.margin_out_left.setValue(3.0)
        self.margin_out_left.valueChanged.connect(self._refresh_summary)
        margins_layout.addRow("Marges externes V (mm) :", self.margin_out_top)
        margins_layout.addRow("Marges externes H (mm) :", self.margin_out_left)
        form_layout.addWidget(margins_panel)

        reference_panel = QGroupBox("Référence visuelle")
        reference_layout = QFormLayout(reference_panel)
        reference_layout.setSpacing(8)

        self.background_path = QLineEdit()
        self.background_path.textChanged.connect(self._refresh_summary)
        browse = QPushButton("Choisir…")
        browse.clicked.connect(self._choose_background)
        reference_layout.addRow("Image de fond :", self.background_path)
        reference_layout.addRow("Sélection :", browse)

        self.background_opacity = QDoubleSpinBox()
        self.background_opacity.setRange(0.0, 1.0)
        self.background_opacity.setSingleStep(0.05)
        self.background_opacity.setValue(0.35)
        self.background_opacity.valueChanged.connect(self._refresh_summary)
        reference_layout.addRow("Opacité :", self.background_opacity)

        self.background_fit = QComboBox()
        self.background_fit.addItem("Contenir", "contain")
        self.background_fit.addItem("Couvrir", "cover")
        self.background_fit.addItem("Étirer", "stretch")
        self.background_fit.currentIndexChanged.connect(self._refresh_summary)
        reference_layout.addRow("Ajustement :", self.background_fit)
        form_layout.addWidget(reference_panel)

        summary = QGroupBox("Résumé")
        summary_layout = QFormLayout(summary)
        summary_layout.setSpacing(8)
        self.summary_name = QLabel("Étiquette_A6_Paliers")
        self.summary_size = QLabel("105 x 148 mm")
        self.summary_margins = QLabel("5 / 5 mm")
        self.summary_reference = QLabel("Aucune image")
        summary_layout.addRow("Nom :", self.summary_name)
        summary_layout.addRow("Dimensions :", self.summary_size)
        summary_layout.addRow("Marges :", self.summary_margins)
        summary_layout.addRow("Référence :", self.summary_reference)
        form_layout.addWidget(summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Créer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form_layout.addWidget(buttons)

        self._refresh_summary()
        outer.addWidget(form_panel, 1)

    def _refresh_summary(self):
        name = self.name_input.text().strip() or "Sans nom"
        width = self.width_spin.value()
        height = self.height_spin.value()
        inner = self.margin_in_top.value()
        outer = self.margin_out_top.value()
        ref = self.background_path.text().strip()
        self.summary_name.setText(name)
        self.summary_size.setText(f"{width:.1f} x {height:.1f} mm")
        self.summary_margins.setText(f"intérieur {inner:.1f} mm — extérieur {outer:.1f} mm")
        self.summary_reference.setText(ref if ref else "Aucune image")

    def _choose_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir l'image de référence",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.background_path.setText(path)

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
            ),
            background_image_path=self.background_path.text().strip() or None,
            background_image_opacity=self.background_opacity.value(),
            background_image_fit=self.background_fit.currentData(),
        )