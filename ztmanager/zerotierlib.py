import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ZeroTierNetwork:
    COMMANDS = ("start", "stop", "enable", "disable")
    BASE_URL = "http://localhost:9993/"
    PATH = Path(
        os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config" / "ztmanager")
    )
    FILE = "zt.conf"
    SERVICE = "zerotier-one.service"

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token
        self.serviceStatus = None
        self.headers = {"X-ZT1-Auth": f"{api_token}"} if api_token else None
        self.read_token()

    def zt_start(self) -> str:
        try:
            if self.check_token(self.api_token):
                return "OK"
            return "MISSING TOKEN"
        except Exception as e:
            return f"ERROR: {e}"

    def zt_status(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", self.SERVICE],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def is_installed(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "list-unit-files", self.SERVICE],
                capture_output=True, text=True, timeout=5,
            )
            return self.SERVICE in result.stdout
        except Exception:
            return False

    def zt_enable_status(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-enabled", self.SERVICE],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "enabled"
        except Exception:
            return False

    def service(self, setstatus: int) -> bool:
        if setstatus:
            try:
                self.serviceStatus = self.COMMANDS[setstatus - 1]
                self._zt_activate()
                return True
            except Exception as e:
                print(f"Error changing service state: {e}")
                return False
        return False

    def _zt_activate(self):
        cmd_map = {
            "start":   ["systemctl", "start",   self.SERVICE],
            "stop":    ["systemctl", "stop",    self.SERVICE],
            "enable":  ["systemctl", "enable",  self.SERVICE],
            "disable": ["systemctl", "disable", self.SERVICE],
        }
        cmd = cmd_map.get(self.serviceStatus)
        if cmd:
            try:
                subprocess.run(["pkexec"] + cmd, check=False, timeout=30)
            except Exception as e:
                print(f"Service command error: {e}")
        self.serviceStatus = None

    def save_token(self):
        config = {"X-ZT1-Auth": self.api_token}
        configpath = self.PATH / self.FILE
        configpath.parent.mkdir(parents=True, exist_ok=True)
        with open(configpath, "w") as f:
            json.dump(config, f, indent=4)
        os.chmod(configpath, 0o600)

    def read_token(self) -> int:
        configpath = self.PATH / self.FILE
        if not configpath.exists():
            return 404
        with open(configpath, "r") as f:
            config = json.load(f)

        api_token = config.get("X-ZT1-Auth")
        if api_token and self.check_token(api_token):
            self.api_token = api_token
            self.headers = {"X-ZT1-Auth": f"{api_token}"}
            return 200
        return 401

    def check_token(self, api_token: str) -> bool:
        try:
            response = requests.get(
                self.BASE_URL + "status",
                headers={"X-ZT1-Auth": api_token},
                verify=False,
                timeout=5,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Token check error: {e}")
            return False

    def send_request(self, method: str, endpoint: str, data: Optional[dict] = None):
        try:
            url = self.BASE_URL + endpoint
            response = getattr(requests, method)(
                url, headers=self.headers, json=data, verify=False, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None

    def get_networks(self, network: Optional[str] = None):
        endpoint = f"network/{network}" if network else "network"
        result = self.send_request("get", endpoint)
        return result if result is not None else []

    def join_networks(self, network: str):
        return self.send_request("post", f"network/{network}")

    def update_network(self, network: str, config: dict):
        return self.send_request("post", f"network/{network}", config)

    def leave_networks(self, network: str):
        return self.send_request("delete", f"network/{network}")

    def get_peers(self, network: Optional[str] = None):
        endpoint = f"peer/{network}" if network else "peer"
        result = self.send_request("get", endpoint)
        return result if result is not None else []

    def get_network_details(self, network_id: str):
        return self.send_request("get", f"network/{network_id}")

    def delete_network(self, network_id: str):
        return self.send_request("delete", f"network/{network_id}")

    def get_peer_details(self, peer_id: str):
        return self.send_request("get", f"peer/{peer_id}")

    def read_system_token(self) -> Optional[str]:
        token_path = Path("/var/lib/zerotier-one/authtoken.secret")
        try:
            return token_path.read_text().strip()
        except PermissionError:
            pass
        except Exception:
            return None

        try:
            result = subprocess.run(
                ["pkexec", "cat", str(token_path)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None
