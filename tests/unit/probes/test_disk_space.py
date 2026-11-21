import asyncio
import pytest
from unittest.mock import patch
from collections import namedtuple
from sysmgr.core.models import DiagnosticStatus, RiskLevel
from sysmgr.probes.storage.disk_space import DiskSpaceProbe

DiskUsage = namedtuple("DiskUsage", ["total", "used", "free", "percent"])
Partition = namedtuple("Partition", ["mountpoint", "device", "fstype"])


def test_disk_space_probe_healthy():
    async def _run():
        probe = DiskSpaceProbe()
        with patch(
            "psutil.disk_partitions",
            return_value=[Partition("C:\\", "C:", "NTFS")],
        ), patch(
            "psutil.disk_usage",
            return_value=DiskUsage(100 * 1024**3, 50 * 1024**3, 50 * 1024**3, 50.0),
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "healthy" in result.summary.lower()
            assert len(result.details["partitions"]) == 1

    asyncio.run(_run())


def test_disk_space_probe_warning_space():
    async def _run():
        probe = DiskSpaceProbe()
        with patch(
            "psutil.disk_partitions",
            return_value=[Partition("C:\\", "C:", "NTFS")],
        ), patch(
            "psutil.disk_usage",
            return_value=DiskUsage(100 * 1024**3, 88 * 1024**3, 12 * 1024**3, 88.0),
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "low disk space" in result.summary.lower()
            assert any(r.id == "clean-temp-files" for r in result.remediations)

    asyncio.run(_run())


def test_disk_space_probe_critical_space():
    async def _run():
        probe = DiskSpaceProbe()
        with patch(
            "psutil.disk_partitions",
            return_value=[Partition("C:\\", "C:", "NTFS")],
        ), patch(
            "psutil.disk_usage",
            return_value=DiskUsage(100 * 1024**3, 97 * 1024**3, 3 * 1024**3, 97.0),
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "critical disk space" in result.summary.lower()
            assert any(r.id == "clean-temp-files" for r in result.remediations)

    asyncio.run(_run())
