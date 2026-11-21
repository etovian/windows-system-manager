import asyncio
from unittest.mock import MagicMock, patch
import pytest
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.storage.disk_performance import DiskPerformanceProbe


def test_disk_performance_probe_normal():
    async def _run():
        probe = DiskPerformanceProbe()
        with patch.object(
            probe,
            "_get_io_counters",
            return_value={"read_bytes": 10_000_000, "write_bytes": 5_000_000, "read_count": 500, "write_count": 300},
        ), patch.object(
            probe,
            "_get_top_io_processes",
            return_value=[{"pid": 100, "name": "explorer.exe", "read_mb": 5.0, "write_mb": 2.0, "total_mb": 7.0}],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "normal" in result.summary.lower()
            assert result.probe_id == "storage.disk_performance"
            assert result.category == "storage"
            assert len(result.details["top_processes"]) == 1

    asyncio.run(_run())


def test_disk_performance_probe_heavy_io_saturation():
    async def _run():
        probe = DiskPerformanceProbe()
        # High I/O volume and heavy top consumer
        with patch.object(
            probe,
            "_get_io_counters",
            return_value={"read_bytes": 200_000_000_000, "write_bytes": 150_000_000_000, "read_count": 50000, "write_count": 30000},
        ), patch.object(
            probe,
            "_get_top_io_processes",
            return_value=[
                {"pid": 2000, "name": "runaway_logger.exe", "read_mb": 100.0, "write_mb": 150000.0, "total_mb": 150100.0}
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "heavy disk i/o" in result.summary.lower() or "saturation" in result.summary.lower()
            assert "runaway_logger.exe" in result.summary.lower()
            assert len(result.remediations) > 0

    asyncio.run(_run())


def test_disk_performance_probe_empty_counters():
    async def _run():
        probe = DiskPerformanceProbe()
        with patch.object(probe, "_get_io_counters", return_value=None):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "unable to retrieve" in result.summary.lower()

    asyncio.run(_run())


def test_disk_performance_probe_helpers():
    probe = DiskPerformanceProbe()

    # Test _get_io_counters with mock psutil
    mock_counters = MagicMock()
    mock_counters.read_bytes = 1000
    mock_counters.write_bytes = 2000
    mock_counters.read_count = 10
    mock_counters.write_count = 20

    with patch("psutil.disk_io_counters", return_value=mock_counters):
        counters = probe._get_io_counters()
        assert counters == {
            "read_bytes": 1000,
            "write_bytes": 2000,
            "read_count": 10,
            "write_count": 20,
        }

    with patch("psutil.disk_io_counters", side_effect=Exception("I/O error")):
        assert probe._get_io_counters() is None

    # Test _get_top_io_processes
    mock_proc1 = {
        "pid": 1,
        "name": "system",
        "io_counters": MagicMock(read_bytes=10 * 1024 * 1024, write_bytes=5 * 1024 * 1024),
    }
    mock_proc2 = {
        "pid": 2,
        "name": "app.exe",
        "io_counters": MagicMock(read_bytes=100 * 1024 * 1024, write_bytes=200 * 1024 * 1024),
    }
    mock_proc3 = {
        "pid": 3,
        "name": "no_io",
        "io_counters": None,
    }

    with patch("psutil.process_iter", return_value=[mock_proc1, mock_proc2, mock_proc3]):
        procs = probe._get_top_io_processes(limit=2)
        assert len(procs) == 2
        assert procs[0]["name"] == "app.exe"
        assert procs[0]["total_mb"] == 300.0
        assert procs[1]["name"] == "system"
        assert procs[1]["total_mb"] == 15.0
