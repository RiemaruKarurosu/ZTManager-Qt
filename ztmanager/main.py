import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from .window import MainWindow


_APP_STYLESHEET = """
    QLabel#SubtitleLabel {
        color: palette(mid);
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid palette(mid);
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 8px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ZT Manager")
    app.setApplicationDisplayName("ZT Manager")
    app.setOrganizationName("RiemaruKarurosu")
    app.setWindowIcon(QIcon.fromTheme("network-vpn"))

    # Prefer Breeze (KDE) — fall back to Fusion (Qt built-in, looks clean)
    available = [s.lower() for s in QStyleFactory.keys()]
    for candidate in ("breeze", "fusion"):
        if candidate in available:
            app.setStyle(candidate)
            break

    app.setStyleSheet(_APP_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
