import asyncio
import os
import time
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
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


def test_hygiene_probe_multi_issue():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(
            probe, "_check_pending_reboots", return_value=["Windows Update (RebootRequired)"]
        ), patch.object(probe, "_get_uptime_days", return_value=35.0), patch.object(
            probe, "_check_crash_dumps", return_value=["recent.dmp"]
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "reboot pending" in result.summary.lower()
            assert "crash dump" in result.summary.lower()
            assert "35" in result.summary.lower()

    asyncio.run(_run())


def test_check_crash_dumps_filtering(tmp_path: Path):
    probe = SystemHygieneProbe()
    minidump_dir = tmp_path / "Minidump"
    minidump_dir.mkdir()

    # Create recent .dmp file
    recent_dump = minidump_dir / "recent.dmp"
    recent_dump.write_text("dump content")

    # Create non-dmp file
    other_file = minidump_dir / "notes.txt"
    other_file.write_text("text content")

    with patch.dict(os.environ, {"SystemRoot": str(tmp_path)}):
        dumps = probe._check_crash_dumps(days=7)
        assert len(dumps) == 1
        assert dumps[0] == "recent.dmp"


def test_get_uptime_days_calculation():
    probe = SystemHygieneProbe()
    with patch("psutil.boot_time", return_value=time.time() - 86400 * 2):
        days = probe._get_uptime_days()
        assert 1.95 <= days <= 2.05
