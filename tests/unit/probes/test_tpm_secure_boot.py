import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus, RiskLevel
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe


def test_tpm_secure_boot_healthy():
    async def _run():
        probe = TpmSecureBootProbe()
        with patch.object(
            probe,
            "_check_tpm",
            return_value={"present": True, "spec_version": "2.0", "enabled": True, "manufacturer": "INTC"},
        ), patch.object(
            probe,
            "_check_secure_boot",
            return_value={"uefi": True, "secure_boot_enabled": True},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "tpm 2.0 and secure boot are enabled" in result.summary.lower()

    asyncio.run(_run())


def test_tpm_missing_or_disabled():
    async def _run():
        probe = TpmSecureBootProbe()
        with patch.object(
            probe,
            "_check_tpm",
            return_value={"present": False, "spec_version": None, "enabled": False, "manufacturer": None},
        ), patch.object(
            probe,
            "_check_secure_boot",
            return_value={"uefi": True, "secure_boot_enabled": True},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "tpm 2.0" in result.summary.lower()
            assert any(r.id == "enable-tpm-in-bios" for r in result.remediations)

    asyncio.run(_run())


def test_tpm_present_but_secure_boot_disabled():
    async def _run():
        probe = TpmSecureBootProbe()
        with patch.object(
            probe,
            "_check_tpm",
            return_value={"present": True, "spec_version": "2.0", "enabled": True, "manufacturer": "AMD"},
        ), patch.object(
            probe,
            "_check_secure_boot",
            return_value={"uefi": True, "secure_boot_enabled": False},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "secure boot is disabled" in result.summary.lower()
            assert any(r.id == "enable-secure-boot" for r in result.remediations)

    asyncio.run(_run())


def test_legacy_bios_detected():
    async def _run():
        probe = TpmSecureBootProbe()
        with patch.object(
            probe,
            "_check_tpm",
            return_value={"present": True, "spec_version": "2.0", "enabled": True, "manufacturer": "INTC"},
        ), patch.object(
            probe,
            "_check_secure_boot",
            return_value={"uefi": False, "secure_boot_enabled": False},
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "legacy bios" in result.summary.lower()

    asyncio.run(_run())
