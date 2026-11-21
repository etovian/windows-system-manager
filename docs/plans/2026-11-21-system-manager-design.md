# System Manager (`sysmgr`) Design Specification

**Date:** 2026-11-21  
**Status:** Approved  
**Author:** Antigravity & User  

---

## 1. Overview & Goals

`sysmgr` is an agent-integrated Windows system utilities, health, and management suite. It combines deterministic diagnostic probes, automated safe remediations, and a structured system troubleshooting knowledge base.

It is designed for direct collaborative use by an AI assistant (Antigravity) and human administrators via a unified CLI (`uv run sysmgr`) and structured machine-readable outputs (`--json`).

### Primary Objectives
- **Comprehensive Diagnostics:** Modular probes for Hardware & Peripherals (Bluetooth, USB, Network, Drivers), Storage & Disks (SMART, partition space, I/O performance), and System Health & Upgrade Readiness (TPM 2.0, Secure Boot, CPU/RAM, OS integrity).
- **Agent Integration:** Structured JSON outputs, clear error classification, and evidence tagging designed for AI decision-making.
- **Troubleshooting Knowledge Base:** Curated runbooks, failure mode trees, and Windows Event ID mappings to inform diagnostic interpretation and resolution pathways.
- **Safe & Deterministic Remediation:** Clearly segregated risk tiers (`SAFE`, `CONFIRMATION_REQUIRED`, `ELEVATED`) with explicit pre-conditions and verification.

---

## 2. Architecture & Core Abstractions

```
       ┌────────────────────────────────────────────────────────┐
       │                Antigravity Chat Session                │
       └──────────────────────────┬─────────────────────────────┘
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│       Knowledge Base          │               │        CLI & Tool Suite       │
│  - Diagnostic Decision Trees  │               │  `sysmgr <subsystem> check`   │
│  - Windows Event ID Mappings  │               │  `sysmgr <subsystem> fix`     │
│  - Driver & Hardware Runbooks │               │  `sysmgr doctor --json`       │
└─────────┬─────────────────────┘               └───────────────┬───────────────┘
          │                                                     │
          └───────────────────────┬─────────────────────────────┘
                                  ▼
                   Informed Diagnosis & Remediation
                   (Agent analyzes data against playbooks,
                    explains cause, recommends/runs action)
```

### Core Data Models (`src/sysmgr/core/models.py`)

- **`DiagnosticStatus` (Enum):**
  - `PASS`: Subsystem is operating normally within expected parameters.
  - `WARN`: Non-critical anomaly, impending capacity threshold, or missing optional feature.
  - `FAIL`: Critical failure, driver error code, device offline, or blocking readiness check.
  - `INFO`: Informational telemetry or state where pass/fail is not applicable.

- **`RemediationAction` (Pydantic Model):**
  - `id`: Unique identifier (e.g., `hardware.bluetooth.restart-service`).
  - `description`: Human-readable explanation of the fix.
  - `risk_level`: `SAFE`, `CONFIRMATION_REQUIRED`, or `ELEVATED`.
  - `requires_admin`: Boolean flag indicating if elevation is mandatory.
  - `execute()`: Callable method executing the remediation logic.

- **`DiagnosticResult` (Pydantic Model):**
  - `probe_id`: Unique string ID (e.g. `hardware.bluetooth`).
  - `category`: Domain group (`hardware`, `storage`, `readiness`).
  - `status`: `DiagnosticStatus`.
  - `summary`: High-level 1–2 sentence summary of findings.
  - `details`: Structured dictionary containing raw telemetry and metrics.
  - `remediations`: List of applicable `RemediationAction` objects.
  - `knowledge_refs`: List of file paths to related runbooks in `knowledge/`.

- **`BaseProbe` (Protocol):**
  - `name`: Human-readable probe title.
  - `category`: Probe category.
  - `description`: Purpose and scope of the probe.
  - `requires_admin`: Whether the probe needs administrator privileges.
  - `async check() -> DiagnosticResult`: Execution method returning standardized results.

---

## 3. Component Breakdown & Initial Probes

### 3.1 Hardware & Peripherals (`sysmgr.probes.hardware`)
- **`BluetoothProbe`**:
  - Inspects radio power state, PnP device status codes (e.g. Code 43, Code 10).
  - Queries driver version and active services (`bthserv`, `BthHFSrv`).
  - Scans Windows Event Log for recent `BTHUSB` or Bluetooth stack errors.
- **`DeviceManagerProbe`**:
  - Scans active PnP devices for non-zero `ConfigManagerErrorCode`.
  - Flags missing drivers, suspended devices, or hardware fault codes.
- **`NetworkAdapterProbe`**:
  - Verifies interface status (Ethernet/Wi-Fi), DHCP/DNS reachability, gateway connectivity.

### 3.2 Storage & Disk Utilities (`sysmgr.probes.storage`)
- **`DiskSpaceProbe`**:
  - Evaluates partition usage and capacity limits across all mount points.
  - Flags temporary directory bloat and candidate cleanup targets.
- **`DiskHealthProbe`**:
  - Queries SMART health status via WMI (`MSStorageDriver_FailurePredictStatus`) and Windows Storage Management API (`Get-PhysicalDisk`).
  - Detects predictive failure flags and media errors.
- **`DiskPerformanceProbe`**:
  - Measures disk queue length, read/write latency spikes, and top I/O consumer processes via `psutil`.

### 3.3 System Health & Upgrade Readiness (`sysmgr.probes.readiness`)
- **`TpmSecureBootProbe`**:
  - Validates TPM 2.0 presence, manufacturer, and enablement (`Win32_Tpm`).
  - Inspects Secure Boot UEFI status (`Confirm-SecureBootUEFI`).
- **`HardwareBaselineProbe`**:
  - Assesses CPU architecture/generation, core count, RAM capacity, and firmware mode (UEFI vs. Legacy BIOS).
- **`SystemHygieneProbe`**:
  - Detects pending reboot states (Component-Based Servicing, Windows Update registry keys).
  - Inspects pending servicing updates and basic OS build currency.

---

## 4. Execution Pipeline & Data Flow

1. **Discovery & Filtering:** Probes are registered in a centralized `ProbeRegistry`. Users/agents can target single probes, categories (`--category hardware`), or run the full suite (`sysmgr doctor`).
2. **Pre-flight Checks:** Privilege inspection via `ctypes.windll.shell32.IsUserAnAdmin()`. Probes requiring elevation degrade gracefully with clear status notes rather than unhandled errors.
3. **Concurrent Execution:** Run asynchronously with strict per-probe timeouts (default: 5s) using `asyncio.wait_for`.
4. **Aggregation:** Results collated into a `DiagnosticReport` sorted by severity (`FAIL` > `WARN` > `INFO` > `PASS`).
5. **Output Presentation:**
   - Interactive terminal: Formatted tables, status badges, and spinners via `Rich`.
   - Machine/Agent interface: Full structured JSON via `--json`.
6. **Remediation Execution:** Remediations can be triggered via `--fix` on the CLI or directly requested through specific subcommands.

---

## 5. Knowledge Base Structure

Stored in `knowledge/` as human- and agent-readable Markdown documents:
- `knowledge/hardware/bluetooth-troubleshooting.md`: Decision tree for Code 43, audio stutters, radio power states, and Windows service dependencies.
- `knowledge/hardware/pnp-error-codes.md`: Reference guide for Windows Device Manager error codes (Code 10, 19, 28, 43) and resolution strategies.
- `knowledge/storage/smart-health-monitoring.md`: Interpreting predictive disk failures, bad sectors, and NTFS event logs.
- `knowledge/storage/disk-cleanup-guidelines.md`: Safe vs. risky cleanup targets in Windows (WinSxS, temp directories, crash dumps).
- `knowledge/readiness/windows-upgrade-readiness.md`: Hardware and firmware requirements (TPM 2.0, UEFI, Secure Boot, CPU lists) and verification steps.

---

## 6. Project Layout & Dependencies

### Package Management
Managed via **`uv`**:
- Python version: >= 3.11
- Primary dependencies: `typer`, `rich`, `pydantic`, `psutil`, `pywin32`
- Development dependencies: `pytest`, `pytest-asyncio`, `pytest-mock`, `ruff`

### Directory Structure
```text
system-manager/
├── pyproject.toml
├── README.md
├── docs/
│   └── plans/
│       └── 2026-11-21-system-manager-design.md
├── knowledge/
│   ├── hardware/
│   ├── storage/
│   └── readiness/
├── src/
│   └── sysmgr/
│       ├── __init__.py
│       ├── cli.py
│       ├── core/
│       ├── probes/
│       │   ├── hardware/
│       │   ├── storage/
│       │   └── readiness/
│       ├── remediations/
│       └── utils/
└── tests/
    ├── unit/
    └── integration/
```

---

## 7. Testing Strategy

1. **Unit Testing:**
   - Isolated probe tests with mocked WMI, registry, and subprocess outputs (`pytest-mock`).
   - Validates classification logic (`PASS`/`WARN`/`FAIL`) across different synthetic device states (e.g. failed Bluetooth adapter, failing disk drive).
2. **Integration Smoke Testing:**
   - Live read-only tests against the host system (e.g., verifying `psutil` reads valid CPU/RAM, real volume partitions).
3. **Schema & Contract Verification:**
   - Validates that every probe strictly implements `BaseProbe` and produces serializable `DiagnosticResult` models matching the JSON schema.
