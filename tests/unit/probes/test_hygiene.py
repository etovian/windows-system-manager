import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.readiness.hygiene import SystemHygieneProbe


def test_hygiene_probe_clean():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(probe, "_check_pending_reboots", return_value=[]), patch.object(
            probe, "_get_uptime_days", return_value=3.5
        ), patch.object(probe, "_check_crash_dumps", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "clean" in result.summary.lower()
            assert result.probe_id == "readiness.hygiene"
            assert result.category == "readiness"

    asyncio.run(_run())


def test_hygiene_probe_reboot_pending():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(
            probe, "_check_pending_reboots", return_value=["Component Based Servicing (RebootPending)"]
        ), patch.object(probe, "_get_uptime_days", return_value=5.0), patch.object(
            probe, "_check_crash_dumps", return_value=[]
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "reboot pending" in result.summary.lower()
            assert len(result.remediations) > 0
            assert any(r.id == "schedule-system-reboot" for r in result.remediations)

    asyncio.run(_run())


def test_hygiene_probe_long_uptime():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(probe, "_check_pending_reboots", return_value=[]), patch.object(
            probe, "_get_uptime_days", return_value=45.0
        ), patch.object(probe, "_check_crash_dumps", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "45" in result.summary.lower()
            assert any(r.id == "schedule-system-reboot" for r in result.remediations)

    asyncio.run(_run())


def test_hygiene_probe_recent_crash_dump():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(probe, "_check_pending_reboots", return_value=[]), patch.object(
            probe, "_get_uptime_days", return_value=2.0
        ), patch.object(probe, "_check_crash_dumps", return_value=["052126-12345-01.dmp"]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "crash dump" in result.summary.lower()

    asyncio.run(_run())
