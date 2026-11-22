import json
import os
import time
from pathlib import Path
import pytest
from typer.testing import CliRunner

from sysmgr.cli import app
from sysmgr.remediations import RemediationRunner, default_remediation_registry
from sysmgr.remediations.models import RemediationContext, RemediationScope, RollbackPlan
from sysmgr.remediations.rollback import RollbackManager
import sysmgr.remediations.handlers  # Ensure all default handlers are registered


cli_runner = CliRunner()


@pytest.mark.asyncio
async def test_remediation_flush_dns_cache_dry_run():
    """Verify dry-run of flush-dns-cache returns expected result, messages, and scope."""
    entry = default_remediation_registry.get("flush-dns-cache")
    assert entry is not None
    assert entry.scope == RemediationScope.TRANSIENT
    assert entry.parent_probe_id == "hardware.network"

    # Test via RemediationRunner
    runner = RemediationRunner(registry=default_remediation_registry)
    ctx = RemediationContext(dry_run=True)
    result = await runner.execute("flush-dns-cache", ctx=ctx)

    assert result.success is True
    assert result.action_id == "flush-dns-cache"
    assert result.error is None
    assert len(result.changes_made) == 1
    assert "[DRY RUN]" in result.changes_made[0]
    assert "TRANSIENT" in result.changes_made[0]

    # Test handler directly in dry-run mode
    handler_changes = await entry.handler(ctx)
    assert len(handler_changes) == 1
    assert "[Dry Run]" in handler_changes[0]
    assert "ipconfig /flushdns" in handler_changes[0]


@pytest.mark.asyncio
async def test_remediation_enable_tpm_in_bios_firmware_guidance():
    """Verify enable-tpm-in-bios provides real manual firmware guidance mentioning Intel PTT / AMD fTPM and UEFI."""
    entry = default_remediation_registry.get("enable-tpm-in-bios")
    assert entry is not None
    assert entry.scope == RemediationScope.MANUAL
    assert entry.parent_probe_id == "readiness.tpm_secure_boot"

    runner = RemediationRunner(registry=default_remediation_registry)
    ctx = RemediationContext()
    result = await runner.execute("enable-tpm-in-bios", ctx=ctx)

    assert result.success is True
    assert result.action_id == "enable-tpm-in-bios"
    assert result.error is None

    guidance_full = "\n".join(result.changes_made)
    assert "UEFI/BIOS" in guidance_full
    assert "Intel Platform Trust Technology (PTT)" in guidance_full or "Intel" in guidance_full
    assert "AMD fTPM" in guidance_full
    assert "TPM 2.0" in guidance_full
    assert "GPT" in guidance_full

    # Post-check verification against live probe engine
    assert result.post_check is not None
    assert result.post_check.probe_id == "readiness.tpm_secure_boot"


@pytest.mark.asyncio
async def test_remediation_clean_temp_files_dry_run_isolated(tmp_path, monkeypatch):
    """Verify clean-temp-files dry-run in an isolated directory with aged files."""
    isolated_temp = tmp_path / "temp"
    isolated_temp.mkdir()

    old_file = isolated_temp / "old_stale.tmp"
    old_file.write_text("sample stale content")
    two_days_ago = time.time() - (48 * 3600)
    os.utime(old_file, (two_days_ago, two_days_ago))

    recent_file = isolated_temp / "recent_active.tmp"
    recent_file.write_text("sample active content")

    monkeypatch.setenv("TEMP", str(isolated_temp))
    monkeypatch.setenv("TMP", str(isolated_temp))

    entry = default_remediation_registry.get("clean-temp-files")
    assert entry is not None
    assert entry.scope == RemediationScope.PERSISTENT
    assert entry.parent_probe_id == "storage.disk_space"

    # Handler dry-run
    ctx = RemediationContext(dry_run=True)
    handler_changes = await entry.handler(ctx)
    assert len(handler_changes) == 1
    assert "[Dry Run]" in handler_changes[0]
    assert "Would clean 1 temporary files" in handler_changes[0]

    # Verify dry-run did not delete any files
    assert old_file.exists()
    assert recent_file.exists()

    # Runner dry-run
    runner = RemediationRunner(registry=default_remediation_registry)
    runner_result = await runner.execute("clean-temp-files", ctx=ctx)
    assert runner_result.success is True
    assert len(runner_result.changes_made) == 1
    assert "[DRY RUN]" in runner_result.changes_made[0]
    assert "PERSISTENT" in runner_result.changes_made[0]


@pytest.mark.asyncio
async def test_remediation_clean_temp_files_dry_run_system_temp():
    """Verify clean-temp-files dry-run against the actual live host %TEMP% directory."""
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp_dir or not Path(temp_dir).exists():
        pytest.skip("%TEMP% environment variable not set or directory does not exist")

    entry = default_remediation_registry.get("clean-temp-files")
    assert entry is not None

    ctx = RemediationContext(dry_run=True)
    changes = await entry.handler(ctx)
    assert len(changes) == 1
    assert "[Dry Run] Would clean" in changes[0]
    assert str(Path(temp_dir)) in changes[0]


def test_rollback_manager_markdown_schema_generation(tmp_path):
    """Verify RollbackManager outputs markdown conforming to docs/rollback/ schema."""
    plan = RollbackPlan(
        action_id="test-integration-service",
        title="Integration Rollback Service Plan",
        target_subsystem="services",
        pre_state={"service_name": "TestSvc", "status": "Stopped", "start_type": 3},
        reversal_commands=[
            "Stop-Service -Name TestSvc -Force",
            "Set-Service -Name TestSvc -StartupType Manual",
        ],
        safe_mode_instructions=[
            "sc.exe stop TestSvc",
            "sc.exe config TestSvc start= demand",
        ],
    )

    manager = RollbackManager(rollback_dir=tmp_path)
    output_path = manager.save_and_commit(plan)

    assert output_path.exists()
    assert output_path.parent == tmp_path
    assert output_path.name.endswith("-test-integration-service-rollback.md")

    content = output_path.read_text(encoding="utf-8")

    # Header section
    assert "# Rollback Plan: Integration Rollback Service Plan" in content
    assert "- **Action ID:** `test-integration-service`" in content
    assert "- **Target Subsystem:** `services`" in content
    assert "- **Timestamp:**" in content

    # Pre-Change Baseline State (JSON)
    assert "## Pre-Change Baseline State" in content
    assert "```json" in content
    assert '"service_name": "TestSvc"' in content
    assert '"status": "Stopped"' in content

    # Automated Reversal Commands
    assert "## Automated Reversal Commands" in content
    assert "```powershell" in content
    assert "Stop-Service -Name TestSvc -Force" in content

    # Safe Mode Instructions
    assert "## Safe Mode Manual Execution Instructions" in content
    assert "> [!IMPORTANT]" in content
    assert "boot into Safe Mode with Command Prompt" in content
    assert "- sc.exe stop TestSvc" in content
    assert "- sc.exe config TestSvc start= demand" in content


def test_cli_fix_enable_tpm_in_bios():
    """Verify CLI invocation 'fix enable-tpm-in-bios' runs and displays manual guidance."""
    result = cli_runner.invoke(app, ["fix", "enable-tpm-in-bios"])
    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    assert "enable-tpm-in-bios" in result.stdout
    assert "UEFI/BIOS" in result.stdout
    assert "Intel" in result.stdout or "PTT" in result.stdout
    assert "AMD fTPM" in result.stdout


def test_cli_fix_flush_dns_cache_dry_run():
    """Verify CLI invocation 'fix flush-dns-cache --dry-run' succeeds with dry-run message."""
    result = cli_runner.invoke(app, ["fix", "flush-dns-cache", "--dry-run"])
    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    assert "flush-dns-cache" in result.stdout
    assert "DRY RUN" in result.stdout


def test_cli_fix_json_output():
    """Verify CLI invocation with --json outputs valid parseable JSON."""
    result = cli_runner.invoke(app, ["fix", "flush-dns-cache", "--dry-run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["action_id"] == "flush-dns-cache"
    assert any("DRY RUN" in c for c in data["changes_made"])
