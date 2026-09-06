"""Inspecteur latéral dynamique gérant mono et multi-sélection."""

from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, 
    QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QLabel, QScrollArea,
    QComboBox, QPushButton, QColorDialog
)
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor

from label_items import BaseLabelItem
from item_properties import PropertySpec, MULTIPLE_VALUES_INDICATOR
from domain_fields import DOMAIN_FIELDS


class PropertyInspectorWidget(QWidget):
    """Panneau de propriétés réactif et universel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(290)
        self.selected_items: List[BaseLabelItem] = []
        self._is_updating = False

        self.main_layout = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)

        self.empty_label = QLabel("Aucun élément sélectionné.")
        self.empty_label.setAlignment(Qt.AlignCenter)

        self.main_layout.addWidget(self.empty_label)
        self.main_layout.addWidget(self.scroll)
        self.scroll.hide()

    def set_selected_items(self, items: List[BaseLabelItem]):
        for item in self.selected_items:
            try: item.item_changed.disconnect(self.refresh_values)
            except RuntimeError: pass

        self.selected_items = items

        for item in self.selected_items:
            item.item_changed.connect(self.refresh_values)

        if not items:
            self.scroll.hide()
            self.empty_label.show()
            return

        self.empty_label.hide()
        self.scroll.show()
        self._rebuild_ui()

    def _get_common_properties(self) -> List[PropertySpec]:
        if not self.selected_items: return []
        first_props = {p.key: p for p in self.selected_items[0].get_properties()}
        common_keys = set(first_props.keys())

        for item in self.selected_items[1:]:
            common_keys.intersection_update({p.key for p in item.get_properties()})

        return [first_props[k] for k in first_props if k in common_keys]

    def _rebuild_ui(self):
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        common_props = self._get_common_properties()
        categories: Dict[str, List[PropertySpec]] = {}
        for prop in common_props:
            categories.setdefault(prop.category, []).append(prop)

        for cat_name, props in categories.items():
            title = f"{cat_name} ({len(self.selected_items)})" if len(self.selected_items) > 1 else cat_name
            group_box = QGroupBox(title)
            group_layout = QFormLayout(group_box)

            for prop in props:
                widget = self._create_widget(prop)
                widget._property_spec = prop
                group_layout.addRow(f"{prop.label} :", widget)

            self.container_layout.addWidget(group_box)

        self.container_layout.addStretch()
        self.refresh_values()

    def _create_widget(self, prop: PropertySpec) -> QWidget:
        if prop.type_name == "float":
            spin = QDoubleSpinBox()
            spin.setRange(prop.min_val or -9999, prop.max_val or 9999)
            spin.setSuffix(prop.suffix)
            spin.setDecimals(2)
            spin.valueChanged.connect(lambda val, p=prop: self._apply_val(p, val))
            return spin
        elif prop.type_name == "int":
            spin = QSpinBox()
            spin.setRange(int(prop.min_val or -9999), int(prop.max_val or 9999))
            spin.valueChanged.connect(lambda val, p=prop: self._apply_val(p, val))
            return spin
        elif prop.type_name == "bool":
            check = QCheckBox()
            check.toggled.connect(lambda val, p=prop: self._apply_val(p, val))
            return check
        elif prop.key == "domain_field":
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItem("Personnalisé", "")
            for field in DOMAIN_FIELDS:
                combo.addItem(f"{field.label} ({field.key.value})", field.key.value)
            combo.currentTextChanged.connect(lambda _text, p=prop, c=combo: self._apply_val(p, c.currentData() or c.currentText()))
            return combo
        elif prop.key in {"valign", "overflow", "barcode_type"}:
            combo = QComboBox()
            values = {
                "valign": ("TOP", "MIDDLE", "BOTTOM"),
                "overflow": ("CLIP", "VISIBLE", "AUTOFIT_SHRINK", "AUTOFIT_GROW"),
                "barcode_type": ("code128", "ean13"),
            }[prop.key]
            combo.addItems(values)
            combo.currentTextChanged.connect(lambda val, p=prop: self._apply_val(p, val))
            return combo
        elif "color" in prop.key:
            button = QPushButton()
            button.setToolTip("Choisir une couleur")
            button.clicked.connect(lambda checked=False, p=prop, b=button: self._choose_color(p, b))
            return button
        else:
            line = QLineEdit()
            line.textChanged.connect(lambda val, p=prop: self._apply_val(p, val))
            return line

    def _choose_color(self, prop: PropertySpec, button: QPushButton):
        color = QColorDialog.getColor(QColor(prop.getter()), self, prop.label)
        if color.isValid():
            value = color.name(QColor.HexArgb) if color.alpha() < 255 else color.name()
            prop.setter(value)
            button.setStyleSheet(f"background-color: {value};")

    @staticmethod
    def _set_color_button(button: QPushButton, value: Any):
        color = QColor(str(value))
        button.setStyleSheet(f"background-color: {color.name(QColor.HexArgb)};" if color.isValid() else "")

    def _apply_val(self, prop: PropertySpec, val: Any):
        if self._is_updating or not self.selected_items: return
        for item in self.selected_items:
            props_map = {p.key: p for p in item.get_properties()}
            if prop.key in props_map:
                props_map[prop.key].setter(val)

    def refresh_values(self):
        if self._is_updating or not self.selected_items: return
        self._is_updating = True

        for i in range(self.container_layout.count()):
            group = self.container_layout.itemAt(i).widget()
            if isinstance(group, QGroupBox):
                form = group.layout()
                for row in range(form.rowCount()):
                    widget = form.itemAt(row, QFormLayout.FieldRole).widget()
                    prop_spec = widget._property_spec

                    vals = [p[prop_spec.key].getter() for item in self.selected_items 
                            for p in [{sp.key: sp for sp in item.get_properties()}]]
                    is_identical = len(set(vals)) == 1
                    v = vals[0] if is_identical else MULTIPLE_VALUES_INDICATOR

                    blocker = QSignalBlocker(widget)
                    if isinstance(widget, QDoubleSpinBox) and is_identical: widget.setValue(float(v))
                    elif isinstance(widget, QSpinBox) and is_identical: widget.setValue(int(v))
                    elif isinstance(widget, QCheckBox) and is_identical: widget.setChecked(bool(v))
                    elif isinstance(widget, QComboBox) and is_identical:
                        if prop_spec.key == "domain_field":
                            index = widget.findData(str(v))
                            if index >= 0:
                                widget.setCurrentIndex(index)
                            else:
                                widget.setEditText(str(v))
                        else:
                            widget.setCurrentText(str(v))
                    elif isinstance(widget, QPushButton) and is_identical:
                        self._set_color_button(widget, v)
                    elif isinstance(widget, QLineEdit):
                        widget.setPlaceholderText("" if is_identical else MULTIPLE_VALUES_INDICATOR)
                        widget.setText(str(v) if is_identical else "")

                    if isinstance(widget, (QDoubleSpinBox, QSpinBox, QCheckBox)):
                        widget.setToolTip("Valeurs multiples" if not is_identical else "")

        self._is_updating = False