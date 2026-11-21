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


class DiskHealthProbe(BaseProbe):
    """Monitors physical storage drives for SMART predictive failures and operational health."""

    probe_id = "storage.disk_health"
    name = "Physical Disk SMART & Hardware Health"
    category = "storage"
    description = (
        "Inspects physical storage drives for SMART predictive failure alerts, "
        "hardware degradation, and controller communication errors."
    )
    requires_admin = False

    def _query_physical_disks(self) -> Optional[List[Dict[str, Any]]]:
        """Queries physical storage drives using Get-PhysicalDisk and MSStorageDriver_FailurePredictStatus."""
        ps_cmd = (
            "try { "
            "  $smartPredict = $false; "
            "  try { "
            "    $wmi = Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue; "
            "    if ($wmi -and ($wmi | Where-Object { $_.PredictFailure -eq $true })) { $smartPredict = $true; } "
            "  } catch {} "
            "  $disks = Get-PhysicalDisk -ErrorAction Stop; "
            "  $results = @(); "
            "  foreach ($d in $disks) { "
            "    $predictFailure = $false; "
            "    if (($d.OperationalStatus -contains 'Predictive Failure') -or $smartPredict) { $predictFailure = $true } "
            "    $results += [PSCustomObject]@{ "
            "      DeviceId = [string]$d.DeviceId; "
            "      Model = [string]$d.FriendlyName; "
            "      MediaType = [string]$d.MediaType; "
            "      Status = [string]($d.OperationalStatus -join ', '); "
            "      PredictFailure = [bool]$predictFailure; "
            "    }; "
            "  } "
            "  $results | ConvertTo-Json -Compress "
            "} catch { "
            "  exit 1 "
            "}"
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
                    "device_id": str(d.get("DeviceId", "")),
                    "model": d.get("Model", "Unknown"),
                    "media_type": d.get("MediaType", "Unknown"),
                    "status": d.get("Status", "Unknown"),
                    "predict_failure": bool(d.get("PredictFailure", False)),
                }
                for d in data
            ]
        except Exception:
            return None

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/storage/smart-health-monitoring.md"]
        disks = await asyncio.to_thread(self._query_physical_disks)

        if disks is None:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="Unable to query physical disk SMART status; command failed or timed out.",
                details={"disks": []},
                remediations=[],
                knowledge_refs=knowledge_refs,
            )

        failing_disks: List[str] = []
        degraded_disks: List[str] = []

        for disk in disks:
            status_str = str(disk.get("status", "")).lower()
            predict_failure = bool(disk.get("predict_failure", False))
            model = disk.get("model") or disk.get("device_id") or "Unknown Disk"

            if predict_failure or any(
                err in status_str
                for err in ("predictive failure", "error", "lost communication")
            ):
                failing_disks.append(
                    f"{model} (Status: {disk.get('status')}, PredictFailure: {predict_failure})"
                )
            elif any(warn in status_str for warn in ("degraded", "warning")):
                degraded_disks.append(f"{model} (Status: {disk.get('status')})")

        if failing_disks:
            remediations = [
                RemediationAction(
                    id="backup-failing-drive",
                    description="Immediately backup critical data from failing physical drive",
                    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                    requires_admin=False,
                ),
                RemediationAction(
                    id="plan-drive-replacement",
                    description="Plan replacement for failing physical storage drive",
                    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
                    requires_admin=False,
                ),
            ]
            summary = (
                f"Physical disk predictive failure detected on: {', '.join(failing_disks)}."
            )
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.FAIL,
                summary=summary,
                details={"disks": disks},
                remediations=remediations,
                knowledge_refs=knowledge_refs,
            )

        if degraded_disks:
            summary = (
                f"Degraded physical disk status detected on: {', '.join(degraded_disks)}."
            )
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary=summary,
                details={"disks": disks},
                remediations=[],
                knowledge_refs=knowledge_refs,
            )

        if not disks:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.INFO,
                summary="No physical storage drives detected.",
                details={"disks": []},
                remediations=[],
                knowledge_refs=knowledge_refs,
            )

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="All physical storage drives are healthy with zero SMART failure predictions.",
            details={"disks": disks},
            remediations=[],
            knowledge_refs=knowledge_refs,
        )
