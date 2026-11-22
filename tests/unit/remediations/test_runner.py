import pytest
from unittest.mock import AsyncMock, MagicMock
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationScope,
    RollbackPlan,
)
from sysmgr.remediations.registry import (
    RemediationRegistry,
    remediation_handler,
    remediation_rollback,
    default_remediation_registry,
)
from sysmgr.remediations.runner import RemediationRunner
from sysmgr.core.models import RiskLevel, DiagnosticResult, DiagnosticStatus


@pytest.fixture
def mock_registry():
    reg = RemediationRegistry()

    @reg.register(
        action_id="dummy-transient",
        description="Dummy transient fix",
        scope=RemediationScope.TRANSIENT,
        risk_level=RiskLevel.SAFE,
    )
    async def fix_transient(ctx: RemediationContext):
        return ["Dummy transient executed"]

    @reg.register(
        action_id="dummy-persistent",
        description="Dummy persistent fix",
        scope=RemediationScope.PERSISTENT,
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    async def fix_persistent(ctx: RemediationContext):
        return ["Dummy persistent modified"]

    @reg.register_rollback("dummy-persistent")
    async def rollback_persistent():
        return RollbackPlan(
            action_id="dummy-persistent",
            title="Dummy Persistent Rollback",
            target_subsystem="dummy",
            reversal_commands=["revert"],
            safe_mode_instructions=["safe revert"],
        )

    @reg.register(
        action_id="dummy-failing",
        description="Dummy failing fix",
        scope=RemediationScope.TRANSIENT,
        risk_level=RiskLevel.SAFE,
    )
    async def fix_failing(ctx: RemediationContext):
        raise RuntimeError("Remediation explosive failure")

    @reg.register(
        action_id="dummy-failing-rollback",
        description="Dummy failing rollback fix",
        scope=RemediationScope.PERSISTENT,
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    async def fix_failing_rollback(ctx: RemediationContext):
        return ["Should not reach here"]

    @reg.register_rollback("dummy-failing-rollback")
    async def rollback_failing():
        raise ValueError("Rollback plan generator failed")

    @reg.register(
        action_id="dummy-with-probe",
        description="Dummy fix with probe check",
        scope=RemediationScope.TRANSIENT,
        risk_level=RiskLevel.SAFE,
        parent_probe_id="test-probe",
    )
    async def fix_with_probe(ctx: RemediationContext):
        return ["Fixed something"]

    return reg


@pytest.mark.asyncio
async def test_runner_executes_transient(mock_registry):
    runner = RemediationRunner(registry=mock_registry)
    ctx = RemediationContext()
    res = await runner.execute("dummy-transient", ctx)

    assert res.success is True
    assert "Dummy transient executed" in res.changes_made
    assert res.rollback_file is None


@pytest.mark.asyncio
async def test_runner_dry_run_does_not_execute(mock_registry):
    runner = RemediationRunner(registry=mock_registry)
    ctx = RemediationContext(dry_run=True)
    res = await runner.execute("dummy-persistent", ctx)

    assert res.success is True
    assert any("[DRY RUN]" in chg for chg in res.changes_made)


@pytest.mark.asyncio
async def test_runner_persistent_creates_rollback(mock_registry, tmp_path, monkeypatch):
    mock_rollback_mgr = MagicMock()
    mock_rollback_mgr.save_and_commit.return_value = tmp_path / "rollback.md"

    runner = RemediationRunner(registry=mock_registry, rollback_manager=mock_rollback_mgr)
    ctx = RemediationContext()
    res = await runner.execute("dummy-persistent", ctx)

    assert res.success is True
    assert mock_rollback_mgr.save_and_commit.called
    assert res.rollback_file is not None


@pytest.mark.asyncio
async def test_runner_unregistered_action(mock_registry):
    runner = RemediationRunner(registry=mock_registry)
    ctx = RemediationContext()
    res = await runner.execute("non-existent", ctx)

    assert res.success is False
    assert "No remediation registered" in res.error


@pytest.mark.asyncio
async def test_runner_execution_failure_handled(mock_registry):
    runner = RemediationRunner(registry=mock_registry)
    ctx = RemediationContext()
    res = await runner.execute("dummy-failing", ctx)

    assert res.success is False
    assert "Remediation execution failed: Remediation explosive failure" in res.error


@pytest.mark.asyncio
async def test_runner_rollback_failure_aborts(mock_registry):
    runner = RemediationRunner(registry=mock_registry)
    ctx = RemediationContext()
    res = await runner.execute("dummy-failing-rollback", ctx)

    assert res.success is False
    assert "Rollback plan creation failed" in res.error


@pytest.mark.asyncio
async def test_runner_with_post_check(mock_registry):
    mock_probe_engine = MagicMock()
    mock_probe = MagicMock()
    mock_probe_engine.get_probe.return_value = mock_probe

    expected_result = DiagnosticResult(
        probe_id="test-probe",
        category="test",
        status=DiagnosticStatus.PASS,
        summary="Probe passed after fix",
    )
    mock_probe_engine.run_probe = AsyncMock(return_value=expected_result)

    runner = RemediationRunner(registry=mock_registry, probe_engine=mock_probe_engine)
    ctx = RemediationContext()
    res = await runner.execute("dummy-with-probe", ctx)

    assert res.success is True
    assert res.post_check == expected_result
    mock_probe_engine.get_probe.assert_called_once_with("test-probe")
    mock_probe_engine.run_probe.assert_called_once_with(mock_probe)


def test_registry_list_all_and_decorators(mock_registry):
    handlers = mock_registry.list_all()
    assert "dummy-transient" in handlers
    assert "dummy-persistent" in handlers
    assert handlers["dummy-persistent"].rollback_generator is not None

    # Test global decorator
    try:
        @remediation_handler(action_id="global-test", description="Global test handler")
        async def global_handler(ctx: RemediationContext):
            return []

        assert default_remediation_registry.get("global-test") is not None
    finally:
        default_remediation_registry._handlers.pop("global-test", None)


def test_register_rollback_unknown_action_raises_key_error():
    reg = RemediationRegistry()
    with pytest.raises(KeyError, match="unknown remediation action"):
        @reg.register_rollback("unknown-action")
        async def fake_rollback():
            pass


@pytest.mark.asyncio
async def test_runner_persistent_without_rollback_generator_fails_closed():
    reg = RemediationRegistry()

    @reg.register(
        action_id="unsafe-persistent",
        description="Persistent action lacking rollback generator",
        scope=RemediationScope.PERSISTENT,
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    )
    async def unsafe_handler(ctx: RemediationContext):
        return ["Should never execute"]

    runner = RemediationRunner(registry=reg)
    res = await runner.execute("unsafe-persistent", RemediationContext())

    assert res.success is False
    assert "requires a registered rollback generator" in res.error
    assert res.changes_made == []

