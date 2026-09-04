# E-Studio

E-Studio is a PySide6 desktop editor for creating and saving printable label templates.

## Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Create a template, add tier-price blocks, validate their printable bounds, then save or reopen the versioned JSON document.

## Template format

Saved files contain `schema_version: 1`, label dimensions and margins in millimetres, and serialized items. Unsupported or malformed item records are ignored while loading so a document can still be inspected and repaired.

## Project layout

- `main.py`: desktop application and file workflow.
- `template_model.py`: validated, versioned document model.
- `template_canvas.py`: Qt scene and printable-area validation.
- `label_items.py`: movable item implementations and serialization.
- `oth/`: experimental text/layout/rendering engine retained for the next integration phase.
