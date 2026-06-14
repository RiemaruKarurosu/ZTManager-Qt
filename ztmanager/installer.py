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
        # install.zerotier.com doesn't recognise "nobara", but Nobara is
        # Fedora-based.  Download the script to /tmp, patch it in-place to
        # add Nobara wherever Fedora appears, then run it.  No system files
        # are touched.
        return r"""set -e
echo "Downloading ZeroTier install script..."
curl -fsS https://install.zerotier.com > /tmp/zt_install.sh

echo "Patching script for Nobara compatibility..."
# After sourcing /etc/os-release, remap nobara → fedora so we enter the RPM branch.
# The install script uses 'source', not '.', so we match that exactly.
sed -i 's/^source \/etc\/os-release/source \/etc\/os-release; [ "$ID" = "nobara" ] \&\& ID=fedora/' /tmp/zt_install.sh
# The inner check reads /etc/redhat-release for "fedora" to pick fc/ vs el/ repos.
# Nobara's /etc/redhat-release says "Nobara release 43", not "Fedora ...", so we
# extend the test to also trust $ID directly (which we just set to "fedora" above).
sed -i 's@\[ -n "`cat /etc/redhat-release 2>/dev/null | grep -i fedora`" \]@[ -n "`cat /etc/redhat-release 2>/dev/null | grep -i fedora`" ] || [ "$ID" = "fedora" ]@g' /tmp/zt_install.sh

echo "Running patched install script..."
bash /tmp/zt_install.sh
rm -f /tmp/zt_install.sh
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
                _("Nobara Linux detected (Fedora-based).\n"
                  "Running official ZeroTier install script — Fedora is supported via ID_LIKE.\n\n")
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
