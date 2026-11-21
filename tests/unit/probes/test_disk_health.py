import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.storage.disk_health import DiskHealthProbe


def test_disk_health_probe_healthy():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(
            probe,
            "_query_physical_disks",
            return_value=[
                {
                    "device_id": "0",
                    "model": "Samsung SSD 980 PRO 1TB",
                    "media_type": "SSD",
                    "status": "OK",
                    "predict_failure": False,
                }
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "healthy" in result.summary.lower()
            assert result.probe_id == "storage.disk_health"
            assert result.category == "storage"

    asyncio.run(_run())


def test_disk_health_probe_predictive_failure():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(
            probe,
            "_query_physical_disks",
            return_value=[
                {
                    "device_id": "1",
                    "model": "Seagate Barracuda 2TB",
                    "media_type": "HDD",
                    "status": "Predictive Failure",
                    "predict_failure": True,
                }
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "predictive failure" in result.summary.lower()
            assert len(result.remediations) > 0
            assert any(r.id == "backup-failing-drive" for r in result.remediations)

    asyncio.run(_run())


def test_disk_health_probe_degraded_drive():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(
            probe,
            "_query_physical_disks",
            return_value=[
                {
                    "device_id": "2",
                    "model": "Crucial MX500",
                    "media_type": "SSD",
                    "status": "Degraded",
                    "predict_failure": False,
                }
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "degraded" in result.summary.lower()

    asyncio.run(_run())


def test_disk_health_probe_query_failure():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(probe, "_query_physical_disks", return_value=None):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "unable to query" in result.summary.lower()

    asyncio.run(_run())
