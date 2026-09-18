from __future__ import annotations

import sys
import types
from pathlib import Path

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The repo has both app.py and an app package. When this file is launched directly,
# Python resolves this file before the package directory, so we replace the module alias
# with the real package namespace before importing submodules such as app.application_service.
app_pkg_dir = ROOT / "app"
if "app" not in sys.modules or getattr(sys.modules["app"], "__file__", None) in {None, str(ROOT / "app.py")}:
    pkg = types.ModuleType("app")
    pkg.__file__ = str(app_pkg_dir / "__init__.py")
    pkg.__path__ = [str(app_pkg_dir)]
    sys.modules["app"] = pkg

from ui.windows.home_window import HomeWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = HomeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
