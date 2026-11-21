import asyncio
import json
import subprocess
from typing import Any, Dict, List, Optional

from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class DeviceManagerProbe(BaseProbe):
    """Probes Windows Device Manager for non-zero Plug and Play (PnP) error codes."""

    probe_id = "hardware.device_manager"
    name = "Device Manager Hardware Audit"
    category = "hardware"
    description = (
        "Audits Windows Plug and Play (PnP) devices for non-zero Configuration Manager error codes."
    )
    requires_admin = False

    def _query_error_devices(self) -> Optional[List[Dict[str, Any]]]:
        """Queries Windows PnP for entities reporting non-zero ConfigManagerErrorCode."""
        ps_cmd = (
            'Get-CimInstance Win32_PnPEntity -Filter "ConfigManagerErrorCode <> 0" | '
            "Select-Object Name, DeviceID, PNPClass, ConfigManagerErrorCode | "
            "ConvertTo-Json -Compress"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if res.returncode != 0:
                return None
            if not res.stdout.strip():
                return []
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                data = [data]
            return [
                {
                    "name": d.get("Name") or "Unknown Device",
                    "device_id": d.get("DeviceID", ""),
                    "pnp_class": d.get("PNPClass", "Unknown"),
                    "code": d.get("ConfigManagerErrorCode", 0),
                }
                for d in data
            ]
        except Exception:
            return None

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/hardware/pnp-error-codes.md"]
        devices = await asyncio.to_thread(self._query_error_devices)

        if devices is None:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="Unable to query Windows PnP subsystem; command failed or timed out.",
                details={"error_devices": [], "total_errors": 0},
                knowledge_refs=knowledge_refs,
            )

        details = {
            "error_devices": devices,
            "total_errors": len(devices),
        }

        if not devices:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.PASS,
                summary="Zero hardware error codes detected across all PnP devices.",
                details=details,
                knowledge_refs=knowledge_refs,
            )

        # Check if all error devices are user-disabled (Code 22)
        all_user_disabled = all(d.get("code") == 22 for d in devices)
        if all_user_disabled:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.INFO,
                summary=(
                    f"Found {len(devices)} non-running device(s); all non-running devices are deliberately disabled by user."
                ),
                details=details,
                knowledge_refs=knowledge_refs,
                remediations=[
                    RemediationAction(
                        id="enable-pnp-device",
                        description="Enable user-disabled PnP device via Device Manager or pnputil",
                        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                        requires_admin=True,
                    )
                ],
            )

        # There are actual hardware / driver errors (code != 22)
        non_disabled = [d for d in devices if d.get("code") != 22]
        device_summaries = [f"{d['name']} (Code {d['code']})" for d in non_disabled]
        summary = (
            f"Detected {len(non_disabled)} hardware device(s) reporting error codes: "
            f"{', '.join(device_summaries)}."
        )

        remediations: List[RemediationAction] = []
        if any(d.get("code") == 43 for d in non_disabled):
            remediations.append(
                RemediationAction(
                    id="restart-pnp-device",
                    description="Restart crashed PnP hardware device via pnputil",
                    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                    requires_admin=True,
                )
            )
        if any(d.get("code") == 28 for d in non_disabled):
            remediations.append(
                RemediationAction(
                    id="install-pnp-driver",
                    description="Scan Windows Update or install missing INF driver package",
                    risk_level=RiskLevel.SAFE,
                    requires_admin=True,
                )
            )
        if any(d.get("code") == 10 for d in non_disabled):
            remediations.append(
                RemediationAction(
                    id="reinstall-device-driver",
                    description="Reinstall device driver or rollback recent driver update",
                    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                    requires_admin=True,
                )
            )
        if not remediations:
            remediations.append(
                RemediationAction(
                    id="inspect-device-manager",
                    description="Review Windows Device Manager properties and system event log",
                    risk_level=RiskLevel.SAFE,
                    requires_admin=False,
                )
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
