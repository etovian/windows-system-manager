# Windows System Manager (`sysmgr`) - Agent & Developer Guide

## Project Mission
`sysmgr` is an agent-integrated Windows system utilities, health diagnostics, and remediation management toolkit designed for both automated AI agent workflows and human CLI system administration. It provides deep hardware/software inspection, upgrade readiness auditing, structured advisory troubleshooting runbooks, and safe, verifiable system remediation.

---

## 1. Core Operational Invariants & Safety Rules

> [!CAUTION]
> **MANDATORY ROLLBACK RULE**:
> NEVER update system settings, drivers, services, or registry without first creating an executable rollback plan in a `.md` file checked into git under `docs/rollback/`, with Safe Mode manual execution instructions.

### Golden Rules for Agents & Developers
1. **Detection is 100% Read-Only**: Diagnostic probes must never alter system state. They only query, inspect, and report findings.
2. **Remediation Safety Gate**:
   - `TRANSIENT` remediations (e.g. flushing DNS cache, releasing DHCP) operate in memory/cache only.
   - `PERSISTENT` remediations (e.g. starting/stopping services, modifying registry, purging files) **must** generate and git-commit an executable rollback plan under `docs/rollback/` before executing.
   - `MANUAL` remediations (e.g. UEFI/BIOS settings, TPM firmware, Secure Boot) provide structured operational runbooks rather than blind OS mutations.
3. **Autonomous Testing Permission**: You always have permanent permission to run tests, linters, and verification checks autonomously without asking.
4. **Git Branch Discipline**:
   - NEVER commit directly to `master` without explicit user permission.
   - ALWAYS create a dedicated working branch (`feat/...` or `fix/...`) when beginning code modifications.
   - ALWAYS pause and ask for user review upon completing specifications or implementation plans before touching code.

---

## 2. Architecture & Codebase Layout

```
sysmgr/
├── src/sysmgr/
│   ├── cli.py                     # Typer CLI (doctor, check, fix, knowledge)
│   ├── core/                      # Engine primitives and diagnostic models
│   │   ├── engine.py              # Async ProbeEngine with per-probe timeouts (default 15s)
│   │   └── models.py              # DiagnosticResult, DiagnosticStatus, RemediationAction, RiskLevel
│   ├── probes/                    # 100% read-only diagnostic probes
│   │   ├── hardware/              # bluetooth, device_manager (PnP error codes), network
│   │   ├── storage/               # disk_space, disk_health (SMART), disk_performance (I/O)
│   │   └── readiness/             # tpm_secure_boot, hygiene (reboot flags, uptime, dumps)
│   └── remediations/              # Remediation execution & rollback engine
│       ├── models.py              # RemediationContext, RollbackPlan, RemediationResult, RemediationScope
│       ├── registry.py            # RemediationRegistry & @remediation_handler / @remediation_rollback
│       ├── rollback.py            # RollbackManager (markdown generation & git auto-commit)
│       ├── runner.py              # RemediationRunner (5-stage execution pipeline)
│       └── handlers/              # network, bluetooth, storage, firmware
├── knowledge/                     # Markdown troubleshooting playbooks & runbooks
├── docs/
│   ├── plans/                     # Architecture design & bite-sized implementation specs
│   └── rollback/                  # Committed executable rollback plans with Safe Mode guides
└── tests/
    ├── unit/                      # Fast, mocked unit tests (probes, remediations, CLI, engine)
    └── integration/               # Live host read-only smoke & dry-run integration tests
```

---

## 3. CLI Quick Reference

```bash
# Full diagnostic scan across all subsystems
sysmgr doctor

# Diagnostic scan with custom timeout and category filter
sysmgr doctor --category hardware --timeout 20.0

# Diagnostic triage with interactive remediation
sysmgr doctor --fix
sysmgr doctor --fix --dry-run
sysmgr doctor --fix --yes

# Machine-readable diagnostic telemetry
sysmgr doctor --json

# Run a single probe
sysmgr check hardware.bluetooth
sysmgr check readiness.tpm_secure_boot --json

# Execute targeted remediation
sysmgr fix flush-dns-cache
sysmgr fix start-bluetooth-service --dry-run
sysmgr fix clean-temp-files --yes
sysmgr fix enable-tpm-in-bios

# Read troubleshooting runbooks
sysmgr knowledge
sysmgr knowledge smart-health-monitoring.md
```

---

## 4. Development & Testing Workflow

### Virtual Environment & Dependencies
Managed via `uv` with Python 3.11+. The local virtual environment resides in `.venv`.

### Global CLI Tool (`sysmgr.exe` via `uv tool`) & Process Locking
- **`sysmgr` is installed in editable mode**: Installed via `uv tool install --force --editable .`, which links directly to `c:\dev\system-manager\src`. All code, probe, and web asset changes are live immediately without reinstalling.
- **NEVER run `uv tool install` while `sysmgr` is running**: On Windows, running `sysmgr` processes lock their `.exe` files in `AppData\Roaming\uv\tools\sysmgr\Scripts`. Running `uv tool install` while locked causes uv to wipe package metadata and fail with `Access is denied (os error 5)`, corrupting the tool environment with `No module named 'sysmgr'`.
- **Always terminate before tool maintenance**: If reinstalling the tool is necessary, always run `Stop-Process -Name sysmgr, python -Force -ErrorAction SilentlyContinue` first, then run `uv tool install --force --editable .` outside the sandbox (`BypassSandbox: true`).

### Running Tests
All tests are configured to run completely local, sandboxed, and offline:
```powershell
# Run the entire test suite (unit + live integration)
.venv\Scripts\pytest

# Run only unit tests
.venv\Scripts\pytest tests/unit

# Run with verbose output
.venv\Scripts\pytest -v
```

### Subprocess Guidelines
- Never use raw string commands or `shell=True` without strict argument arrays.
- Always provide explicit timeouts (`timeout=10` to `timeout=30`) on subprocess executions (`ipconfig`, `powershell`, `git`).
- For PowerShell commands affecting services, always include `-ErrorAction Stop` to ensure non-terminating errors properly trigger non-zero exit codes.
- Handle file lock exceptions (`PermissionError`, `OSError`) gracefully when inspecting or purging temporary storage.
