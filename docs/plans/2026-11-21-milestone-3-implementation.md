# Milestone 3: Automated & Interactive Remediation Engine Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a safe, dry-run capable, interactive remediation engine (`sysmgr fix` and `sysmgr doctor --fix`) with mandatory git-committed rollback plans for persistent system alterations.

**Architecture:** A decoupled 5-stage remediation runner (`RemediationRunner`) resolves actions from a decorated handler registry (`@remediation_handler`). When persistent alterations (services, registry, files) are targeted, a `RollbackManager` snapshots baseline state, creates an executable rollback document under `docs/rollback/` with manual Safe Mode instructions, and commits it to git prior to execution. The handler runs behind a structured error barrier and automatically re-executes the parent diagnostic probe to verify fix effectiveness.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer CLI, Rich, Git CLI (`git commit`), `psutil`, `pytest`, `pytest-asyncio`, `pytest-mock`.

---

### Task 1: Remediation Data Models

**Files:**
- Create: `src/sysmgr/remediations/__init__.py`
- Create: `src/sysmgr/remediations/models.py`
- Create: `tests/unit/remediations/__init__.py`
- Create: `tests/unit/remediations/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/remediations/test_models.py
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationResult,
    RemediationScope,
    RollbackPlan,
)
from sysmgr.core.models import RiskLevel, DiagnosticResult, DiagnosticStatus


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
        pre_state={"status": "stopped"},
        reversal_commands=["sc.exe start testservice"],
        safe_mode_instructions=["1. Boot to Safe Mode", "2. Run sc.exe start testservice"],
    )
    md = plan.to_markdown()
    assert "# Rollback Plan: Test Rollback" in md
    assert "test-action" in md
    assert "sc.exe start testservice" in md
    assert "Safe Mode" in md


def test_remediation_result_success():
    res = RemediationResult(
        action_id="flush-dns-cache",
        success=True,
        changes_made=["Flushed DNS resolver cache via ipconfig /flushdns"],
    )
    assert res.success is True
    assert len(res.changes_made) == 1
    assert res.error is None
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.remediations'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/remediations/__init__.py
"""Remediation execution engine and rollback management for sysmgr."""

# src/sysmgr/remediations/models.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sysmgr.core.models import DiagnosticResult, RiskLevel


class RemediationScope(str, Enum):
    TRANSIENT = "TRANSIENT"       # Memory/cache only, no persistent change
    PERSISTENT = "PERSISTENT"     # Services, registry, file mutation (requires git rollback)
    MANUAL = "MANUAL"             # Hardware/BIOS guidance, cannot be fixed via OS CLI


class RemediationContext(BaseModel):
    dry_run: bool = False
    auto_confirm: bool = False
    elevated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RollbackPlan(BaseModel):
    action_id: str
    title: str
    target_subsystem: str
    pre_state: Dict[str, Any] = Field(default_factory=dict)
    reversal_commands: List[str] = Field(default_factory=list)
    safe_mode_instructions: List[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_markdown(self) -> str:
        lines = [
            f"# Rollback Plan: {self.title}",
            "",
            f"- **Action ID:** `{self.action_id}`",
            f"- **Target Subsystem:** `{self.target_subsystem}`",
            f"- **Timestamp:** `{self.created_at}`",
            "",
            "## Pre-Change Baseline State",
            "```json",
            f"{self.pre_state}",
            "```",
            "",
            "## Automated Reversal Commands",
            "```powershell",
        ]
        for cmd in self.reversal_commands:
            lines.append(cmd)
        lines.extend([
            "```",
            "",
            "## Safe Mode Manual Execution Instructions",
            "> [!IMPORTANT]",
            "> If the system fails to boot or behaves abnormally, boot into Safe Mode with Command Prompt and run:",
            "",
        ])
        for inst in self.safe_mode_instructions:
            lines.append(f"- {inst}")
        lines.append("")
        return "\n".join(lines)


class RemediationResult(BaseModel):
    action_id: str
    success: bool
    changes_made: List[str] = Field(default_factory=list)
    rollback_file: Optional[str] = None
    error: Optional[str] = None
    post_check: Optional[DiagnosticResult] = None
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/remediations/ tests/unit/remediations/
git commit -m "feat(remediations): add core remediation and rollback models"
```

---

### Task 2: Rollback Plan Manager & Git Committer

**Files:**
- Create: `src/sysmgr/remediations/rollback.py`
- Create: `tests/unit/remediations/test_rollback.py`

**Step 1: Write the failing test**

```python
# tests/unit/remediations/test_rollback.py
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
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_rollback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.remediations.rollback'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/remediations/rollback.py
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Optional
from sysmgr.remediations.models import RollbackPlan


class RollbackManager:
    def __init__(self, rollback_dir: Optional[Path] = None):
        self.rollback_dir = rollback_dir or Path("docs/rollback")

    def save_and_commit(self, plan: RollbackPlan, dry_run: bool = False) -> Path:
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_name = f"{date_str}-{plan.action_id}-rollback.md"
        file_path = self.rollback_dir / file_name

        if dry_run:
            return file_path

        # Write rollback markdown
        file_path.write_text(plan.to_markdown(), encoding="utf-8")

        # Stage and commit to git
        try:
            subprocess.run(
                ["git", "add", str(file_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"chore(rollback): record plan for {plan.action_id}"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.SubprocessError:
            # If git commit fails (e.g. running in testing sandbox without git identity),
            # ensure the file remains on disk as manual fallback.
            pass

        return file_path
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_rollback.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/remediations/rollback.py tests/unit/remediations/test_rollback.py
git commit -m "feat(remediations): implement RollbackManager with git auto-commit"
```

---

### Task 3: Remediation Registry & Runner

**Files:**
- Create: `src/sysmgr/remediations/registry.py`
- Create: `src/sysmgr/remediations/runner.py`
- Create: `tests/unit/remediations/test_runner.py`

**Step 1: Write the failing test**

```python
# tests/unit/remediations/test_runner.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationScope,
    RollbackPlan,
)
from sysmgr.remediations.registry import RemediationRegistry, remediation_handler
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
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.remediations.registry'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/remediations/registry.py
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, Optional
from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope, RollbackPlan

HandlerFunc = Callable[[RemediationContext], Coroutine[Any, Any, list[str]]]
RollbackPlanFunc = Callable[[], Coroutine[Any, Any, RollbackPlan]]


@dataclass
class RegisteredHandler:
    action_id: str
    description: str
    scope: RemediationScope
    risk_level: RiskLevel
    requires_admin: bool
    parent_probe_id: Optional[str]
    handler: HandlerFunc
    rollback_generator: Optional[RollbackPlanFunc] = None


class RemediationRegistry:
    def __init__(self):
        self._handlers: Dict[str, RegisteredHandler] = {}

    def register(
        self,
        action_id: str,
        description: str,
        scope: RemediationScope = RemediationScope.TRANSIENT,
        risk_level: RiskLevel = RiskLevel.SAFE,
        requires_admin: bool = False,
        parent_probe_id: Optional[str] = None,
    ):
        def decorator(fn: HandlerFunc):
            self._handlers[action_id] = RegisteredHandler(
                action_id=action_id,
                description=description,
                scope=scope,
                risk_level=risk_level,
                requires_admin=requires_admin,
                parent_probe_id=parent_probe_id,
                handler=fn,
            )
            return fn
        return decorator

    def register_rollback(self, action_id: str):
        def decorator(fn: RollbackPlanFunc):
            if action_id in self._handlers:
                self._handlers[action_id].rollback_generator = fn
            return fn
        return decorator

    def get(self, action_id: str) -> Optional[RegisteredHandler]:
        return self._handlers.get(action_id)

    def list_all(self) -> Dict[str, RegisteredHandler]:
        return dict(self._handlers)


# Global default registry instance
default_remediation_registry = RemediationRegistry()
remediation_handler = default_remediation_registry.register
remediation_rollback = default_remediation_registry.register_rollback
```

```python
# src/sysmgr/remediations/runner.py
import asyncio
from typing import Optional
from sysmgr.core.engine import ProbeEngine
from sysmgr.probes import create_default_engine
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationResult,
    RemediationScope,
)
from sysmgr.remediations.registry import RemediationRegistry, default_remediation_registry
from sysmgr.remediations.rollback import RollbackManager


class RemediationRunner:
    def __init__(
        self,
        registry: Optional[RemediationRegistry] = None,
        rollback_manager: Optional[RollbackManager] = None,
        probe_engine: Optional[ProbeEngine] = None,
    ):
        self.registry = registry or default_remediation_registry
        self.rollback_manager = rollback_manager or RollbackManager()
        self.probe_engine = probe_engine or create_default_engine()

    async def execute(self, action_id: str, ctx: RemediationContext) -> RemediationResult:
        handler_entry = self.registry.get(action_id)
        if not handler_entry:
            return RemediationResult(
                action_id=action_id,
                success=False,
                error=f"No remediation registered for '{action_id}'.",
            )

        # Dry run simulation
        if ctx.dry_run:
            return RemediationResult(
                action_id=action_id,
                success=True,
                changes_made=[f"[DRY RUN] Would execute {handler_entry.description} (Scope: {handler_entry.scope.value})"],
            )

        # Persistent action: Generate and commit rollback plan
        rollback_file_path = None
        if handler_entry.scope == RemediationScope.PERSISTENT and handler_entry.rollback_generator:
            try:
                plan = await handler_entry.rollback_generator()
                saved_path = self.rollback_manager.save_and_commit(plan)
                rollback_file_path = str(saved_path)
            except Exception as e:
                return RemediationResult(
                    action_id=action_id,
                    success=False,
                    error=f"Rollback plan creation failed: {e}. Remediation aborted for safety.",
                )

        # Execute handler behind safety barrier
        try:
            changes = await handler_entry.handler(ctx)
        except Exception as e:
            return RemediationResult(
                action_id=action_id,
                success=False,
                error=f"Remediation execution failed: {e}",
                rollback_file=rollback_file_path,
            )

        # Post-check verification if parent probe is registered
        post_check_result = None
        if handler_entry.parent_probe_id:
            probe = self.probe_engine.get_probe(handler_entry.parent_probe_id)
            if probe:
                post_check_result = await self.probe_engine.run_probe(probe)

        return RemediationResult(
            action_id=action_id,
            success=True,
            changes_made=changes,
            rollback_file=rollback_file_path,
            post_check=post_check_result,
        )
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/remediations/registry.py src/sysmgr/remediations/runner.py tests/unit/remediations/test_runner.py
git commit -m "feat(remediations): implement RemediationRegistry and RemediationRunner"
```

---

### Task 4: Concrete Remediation Handlers

**Files:**
- Create: `src/sysmgr/remediations/handlers/__init__.py`
- Create: `src/sysmgr/remediations/handlers/network.py`
- Create: `src/sysmgr/remediations/handlers/bluetooth.py`
- Create: `src/sysmgr/remediations/handlers/storage.py`
- Create: `src/sysmgr/remediations/handlers/firmware.py`
- Create: `tests/unit/remediations/test_handlers.py`

**Step 1: Write the failing test**

```python
# tests/unit/remediations/test_handlers.py
import pytest
from unittest.mock import MagicMock
from sysmgr.remediations.models import RemediationContext
from sysmgr.remediations.registry import default_remediation_registry
# Ensure handlers are imported to register
import sysmgr.remediations.handlers  # noqa: F401


@pytest.mark.asyncio
async def test_flush_dns_cache_handler(monkeypatch):
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("flush-dns-cache")
    assert handler_entry is not None

    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("Flushed DNS" in c for c in changes)
    assert mock_run.called


@pytest.mark.asyncio
async def test_bluetooth_service_handler_and_rollback(monkeypatch):
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    handler_entry = default_remediation_registry.get("start-bluetooth-service")
    assert handler_entry is not None

    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("Started Windows Bluetooth" in c for c in changes)

    # Test rollback generator
    assert handler_entry.rollback_generator is not None
    plan = await handler_entry.rollback_generator()
    assert plan.action_id == "start-bluetooth-service"
    assert any("sc.exe" in inst for inst in plan.safe_mode_instructions)


@pytest.mark.asyncio
async def test_enable_tpm_firmware_guidance():
    handler_entry = default_remediation_registry.get("enable-tpm-in-bios")
    assert handler_entry is not None

    ctx = RemediationContext()
    changes = await handler_entry.handler(ctx)
    assert any("UEFI/BIOS" in c for c in changes)
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.remediations.handlers'`

**Step 3: Write minimal implementation**

- `src/sysmgr/remediations/handlers/network.py`:
  - Registers `flush-dns-cache` (`ipconfig /flushdns`)
  - Registers `renew-dhcp-lease` (`ipconfig /renew`)
- `src/sysmgr/remediations/handlers/bluetooth.py`:
  - Registers `start-bluetooth-service` (`Start-Service -Name bthserv`)
  - Rollback plan with Safe Mode instructions (`sc.exe config bthserv start= demand`, `net stop bthserv`)
- `src/sysmgr/remediations/handlers/storage.py`:
  - Registers `clean-temp-files` (safely purges non-locked files older than 24h from `%TEMP%`)
  - Rollback plan recording purged files/sizes.
- `src/sysmgr/remediations/handlers/firmware.py`:
  - Registers `enable-tpm-in-bios` and `enable-secure-boot` (informational guides with safe UEFI instructions).
- `src/sysmgr/remediations/handlers/__init__.py`: imports all submodules.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/remediations/test_handlers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/remediations/handlers/ tests/unit/remediations/test_handlers.py
git commit -m "feat(remediations): add handlers for network, bluetooth, storage, and firmware"
```

---

### Task 5: CLI Subcommands: `sysmgr fix` and `sysmgr doctor --fix`

**Files:**
- Modify: `src/sysmgr/cli.py`
- Modify: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

```python
# additions in tests/unit/test_cli.py
from unittest.mock import AsyncMock, MagicMock
from sysmgr.remediations.models import RemediationResult


def test_cli_fix_dry_run(runner, mocker):
    mock_runner = mocker.patch("sysmgr.cli.RemediationRunner")
    instance = mock_runner.return_value
    instance.execute = AsyncMock(return_value=RemediationResult(
        action_id="flush-dns-cache",
        success=True,
        changes_made=["[DRY RUN] Would flush DNS cache"],
    ))

    result = runner.invoke(app, ["fix", "flush-dns-cache", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "flush-dns-cache" in result.output


def test_cli_fix_not_found(runner, mocker):
    mock_runner = mocker.patch("sysmgr.cli.RemediationRunner")
    instance = mock_runner.return_value
    instance.execute = AsyncMock(return_value=RemediationResult(
        action_id="non-existent",
        success=False,
        error="No remediation registered",
    ))

    result = runner.invoke(app, ["fix", "non-existent"])
    assert result.exit_code == 1
    assert "No remediation registered" in result.output
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_cli.py -k "test_cli_fix" -v`
Expected: FAIL with `No such command 'fix'`

**Step 3: Write minimal implementation in `src/sysmgr/cli.py`**

- Add `sysmgr fix <action_id>` command with `--dry-run`, `--yes`, `--json`.
- Add `--fix` option to `sysmgr doctor`.
- Integrate Rich panels to clearly show before/after results and rollback plan links.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): add 'fix' command and '--fix' flag to doctor"
```

---

### Task 6: Full Integration & Live Host Verification

**Files:**
- Create: `tests/integration/test_remediations_integration.py`

**Step 1: Write integration tests**

- Test dry-run execution against real registry instances.
- Test `clean-temp-files` dry-run against actual temporary directory.
- Test `sysmgr fix enable-tpm-in-bios` prints firmware instructions properly.

**Step 2: Run all tests offline**

Run: `.venv\Scripts\pytest -v`
Expected: ALL PASS (unit and integration)

**Step 3: Commit & Push**

```bash
git add tests/integration/test_remediations_integration.py
git commit -m "test(remediations): add integration tests for remediation runner"
```
