from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .installer import ZeroTierInstallerDialog
from .zerotierlib import ZeroTierNetwork
from . import _

# ── Breeze colours ────────────────────────────────────────────────────────────
BREEZE_BLUE   = "#3daee9"
BREEZE_GREEN  = "#1cdc9a"
BREEZE_ORANGE = "#f67400"
BREEZE_RED    = "#da4453"
BREEZE_GRAY   = "#7f8c8d"

_STATUS_MAP: dict[str, tuple[str, str]] = {
    "OK":                       (BREEZE_GREEN,  _("Connected")),
    "REQUESTING_CONFIGURATION": (BREEZE_ORANGE, _("Connecting…")),
    "WAITING_FOR_NETWORK_DATA": (BREEZE_ORANGE, _("Waiting…")),
    "JOINING":                  (BREEZE_ORANGE, _("Joining…")),
    "ACCESS_DENIED":            (BREEZE_RED,    _("Access Denied")),
    "__disabled__":             (BREEZE_GRAY,   _("Disabled")),
}

def _status_info(network: dict) -> tuple[str, str]:
    if not network.get("allowManaged", True):
        return _STATUS_MAP["__disabled__"]
    return _STATUS_MAP.get(
        network.get("status", ""),
        (BREEZE_RED, network.get("status", "Unknown")),
    )


# ── Reusable widgets ──────────────────────────────────────────────────────────

class _StatusDot(QWidget):
    """12 px painted circle status indicator."""

    def __init__(self, color: str = BREEZE_GRAY, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(color)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(0, 0, 12, 12)
        p.end()


class ToggleSwitch(QAbstractButton):
    """Animated Breeze-style toggle switch."""
    _TW, _TH, _TD = 40, 20, 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(self._TW + 4, self._TH + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"_p", self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.toggled.connect(self._on_toggled)

    def _get_p(self): return self._pos
    def _set_p(self, v):
        self._pos = v
        self.update()
    _p = Property(float, _get_p, _set_p)

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def snap_to(self, checked: bool):
        """Set state instantly, no animation (for programmatic updates)."""
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.blockSignals(True)
        super().setChecked(checked)
        self.blockSignals(False)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tw, th = self._TW, self._TH
        tx = (self.width()  - tw) // 2
        ty = (self.height() - th) // 2
        g, b = QColor(BREEZE_GRAY), QColor(BREEZE_BLUE)
        r_ = int(g.red()   + (b.red()   - g.red())   * self._pos)
        g_ = int(g.green() + (b.green() - g.green()) * self._pos)
        b_ = int(g.blue()  + (b.blue()  - g.blue())  * self._pos)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(r_, g_, b_))
        p.drawRoundedRect(tx, ty, tw, th, th / 2, th / 2)
        td, m = self._TD, (th - self._TD) // 2
        xp = int(tx + m + self._pos * (tw - td - 2 * m))
        p.setBrush(QColor("white"))
        p.drawEllipse(xp, ty + m, td, td)
        p.end()

    def sizeHint(self): return QSize(self._TW + 4, self._TH + 4)


# ── Left panel: compact list row ──────────────────────────────────────────────

class _NetworkRowWidget(QWidget):
    def __init__(self, network: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(10)

        color, _ = _status_info(network)
        self._dot = _StatusDot(color)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(1)
        text.setContentsMargins(0, 0, 0, 0)

        self._name = QLabel()
        f = self._name.font()
        f.setBold(True)
        self._name.setFont(f)
        text.addWidget(self._name)

        self._nwid = QLabel()
        self._nwid.setObjectName("SubtitleLabel")
        f2 = self._nwid.font()
        f2.setPointSize(f2.pointSize() - 1)
        self._nwid.setFont(f2)
        text.addWidget(self._nwid)

        layout.addLayout(text, 1)

        _, status_text = _status_info(network)
        self._status = QLabel(status_text)
        self._status.setObjectName("StatusText")
        f3 = self._status.font()
        f3.setPointSize(f3.pointSize() - 1)
        self._status.setFont(f3)
        layout.addWidget(self._status, 0, Qt.AlignmentFlag.AlignVCenter)

        self.update_data(network)

    def update_data(self, network: dict):
        color, status_text = _status_info(network)
        self._dot.set_color(color)
        self._name.setText(network.get("name") or network.get("nwid") or "Unknown")
        self._nwid.setText(network.get("nwid", ""))
        self._status.setText(status_text)
        self._status.setStyleSheet(f"color: {color};")


# ── Right panel: detail view ──────────────────────────────────────────────────

class _DetailPanel(QWidget):
    network_removed = Signal(str)

    def __init__(self, ztlib: ZeroTierNetwork, parent=None):
        super().__init__(parent)
        self.ztlib = ztlib
        self._network: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Placeholder
        self._placeholder = QWidget()
        ph = QVBoxLayout(self._placeholder)
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setSpacing(10)
        ph_icon = QLabel()
        ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_icon.setPixmap(QIcon.fromTheme("network-wired").pixmap(QSize(48, 48)))
        ph.addWidget(ph_icon)
        ph_lbl = QLabel(_("Select a network to view its details"))
        ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_lbl.setObjectName("SubtitleLabel")
        ph.addWidget(ph_lbl)
        root.addWidget(self._placeholder)

        # Content
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.Shape.NoFrame)
        self._scroll = scroll
        self._scroll.hide()

        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(18, 16, 18, 18)
        il.setSpacing(14)

        # Title row with dot
        title_row = QHBoxLayout()
        self._title_dot = _StatusDot()
        title_row.addWidget(self._title_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self._title = QLabel()
        tf = self._title.font()
        tf.setBold(True)
        tf.setPointSize(tf.pointSize() + 3)
        self._title.setFont(tf)
        title_row.addWidget(self._title, 1)
        il.addLayout(title_row)

        # Info
        info_grp = QGroupBox(_("Network Information"))
        self._form = QFormLayout(info_grp)
        self._form.setSpacing(8)
        self._form.setHorizontalSpacing(20)
        il.addWidget(info_grp)

        # Control
        ctrl_grp = QGroupBox(_("Control"))
        ctrl_l = QVBoxLayout(ctrl_grp)
        ctrl_l.setSpacing(10)

        toggle_row = QHBoxLayout()
        ttext = QVBoxLayout()
        ttext.setSpacing(2)
        ttext.addWidget(QLabel(f"<b>{_('Enable Network')}</b>"))
        ts = QLabel(_("Allow ZeroTier to route traffic through this network"))
        ts.setObjectName("SubtitleLabel")
        ttext.addWidget(ts)
        toggle_row.addLayout(ttext, 1)
        self._toggle = ToggleSwitch()
        self._toggle.toggled.connect(self._on_toggle)
        toggle_row.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        ctrl_l.addLayout(toggle_row)
        il.addWidget(ctrl_grp)

        # Remove
        self._remove_btn = QPushButton(
            QIcon.fromTheme("edit-delete"), _("Remove Network")
        )
        self._remove_btn.setObjectName("DestructiveButton")
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.clicked.connect(self._on_remove)
        il.addWidget(self._remove_btn)
        il.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

    def show_network(self, network: dict):
        self._network = network
        color, _ = _status_info(network)
        self._title_dot.set_color(color)
        self._title.setText(network.get("name") or network.get("nwid") or "Unknown")

        while self._form.rowCount():
            self._form.removeRow(0)

        ips = ", ".join(network.get("assignedAddresses", [])) or "—"
        _, status_text = _status_info(network)
        for label, value in [
            ("ID",        network.get("nwid", "?")),
            (_("Status"), status_text),
            ("IPs",       ips),
            ("MAC",       network.get("mac", "Unknown")),
            ("MTU",       str(network.get("mtu", "?"))),
        ]:
            self._form.addRow(f"<b>{label}</b>", self._copy_row(value))

        self._toggle.snap_to(network.get("allowManaged", True))
        self._placeholder.hide()
        self._scroll.show()

    def _copy_row(self, value: str) -> QWidget:
        w = QWidget()
        rl = QHBoxLayout(w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        lbl = QLabel(value)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        f = lbl.font()
        f.setFamily("monospace")
        lbl.setFont(f)
        rl.addWidget(lbl, 1)
        btn = QPushButton()
        btn.setIcon(QIcon.fromTheme("edit-copy"))
        btn.setFixedSize(24, 24)
        btn.setFlat(True)
        btn.setToolTip(_("Copy"))
        btn.clicked.connect(lambda _, v=value: QApplication.clipboard().setText(v))
        rl.addWidget(btn)
        return w

    def clear(self):
        self._network = None
        self._scroll.hide()
        self._placeholder.show()

    def _on_toggle(self, state: bool):
        if self._network:
            self.ztlib.update_network(self._network["id"], {"allowManaged": state})

    def _on_remove(self):
        if not self._network:
            return
        reply = QMessageBox.warning(
            self, _("Remove Network"),
            _("Remove this network?\nZeroTier will forget it completely."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            nid = self._network["id"]
            self.ztlib.leave_networks(nid)
            self.network_removed.emit(nid)
            self.clear()


# ── Info bar ──────────────────────────────────────────────────────────────────

class InfoBar(QFrame):
    install_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoBar")
        self.setFixedHeight(42)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme("dialog-warning").pixmap(QSize(18, 18)))
        row.addWidget(icon)
        self._msg = QLabel()
        row.addWidget(self._msg, 1)
        self._install_btn = QPushButton(_("Install ZeroTier"))
        self._install_btn.setObjectName("SuggestedButton")
        self._install_btn.clicked.connect(self.install_requested.emit)
        row.addWidget(self._install_btn)
        self.hide()

    def set_message(self, msg: str, show_install: bool = False):
        self._msg.setText(msg)
        self._install_btn.setVisible(show_install)
        self.show()


# ── Dialogs ───────────────────────────────────────────────────────────────────

class AddNetworkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Join Network"))
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(QLabel(f"<b>{_('Network ID:')}</b>"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("8056c2e21c000001")
        self.id_input.setClearButtonEnabled(True)
        self.id_input.setMinimumHeight(32)
        layout.addWidget(self.id_input)
        hint = QLabel(_("16-character hex string provided by the network owner."))
        hint.setObjectName("SubtitleLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_("Join"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def network_id(self) -> str:
        return self.id_input.text().strip()


class PeersDialog(QDialog):
    def __init__(self, parent, ztlib: ZeroTierNetwork):
        super().__init__(parent)
        self.setWindowTitle(_("Connected Peers"))
        self.setMinimumSize(520, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QFrame()
        hdr.setObjectName("ListHeader")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.addWidget(QLabel(f"<b>{_('Peers')}</b>"))
        hl.addStretch()
        layout.addWidget(hdr)

        peer_list = QListWidget()
        peer_list.setFrameStyle(QFrame.Shape.NoFrame)
        peer_list.setAlternatingRowColors(True)
        peers = ztlib.get_peers()
        for peer in (peers or []):
            paths = peer.get("paths", [])
            ip   = paths[0].get("address") if paths else _("No IP")
            lat  = peer.get("latency", -1)
            role = peer.get("role", "LEAF")
            addr = peer.get("address", "Unknown")
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 52))
            peer_list.addItem(item)
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 6, 12, 6)
            rl.setSpacing(10)
            dot = _StatusDot(BREEZE_BLUE if role == "PLANET" else BREEZE_GREEN)
            rl.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            info = QVBoxLayout()
            info.setSpacing(2)
            info.addWidget(QLabel(f"<b>{addr}</b>"))
            sub = QLabel(f"{role}  ·  {ip}  ·  {lat} ms")
            sub.setObjectName("SubtitleLabel")
            info.addWidget(sub)
            rl.addLayout(info, 1)
            peer_list.setItemWidget(item, row)

        if not peers:
            empty = QListWidgetItem(_("No peers found."))
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            peer_list.addItem(empty)

        layout.addWidget(peer_list, 1)
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        bl = QHBoxLayout()
        bl.setContentsMargins(12, 8, 12, 8)
        bl.addStretch()
        bl.addWidget(close_btn)
        layout.addLayout(bl)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZT Manager")
        self.setWindowIcon(QIcon.fromTheme("network-vpn"))
        self.setMinimumSize(720, 500)
        self.resize(860, 580)

        self.ztlib = ZeroTierNetwork()
        self._network_data: dict[str, dict] = {}
        self._row_widgets: dict[str, _NetworkRowWidget] = {}

        self._build_menubar()
        self._build_central()
        self._build_bottom_toolbar()
        self._apply_styles()
        self._check_status()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(3000)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        file_m = mb.addMenu(_("&File"))
        q = QAction(QIcon.fromTheme("application-exit"), _("&Quit"), self)
        q.setShortcut("Ctrl+Q")
        q.triggered.connect(self.close)
        file_m.addAction(q)

        net_m = mb.addMenu(_("&Network"))
        add_a = QAction(QIcon.fromTheme("list-add"), _("&Join Network…"), self)
        add_a.setShortcut("Ctrl+N")
        add_a.triggered.connect(self._on_add_clicked)
        net_m.addAction(add_a)
        ref_a = QAction(QIcon.fromTheme("view-refresh"), _("&Refresh"), self)
        ref_a.setShortcut("F5")
        ref_a.triggered.connect(self._refresh_networks)
        net_m.addAction(ref_a)
        net_m.addSeparator()
        peers_a = QAction(QIcon.fromTheme("network-workgroup"), _("View &Peers"), self)
        peers_a.triggered.connect(self._on_peers_clicked)
        net_m.addAction(peers_a)

        set_m = mb.addMenu(_("&Settings"))
        prefs_a = QAction(QIcon.fromTheme("configure"), _("&Configure ZT Manager…"), self)
        prefs_a.setShortcut("Ctrl+,")
        prefs_a.triggered.connect(self._on_preferences_clicked)
        set_m.addAction(prefs_a)

        help_m = mb.addMenu(_("&Help"))
        about_a = QAction(QIcon.fromTheme("help-about"), _("&About ZT Manager"), self)
        about_a.triggered.connect(self._on_about_clicked)
        help_m.addAction(about_a)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Info bar
        self._info_bar = InfoBar()
        self._info_bar.install_requested.connect(self._on_install_clicked)
        root.addWidget(self._info_bar)

        # ── Splitter ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left: list
        left = QWidget()
        left.setObjectName("LeftPanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # List header with [+] button on the right
        list_hdr = QFrame()
        list_hdr.setObjectName("ListHeader")
        lh = QHBoxLayout(list_hdr)
        lh.setContentsMargins(10, 4, 6, 4)
        lh.setSpacing(6)

        lh.addWidget(QLabel(f"<b>{_('Networks')}</b>"))

        self._count_badge = QLabel()
        self._count_badge.setObjectName("CountBadge")
        self._count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_badge.setFixedHeight(18)
        self._count_badge.hide()
        lh.addWidget(self._count_badge)
        lh.addStretch()

        add_btn = QPushButton()
        add_btn.setIcon(QIcon.fromTheme("list-add"))
        add_btn.setFixedSize(26, 26)
        add_btn.setFlat(True)
        add_btn.setToolTip(_("Join a network (Ctrl+N)"))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_clicked)
        lh.addWidget(add_btn)

        ll.addWidget(list_hdr)

        self._list = QListWidget()
        self._list.setSpacing(0)
        self._list.setFrameStyle(QFrame.Shape.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setAlternatingRowColors(True)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        ll.addWidget(self._list, 1)

        splitter.addWidget(left)

        # Right: detail + empty placeholder panel
        right = QWidget()
        right.setObjectName("RightPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Empty state (shown when list has no networks)
        self._empty_widget = self._make_empty_state()
        rl.addWidget(self._empty_widget)

        self._detail = _DetailPanel(self.ztlib)
        self._detail.network_removed.connect(self._on_network_removed)
        self._detail.hide()
        rl.addWidget(self._detail, 1)

        splitter.addWidget(right)
        splitter.setSizes([240, 580])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _make_empty_state(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.setSpacing(14)
        vbox.setContentsMargins(30, 0, 30, 0)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(
            QIcon.fromTheme("network-disconnect").pixmap(QSize(64, 64))
        )
        vbox.addWidget(icon_lbl)

        title = QLabel(_("No networks joined yet"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        title.setFont(f)
        vbox.addWidget(title)

        sub = QLabel(_("Join a ZeroTier network to connect with other devices."))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setObjectName("SubtitleLabel")
        sub.setWordWrap(True)
        vbox.addWidget(sub)

        big_btn = QPushButton(
            QIcon.fromTheme("list-add"), _("Join a Network…")
        )
        big_btn.setObjectName("BigAddButton")
        big_btn.setMinimumHeight(38)
        big_btn.setMinimumWidth(180)
        big_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        big_btn.clicked.connect(self._on_add_clicked)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(big_btn)
        row.addStretch()
        vbox.addLayout(row)
        return w

    def _build_bottom_toolbar(self):
        """Bottom toolbar: Refresh + Peers on the left, status info on the right."""
        tb = QToolBar(_("Actions"))
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb)

        ref = QAction(QIcon.fromTheme("view-refresh"), _("Refresh"), self)
        ref.setShortcut("F5")
        ref.triggered.connect(self._refresh_networks)
        tb.addAction(ref)

        peers = QAction(QIcon.fromTheme("network-workgroup"), _("Peers"), self)
        peers.triggered.connect(self._on_peers_clicked)
        tb.addAction(peers)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._sb_count   = QLabel(_("0 networks"))
        self._sb_service = QLabel()
        tb.addWidget(self._sb_count)
        tb.addWidget(QLabel("  ·  "))
        tb.addWidget(self._sb_service)
        tb.addWidget(QLabel("  "))

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget#LeftPanel  { border-right:  1px solid palette(mid); }
            QWidget#RightPanel { background: palette(base); }

            QFrame#ListHeader {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QLabel#CountBadge {
                background: #3daee9;
                color: white;
                border-radius: 9px;
                padding: 0 7px;
                font-size: 8pt;
                font-weight: bold;
                min-width: 18px;
                margin-left: 4px;
            }

            QLabel#SubtitleLabel { color: palette(mid); }
            QLabel#StatusText    { font-size: 8pt; }

            QFrame#InfoBar {
                background: qlineargradient(
                    x1:0,y1:0,x2:0,y2:1,
                    stop:0 #f0a500, stop:1 #d99000);
                border-bottom: 1px solid #b07800;
            }
            QFrame#InfoBar QLabel { color: #1a1200; }
            QPushButton#SuggestedButton {
                background: rgba(255,255,255,.28);
                color: #1a1200;
                border: 1px solid rgba(255,255,255,.55);
                border-radius: 4px;
                padding: 3px 12px;
                font-weight: bold;
            }
            QPushButton#SuggestedButton:hover {
                background: rgba(255,255,255,.42);
            }

            QPushButton#BigAddButton {
                background: palette(highlight);
                color: palette(highlighted-text);
                border: none;
                border-radius: 5px;
                padding: 8px 22px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton#BigAddButton:hover  { background: palette(dark); }
            QPushButton#BigAddButton:pressed { background: palette(shadow); }

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
            """
        )

    # ── Status / refresh ──────────────────────────────────────────────────────

    def _check_status(self) -> bool:
        has_service = self.ztlib.zt_status()
        has_token   = bool(
            self.ztlib.api_token and self.ztlib.check_token(self.ztlib.api_token)
        )
        self._sb_service.setText(
            _("Service: active") if has_service else _("Service: stopped")
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
                _("No token set — open Settings → Configure to enter your X-ZT1-Auth token.")
            )
        else:
            self._info_bar.set_message(
                _("ZeroTier service is not running. Start it from Settings → Configure.")
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

        for nid in list(self._network_data):
            if nid not in current:
                del self._network_data[nid]
                del self._row_widgets[nid]
                for i in range(self._list.count()):
                    if self._list.item(i).data(Qt.ItemDataRole.UserRole) == nid:
                        self._list.takeItem(i)
                        break

        for network in networks:
            nid = network["id"]
            self._network_data[nid] = network
            if nid in self._row_widgets:
                self._row_widgets[nid].update_data(network)
                cur = self._list.currentItem()
                if cur and cur.data(Qt.ItemDataRole.UserRole) == nid:
                    self._detail.show_network(network)
            else:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, nid)
                item.setSizeHint(QSize(0, 54))
                self._list.addItem(item)
                rw = _NetworkRowWidget(network)
                self._list.setItemWidget(item, rw)
                self._row_widgets[nid] = rw

        count = len(self._network_data)
        self._sb_count.setText(
            f"{count} " + (_("network") if count == 1 else _("networks"))
        )
        has = bool(count)
        self._count_badge.setText(str(count))
        self._count_badge.setVisible(has)
        self._empty_widget.setVisible(not has)
        if has and self._detail.isHidden() and not self._list.currentItem():
            pass  # keep empty detail placeholder
        elif not has:
            self._detail.hide()
            self._empty_widget.show()

    # ── Action handlers ───────────────────────────────────────────────────────

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
            self, _("About ZT Manager"),
            "<b>ZT Manager</b> — Qt6/KDE Edition<br>"
            "Version 0.1.0<br><br>"
            "Copyright © 2026 Riemaru Karurosu<br>"
            "License: GPL-3.0-or-later",
        )

    def _on_selection_changed(self, current: QListWidgetItem, _prev):
        if current is None:
            self._detail.clear()
            return
        nid = current.data(Qt.ItemDataRole.UserRole)
        if nid and nid in self._network_data:
            self._empty_widget.hide()
            self._detail.show()
            self._detail.show_network(self._network_data[nid])

    def _on_network_removed(self, _nid: str):
        self._refresh_networks()

    # ── Used by PreferencesDialog ─────────────────────────────────────────────

    def get_service_status(self) -> bool:
        return self.ztlib.zt_enable_status()

    def on_service_set(self, status: int) -> bool:
        result = self.ztlib.service(status)
        self._check_status()
        return result
