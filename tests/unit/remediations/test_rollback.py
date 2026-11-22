from pathlib import Path
import pytest
from unittest.mock import MagicMock
from sysmgr.remediations.models import RollbackPlan
from sysmgr.remediations.rollback import RollbackManager


def test_rollback_manager_create_and_commit(tmp_path, monkeypatch):
    docs_rollback = tmp_path / "docs" / "rollback"
    manager = RollbackManager(rollback_dir=docs_rollback)

    plan = RollbackPlan(
        action_id="start-bluetooth-service",
        title="Bluetooth Service Restoration",
        target_subsystem="services",
        pre_state={"service": "bthserv", "status": "Stopped"},
        reversal_commands=["Stop-Service -Name bthserv -Force"],
        safe_mode_instructions=["sc.exe stop bthserv"],
    )

    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    file_path = manager.save_and_commit(plan, dry_run=False)

    assert file_path.exists()
    assert "start-bluetooth-service" in file_path.name
    content = file_path.read_text(encoding="utf-8")
    assert "Bluetooth Service Restoration" in content
    assert mock_run.call_count == 2  # git add + git commit


def test_rollback_manager_dry_run_does_not_write_or_commit(tmp_path, monkeypatch):
    docs_rollback = tmp_path / "docs" / "rollback"
    manager = RollbackManager(rollback_dir=docs_rollback)

    plan = RollbackPlan(
        action_id="test-action",
        title="Test Rollback",
        target_subsystem="services",
    )

    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)

    file_path = manager.save_and_commit(plan, dry_run=True)
    assert not file_path.exists()
    assert not docs_rollback.exists()
    assert mock_run.call_count == 0


def test_rollback_manager_git_failure_retains_file(tmp_path, monkeypatch):
    docs_rollback = tmp_path / "docs" / "rollback"
    manager = RollbackManager(rollback_dir=docs_rollback)

    plan = RollbackPlan(
        action_id="test-action",
        title="Test Rollback",
        target_subsystem="services",
    )

    # Simulate git CLI failure (e.g. FileNotFoundError / OSError)
    monkeypatch.setattr("subprocess.run", MagicMock(side_effect=FileNotFoundError("git not found")))

    file_path = manager.save_and_commit(plan, dry_run=False)
    # File must still be written to disk despite git failure
    assert file_path.exists()
    assert "Test Rollback" in file_path.read_text(encoding="utf-8")

