import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from .window import MainWindow

_ICON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "icons", "hicolor",
    "scalable", "apps", "io.github.riemarukarurosu.ZTManager.svg",
)

# Applied at application level so all windows (including dialogs) inherit it
_GLOBAL_STYLESHEET = """
    QLabel#SubtitleLabel { color: palette(mid); }

    QGroupBox {
        font-weight: bold;
        border: 1px solid palette(mid);
        border-radius: 5px;
        margin-top: 9px;
        padding-top: 9px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }

    /* Token-valid / invalid colours used in PreferencesDialog */
    QLabel#TokenValid   { color: #1cdc9a; font-weight: bold; }
    QLabel#TokenInvalid { color: #da4453; font-weight: bold; }

    QPushButton#DestructiveButton {
        background: #da4453;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: bold;
    }
    QPushButton#DestructiveButton:hover   { background: #e5555f; }
    QPushButton#DestructiveButton:pressed { background: #c23040; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ZT Manager")
    app.setApplicationDisplayName("ZT Manager")
    app.setOrganizationName("RiemaruKarurosu")
    # Use the app's own SVG icon; fall back to a theme icon
    if os.path.isfile(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))
    else:
        app.setWindowIcon(QIcon.fromTheme("network-vpn"))

    # Prefer Breeze (KDE), fall back to Fusion
    available = [s.lower() for s in QStyleFactory.keys()]
    for candidate in ("breeze", "fusion"):
        if candidate in available:
            app.setStyle(candidate)
            break

    app.setStyleSheet(_GLOBAL_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
