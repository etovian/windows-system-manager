import pytest
from sysmgr.probes.storage.disk_space import DiskSpaceProbe
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe
from sysmgr.probes.hardware.bluetooth import BluetoothProbe
from sysmgr.core.models import DiagnosticStatus


@pytest.mark.asyncio
async def test_live_disk_space_on_host():
    probe = DiskSpaceProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL)
    assert "partitions" in result.details
    assert len(result.details["partitions"]) > 0


@pytest.mark.asyncio
async def test_live_tpm_secure_boot_on_host():
    probe = TpmSecureBootProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL)
    assert "tpm" in result.details
    assert "firmware" in result.details


@pytest.mark.asyncio
async def test_live_bluetooth_on_host():
    probe = BluetoothProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL)
    assert "devices" in result.details
    assert "service" in result.details
