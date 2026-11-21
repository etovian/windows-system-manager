import pytest
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
    DiagnosticReport,
)


def test_diagnostic_status_values():
    assert DiagnosticStatus.PASS.value == "PASS"
    assert DiagnosticStatus.WARN.value == "WARN"
    assert DiagnosticStatus.FAIL.value == "FAIL"
    assert DiagnosticStatus.INFO.value == "INFO"


def test_remediation_action_creation():
    action = RemediationAction(
        id="restart-service",
        description="Restart the target service",
        risk_level=RiskLevel.SAFE,
        requires_admin=False,
    )
    assert action.id == "restart-service"
    assert action.risk_level == RiskLevel.SAFE
    assert action.requires_admin is False


def test_diagnostic_result_serialization():
    result = DiagnosticResult(
        probe_id="hardware.bluetooth",
        category="hardware",
        status=DiagnosticStatus.WARN,
        summary="Bluetooth adapter has code 43 error.",
        details={"device_id": "USB\\VID_8087", "error_code": 43},
        knowledge_refs=["knowledge/hardware/bluetooth-troubleshooting.md"],
    )
    data = result.model_dump()
    assert data["probe_id"] == "hardware.bluetooth"
    assert data["status"] == "WARN"
    assert data["details"]["error_code"] == 43


def test_diagnostic_report_structure():
    report = DiagnosticReport(
        timestamp="2026-11-21T20:00:00Z",
        total_probes=1,
        pass_count=1,
        warn_count=0,
        fail_count=0,
        results=[
            DiagnosticResult(
                probe_id="test.probe",
                category="test",
                status=DiagnosticStatus.PASS,
                summary="All good",
            )
        ],
    )
    data = report.model_dump()
    assert data["total_probes"] == 1
    assert data["pass_count"] == 1
    assert len(data["results"]) == 1
