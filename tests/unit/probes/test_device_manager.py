import asyncio
import pytest
from unittest.mock import patch, MagicMock
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.hardware.device_manager import DeviceManagerProbe


def test_device_manager_probe_all_healthy():
    async def _run():
        probe = DeviceManagerProbe()
        with patch.object(probe, "_query_error_devices", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "zero hardware error codes" in result.summary.lower()
            assert result.probe_id == "hardware.device_manager"

    asyncio.run(_run())


def test_device_manager_probe_hardware_crash():
    async def _run():
        probe = DeviceManagerProbe()
        mock_devices = [
            {
                "name": "NVIDIA GeForce RTX",
                "device_id": "PCI\\VEN_10DE",
                "pnp_class": "Display",
                "code": 43,
            }
        ]
        with patch.object(probe, "_query_error_devices", return_value=mock_devices):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "nvidia geforce rtx" in result.summary.lower()
            assert "code 43" in result.summary.lower()
            assert len(result.details["error_devices"]) == 1

    asyncio.run(_run())


def test_device_manager_probe_user_disabled_device():
    async def _run():
        probe = DeviceManagerProbe()
        mock_devices = [
            {
                "name": "Virtual Audio Device",
                "device_id": "ROOT\\MEDIA",
                "pnp_class": "Media",
                "code": 22,
            }
        ]
        with patch.object(probe, "_query_error_devices", return_value=mock_devices):
            result = await probe.check()
            assert result.status == DiagnosticStatus.INFO
            assert "disabled by user" in result.summary.lower()

    asyncio.run(_run())


def test_device_manager_query_error_devices_parsing():
    probe = DeviceManagerProbe()
    mock_json = (
        '[{"Name": "Test Device", "DeviceID": "PCI\\\\VEN_1234", "PNPClass": "System", "ConfigManagerErrorCode": 10}]'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_json)
        devices = probe._query_error_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "Test Device"
        assert devices[0]["code"] == 10
        assert devices[0]["pnp_class"] == "System"


def test_device_manager_query_error_devices_single_object():
    probe = DeviceManagerProbe()
    mock_json = '{"Name": "Single Device", "DeviceID": "USB\\\\VID_5678", "PNPClass": "USB", "ConfigManagerErrorCode": 28}'
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_json)
        devices = probe._query_error_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "Single Device"
        assert devices[0]["code"] == 28


def test_device_manager_query_error_devices_failure():
    probe = DeviceManagerProbe()
    with patch("subprocess.run", side_effect=Exception("Timeout")):
        devices = probe._query_error_devices()
        assert devices == []
