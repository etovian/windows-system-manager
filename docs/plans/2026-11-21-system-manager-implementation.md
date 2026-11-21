# System Manager (`sysmgr`) Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundation of `sysmgr`, an agent-integrated Windows system utilities and health toolkit with modular diagnostic probes, structured JSON/Rich CLI outputs, safe remediations, and a troubleshooting knowledge base.

**Architecture:** A pluggable diagnostic engine where independent probes implement `BaseProbe` and return strongly typed `DiagnosticResult` models. The execution engine runs probes concurrently with per-probe timeouts, outputting formatted terminal tables or machine-readable JSON via a Typer CLI. Curated Markdown runbooks in `knowledge/` provide context for root-cause analysis and automated remediation.

**Tech Stack:** Python 3.11+, `uv`, `typer`, `rich`, `pydantic`, `psutil`, `pytest`, `pytest-mock`, `pytest-asyncio`.

---

### Task 1: Project Initialization & Dependency Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/sysmgr/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Step 1: Write .gitignore and pyproject.toml**

```toml
[project]
name = "sysmgr"
version = "0.1.0"
description = "Agent-integrated Windows system utilities, health diagnostics, and management"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.7.0",
    "psutil>=5.9.8",
]

[project.scripts]
sysmgr = "sysmgr.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Write basic smoke test**

```python
# tests/test_smoke.py
import sysmgr


def test_package_metadata():
    assert sysmgr.__version__ == "0.1.0"
```

**Step 3: Run test to verify it fails**

Run: `$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User"); uv run pytest`
Expected: FAIL with `AttributeError: module 'sysmgr' has no attribute '__version__'`

**Step 4: Implement minimal package init**

```python
# src/sysmgr/__init__.py
__version__ = "0.1.0"
```

**Step 5: Run test to verify it passes**

Run: `$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User"); uv run pytest`
Expected: PASS (1 passed)

**Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/ tests/
git commit -m "chore: initialize project structure with uv, dependencies, and smoke test"
```

---

### Task 2: Core Diagnostic Models

**Files:**
- Create: `tests/unit/test_models.py`
- Create: `src/sysmgr/core/models.py`

**Step 1: Write failing test for core models**

```python
# tests/unit/test_models.py
import pytest
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.core'`

**Step 3: Implement core models**

```python
# src/sysmgr/core/models.py
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiagnosticStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    INFO = "INFO"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    ELEVATED = "ELEVATED"


class RemediationAction(BaseModel):
    id: str
    description: str
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_admin: bool = False


class DiagnosticResult(BaseModel):
    probe_id: str
    category: str
    status: DiagnosticStatus
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    remediations: List[RemediationAction] = Field(default_factory=list)
    knowledge_refs: List[str] = Field(default_factory=list)


class DiagnosticReport(BaseModel):
    timestamp: str
    total_probes: int
    pass_count: int
    warn_count: int
    fail_count: int
    results: List[DiagnosticResult] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/core/models.py tests/unit/test_models.py
git commit -m "feat(core): implement DiagnosticResult, RemediationAction, and DiagnosticStatus models"
```

---

### Task 3: BaseProbe Protocol & ProbeEngine

**Files:**
- Create: `tests/unit/test_engine.py`
- Create: `src/sysmgr/core/engine.py`

**Step 1: Write failing test for ProbeEngine**

```python
# tests/unit/test_engine.py
import pytest
import asyncio
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


@pytest.mark.asyncio
async def test_probe_engine_execution():
    engine = ProbeEngine()
    engine.register(DummyPassingProbe())

    report = await engine.run_all()
    assert report.total_probes == 1
    assert report.pass_count == 1
    assert report.results[0].status == DiagnosticStatus.PASS


@pytest.mark.asyncio
async def test_probe_engine_timeout_isolation():
    engine = ProbeEngine(probe_timeout_seconds=0.1)
    engine.register(DummyPassingProbe())
    engine.register(DummySlowProbe())

    report = await engine.run_all()
    assert report.total_probes == 2
    slow_result = next(r for r in report.results if r.probe_id == "test.dummy_slow")
    assert slow_result.status == DiagnosticStatus.WARN
    assert "timed out" in slow_result.summary.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.core.engine'`

**Step 3: Implement BaseProbe & ProbeEngine**

```python
# src/sysmgr/core/engine.py
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sysmgr.core.models import (
    DiagnosticReport,
    DiagnosticResult,
    DiagnosticStatus,
)


class BaseProbe:
    probe_id: str
    name: str
    category: str
    description: str
    requires_admin: bool = False

    async def check(self) -> DiagnosticResult:
        raise NotImplementedError("Probes must implement check()")


class ProbeEngine:
    def __init__(self, probe_timeout_seconds: float = 5.0):
        self.probes: Dict[str, BaseProbe] = {}
        self.timeout = probe_timeout_seconds

    def register(self, probe: BaseProbe) -> None:
        self.probes[probe.probe_id] = probe

    async def run_probe(self, probe: BaseProbe) -> DiagnosticResult:
        try:
            return await asyncio.wait_for(probe.check(), timeout=self.timeout)
        except asyncio.TimeoutError:
            return DiagnosticResult(
                probe_id=probe.probe_id,
                category=probe.category,
                status=DiagnosticStatus.WARN,
                summary=f"Probe '{probe.name}' timed out after {self.timeout}s.",
                details={"error": "TimeoutError"},
            )
        except Exception as exc:
            return DiagnosticResult(
                probe_id=probe.probe_id,
                category=probe.category,
                status=DiagnosticStatus.FAIL,
                summary=f"Probe '{probe.name}' failed with unexpected error: {str(exc)}",
                details={"error": type(exc).__name__, "message": str(exc)},
            )

    async def run_all(self, category: Optional[str] = None) -> DiagnosticReport:
        targets = [
            p for p in self.probes.values()
            if category is None or p.category.lower() == category.lower()
        ]
        results: List[DiagnosticResult] = await asyncio.gather(
            *[self.run_probe(p) for p in targets]
        )

        pass_count = sum(1 for r in results if r.status == DiagnosticStatus.PASS)
        warn_count = sum(1 for r in results if r.status == DiagnosticStatus.WARN)
        fail_count = sum(1 for r in results if r.status == DiagnosticStatus.FAIL)

        # Sort so FAIL and WARN appear first
        severity_rank = {
            DiagnosticStatus.FAIL: 0,
            DiagnosticStatus.WARN: 1,
            DiagnosticStatus.INFO: 2,
            DiagnosticStatus.PASS: 3,
        }
        sorted_results = sorted(results, key=lambda r: severity_rank.get(r.status, 99))

        return DiagnosticReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_probes=len(results),
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            results=sorted_results,
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/core/engine.py tests/unit/test_engine.py
git commit -m "feat(core): implement BaseProbe protocol and asynchronous ProbeEngine with timeout isolation"
```

---

### Task 4: Hardware Probes & Bluetooth Diagnostic

**Files:**
- Create: `knowledge/hardware/bluetooth-troubleshooting.md`
- Create: `tests/unit/probes/test_bluetooth.py`
- Create: `src/sysmgr/probes/hardware/bluetooth.py`

**Step 1: Write knowledge base runbook for Bluetooth**

Create `knowledge/hardware/bluetooth-troubleshooting.md` documenting:
- Error Code 43 (driver crashed / failed to reset) vs Code 10 (device cannot start).
- Windows service dependencies (`bthserv`, `BthHFSrv`).
- Power management suspension issues.
- Step-by-step remediation procedures.

**Step 2: Write failing test for BluetoothProbe**

```python
# tests/unit/probes/test_bluetooth.py
import pytest
from unittest.mock import AsyncMock, patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.hardware.bluetooth import BluetoothProbe


@pytest.mark.asyncio
async def test_bluetooth_probe_healthy():
    probe = BluetoothProbe()
    with patch.object(
        probe, "_query_bluetooth_devices", return_value=[{"name": "Intel Wireless Bluetooth", "status": "OK", "code": 0}]
    ), patch.object(
        probe, "_query_bluetooth_service", return_value={"status": "Running", "start_type": "Auto"}
    ):
        result = await probe.check()
        assert result.status == DiagnosticStatus.PASS
        assert "operational" in result.summary.lower()


@pytest.mark.asyncio
async def test_bluetooth_probe_code_43_detection():
    probe = BluetoothProbe()
    with patch.object(
        probe, "_query_bluetooth_devices", return_value=[{"name": "Intel Wireless Bluetooth", "status": "Error", "code": 43}]
    ), patch.object(
        probe, "_query_bluetooth_service", return_value={"status": "Running", "start_type": "Auto"}
    ):
        result = await probe.check()
        assert result.status == DiagnosticStatus.FAIL
        assert "code 43" in result.summary.lower()
        assert len(result.remediations) > 0
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/probes/test_bluetooth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.probes.hardware.bluetooth'`

**Step 4: Implement BluetoothProbe**

Implement `BluetoothProbe` in `src/sysmgr/probes/hardware/bluetooth.py` with mockable helpers for device status and service status queries.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/probes/test_bluetooth.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/hardware/bluetooth-troubleshooting.md src/sysmgr/probes/hardware/bluetooth.py tests/unit/probes/test_bluetooth.py
git commit -m "feat(hardware): implement BluetoothProbe with Code 43 detection and knowledge base runbook"
```

---

### Task 5: Storage Probes & Disk Space Utilities

**Files:**
- Create: `knowledge/storage/disk-cleanup-guidelines.md`
- Create: `tests/unit/probes/test_disk_space.py`
- Create: `src/sysmgr/probes/storage/disk_space.py`

**Step 1: Write knowledge base runbook for Disk Space & Cleanup**

Create `knowledge/storage/disk-cleanup-guidelines.md` detailing:
- Safe vs dangerous cleanup locations in Windows (Temp, Recycle Bin, Delivery Optimization vs WinSxS).
- Low space thresholds (Warn < 15%, Fail < 5%).

**Step 2: Write failing test for DiskSpaceProbe**

```python
# tests/unit/probes/test_disk_space.py
import pytest
from unittest.mock import patch
from collections import namedtuple
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.storage.disk_space import DiskSpaceProbe

DiskUsage = namedtuple("DiskUsage", ["total", "used", "free", "percent"])


@pytest.mark.asyncio
async def test_disk_space_probe_healthy():
    probe = DiskSpaceProbe()
    with patch("psutil.disk_partitions", return_value=[namedtuple("Part", ["mountpoint", "device"])("C:\\", "C:")]), \
         patch("psutil.disk_usage", return_value=DiskUsage(100_000, 50_000, 50_000, 50.0)):
        result = await probe.check()
        assert result.status == DiagnosticStatus.PASS


@pytest.mark.asyncio
async def test_disk_space_probe_critical_space():
    probe = DiskSpaceProbe()
    with patch("psutil.disk_partitions", return_value=[namedtuple("Part", ["mountpoint", "device"])("C:\\", "C:")]), \
         patch("psutil.disk_usage", return_value=DiskUsage(100_000, 96_000, 4_000, 96.0)):
        result = await probe.check()
        assert result.status == DiagnosticStatus.FAIL
        assert "c:\\" in result.summary.lower()
        assert len(result.remediations) > 0
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/probes/test_disk_space.py -v`
Expected: FAIL

**Step 4: Implement DiskSpaceProbe**

Implement `DiskSpaceProbe` using `psutil` partition iteration, tracking percent utilization and free space.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/probes/test_disk_space.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/storage/disk-cleanup-guidelines.md src/sysmgr/probes/storage/disk_space.py tests/unit/probes/test_disk_space.py
git commit -m "feat(storage): implement DiskSpaceProbe and cleanup guidance runbook"
```

---

### Task 6: Readiness Probes & TPM / Secure Boot Verification

**Files:**
- Create: `knowledge/readiness/windows-upgrade-readiness.md`
- Create: `tests/unit/probes/test_tpm_secure_boot.py`
- Create: `src/sysmgr/probes/readiness/tpm_secure_boot.py`

**Step 1: Write knowledge base runbook for Upgrade Readiness**

Create `knowledge/readiness/windows-upgrade-readiness.md` specifying:
- TPM 2.0 requirements (`Win32_Tpm` spec version 2.0).
- UEFI vs Legacy BIOS verification.
- Secure Boot activation checks.

**Step 2: Write failing test for TpmSecureBootProbe**

```python
# tests/unit/probes/test_tpm_secure_boot.py
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe


@pytest.mark.asyncio
async def test_tpm_secure_boot_healthy():
    probe = TpmSecureBootProbe()
    with patch.object(probe, "_check_tpm", return_value={"present": True, "spec_version": "2.0", "enabled": True}), \
         patch.object(probe, "_check_secure_boot", return_value={"secure_boot_enabled": True, "uefi": True}):
        result = await probe.check()
        assert result.status == DiagnosticStatus.PASS


@pytest.mark.asyncio
async def test_tpm_missing_or_disabled():
    probe = TpmSecureBootProbe()
    with patch.object(probe, "_check_tpm", return_value={"present": False, "spec_version": None, "enabled": False}), \
         patch.object(probe, "_check_secure_boot", return_value={"secure_boot_enabled": True, "uefi": True}):
        result = await probe.check()
        assert result.status == DiagnosticStatus.FAIL
        assert "tpm" in result.summary.lower()
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/probes/test_tpm_secure_boot.py -v`
Expected: FAIL

**Step 4: Implement TpmSecureBootProbe**

Implement `TpmSecureBootProbe` in `src/sysmgr/probes/readiness/tpm_secure_boot.py`.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/probes/test_tpm_secure_boot.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/readiness/windows-upgrade-readiness.md src/sysmgr/probes/readiness/tpm_secure_boot.py tests/unit/probes/test_tpm_secure_boot.py
git commit -m "feat(readiness): implement TpmSecureBootProbe and upgrade readiness runbook"
```

---

### Task 7: CLI Interface & Default Registry

**Files:**
- Create: `tests/unit/test_cli.py`
- Create: `src/sysmgr/probes/__init__.py`
- Create: `src/sysmgr/cli.py`

**Step 1: Write failing test for CLI commands**

```python
# tests/unit/test_cli.py
from typer.testing import CliRunner
import json
from sysmgr.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_doctor_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "total_probes" in data
    assert "results" in data
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.cli'`

**Step 3: Implement CLI & default probe registry**

Implement `src/sysmgr/cli.py` using `typer` and `rich`, supporting:
- `sysmgr doctor` (runs all probes, shows Rich table summary or JSON if `--json` passed).
- `sysmgr check <probe_id>` (runs a specific probe).
- `sysmgr knowledge <subsystem>` (prints/summarizes knowledge base entries).

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/cli.py src/sysmgr/probes/__init__.py tests/unit/test_cli.py
git commit -m "feat(cli): implement Typer CLI with doctor and JSON export"
```

---

### Task 8: Integration Smoke Test on Host

**Files:**
- Create: `tests/integration/test_live_smoke.py`

**Step 1: Write live read-only host integration test**

```python
# tests/integration/test_live_smoke.py
import pytest
from sysmgr.probes.storage.disk_space import DiskSpaceProbe
from sysmgr.core.models import DiagnosticStatus


@pytest.mark.asyncio
async def test_live_disk_space_on_host():
    probe = DiskSpaceProbe()
    result = await probe.check()
    assert result.status in (DiagnosticStatus.PASS, DiagnosticStatus.WARN, DiagnosticStatus.FAIL)
    assert len(result.details["partitions"]) > 0
```

**Step 2: Run integration test against host**

Run: `uv run pytest tests/integration/test_live_smoke.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_live_smoke.py
git commit -m "test(integration): add live host read-only smoke test"
```
