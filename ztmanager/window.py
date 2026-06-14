from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .installer import ZeroTierInstallerDialog
from .zerotierlib import ZeroTierNetwork
from . import _


class ToggleSwitch(QAbstractButton):
    """Breeze-style toggle switch that replaces GtkSwitch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()

        track_color = (
            palette.highlight().color() if self.isChecked() else palette.mid().color()
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(1, 5, 46, 16, 8, 8)

        thumb_color = (
            palette.base().color() if self.isChecked() else palette.light().color()
        )
        painter.setBrush(thumb_color)
        x = 23 if self.isChecked() else 2
        painter.drawEllipse(x, 1, 24, 24)
        painter.end()

    def sizeHint(self):
        return QSize(48, 26)


class NetworkCard(QFrame):
    """Single network row — equivalent to Adw.ActionRow."""

    toggle_changed = Signal(str, bool)
    settings_requested = Signal(str)

    def __init__(self, network: dict, parent=None):
        super().__init__(parent)
        self.network_id = network["id"]
        self._build_ui(network)

    def _build_ui(self, network: dict):
        self.setObjectName("NetworkCard")
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        self._icon = QLabel()
        self._icon.setFixedSize(22, 22)
        row.addWidget(self._icon)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.setContentsMargins(0, 0, 0, 0)

        self._name = QLabel()
        bold = self._name.font()
        bold.setBold(True)
        self._name.setFont(bold)
        text.addWidget(self._name)

        self._sub = QLabel()
        self._sub.setObjectName("SubtitleLabel")
        text.addWidget(self._sub)

        row.addLayout(text, 1)

        self._toggle = ToggleSwitch()
        self._toggle.toggled.connect(
            lambda state: self.toggle_changed.emit(self.network_id, state)
        )
        row.addWidget(self._toggle)

        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon.fromTheme("configure"))
        settings_btn.setFixedSize(30, 30)
        settings_btn.setFlat(True)
        settings_btn.setToolTip(_("Network settings"))
        settings_btn.clicked.connect(
            lambda: self.settings_requested.emit(self.network_id)
        )
        row.addWidget(settings_btn)

        self.update_data(network)

    def update_data(self, network: dict):
        name = network.get("name") or network.get("nwid") or "Unknown"
        self._name.setText(name)

        allow_managed = network.get("allowManaged", True)
        display_status = _("Disabled") if not allow_managed else network.get("status", "")
        addrs = network.get("assignedAddresses", [])
        ips = ", ".join(addrs) if isinstance(addrs, list) and addrs else "—"
        self._sub.setText(
            f"ID: {network.get('nwid', '?')}   IP: {ips}   Status: {display_status}"
        )

        if not allow_managed:
            icon_name = "network-offline"
        elif network.get("status") == "OK":
            icon_name = "emblem-default"
        elif network.get("status") in (
            "REQUESTING_CONFIGURATION",
            "WAITING_FOR_NETWORK_DATA",
            "JOINING",
        ):
            icon_name = "view-refresh"
        elif network.get("status") == "ACCESS_DENIED":
            icon_name = "emblem-important"
        else:
            icon_name = "dialog-error"

        self._icon.setPixmap(QIcon.fromTheme(icon_name).pixmap(QSize(22, 22)))

        self._toggle.blockSignals(True)
        self._toggle.setChecked(allow_managed)
        self._toggle.blockSignals(False)


class InfoBar(QFrame):
    """Warning banner shown when ZeroTier is unavailable."""

    install_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoBar")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme("dialog-warning").pixmap(QSize(20, 20)))
        row.addWidget(icon)

        self._msg = QLabel()
        self._msg.setWordWrap(True)
        row.addWidget(self._msg, 1)

        self._install_btn = QPushButton(_("Install ZeroTier"))
        self._install_btn.setObjectName("suggestedButton")
        self._install_btn.clicked.connect(self.install_requested.emit)
        row.addWidget(self._install_btn)

        self.hide()

    def set_message(self, message: str, show_install: bool = False):
        self._msg.setText(message)
        self._install_btn.setVisible(show_install)
        self.show()


class AddNetworkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Add Network"))
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(QLabel(_("Enter the Network ID to join:")))

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(_("Network ID (e.g. 8056c2e21c000001)"))
        self.id_input.setClearButtonEnabled(True)
        layout.addWidget(self.id_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def network_id(self) -> str:
        return self.id_input.text().strip()


class PeersDialog(QDialog):
    def __init__(self, parent, ztlib: ZeroTierNetwork):
        super().__init__(parent)
        self.setWindowTitle(_("Peers"))
        self.setMinimumSize(520, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.Shape.StyledPanel)

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setSpacing(4)
        vbox.setContentsMargins(8, 8, 8, 8)

        peers = ztlib.get_peers()
        if peers:
            for peer in peers:
                card = QFrame()
                card.setObjectName("NetworkCard")
                card.setFrameStyle(QFrame.Shape.StyledPanel)

                cl = QVBoxLayout(card)
                cl.setContentsMargins(10, 8, 10, 8)
                cl.setSpacing(2)

                title = QLabel(f"<b>Peer: {peer.get('address', 'Unknown')}</b>")
                cl.addWidget(title)

                paths = peer.get("paths", [])
                ip = paths[0].get("address") if paths else _("No IP")
                lat = peer.get("latency", -1)
                sub = QLabel(
                    _("Role: {role}  |  IP: {ip}  |  Latency: {lat} ms").format(
                        role=peer.get("role", "Unknown"), ip=ip, lat=lat
                    )
                )
                sub.setObjectName("SubtitleLabel")
                cl.addWidget(sub)
                vbox.addWidget(card)
        else:
            lbl = QLabel(_("No peers found."))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(lbl)

        vbox.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)


class NetworkDetailsDialog(QDialog):
    def __init__(self, parent, ztlib: ZeroTierNetwork, network: dict, refresh_callback):
        super().__init__(parent)
        self.setWindowTitle(f"{_('Details')}: {network.get('name', 'Unknown')}")
        self.setMinimumWidth(400)
        self.ztlib = ztlib
        self.network_id = network.get("id")
        self.refresh_callback = refresh_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        group = QGroupBox(_("Network Information"))
        form = QFormLayout(group)
        form.setSpacing(8)

        allow_managed = network.get("allowManaged", True)
        display_status = (
            _("Disabled") if not allow_managed else network.get("status", "Unknown")
        )
        ips = ", ".join(network.get("assignedAddresses", [])) or "None"

        fields = [
            ("ID", self.network_id or ""),
            (_("Name"), network.get("name", "Unknown")),
            ("MAC", network.get("mac", "Unknown")),
            ("MTU", str(network.get("mtu", "Unknown"))),
            (_("Status"), display_status),
            ("IPs", ips),
        ]

        for field_name, value in fields:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            val_label = QLabel(value)
            val_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            row_layout.addWidget(val_label, 1)

            copy_btn = QPushButton()
            copy_btn.setIcon(QIcon.fromTheme("edit-copy"))
            copy_btn.setFixedSize(26, 26)
            copy_btn.setFlat(True)
            copy_btn.setToolTip(_("Copy"))
            copy_btn.clicked.connect(
                lambda checked, v=value: QApplication.clipboard().setText(v)
            )
            row_layout.addWidget(copy_btn)

            form.addRow(f"<b>{field_name}</b>", row_widget)

        layout.addWidget(group)

        remove_btn = QPushButton(_("Remove Network"))
        remove_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white;"
            " border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(remove_btn)

        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    def _on_remove_clicked(self):
        reply = QMessageBox.warning(
            self,
            _("Confirm Removal"),
            _("Are you sure you want to remove this network?\n\n"
              "ZeroTier will forget it completely."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.ztlib.leave_networks(self.network_id)
            if self.refresh_callback:
                self.refresh_callback()
            self.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZT Manager")
        self.setWindowIcon(QIcon.fromTheme("network-vpn"))
        self.setMinimumSize(600, 450)
        self.resize(720, 520)

        self.ztlib = ZeroTierNetwork()
        self._cards: dict[str, NetworkCard] = {}

        self._build_ui()
        self._build_toolbar()
        self._apply_styles()

        self._check_status()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(3000)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._info_bar = InfoBar()
        self._info_bar.install_requested.connect(self._on_install_clicked)
        root.addWidget(self._info_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.Shape.NoFrame)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(12, 12, 12, 12)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()

        self._empty_label = QLabel(_("No networks joined yet."))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setObjectName("SubtitleLabel")
        self._list_layout.insertWidget(0, self._empty_label)

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, 1)

    def _build_toolbar(self):
        tb = QToolBar(_("Actions"))
        tb.setMovable(False)
        tb.setIconSize(QSize(22, 22))
        self.addToolBar(tb)

        add = QAction(QIcon.fromTheme("list-add"), _("Add Network"), self)
        add.setShortcut("Ctrl+N")
        add.triggered.connect(self._on_add_clicked)
        tb.addAction(add)

        refresh = QAction(QIcon.fromTheme("view-refresh"), _("Refresh"), self)
        refresh.setShortcut("F5")
        refresh.triggered.connect(self._refresh_networks)
        tb.addAction(refresh)

        tb.addSeparator()

        peers = QAction(QIcon.fromTheme("network-workgroup"), _("Peers"), self)
        peers.triggered.connect(self._on_peers_clicked)
        tb.addAction(peers)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        about = QAction(QIcon.fromTheme("help-about"), _("About"), self)
        about.triggered.connect(self._on_about_clicked)
        tb.addAction(about)

        prefs = QAction(QIcon.fromTheme("configure"), _("Preferences"), self)
        prefs.setShortcut("Ctrl+,")
        prefs.triggered.connect(self._on_preferences_clicked)
        tb.addAction(prefs)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QFrame#NetworkCard {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            QFrame#NetworkCard:hover {
                border-color: palette(highlight);
            }
            QFrame#InfoBar {
                background-color: #f5a623;
                color: #1a1a1a;
                border-bottom: 1px solid #d4901d;
            }
            QLabel#SubtitleLabel {
                color: palette(mid);
            }
            QPushButton#suggestedButton {
                background-color: palette(highlight);
                color: palette(highlighted-text);
                border-radius: 4px;
                padding: 4px 12px;
                border: none;
            }
            QPushButton#suggestedButton:hover {
                background-color: palette(dark);
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
        )

    # ── Status / refresh ──────────────────────────────────────────────────────

    def _check_status(self) -> bool:
        has_service = self.ztlib.zt_status()
        has_token = bool(
            self.ztlib.api_token and self.ztlib.check_token(self.ztlib.api_token)
        )

        if has_service and has_token:
            self._info_bar.hide()
            self._refresh_networks()
            return True

        is_installed = self.ztlib.is_installed()
        if not is_installed:
            self._info_bar.set_message(
                _("ZeroTier-One is not installed on your system."),
                show_install=True,
            )
        elif not self.ztlib.api_token:
            self._info_bar.set_message(
                _("No token set. Open Preferences and enter a valid X-ZT1-Auth token.")
            )
        else:
            self._info_bar.set_message(
                _("ZeroTier service is not running. Start it from Preferences.")
            )
        return False

    def _auto_refresh(self):
        if not self._info_bar.isVisible():
            self._refresh_networks()

    def _refresh_networks(self):
        networks = self.ztlib.get_networks()
        if not isinstance(networks, list):
            return

        current = {n["id"]: n for n in networks}

        for nid in list(self._cards):
            if nid not in current:
                card = self._cards.pop(nid)
                self._list_layout.removeWidget(card)
                card.deleteLater()

        for network in networks:
            nid = network["id"]
            if nid in self._cards:
                self._cards[nid].update_data(network)
            else:
                card = NetworkCard(network)
                card.toggle_changed.connect(self._on_toggle_changed)
                card.settings_requested.connect(self._on_settings_requested)
                # Insert before the trailing stretch (last item)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
                self._cards[nid] = card

        has_networks = bool(self._cards)
        self._empty_label.setVisible(not has_networks)

    # ── Toolbar handlers ──────────────────────────────────────────────────────

    def _on_add_clicked(self):
        dlg = AddNetworkDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nid = dlg.network_id()
            if nid:
                self.ztlib.join_networks(nid)
                self._refresh_networks()
            else:
                QMessageBox.warning(self, _("Error"), _("Invalid Network ID."))

    def _on_peers_clicked(self):
        PeersDialog(self, self.ztlib).exec()

    def _on_preferences_clicked(self):
        from .preferences import PreferencesDialog
        PreferencesDialog(self, self.ztlib).exec()
        self._check_status()

    def _on_install_clicked(self):
        ZeroTierInstallerDialog(self, on_install_complete=self._check_status).exec()

    def _on_about_clicked(self):
        QMessageBox.about(
            self,
            _("About ZT Manager"),
            "<b>ZT Manager</b> — Qt6/KDE Edition<br>"
            "Version 0.1.0<br><br>"
            "Copyright © 2026 Riemaru Karurosu<br>"
            "License: GPL-3.0-or-later<br><br>"
            "<a href='https://github.com/RiemaruKarurosu/ZTManager'>"
            "github.com/RiemaruKarurosu/ZTManager</a>",
        )

    # ── Card signal handlers ──────────────────────────────────────────────────

    def _on_toggle_changed(self, network_id: str, state: bool):
        self.ztlib.update_network(network_id, {"allowManaged": state})

    def _on_settings_requested(self, network_id: str):
        network = self.ztlib.get_network_details(network_id)
        if network:
            NetworkDetailsDialog(self, self.ztlib, network, self._refresh_networks).exec()

    # ── Helpers used by PreferencesDialog ────────────────────────────────────

    def get_service_status(self) -> bool:
        return self.ztlib.zt_enable_status()

    def on_service_set(self, status: int) -> bool:
        result = self.ztlib.service(status)
        self._check_status()
        return result
