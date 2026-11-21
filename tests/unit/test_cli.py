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
