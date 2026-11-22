import json
from typer.testing import CliRunner
from unittest.mock import patch
from sysmgr.cli import app
from sysmgr.core.models import DiagnosticResult, DiagnosticStatus

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_doctor_json():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe

        engine = ProbeEngine()

        class MockProbe(BaseProbe):
            probe_id = "mock.probe"
            name = "Mock Probe"
            category = "mock"
            description = "Mock description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.PASS,
                    summary="All systems nominal",
                )

        engine.register(MockProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_probes"] == 1
        assert data["pass_count"] == 1
        assert data["results"][0]["probe_id"] == "mock.probe"


def test_cli_doctor_table():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe

        engine = ProbeEngine()

        class MockProbe(BaseProbe):
            probe_id = "mock.probe"
            name = "Mock Probe"
            category = "mock"
            description = "Mock description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.PASS,
                    summary="All systems nominal",
                )

        engine.register(MockProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "mock.probe" in result.stdout
        assert "PASS" in result.stdout


def test_cli_knowledge_list():
    result = runner.invoke(app, ["knowledge"])
    assert result.exit_code == 0
    assert "bluetooth-troubleshooting.md" in result.stdout or "Runbooks" in result.stdout


def test_default_engine_registration():
    from sysmgr.probes import create_default_engine

    engine = create_default_engine()
    assert len(engine.probes) == 8
    expected_ids = {
        "hardware.bluetooth",
        "hardware.device_manager",
        "hardware.network",
        "storage.disk_space",
        "storage.disk_health",
        "storage.disk_performance",
        "readiness.tpm_secure_boot",
        "readiness.hygiene",
    }
    assert set(engine.probes.keys()) == expected_ids



def test_cli_check_command():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe

        engine = ProbeEngine()

        class MockProbe(BaseProbe):
            probe_id = "test.single"
            name = "Single Probe"
            category = "test"
            description = "Single probe description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.PASS,
                    summary="Single check ok",
                )

        engine.register(MockProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["check", "test.single"])
        assert result.exit_code == 0
        assert "Single check ok" in result.stdout

        result_unknown = runner.invoke(app, ["check", "nonexistent.probe"])
        assert result_unknown.exit_code == 1
        assert "not found" in result_unknown.stdout.lower()


def test_probes_all_exports():
    import sysmgr.probes as p
    from sysmgr.core.engine import BaseProbe

    for name in p.__all__:
        obj = getattr(p, name)
        if name != "create_default_engine":
            assert issubclass(obj, BaseProbe)
        else:
            assert callable(obj)


def test_cli_fix_dry_run():
    result = runner.invoke(app, ["fix", "flush-dns-cache", "--dry-run"])
    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    assert "DRY RUN" in result.stdout


def test_cli_fix_not_found():
    result = runner.invoke(app, ["fix", "non-existent-action"])
    assert result.exit_code == 1
    assert "No remediation registered" in result.stdout

    # Also check JSON output when not found
    result_json = runner.invoke(app, ["fix", "non-existent-action", "--json"])
    assert result_json.exit_code == 1
    data = json.loads(result_json.stdout)
    assert data["success"] is False
    assert data["action_id"] == "non-existent-action"


def test_cli_fix_json():
    result = runner.invoke(app, ["fix", "flush-dns-cache", "--dry-run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["action_id"] == "flush-dns-cache"
    assert data["success"] is True
    assert len(data["changes_made"]) > 0


def test_cli_doctor_fix_flag():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe
        from sysmgr.core.models import RemediationAction, RiskLevel

        engine = ProbeEngine()

        class MockFailingProbe(BaseProbe):
            probe_id = "mock.failing"
            name = "Mock Failing Probe"
            category = "mock"
            description = "Mock failing description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.WARN,
                    summary="Needs remediation",
                    remediations=[
                        RemediationAction(
                            id="flush-dns-cache",
                            description="Flush DNS resolver cache",
                            risk_level=RiskLevel.SAFE,
                        )
                    ],
                )

        engine.register(MockFailingProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["doctor", "--fix", "--yes", "--dry-run"])
        assert result.exit_code == 0
        assert "flush-dns-cache" in result.stdout
        assert "SUCCESS" in result.stdout


def test_cli_fix_persistent_confirmation_declined():
    result = runner.invoke(app, ["fix", "start-bluetooth-service"], input="n\n")
    assert result.exit_code == 0
    assert "Confirm executing persistent remediation" in result.stdout
    assert "cancelled" in result.stdout.lower() or "aborted" in result.stdout.lower()


def test_cli_fix_persistent_with_yes():
    result = runner.invoke(app, ["fix", "start-bluetooth-service", "--yes", "--dry-run"])
    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    assert "start-bluetooth-service" in result.stdout


def test_cli_fix_post_check_and_rollback(tmp_path):
    from sysmgr.remediations.models import RemediationResult, RollbackPlan
    from sysmgr.core.models import DiagnosticResult, DiagnosticStatus
    from unittest.mock import AsyncMock

    mock_runner = AsyncMock()
    mock_runner.execute.return_value = RemediationResult(
        action_id="start-bluetooth-service",
        success=True,
        changes_made=["Started Bluetooth service successfully"],
        rollback_file=str(tmp_path / "rollback.md"),
        post_check=DiagnosticResult(
            probe_id="hardware.bluetooth",
            category="hardware",
            status=DiagnosticStatus.PASS,
            summary="Bluetooth operational",
        ),
    )

    with patch("sysmgr.cli.RemediationRunner", return_value=mock_runner):
        result = runner.invoke(app, ["fix", "start-bluetooth-service", "--yes"])
        assert result.exit_code == 0
        assert "Rollback Plan:" in result.stdout
        assert "Post-Check:" in result.stdout
        assert "Bluetooth operational" in result.stdout


def test_cli_fix_failure():
    from sysmgr.remediations.models import RemediationResult
    from unittest.mock import AsyncMock

    mock_runner = AsyncMock()
    mock_runner.execute.return_value = RemediationResult(
        action_id="flush-dns-cache",
        success=False,
        error="Access denied while flushing cache",
    )

    with patch("sysmgr.cli.RemediationRunner", return_value=mock_runner):
        result = runner.invoke(app, ["fix", "flush-dns-cache"])
        assert result.exit_code == 1
        assert "FAILED" in result.stdout
        assert "Access denied while flushing cache" in result.stdout

        # Also test with --json on failure
        result_json = runner.invoke(app, ["fix", "flush-dns-cache", "--json"])
        assert result_json.exit_code == 1
        data = json.loads(result_json.stdout)
        assert data["success"] is False
        assert "Access denied" in data["error"]



def test_cli_doctor_fix_no_remediations():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe

        engine = ProbeEngine()

        class MockPassingProbe(BaseProbe):
            probe_id = "mock.passing"
            name = "Mock Passing Probe"
            category = "mock"
            description = "Mock passing description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.PASS,
                    summary="All nominal",
                )

        engine.register(MockPassingProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["doctor", "--fix"])
        assert result.exit_code == 0
        assert "No remediations required" in result.stdout


def test_cli_doctor_fix_prompt_declined():
    with patch("sysmgr.cli.create_default_engine") as mock_engine_factory:
        from sysmgr.core.engine import ProbeEngine, BaseProbe
        from sysmgr.core.models import RemediationAction, RiskLevel

        engine = ProbeEngine()

        class MockFailingProbe(BaseProbe):
            probe_id = "mock.failing"
            name = "Mock Failing Probe"
            category = "mock"
            description = "Mock failing description"

            async def check(self):
                return DiagnosticResult(
                    probe_id=self.probe_id,
                    category=self.category,
                    status=DiagnosticStatus.WARN,
                    summary="Needs remediation",
                    remediations=[
                        RemediationAction(
                            id="flush-dns-cache",
                            description="Flush DNS resolver cache",
                            risk_level=RiskLevel.SAFE,
                        )
                    ],
                )

        engine.register(MockFailingProbe())
        mock_engine_factory.return_value = engine

        result = runner.invoke(app, ["doctor", "--fix"], input="n\n")
        assert result.exit_code == 0
        assert "Apply 1 remediation(s)?" in result.stdout
        assert "cancelled" in result.stdout.lower() or "aborted" in result.stdout.lower()


