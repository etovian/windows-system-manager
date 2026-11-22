import json
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationResult,
    RemediationScope,
    RollbackPlan,
)
from sysmgr.core.models import DiagnosticResult, DiagnosticStatus


def test_remediation_context_defaults():
    ctx = RemediationContext()
    assert ctx.dry_run is False
    assert ctx.auto_confirm is False
    assert ctx.elevated is False


def test_rollback_plan_markdown_render():
    plan = RollbackPlan(
        action_id="test-action",
        title="Test Rollback",
        target_subsystem="services",
        pre_state={"status": "stopped", "active": True},
        reversal_commands=["sc.exe start testservice"],
        safe_mode_instructions=["1. Boot to Safe Mode", "2. Run sc.exe start testservice"],
    )
    md = plan.to_markdown()
    assert "# Rollback Plan: Test Rollback" in md
    assert "test-action" in md
    assert "sc.exe start testservice" in md
    assert "Safe Mode" in md
    # Verify pre_state is formatted as valid JSON
    assert '"status": "stopped"' in md
    assert '"active": true' in md


def test_remediation_result_success():
    res = RemediationResult(
        action_id="flush-dns-cache",
        success=True,
        changes_made=["Flushed DNS resolver cache via ipconfig /flushdns"],
    )
    assert res.success is True
    assert len(res.changes_made) == 1
    assert res.error is None


def test_remediation_scope_values():
    assert RemediationScope.TRANSIENT.value == "TRANSIENT"
    assert RemediationScope.PERSISTENT.value == "PERSISTENT"
    assert RemediationScope.MANUAL.value == "MANUAL"

