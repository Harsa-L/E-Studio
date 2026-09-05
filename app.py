"""Application entry point for E-Studio."""

import sys

from PySide6.QtWidgets import QApplication

from main import EditorMainWindow


def main() -> int:
    """Start the desktop editor and return Qt's process exit status."""
    app = QApplication(sys.argv)
    window = EditorMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
