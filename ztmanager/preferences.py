from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .window import ToggleSwitch, BREEZE_GREEN, BREEZE_RED
from .zerotierlib import ZeroTierNetwork
from . import _


class PreferencesDialog(QDialog):
    def __init__(self, parent, ztlib: ZeroTierNetwork):
        super().__init__(parent)
        self.setWindowTitle(_("Configure ZT Manager"))
        self.setMinimumWidth(460)
        self.ztlib = ztlib
        self._main_window = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        layout.addWidget(self._build_auth_group())
        layout.addWidget(self._build_service_group())
        layout.addStretch()

        self._status_lbl = QLabel()
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

        close_btn = QPushButton(_("Close"))
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        bl = QHBoxLayout()
        bl.addStretch()
        bl.addWidget(close_btn)
        layout.addLayout(bl)

    # ── Authentication ────────────────────────────────────────────────────────

    def _build_auth_group(self) -> QGroupBox:
        grp = QGroupBox(_("Authentication"))
        layout = QVBoxLayout(grp)
        layout.setSpacing(12)

        # Token row
        row = QHBoxLayout()
        key_icon = QLabel()
        key_icon.setPixmap(QIcon.fromTheme("dialog-password").pixmap(QSize(20, 20)))
        row.addWidget(key_icon)

        self._token_input = QLineEdit()
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setPlaceholderText(_("X-ZT1-Auth Token"))
        self._token_input.setClearButtonEnabled(True)
        self._token_input.setMinimumHeight(32)
        if self.ztlib.api_token:
            self._token_input.setText(self.ztlib.api_token)
        self._token_input.textChanged.connect(self._on_token_changed)
        row.addWidget(self._token_input, 1)

        eye = QPushButton()
        eye.setIcon(QIcon.fromTheme("view-visible"))
        eye.setCheckable(True)
        eye.setFixedSize(30, 30)
        eye.setFlat(True)
        eye.setToolTip(_("Show / hide token"))
        eye.toggled.connect(
            lambda on: self._token_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        row.addWidget(eye)
        layout.addLayout(row)

        # Inline token status
        self._token_status = QLabel()
        self._token_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._token_status)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Auto-detect row
        detect_row = QHBoxLayout()
        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.addWidget(QLabel(f"<b>{_('Auto-detect Token')}</b>"))
        hint = QLabel(_("Read from /var/lib/zerotier-one/authtoken.secret"))
        hint.setObjectName("SubtitleLabel")
        txt.addWidget(hint)
        detect_row.addLayout(txt, 1)

        detect_btn = QPushButton(_("Detect"))
        detect_btn.setMinimumWidth(80)
        detect_btn.clicked.connect(self._on_auto_detect)
        detect_row.addWidget(detect_btn)
        layout.addLayout(detect_row)

        return grp

    # ── Service ───────────────────────────────────────────────────────────────

    def _build_service_group(self) -> QGroupBox:
        grp = QGroupBox(_("ZeroTier Service"))
        layout = QVBoxLayout(grp)
        layout.setSpacing(12)

        is_running = self.ztlib.zt_status()
        is_enabled = self._main_window.get_service_status()

        self._add_toggle_row(
            layout,
            _("Start ZeroTier"),
            _("The application needs the service to be running"),
            is_running,
            self._on_start_toggled,
        )

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        self._add_toggle_row(
            layout,
            _("Start on boot"),
            _("Automatically start ZeroTier when the system boots"),
            is_enabled,
            self._on_enable_toggled,
        )
        return grp

    def _add_toggle_row(self, parent_layout, title: str, subtitle: str,
                        state: bool, callback):
        row = QHBoxLayout()
        txt = QVBoxLayout()
        txt.setSpacing(3)
        txt.addWidget(QLabel(f"<b>{title}</b>"))
        sub = QLabel(subtitle)
        sub.setObjectName("SubtitleLabel")
        txt.addWidget(sub)
        row.addLayout(txt, 1)

        toggle = ToggleSwitch()
        toggle.snap_to(state)
        toggle.toggled.connect(callback)
        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        parent_layout.addLayout(row)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_token_changed(self, text: str):
        token = text.strip()
        if not token:
            self._token_status.clear()
            return
        if self.ztlib.check_token(token):
            self.ztlib.api_token = token
            self.ztlib.headers = {"X-ZT1-Auth": token}
            self.ztlib.save_token()
            self._token_status.setText(
                f"<span style='color:{BREEZE_GREEN};font-weight:bold;'>"
                f"✓ {_('Token valid — saved.')}</span>"
            )
        else:
            self._token_status.setText(
                f"<span style='color:{BREEZE_RED};font-weight:bold;'>"
                f"✗ {_('Token invalid.')}</span>"
            )

    def _on_auto_detect(self):
        token = self.ztlib.read_system_token()
        if token:
            self._token_input.setText(token)
        else:
            QMessageBox.warning(
                self, _("Detection Failed"),
                _("Could not read the system token. Is ZeroTier installed?"),
            )

    def _on_start_toggled(self, state: bool):
        self._main_window.on_service_set(1 if state else 2)

    def _on_enable_toggled(self, state: bool):
        self._main_window.on_service_set(3 if state else 4)
