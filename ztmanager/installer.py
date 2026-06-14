import subprocess
import threading

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from . import _


def _get_os_info() -> dict:
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k] = v.strip('"')
    except Exception:
        pass
    return info


def _build_install_script(os_id: str) -> str:
    if os_id == "nobara":
        # Write the .repo file inline so we never depend on download.zerotier.com/redhat/zerotier.repo
        # ($releasever and $basearch are DNF variables, not shell variables — use 'REPOEOF' to prevent expansion)
        return r"""set -e
echo "Importing ZeroTier GPG key..."
rpm --import https://raw.githubusercontent.com/zerotier/ZeroTierOne/main/doc/contact%40zerotier.com.gpg

echo "Writing ZeroTier repository file..."
cat > /etc/yum.repos.d/zerotier.repo << 'REPOEOF'
[zerotier]
name=ZeroTier Package Repository
baseurl=https://download.zerotier.com/redhat/fc/$releasever/$basearch/
enabled=1
gpgcheck=1
gpgkey=https://raw.githubusercontent.com/zerotier/ZeroTierOne/main/doc/contact%40zerotier.com.gpg
REPOEOF

echo "Installing zerotier-one via dnf..."
dnf install -y zerotier-one || {
    echo "Fedora path failed, trying RHEL9 fallback..."
    sed -i 's|fc/$releasever|el/9|g' /etc/yum.repos.d/zerotier.repo
    dnf install -y zerotier-one
}

echo "Enabling and starting zerotier-one service..."
systemctl enable zerotier-one
systemctl start zerotier-one
echo "Installation complete!"
"""
    return "curl -s https://install.zerotier.com | bash"


class _WorkerSignals(QObject):
    output_ready = Signal(str)
    done = Signal(int)


class ZeroTierInstallerDialog(QDialog):
    def __init__(self, parent=None, on_install_complete=None):
        super().__init__(parent)
        self.setWindowTitle(_("Install ZeroTier One"))
        self.setMinimumSize(640, 460)
        self.on_install_complete = on_install_complete
        self._process = None
        self._signals = _WorkerSignals()
        self._signals.output_ready.connect(self._append_output)
        self._signals.done.connect(self._on_done)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        os_info = _get_os_info()
        self._os_id = os_info.get("ID", "").lower()
        os_name = os_info.get("NAME", _("Unknown OS"))

        if self._os_id == "nobara":
            os_text = _("Detected: {} — Nobara patch will be applied (Fedora RPM path)").format(os_name)
        else:
            os_text = _("Detected: {}").format(os_name)

        os_label = QLabel(os_text)
        os_label.setProperty("class", "subtitle")
        layout.addWidget(os_label)

        self.status_label = QLabel(_("Click Install to begin."))
        layout.addWidget(self.status_label)

        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)
        self.output_view.setFont(mono)
        self.output_view.setMinimumHeight(280)
        layout.addWidget(self.output_view, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)

        self.install_btn = QPushButton(_("Install"))
        self.install_btn.setDefault(True)
        self.install_btn.setObjectName("suggestedButton")
        self.install_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self.install_btn)

        layout.addLayout(btn_row)

    def _on_install(self):
        self.install_btn.setEnabled(False)
        self.output_view.clear()

        script = _build_install_script(self._os_id)

        if self._os_id == "nobara":
            self._append_output(
                _(
                    "Nobara Linux detected.\n"
                    "The official install script does not support Nobara, so ZT Manager\n"
                    "will add the Fedora ZeroTier RPM repository and install via dnf.\n\n"
                )
            )
        else:
            self._append_output(_("Running official ZeroTier install script...\n\n"))

        self.status_label.setText(_("Installing ZeroTier One — please wait..."))
        threading.Thread(target=self._run_install, args=(script,), daemon=True).start()

    def _run_install(self, script: str):
        try:
            self._process = subprocess.Popen(
                ["pkexec", "bash", "-c", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in iter(self._process.stdout.readline, ""):
                self._signals.output_ready.emit(line)
            self._process.stdout.close()
            self._process.wait()
            self._signals.done.emit(self._process.returncode)
        except Exception as e:
            self._signals.output_ready.emit(f"\n{_('Error')}: {e}\n")
            self._signals.done.emit(1)

    def _append_output(self, text: str):
        self.output_view.moveCursor(self.output_view.textCursor().MoveOperation.End)
        self.output_view.insertPlainText(text)
        self.output_view.ensureCursorVisible()

    def _on_done(self, returncode: int):
        self._process = None
        if returncode == 0:
            self.status_label.setText(_("ZeroTier One installed successfully!"))
            self._append_output(_("\n✓ Done. You can now close this window.\n"))
            self.install_btn.setText(_("Close"))
            self.install_btn.setEnabled(True)
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self.close)
            if self.on_install_complete:
                self.on_install_complete()
        else:
            self.status_label.setText(
                _("Installation failed (exit code: {code})").format(code=returncode)
            )
            self.install_btn.setText(_("Retry"))
            self.install_btn.setEnabled(True)

    def _on_cancel(self):
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        self.close()
