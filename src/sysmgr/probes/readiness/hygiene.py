import asyncio
from datetime import datetime
import os
from pathlib import Path
import time
from typing import Any, Dict, List

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

import psutil

from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class SystemHygieneProbe(BaseProbe):
    """Monitors Windows system hygiene: pending reboot registry flags, continuous uptime, and recent minidump crashes."""

    probe_id = "readiness.hygiene"
    name = "System Hygiene & Reboot State"
    category = "readiness"
    description = (
        "Inspects pending reboot flags across Component-Based Servicing, Windows Update, "
        "and Session Manager, tracks uptime thresholds, and verifies crash dump health."
    )
    requires_admin = False

    def _check_pending_reboots(self) -> List[str]:
        """Checks Windows registry keys indicating pending reboot operations."""
        flags: List[str] = []
        if winreg is None:
            return flags

        sam = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)

        # 1. Component-Based Servicing: RebootPending
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
                0,
                sam,
            ):
                flags.append("Component Based Servicing (RebootPending)")
        except (FileNotFoundError, OSError, PermissionError):
            pass

        # 2. Windows Update: RebootRequired
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
                0,
                sam,
            ):
                flags.append("Windows Update (RebootRequired)")
        except (FileNotFoundError, OSError, PermissionError):
            pass

        # 3. Session Manager: PendingFileRenameOperations
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager",
                0,
                sam,
            ) as key:
                val, _ = winreg.QueryValueEx(key, "PendingFileRenameOperations")
                if val and any(line.strip() for line in val if isinstance(line, str)):
                    flags.append("Session Manager (PendingFileRenameOperations)")
        except (FileNotFoundError, OSError, PermissionError):
            pass

        return flags

    def _get_uptime_days(self) -> float:
        """Calculates system continuous uptime in days."""
        boot_time = psutil.boot_time()
        return (time.time() - boot_time) / 86400.0

    def _check_crash_dumps(self, days: int = 7) -> List[str]:
        """Inspects Minidump directory for crash dumps generated within the specified day window."""
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        minidump_dir = Path(sys_root) / "Minidump"
        if not minidump_dir.exists() or not minidump_dir.is_dir():
            return []

        cutoff = time.time() - (days * 86400)
        dumps: List[str] = []
        try:
            for entry in minidump_dir.iterdir():
                try:
                    if entry.is_file() and entry.suffix.lower() == ".dmp":
                        if entry.stat().st_mtime >= cutoff:
                            dumps.append(entry.name)
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            pass

        return sorted(dumps)

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/readiness/pending-reboot-flags.md"]

        pending_reboots, uptime_days, crash_dumps = await asyncio.gather(
            asyncio.to_thread(self._check_pending_reboots),
            asyncio.to_thread(self._get_uptime_days),
            asyncio.to_thread(self._check_crash_dumps),
        )

        details: Dict[str, Any] = {
            "pending_reboots": pending_reboots,
            "uptime_days": round(uptime_days, 2),
            "recent_crash_dumps": crash_dumps,
        }

        reasons: List[str] = []
        if pending_reboots:
            reasons.append(f"reboot pending ({', '.join(pending_reboots)})")
        if uptime_days > 30.0:
            reasons.append(f"uptime excessive ({uptime_days:.1f} days > 30 days)")
        if crash_dumps:
            reasons.append(f"recent crash dump(s) detected ({', '.join(crash_dumps)})")

        if reasons:
            summary = f"System hygiene warning: {'; '.join(reasons)}."
            remediations = [
                RemediationAction(
                    id="schedule-system-reboot",
                    description="Plan a system restart to clear pending servicing operations and refresh driver states",
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
            summary="System hygiene is clean: zero pending reboots, uptime normal, zero recent crash dumps.",
            details=details,
            remediations=[],
            knowledge_refs=knowledge_refs,
        )
