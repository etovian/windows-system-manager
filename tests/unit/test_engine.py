import asyncio
import pytest
from sysmgr.core.models import DiagnosticResult, DiagnosticStatus
from sysmgr.core.engine import BaseProbe, ProbeEngine


class DummyPassingProbe(BaseProbe):
    probe_id = "test.dummy_pass"
    name = "Dummy Pass"
    category = "test"
    description = "Test probe that passes"

    async def check(self) -> DiagnosticResult:
        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="All good",
        )


class DummySlowProbe(BaseProbe):
    probe_id = "test.dummy_slow"
    name = "Dummy Slow"
    category = "test"
    description = "Test probe that times out"

    async def check(self) -> DiagnosticResult:
        await asyncio.sleep(2.0)
        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="Completed",
        )


def test_probe_engine_execution():
    async def _run():
        engine = ProbeEngine()
        engine.register(DummyPassingProbe())

        report = await engine.run_all()
        assert report.total_probes == 1
        assert report.pass_count == 1
        assert report.results[0].status == DiagnosticStatus.PASS

    asyncio.run(_run())


def test_probe_engine_timeout_isolation():
    async def _run():
        engine = ProbeEngine(probe_timeout_seconds=0.1)
        engine.register(DummyPassingProbe())
        engine.register(DummySlowProbe())

        report = await engine.run_all()
        assert report.total_probes == 2
        slow_result = next(r for r in report.results if r.probe_id == "test.dummy_slow")
        assert slow_result.status == DiagnosticStatus.WARN
        assert "timed out" in slow_result.summary.lower()

    asyncio.run(_run())


def test_probe_engine_filter_by_category():
    async def _run():
        engine = ProbeEngine()
        engine.register(DummyPassingProbe())

        report = await engine.run_all(category="nonexistent")
        assert report.total_probes == 0

        report2 = await engine.run_all(category="test")
        assert report2.total_probes == 1

    asyncio.run(_run())
