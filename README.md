# E-Studio

E-Studio is a PySide6 desktop application for designing and generating printable
price labels. It provides two routes: a Home screen for gabarit discovery and
an editor, and a protected Generation workspace for importing data, previewing,
validating, exporting, and printing labels.

## Features

- Create label templates with millimetre dimensions and inner/outer margins.
- Add tier-price blocks and rich objects from the **Insérer** menu.
- Move, resize, select, and edit objects through the property inspector.
- Render rich text with formatting, alignment, wrapping, and overflow handling.
- Insert images, QR codes, barcodes, lines, shapes, and ellipses.
- Bind fields through canonical domain keys or custom dynamic keys.
- Use non-printing background reference images while designing gabarits.
- Import Excel data, edit rows, reconstruct tiers, and review diagnostics.
- Export PNG/PDF, compose imposed sheets, and print through the system printer.

## Requirements

- Python 3.10 or newer
- PySide6 6.6 or newer
- `qrcode` 7.4 or newer
- `python-barcode` 0.15 or newer
- `openpyxl` 3.1 or newer

Install the dependencies from [requirements.txt](requirements.txt):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Starting The Application

The supported entry point is [app.py](app.py):

```bash
.venv/bin/python app.py
```

The application opens the Home screen. Choose an existing gabarit to edit or
generate labels, or create a new gabarit. Generation uses an immutable copy of
the selected gabarit; editing it happens in a separate window.

### Typical workflow

1. Create or select a gabarit from Home.
2. Design the gabarit and optionally add a non-printing reference image.
3. Save the gabarit, then choose **Générer des étiquettes**.
4. Import Excel, confirm mappings and the article grouping key, and resolve tier conflicts.
5. Correct source rows manually and review preflight diagnostics.
6. Preview rows, export PNG/PDF, or print through the system printer.

Excel import supports `.xlsx` and `.xlsm`. Formula cells use cached values, and
legacy `.xls`/`.xlsb` files must be converted first. Binding profiles and output
manifests can be saved for repeatable generation.

- Python 3.10 or newer
- PySide6 6.6 or newer
- `qrcode` 7.4 or newer
- `python-barcode` 0.15 or newer

Install the dependencies from [requirements.txt](requirements.txt):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Linux, the Qt runtime also needs access to its graphical libraries. A
headless CI or container may require additional system packages such as
`libGL.so.1` before the desktop application can start.

## Starting The Editor

The supported entry point is [app.py](app.py):

```bash
.venv/bin/python app.py
```

The application opens a main window with a graphics view and a property
inspector dock. Use **Fichier > Nouveau Gabarit** to define a label before
adding objects.

### Typical workflow

1. Create a template and specify its width, height, inner margins, and outer
   margins in millimetres.
2. Add a tier-price block or a rich object from **Insérer**.
3. Select an object and edit its geometry and appearance in the inspector.
4. Use **Contrôler Dépassements** to find objects outside the printable area.
5. Save the JSON template with **Fichier > Sauvegarder JSON**.
6. Load optional preview data with **Fichier > Charger données d'aperçu**.
7. Export the label with **Fichier > Exporter PNG**.

## Template Documents

Templates are represented by `LabelTemplate` in
[template_model.py](template_model.py). A document contains:

- `schema_version`: currently `1`.
- `name`: a non-empty template name.
- `width_mm` and `height_mm`: physical label dimensions.
- `inner_margins_mm`: the printable-area boundary used for validation.
- `outer_margins_mm`: the bleed or cutting boundary displayed around the label.
- `bg_color` and `bg_opacity`: label background settings.
- `items`: serialized canvas objects.

Example:

```json
{
  "schema_version": 1,
  "name": "Shelf label",
  "width_mm": 100.0,
  "height_mm": 50.0,
  "inner_margins_mm": {
    "top": 2.0,
    "bottom": 2.0,
    "left": 2.0,
    "right": 2.0
  },
  "outer_margins_mm": {
    "top": 1.0,
    "bottom": 1.0,
    "left": 1.0,
    "right": 1.0
  },
  "bg_color": "#FFFFFF",
  "bg_opacity": 1.0,
  "items": []
}
```

`LabelTemplate.validate()` rejects empty names, non-positive dimensions,
negative margins, margins that remove the printable area, and invalid opacity.
JSON loading validates the schema version and reconstructs margin value
objects. Unsupported item records are skipped by the canvas loader so a
partially damaged document can still be opened and repaired.

## Canvas Items And Rendering

[label_items.py](label_items.py) contains the Qt scene-item layer:

- `BaseLabelItem` provides millimetre geometry, selection, movement, resizing,
  property definitions, and basic serialization.
- `TierPriceLabelItem` displays a configured price tier and serializes its
  tier, prefix, unit, and strictness settings.
- `RichLabelItem` adapts reusable render objects into editable Qt scene items.
- `HazardWarningOverlay` marks objects outside the printable area.

[render_items.py](render_items.py) contains the reusable rendering layer:

- `BaseItem` defines the render and data-binding contract.
- `ShapeItem` and `TextItem` render basic shapes and rich text.
- `ImageItem`, `QRCodeItem`, and `BarcodeItem` render external or generated
  media.
- `LineItem` and `EllipseItem` provide additional geometric primitives.
- `ItemFactory` registers the supported render types.

The render layer does not manage selection or Qt scene ownership. This keeps
objects reusable for both the interactive editor and batch rendering.

## Data Binding And Preview

Bindings use a flat JSON object whose keys match an object's **Clé de données**.
For example:

```json
{
  "ITEMNAME": "Café 250 g",
  "PRODUCT_SCAN": "123456789012",
  "IMAGE_PATH": "/data/products/coffee.png"
}
```

A text object bound to `ITEMNAME` displays the product name during export. A
barcode bound to `PRODUCT_SCAN` renders the supplied scan code. An image bound
to `IMAGE_PATH` loads the referenced image.

Preview data is applied to temporary copies during rendering. It does not
mutate the editor item or the saved template.

## Product And Price Models

[article_models.py](article_models.py) defines typed product and pricing data:

- `ProductIdent` identifies the product and scan code.
- `HierarchyInfo` stores commercial hierarchy fields.
- `PackagingInfo` stores selling and case units.
- `TaxInfo` calculates tax amounts.
- `PricingInfo` calculates promotional, effective, discount, and display prices.
- `BaseArticle` produces a flat binding context for label objects.

[article_types.py](article_types.py) provides specialized articles such as
`WeightedArticle` and `BulkCaseArticle`.

[tier_engine.py](tier_engine.py) resolves a configured tier by priority. It can
try fallback tiers, fall back to the standard selling price, return an empty
result for an optional tier, or raise `CancelLabelGenerationException` when a
strict tier is unavailable.

## Units And Batch Rendering

[units.py](units.py) defines `Unit` and `Length`. `Length` provides explicit
conversion between pixels, millimetres, and points using a configurable DPI.

[label_renderer.py](label_renderer.py) contains `BatchRenderer`, which renders
deep copies of reusable items into a `QImage`. Copies are important because
data binding must not alter the original template objects.

## Project Layout

- [app.py](app.py): supported application entry point.
- [main.py](main.py): main window, menus, file workflow, and export actions.
- [gabarit_wizard.py](gabarit_wizard.py): new-template dialog.
- [template_model.py](template_model.py): validated, versioned template model.
- [template_canvas.py](template_canvas.py): scene, printable bounds, and PNG export.
- [label_items.py](label_items.py): all editable Qt scene items.
- [item_properties.py](item_properties.py): property metadata used by the inspector.
- [property_inspector.py](property_inspector.py): dynamic property editor dock.
- [render_items.py](render_items.py): reusable render objects and factory.
- [rich_text_models.py](rich_text_models.py): rich-text value objects and enums.
- [rich_layout.py](rich_layout.py): Qt text layout engine.
- [article_models.py](article_models.py): product and pricing models.
- [article_types.py](article_types.py): specialized article models.
- [tier_engine.py](tier_engine.py): price-tier resolution and fallback rules.
- [imposition.py](imposition.py): multi-label page layout calculations.
- [label_renderer.py](label_renderer.py): headless image renderer.
- [units.py](units.py): physical-unit value objects.
- [test_core.py](test_core.py): pure-Python regression tests.

## Development Checks

Run the pure-Python regression suite:

```bash
python -m unittest test_core.py
```

Compile all root-level Python modules without starting Qt:

```bash
find . -maxdepth 1 -name '*.py' -print0 | xargs -0 python -m py_compile
```

The regression tests cover template JSON round trips, article binding values,
and tier fallback behavior. Qt rendering and interactive workflows require a
working graphical runtime and are not exercised by the pure-Python test suite.

## Architecture Notes

The root-level modules are the supported architecture. The former duplicated
editor and renderer stacks have been removed. The current separation is
intentional: document models, render primitives, and Qt scene adapters have
different ownership and lifecycle responsibilities.

## Complete Source Reference

This section documents every current root-level Python source file. The files
are listed by responsibility and the descriptions reflect the public classes
and entry points currently implemented.

### Application And User Interface

#### `app.py`

Application launcher. The `main()` function creates `QApplication`, constructs
`EditorMainWindow`, shows it, and returns Qt's event-loop exit code. Run this
file rather than importing the window directly.

#### `main.py`

Desktop application controller. `EditorMainWindow` owns the central
`QGraphicsView`, the `TemplateCanvas`, the property inspector, menus, toolbar
actions, file dialogs, preview-data loading, JSON save/open operations, and PNG
export. It also creates tier-price and rich items from user actions.

Important workflows implemented here:

- `on_file_new_gabarit()` opens `NewGabaritDialog`, validates the result, and
  creates a canvas.
- `on_add_tier_item()` inserts a `TierPriceLabelItem` with a collision-free ID.
- `on_add_rich_item()` inserts text, shape, image, QR, barcode, line, or ellipse
  items.
- `on_file_save()` serializes only valid printable objects.
- `on_file_open()` reconstructs a versioned `LabelTemplate` from JSON.
- `on_load_preview_data()` loads a flat JSON binding record.
- `on_export_png()` exports the label at 300 DPI.

#### `gabarit_wizard.py`

Defines `NewGabaritDialog`, the mandatory template-creation form. It collects
the name, physical dimensions, inner printable margins, and outer bleed
margins, then returns a validated `LabelTemplate` through `get_template()`.

#### `property_inspector.py`

Defines `PropertyInspectorWidget`, a dynamic editor for one or more selected
`BaseLabelItem` objects. It computes properties common to all selected items,
groups them by category, creates suitable Qt controls for floats, integers,
booleans, and strings, and applies changes through `PropertySpec` setters.

#### `item_properties.py`

Defines `PropertySpec`, the metadata object used by the inspector. A property
specification contains a stable key, display label, editor type, category,
getter, setter, optional numeric limits, and an optional suffix. The module
also provides the multiple-values display marker used for multi-selection.

### Template And Canvas

#### `template_model.py`

Defines the serializable document model:

- `Margins` stores top, bottom, left, and right millimetre values.
- `LabelTemplate` stores dimensions, margins, background settings, and item
  records.
- `LabelTemplate.validate()` returns all validation messages.
- `LabelTemplate.to_json()` validates and writes schema version `1`.
- `LabelTemplate.from_json()` parses JSON, restores margin objects, checks the
  schema version, and validates the resulting document.

#### `template_canvas.py`

Defines `TemplateCanvas`, a `QGraphicsScene` that maps millimetres to screen
pixels. It draws the neutral workspace, outer bleed area, label surface, and
inner printable boundary. It loads item records through `BaseLabelItem`,
creates stable item IDs, displays out-of-bounds overlays, serializes valid
items, and exports only the label rectangle to PNG.

#### `label_items.py`

Contains all interactive Qt canvas objects:

- `HazardWarningOverlay` draws a blinking warning over invalid geometry.
- `BaseLabelItem` provides selection, movement, millimetre geometry, common
  properties, and base JSON persistence.
- `TierPriceLabelItem` displays a selected price tier and resolves preview data
  during export.
- `RichLabelItem` wraps reusable render objects and adds editor behavior,
  property inspection, temporary export binding, and rich-item JSON persistence.

`BaseLabelItem.from_dict()` is the item factory for saved canvas records. It
selects the appropriate base, tier, or rich item implementation and restores
its serialized settings.

### Rendering And Text

#### `render_items.py`

Contains renderer objects independent of the graphics-scene selection layer:

- `BaseItem` stores a rectangle, rotation, z-index, lock state, and binding key.
- `ShapeItem` draws a filled, bordered rectangle.
- `TextItem` lays out and paints rich paragraphs with margins, alignment,
  overflow mode, background, borders, and placeholder text.
- `ImageItem` loads file paths or image bytes and caches the resulting image.
- `QRCodeItem` generates vector QR modules when `qrcode` is available.
- `BarcodeItem` generates Code 128 or EAN-13 bars when `python-barcode` is
  available.
- `LineItem` draws a configurable horizontal line.
- `EllipseItem` draws a configurable ellipse.
- `ItemFactory` maps serialized type names to renderer classes.

Every renderer accepts an optional override rectangle and implements
`apply_data_binding()` where its content can come from preview data.

#### `rich_text_models.py`

Defines the pure rich-text value model:

- `TextAlignment`, `VAlign`, `Overflow`, and `SizingMode` describe layout rules.
- `Position` stores cursor or text positions.
- `CharFormat` stores font family, size, weight, style, color, and decoration.
- `ParagraphFormat` stores paragraph alignment and spacing.
- `Run` stores a text span with a character format.
- `Paragraph` stores runs and exposes text and formatting operations.

#### `rich_layout.py`

Bridges the rich-text model to Qt text layout. `_qfont_default()` and
`_qfont()` convert model formatting to `QFont`. `ParagraphLayout` stores the
layout result for one paragraph, `LayoutResult` aggregates paragraph layouts,
and `LayoutEngine.layout()` calculates wrapped, formatted lines for a
`TextItem` within a target rectangle.

#### `label_renderer.py`

Defines `BatchRenderer.render_label_to_image()`. It sorts render items by
z-index, deep-copies each item, applies a data record to the copy, renders into
a `QImage`, and returns the image. The deep-copy step prevents batch data from
changing the source template.

### Product, Pricing, And Utilities

#### `article_models.py`

Defines the typed article domain:

- `ProductIdent`: product number, scan code, name, description, and brand.
- `HierarchyInfo`: division, department, category, and subcategory.
- `PackagingInfo`: pack unit, selling unit, case size, and case unit.
- `TaxInfo`: tax metadata and VAT calculation.
- `PricingInfo`: selling price, promotional price, effective price, discount
  percentage, and discount amount.
- `BaseArticle`: combines those values and creates the flat binding context
  consumed by label objects.

#### `article_types.py`

Defines specialized `BaseArticle` subclasses:

- `WeightedArticle` adds tare information and a price-per-kilogram binding.
- `BulkCaseArticle` calculates the unit price inside a case and adds case
  display bindings.

#### `tier_engine.py`

Defines the price-tier resolution service:

- `CancelLabelGenerationException` signals that a required tier is missing.
- `TierTargetSpec` configures the primary tier, fallback indexes, base-price
  fallback, strictness, prefix, and unit label.
- `TierResolver.resolve()` searches the configured tier chain, then optionally
  uses the selling price, returns an empty optional result, or raises.

#### `units.py`

Defines physical measurement helpers:

- `Unit` enumerates pixels, millimetres, and points.
- `Length` is a float-like value with conversion helpers such as `from_mm()`,
  `from_pt()`, `to_mm()`, and `to_pt()`. DPI validation is performed for every
  conversion that requires it.

#### `imposition.py`

Defines `PageImpositionResult` and `ImpositionCalculator`. The calculator
determines how many copies of a template fit on A4, A3, or Letter paper,
including outer margins and optional gaps, then returns centered offsets.

### Verification

#### `test_core.py`

Defines the pure-Python regression suite:

- `TemplateModelTests` verifies template JSON round trips.
- `PricingTests` verifies article binding values and case pricing.
- `TierResolverTests` verifies fallback to the base selling price.

These tests do not instantiate Qt widgets. Use them for fast checks of the
document and business layers, then use the full application for interactive Qt
validation.
