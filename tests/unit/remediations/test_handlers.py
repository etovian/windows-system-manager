import os
import time
import pytest
from unittest.mock import MagicMock
from sysmgr.remediations.models import RemediationContext
from sysmgr.remediations.registry import default_remediation_registry
import sysmgr.remediations.handlers  # noqa: F401


@pytest.mark.asyncio
async def test_flush_dns_cache_handler(monkeypatch):
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("flush-dns-cache")
    assert handler_entry is not None
    assert handler_entry.parent_probe_id == "hardware.network"

    # Live run
    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("Flushed DNS" in c for c in changes)
    mock_run.assert_called_once_with(
        ["ipconfig", "/flushdns"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Dry run
    mock_run.reset_mock()
    ctx_dry = RemediationContext(dry_run=True)
    changes_dry = await handler_entry.handler(ctx_dry)
    assert any("Dry Run" in c for c in changes_dry)
    assert not mock_run.called


@pytest.mark.asyncio
async def test_renew_dhcp_lease_handler(monkeypatch):
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("renew-dhcp-lease")
    assert handler_entry is not None

    # Live run
    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("DHCP" in c for c in changes)
    mock_run.assert_called_once_with(
        ["ipconfig", "/renew"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Dry run
    mock_run.reset_mock()
    ctx_dry = RemediationContext(dry_run=True)
    changes_dry = await handler_entry.handler(ctx_dry)
    assert any("Dry Run" in c for c in changes_dry)
    assert not mock_run.called


@pytest.mark.asyncio
async def test_bluetooth_service_handler_and_rollback(monkeypatch):
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("start-bluetooth-service")
    assert handler_entry is not None
    assert handler_entry.parent_probe_id == "hardware.bluetooth"

    # Live run
    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("Started Windows Bluetooth" in c for c in changes)
    mock_run.assert_called_once_with(
        ["powershell", "-NoProfile", "-Command", "Start-Service -Name bthserv -ErrorAction Stop"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )

    # Dry run
    ctx_dry = RemediationContext(dry_run=True)
    changes_dry = await handler_entry.handler(ctx_dry)
    assert any("Dry Run" in c for c in changes_dry)

    # Test rollback generator
    assert handler_entry.rollback_generator is not None
    plan = await handler_entry.rollback_generator()
    assert plan.action_id == "start-bluetooth-service"
    assert any("sc.exe" in inst for inst in plan.safe_mode_instructions)


@pytest.mark.asyncio
async def test_bluetooth_rollback_with_json_output(monkeypatch):
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout='{"Status": 1, "StartType": 3}',
        )
    )
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("start-bluetooth-service")
    assert handler_entry is not None
    assert handler_entry.rollback_generator is not None

    plan = await handler_entry.rollback_generator()
    assert plan.pre_state.get("Status") == 1
    assert plan.pre_state.get("StartType") == 3


@pytest.mark.asyncio
async def test_clean_temp_files_handler_and_rollback(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    old_file = temp_dir / "old.tmp"
    old_file.write_text("old data")
    # Set modification time to 2 days ago
    two_days_ago = time.time() - (48 * 3600)
    os.utime(old_file, (two_days_ago, two_days_ago))

    new_file = temp_dir / "new.tmp"
    new_file.write_text("new data")

    monkeypatch.setenv("TEMP", str(temp_dir))

    handler_entry = default_remediation_registry.get("clean-temp-files")
    assert handler_entry is not None
    assert handler_entry.parent_probe_id == "storage.disk_space"

    # Test dry run first
    ctx_dry = RemediationContext(dry_run=True)
    dry_changes = await handler_entry.handler(ctx_dry)
    assert any("Dry Run" in c for c in dry_changes)
    assert old_file.exists()
    assert new_file.exists()

    # Live run
    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("Cleaned" in c for c in changes)
    assert not old_file.exists()
    assert new_file.exists()

    # Test rollback plan
    assert handler_entry.rollback_generator is not None
    plan = await handler_entry.rollback_generator()
    assert plan.action_id == "clean-temp-files"


@pytest.mark.asyncio
async def test_clean_temp_files_missing_or_empty_temp(monkeypatch):
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("TMP", raising=False)

    handler_entry = default_remediation_registry.get("clean-temp-files")
    assert handler_entry is not None

    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("No TEMP or TMP" in c for c in changes)

    monkeypatch.setenv("TEMP", "C:\\nonexistent_temp_directory_xyz")
    changes_missing = await handler_entry.handler(ctx)
    assert any("does not exist" in c for c in changes_missing)


@pytest.mark.asyncio
async def test_clean_temp_files_skips_locked_files(tmp_path, monkeypatch):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    locked_file = temp_dir / "locked.tmp"
    locked_file.write_text("locked")
    two_days_ago = time.time() - (48 * 3600)
    os.utime(locked_file, (two_days_ago, two_days_ago))

    monkeypatch.setenv("TEMP", str(temp_dir))

    # Mock unlink to simulate a locked file raising PermissionError
    orig_unlink = os.unlink

    def mock_unlink(path):
        if "locked.tmp" in str(path):
            raise PermissionError("Access denied / file locked")
        return orig_unlink(path)

    monkeypatch.setattr(os, "unlink", mock_unlink)

    handler_entry = default_remediation_registry.get("clean-temp-files")
    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)

    # Remediation should gracefully skip the locked file without crashing
    assert any("Cleaned 0 temporary files" in c for c in changes)
    assert locked_file.exists()


@pytest.mark.asyncio
async def test_firmware_guidance_handlers():
    tpm_entry = default_remediation_registry.get("enable-tpm-in-bios")
    assert tpm_entry is not None
    assert tpm_entry.parent_probe_id == "readiness.tpm_secure_boot"

    ctx = RemediationContext()
    tpm_changes = await tpm_entry.handler(ctx)
    assert any("UEFI/BIOS" in c for c in tpm_changes)

    sb_entry = default_remediation_registry.get("enable-secure-boot")
    assert sb_entry is not None
    sb_changes = await sb_entry.handler(ctx)
    assert any("Secure Boot" in c for c in sb_changes)
