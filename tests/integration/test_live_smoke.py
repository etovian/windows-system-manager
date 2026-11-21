import pytest
from sysmgr.probes import create_default_engine
from sysmgr.probes.hardware.bluetooth import BluetoothProbe
from sysmgr.probes.hardware.device_manager import DeviceManagerProbe
from sysmgr.probes.hardware.network import NetworkAdapterProbe
from sysmgr.probes.storage.disk_space import DiskSpaceProbe
from sysmgr.probes.storage.disk_health import DiskHealthProbe
from sysmgr.probes.storage.disk_performance import DiskPerformanceProbe
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe
from sysmgr.probes.readiness.hygiene import SystemHygieneProbe
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


@pytest.mark.asyncio
async def test_live_device_manager_on_host():
    probe = DeviceManagerProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL, DiagnosticStatus.INFO)
    assert result.probe_id == "hardware.device_manager"


@pytest.mark.asyncio
async def test_live_network_adapter_on_host():
    probe = NetworkAdapterProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL)
    assert "interfaces" in result.details
    assert "dns_resolution" in result.details


@pytest.mark.asyncio
async def test_live_disk_health_on_host():
    probe = DiskHealthProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL, DiagnosticStatus.INFO)
    assert "disks" in result.details


@pytest.mark.asyncio
async def test_live_disk_performance_on_host():
    probe = DiskPerformanceProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN)
    assert "top_processes" in result.details


@pytest.mark.asyncio
async def test_live_system_hygiene_on_host():
    probe = SystemHygieneProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN)
    assert "uptime_days" in result.details
    assert "pending_reboots" in result.details
    assert "recent_crash_dumps" in result.details


@pytest.mark.asyncio
async def test_live_full_default_engine_doctor():
    engine = create_default_engine()
    assert len(engine.probes) == 8
    report = await engine.run_all()
    assert report.total_probes == 8
    assert len(report.results) == 8
    # Validate report serialization
    json_data = report.model_dump_json()
    assert len(json_data) > 100
