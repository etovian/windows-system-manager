import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sysmgr.core.models import (
    DiagnosticReport,
    DiagnosticResult,
    DiagnosticStatus,
)


class BaseProbe:
    """Base class/protocol for all diagnostic probes."""
    probe_id: str
    name: str
    category: str
    description: str
    requires_admin: bool = False

    async def check(self) -> DiagnosticResult:
        raise NotImplementedError("Probes must implement check()")


class ProbeEngine:
    """Coordinates probe registration, concurrent execution, and result aggregation."""

    def __init__(self, probe_timeout_seconds: float = 5.0):
        self.probes: Dict[str, BaseProbe] = {}
        self.timeout = probe_timeout_seconds

    def register(self, probe: BaseProbe) -> None:
        self.probes[probe.probe_id] = probe

    def get_probe(self, probe_id: str) -> Optional[BaseProbe]:
        return self.probes.get(probe_id)

    async def run_probe(self, probe: BaseProbe) -> DiagnosticResult:
        try:
            return await asyncio.wait_for(probe.check(), timeout=self.timeout)
        except asyncio.TimeoutError:
            return DiagnosticResult(
                probe_id=probe.probe_id,
                category=probe.category,
                status=DiagnosticStatus.WARN,
                summary=f"Probe '{probe.name}' timed out after {self.timeout}s.",
                details={"error": "TimeoutError", "timeout_seconds": self.timeout},
            )
        except Exception as exc:
            return DiagnosticResult(
                probe_id=probe.probe_id,
                category=probe.category,
                status=DiagnosticStatus.FAIL,
                summary=f"Probe '{probe.name}' failed with unexpected error: {str(exc)}",
                details={"error": type(exc).__name__, "message": str(exc)},
            )

    async def run_all(self, category: Optional[str] = None) -> DiagnosticReport:
        targets = [
            p for p in self.probes.values()
            if category is None or p.category.lower() == category.lower()
        ]
        results: List[DiagnosticResult] = await asyncio.gather(
            *[self.run_probe(p) for p in targets]
        )

        pass_count = sum(1 for r in results if r.status == DiagnosticStatus.PASS)
        warn_count = sum(1 for r in results if r.status == DiagnosticStatus.WARN)
        fail_count = sum(1 for r in results if r.status == DiagnosticStatus.FAIL)

        # Sort so FAIL and WARN appear first
        severity_rank = {
            DiagnosticStatus.FAIL: 0,
            DiagnosticStatus.WARN: 1,
            DiagnosticStatus.INFO: 2,
            DiagnosticStatus.PASS: 3,
        }
        sorted_results = sorted(results, key=lambda r: severity_rank.get(r.status, 99))

        return DiagnosticReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_probes=len(results),
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            results=sorted_results,
        )
