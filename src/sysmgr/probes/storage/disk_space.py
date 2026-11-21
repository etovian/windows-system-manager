import psutil
from typing import Any, Dict, List
from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class DiskSpaceProbe(BaseProbe):
    probe_id = "storage.disk_space"
    name = "Storage & Partition Capacity"
    category = "storage"
    description = (
        "Inspects available disk capacity across all active storage partitions, "
        "identifying critical space bottlenecks and cleanup candidates."
    )
    requires_admin = False

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/storage/disk-cleanup-guidelines.md"]
        partitions_data: List[Dict[str, Any]] = []

        overall_status = DiagnosticStatus.PASS
        troubled_partitions: List[str] = []
        is_critical = False

        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception as exc:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary=f"Unable to query disk partitions: {exc}",
                knowledge_refs=knowledge_refs,
            )

        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                free_gb = usage.free / (1024**3)
                total_gb = usage.total / (1024**3)
                part_info = {
                    "mountpoint": part.mountpoint,
                    "device": part.device,
                    "fstype": getattr(part, "fstype", "unknown"),
                    "total_gb": round(total_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "percent_used": usage.percent,
                }
                partitions_data.append(part_info)

                # Evaluate thresholds
                if usage.percent >= 95.0 or free_gb < 3.0:
                    overall_status = DiagnosticStatus.FAIL
                    is_critical = True
                    troubled_partitions.append(f"{part.mountpoint} ({usage.percent}% used, {free_gb:.1f} GB free)")
                elif usage.percent >= 85.0 or free_gb < 10.0:
                    if overall_status != DiagnosticStatus.FAIL:
                        overall_status = DiagnosticStatus.WARN
                    troubled_partitions.append(f"{part.mountpoint} ({usage.percent}% used, {free_gb:.1f} GB free)")
            except (PermissionError, OSError):
                # Drive might be optical, unready, or protected
                continue

        remediations: List[RemediationAction] = []
        if overall_status in (DiagnosticStatus.WARN, DiagnosticStatus.FAIL):
            remediations = [
                RemediationAction(
                    id="clean-temp-files",
                    description="Safely purge temporary files from user and system temp folders",
                    risk_level=RiskLevel.SAFE,
                    requires_admin=False,
                ),
                RemediationAction(
                    id="dism-component-cleanup",
                    description="Run DISM component store cleanup to reclaim space in WinSxS",
                    risk_level=RiskLevel.ELEVATED,
                    requires_admin=True,
                ),
            ]

        if is_critical:
            summary = f"Critical disk space exhaustion on: {', '.join(troubled_partitions)}."
        elif overall_status == DiagnosticStatus.WARN:
            summary = f"Low disk space detected on: {', '.join(troubled_partitions)}."
        else:
            summary = "All disk partitions have healthy free capacity."

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=overall_status,
            summary=summary,
            details={"partitions": partitions_data},
            remediations=remediations,
            knowledge_refs=knowledge_refs,
        )
