import asyncio
from typing import Any, Dict, List, Optional
import psutil

from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class DiskPerformanceProbe(BaseProbe):
    probe_id = "storage.disk_performance"
    name = "Disk I/O Throughput & Performance"
    category = "storage"
    description = (
        "Monitors disk read/write throughput and identifies top I/O consuming processes "
        "to detect bottlenecks, runaway background services, and storage saturation."
    )
    requires_admin = False

    def _get_io_counters(self) -> Optional[Dict[str, Any]]:
        """Retrieve system-wide cumulative disk I/O counters."""
        try:
            counters = psutil.disk_io_counters()
            if counters is None:
                return None
            return {
                "read_bytes": getattr(counters, "read_bytes", 0),
                "write_bytes": getattr(counters, "write_bytes", 0),
                "read_count": getattr(counters, "read_count", 0),
                "write_count": getattr(counters, "write_count", 0),
            }
        except Exception:
            return None

    def _get_top_io_processes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Identify top processes by cumulative I/O bytes."""
        procs: List[Dict[str, Any]] = []

        try:
            for p in psutil.process_iter(["pid", "name", "io_counters"]):
                try:
                    info = p.info if hasattr(p, "info") and isinstance(p.info, dict) else (p if isinstance(p, dict) else {})
                    io = info.get("io_counters")
                    if not io:
                        continue

                    read_bytes = getattr(io, "read_bytes", 0) if not isinstance(io, dict) else io.get("read_bytes", 0)
                    write_bytes = getattr(io, "write_bytes", 0) if not isinstance(io, dict) else io.get("write_bytes", 0)
                    total_bytes = read_bytes + write_bytes

                    procs.append({
                        "pid": info.get("pid"),
                        "name": info.get("name") or "unknown",
                        "read_bytes": read_bytes,
                        "write_bytes": write_bytes,
                        "total_bytes": total_bytes,
                        "read_mb": round(read_bytes / (1024 * 1024), 1),
                        "write_mb": round(write_bytes / (1024 * 1024), 1),
                        "total_mb": round(total_bytes / (1024 * 1024), 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            return []

        # Sort descending by total bytes transferred
        procs.sort(key=lambda x: x["total_bytes"], reverse=True)

        # Drop raw total_bytes internal key and slice to limit
        return [
            {
                "pid": p["pid"],
                "name": p["name"],
                "read_mb": p["read_mb"],
                "write_mb": p["write_mb"],
                "total_mb": p["total_mb"],
            }
            for p in procs[:limit]
        ]

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/storage/disk-io-bottlenecks.md"]

        counters = await asyncio.to_thread(self._get_io_counters)
        top_processes = await asyncio.to_thread(self._get_top_io_processes)

        if counters is None:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="Unable to retrieve system disk I/O performance counters.",
                details={"top_processes": top_processes},
                knowledge_refs=knowledge_refs,
            )

        details = {
            "io_counters": counters,
            "top_processes": top_processes,
        }

        # Threshold evaluation: Check if any process has excessive cumulative I/O (> 100,000 MB / 100 GB)
        high_io_procs = [p for p in top_processes if p["total_mb"] > 100_000.0]

        if high_io_procs:
            top_proc = high_io_procs[0]
            summary = (
                f"Heavy disk I/O activity detected, led by '{top_proc['name']}' "
                f"(PID {top_proc['pid']}) with {top_proc['total_mb']:.1f} MB total I/O."
            )
            remediations = [
                RemediationAction(
                    id="inspect-io-process",
                    description=f"Inspect high-I/O process '{top_proc['name']}' (PID {top_proc['pid']})",
                    risk_level=RiskLevel.SAFE,
                    requires_admin=False,
                )
            ]
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary=summary,
                details=details,
                remediations=remediations,
                knowledge_refs=knowledge_refs,
            )

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="Disk I/O throughput is operating within normal baseline limits.",
            details=details,
            remediations=[],
            knowledge_refs=knowledge_refs,
        )
