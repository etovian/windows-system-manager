import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus, RiskLevel
from sysmgr.probes.hardware.bluetooth import BluetoothProbe


def test_bluetooth_probe_healthy():
    async def _run():
        probe = BluetoothProbe()
        with patch.object(
            probe,
            "_query_bluetooth_devices",
            return_value=[
                {"name": "Intel Wireless Bluetooth", "status": "OK", "code": 0, "device_id": "USB\\VID_8087"}
            ],
        ), patch.object(
            probe,
            "_query_bluetooth_service",
            return_value={"name": "bthserv", "status": "Running", "start_type": "Auto"},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "operational" in result.summary.lower()
            assert result.probe_id == "hardware.bluetooth"
            assert result.category == "hardware"

    asyncio.run(_run())


def test_bluetooth_probe_code_43_detection():
    async def _run():
        probe = BluetoothProbe()
        with patch.object(
            probe,
            "_query_bluetooth_devices",
            return_value=[
                {"name": "Intel Wireless Bluetooth", "status": "Error", "code": 43, "device_id": "USB\\VID_8087"}
            ],
        ), patch.object(
            probe,
            "_query_bluetooth_service",
            return_value={"name": "bthserv", "status": "Running", "start_type": "Auto"},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "code 43" in result.summary.lower()
            assert len(result.remediations) > 0
            assert any(r.id == "reset-bluetooth-device" for r in result.remediations)

    asyncio.run(_run())


def test_bluetooth_probe_service_stopped():
    async def _run():
        probe = BluetoothProbe()
        with patch.object(
            probe,
            "_query_bluetooth_devices",
            return_value=[
                {"name": "Intel Wireless Bluetooth", "status": "OK", "code": 0, "device_id": "USB\\VID_8087"}
            ],
        ), patch.object(
            probe,
            "_query_bluetooth_service",
            return_value={"name": "bthserv", "status": "Stopped", "start_type": "Manual"},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "service is stopped" in result.summary.lower()
            assert any(r.id == "start-bluetooth-service" for r in result.remediations)

    asyncio.run(_run())


def test_bluetooth_probe_no_radio():
    async def _run():
        probe = BluetoothProbe()
        with patch.object(
            probe,
            "_query_bluetooth_devices",
            return_value=[],
        ), patch.object(
            probe,
            "_query_bluetooth_service",
            return_value={"name": "bthserv", "status": "Stopped", "start_type": "Disabled"},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "no bluetooth radio" in result.summary.lower()

    asyncio.run(_run())
