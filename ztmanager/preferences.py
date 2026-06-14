from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .window import ToggleSwitch
from .zerotierlib import ZeroTierNetwork
from . import _


class PreferencesDialog(QDialog):
    def __init__(self, parent, ztlib: ZeroTierNetwork):
        super().__init__(parent)
        self.setWindowTitle(_("Preferences — ZT Manager"))
        self.setMinimumWidth(440)
        self.ztlib = ztlib
        self._main_window = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        layout.addWidget(self._build_auth_group())
        layout.addWidget(self._build_service_group())
        layout.addStretch()

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    # ── Auth group ────────────────────────────────────────────────────────────

    def _build_auth_group(self) -> QGroupBox:
        group = QGroupBox(_("Authentication"))
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Token input row
        token_row = QHBoxLayout()

        icon_lbl = QLabel()
        icon_lbl.setPixmap(QIcon.fromTheme("dialog-password").pixmap(QSize(20, 20)))
        token_row.addWidget(icon_lbl)

        self._token_input = QLineEdit()
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setPlaceholderText(_("X-ZT1-Auth Token"))
        self._token_input.setClearButtonEnabled(True)
        if self.ztlib.api_token:
            self._token_input.setText(self.ztlib.api_token)
        self._token_input.textChanged.connect(self._on_token_changed)
        token_row.addWidget(self._token_input, 1)

        show_btn = QPushButton()
        show_btn.setIcon(QIcon.fromTheme("view-visible"))
        show_btn.setCheckable(True)
        show_btn.setFixedSize(30, 30)
        show_btn.setFlat(True)
        show_btn.setToolTip(_("Show / hide token"))
        show_btn.toggled.connect(
            lambda on: self._token_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        token_row.addWidget(show_btn)
        layout.addLayout(token_row)

        # Auto-detect row
        detect_row = QHBoxLayout()

        detect_text = QVBoxLayout()
        detect_text.setSpacing(2)
        detect_text.addWidget(QLabel(f"<b>{_('Auto-detect Token')}</b>"))
        hint = QLabel(_("Read from /var/lib/zerotier-one/authtoken.secret"))
        hint.setObjectName("SubtitleLabel")
        detect_text.addWidget(hint)
        detect_row.addLayout(detect_text, 1)

        detect_btn = QPushButton(_("Detect"))
        detect_btn.clicked.connect(self._on_auto_detect)
        detect_row.addWidget(detect_btn)
        layout.addLayout(detect_row)

        return group

    # ── Service group ─────────────────────────────────────────────────────────

    def _build_service_group(self) -> QGroupBox:
        group = QGroupBox(_("ZeroTier Service"))
        layout = QVBoxLayout(group)
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
        self._add_toggle_row(
            layout,
            _("Start on boot"),
            _("Automatically start ZeroTier when the system boots"),
            is_enabled,
            self._on_enable_toggled,
        )
        return group

    def _add_toggle_row(self, parent_layout, title, subtitle, state, callback):
        row = QHBoxLayout()

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(QLabel(f"<b>{title}</b>"))
        sub = QLabel(subtitle)
        sub.setObjectName("SubtitleLabel")
        text.addWidget(sub)
        row.addLayout(text, 1)

        toggle = ToggleSwitch()
        toggle.setChecked(state)
        toggle.toggled.connect(callback)
        row.addWidget(toggle)

        parent_layout.addLayout(row)

    # ── Signal handlers ────────────────────────────────────────────────────────

    def _on_token_changed(self, text: str):
        token = text.strip()
        if not token:
            self._status_label.clear()
            return
        if self.ztlib.check_token(token):
            self.ztlib.api_token = token
            self.ztlib.headers = {"X-ZT1-Auth": token}
            self.ztlib.save_token()
            self._status_label.setText(
                f"<font color='green'>{_('Token valid — saved.')}</font>"
            )
        else:
            self._status_label.setText(
                f"<font color='red'>{_('Token invalid.')}</font>"
            )

    def _on_auto_detect(self):
        token = self.ztlib.read_system_token()
        if token:
            self._token_input.setText(token)
        else:
            QMessageBox.warning(
                self,
                _("Detection Failed"),
                _("Could not read the system token. Is ZeroTier installed?"),
            )

    def _on_start_toggled(self, state: bool):
        self._main_window.on_service_set(1 if state else 2)

    def _on_enable_toggled(self, state: bool):
        self._main_window.on_service_set(3 if state else 4)
