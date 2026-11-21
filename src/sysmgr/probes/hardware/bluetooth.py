import subprocess
import json
from typing import Any, Dict, List
from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class BluetoothProbe(BaseProbe):
    probe_id = "hardware.bluetooth"
    name = "Bluetooth Subsystem Diagnostic"
    category = "hardware"
    description = (
        "Inspects Bluetooth radio hardware state, device manager error codes (e.g. Code 43), "
        "and Windows Bluetooth service availability."
    )
    requires_admin = False

    def _query_bluetooth_devices(self) -> List[Dict[str, Any]]:
        """Queries Windows PnP for Bluetooth radios using PowerShell CIM."""
        ps_cmd = (
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.PNPClass -eq 'Bluetooth' -or $_.Service -like '*bth*' } | "
            "Select-Object Name, DeviceID, Status, ConfigManagerErrorCode | "
            "ConvertTo-Json -Compress"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return []
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                data = [data]
            return [
                {
                    "name": d.get("Name", "Unknown"),
                    "device_id": d.get("DeviceID", ""),
                    "status": d.get("Status", "Unknown"),
                    "code": d.get("ConfigManagerErrorCode", 0),
                }
                for d in data
            ]
        except Exception:
            return []

    def _query_bluetooth_service(self) -> Dict[str, Any]:
        """Queries the status of the Bluetooth Support Service (bthserv)."""
        ps_cmd = (
            "Get-Service -Name 'bthserv' -ErrorAction SilentlyContinue | "
            "Select-Object Name, Status, StartType | "
            "ConvertTo-Json -Compress"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return {"name": "bthserv", "status": "Unknown", "start_type": "Unknown"}
            data = json.loads(res.stdout)
            return {
                "name": data.get("Name", "bthserv"),
                "status": str(data.get("Status", "Unknown")),
                "start_type": str(data.get("StartType", "Unknown")),
            }
        except Exception:
            return {"name": "bthserv", "status": "Unknown", "start_type": "Unknown"}

    async def check(self) -> DiagnosticResult:
        devices = self._query_bluetooth_devices()
        service = self._query_bluetooth_service()

        knowledge_refs = ["knowledge/hardware/bluetooth-troubleshooting.md"]
        details = {
            "devices": devices,
            "service": service,
        }

        if not devices:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="No Bluetooth radio hardware detected or radio is powered down.",
                details=details,
                knowledge_refs=knowledge_refs,
            )

        # Check for device hardware or driver errors
        error_devices = [d for d in devices if d.get("code", 0) != 0]
        if error_devices:
            first_err = error_devices[0]
            code = first_err.get("code")
            name = first_err.get("name")
            remediations = [
                RemediationAction(
                    id="restart-bluetooth-service",
                    description="Restart Windows Bluetooth Support Service (bthserv)",
                    risk_level=RiskLevel.SAFE,
                    requires_admin=False,
                ),
                RemediationAction(
                    id="reset-bluetooth-device",
                    description=f"Reset Bluetooth device '{name}' via PnP device restart",
                    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                    requires_admin=True,
                ),
            ]
            summary = (
                f"Bluetooth radio '{name}' reported Code 43 (device failed or crashed)."
                if code == 43
                else f"Bluetooth radio '{name}' reported error Code {code}."
            )
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.FAIL,
                summary=summary,
                details=details,
                remediations=remediations,
                knowledge_refs=knowledge_refs,
            )

        # Check service status
        service_status = service.get("status", "").lower()
        if "running" not in service_status and service_status not in ("ok", "4"):
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary=f"Bluetooth radio hardware is operational, but '{service.get('name')}' service is stopped ({service.get('status')}).",
                details=details,
                remediations=[
                    RemediationAction(
                        id="start-bluetooth-service",
                        description=f"Start the '{service.get('name')}' Windows service",
                        risk_level=RiskLevel.SAFE,
                        requires_admin=False,
                    )
                ],
                knowledge_refs=knowledge_refs,
            )

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="Bluetooth adapter is operational and service is running.",
            details=details,
            knowledge_refs=knowledge_refs,
        )
