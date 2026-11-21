# System Manager (`sysmgr`) High-Level Roadmap & Milestones

**Status:** Living Roadmap  
**Current State:** Milestone 1 Complete & Shipped on `master`  
**Remote:** [https://github.com/etovian/windows-system-manager](https://github.com/etovian/windows-system-manager)  

---

## Roadmap Overview

```
┌────────────────────────────────┐
│ Milestone 1: Core Foundation   │ ──► [COMPLETED & SHIPPED]
│ - Engine, Typer CLI, Initial   │
│   Probes (BT, Space, TPM)      │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 2: Full Detection &  │ ──► [CURRENT FOCUS: 100% READ-ONLY]
│ Diagnostic Suite               │
│ - Device Manager (All PnP)     │
│ - Network & DNS Adapters       │
│ - Disk SMART & I/O Metrics     │
│ - System Hygiene & Reboots     │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 3: Remediation Engine│ ──► [FUTURE]
│ - `sysmgr fix`, Safety Tiers,  │
│   Dry-Run, Mutation Handlers   │
└────────────────────────────────┘
```

---

## Milestone 2: Full Detection & Diagnostic Suite (100% Read-Only)

**Goal:** Complete the full diagnostic observation and reporting surface across Windows hardware, networking, storage health, and system hygiene without applying any mutations or fixes.

### Core Deliverables

#### 1. Hardware & Peripheral Probes (`sysmgr.probes.hardware`)
* **`DeviceManagerProbe` (`hardware.device_manager`)**:
  - Scans all system PnP entities (`Win32_PnPEntity`).
  - Identifies and flags any device with non-zero `ConfigManagerErrorCode` (e.g. Code 10, Code 19, Code 28, Code 43).
  - Reports affected device class, hardware ID, and driver status.
* **`NetworkAdapterProbe` (`hardware.network`)**:
  - Evaluates active physical and Wi-Fi network interfaces.
  - Tests default gateway ICMP reachability and DNS resolution.
  - Detects link drops, APIPA self-assigned IPs (`169.254.x.x`), and unconfigured DNS.

#### 2. Storage & Disk Probes (`sysmgr.probes.storage`)
* **`DiskHealthProbe` (`storage.disk_health`)**:
  - Queries physical drive health and SMART predictive failure status using WMI (`MSStorageDriver_FailurePredictStatus`) and Windows Storage Management (`Get-PhysicalDisk`).
  - Reports operational status (`OK`, `Degraded`, `Error`) and bad sectors.
* **`DiskPerformanceProbe` (`storage.disk_performance`)**:
  - Measures active disk queue lengths and read/write latency.
  - Identifies top 5 processes currently generating disk I/O via `psutil`.

#### 3. System Hygiene & Readiness Probes (`sysmgr.probes.readiness`)
* **`SystemHygieneProbe` (`readiness.hygiene`)**:
  - Inspects pending reboot flags across:
    - Component-Based Servicing (`RebootPending`)
    - Windows Update (`RebootRequired`)
    - `PendingFileRenameOperations`
  - Flags system uptime > 30 days without restart.
  - Detects recent BSOD crash dumps in `C:\Windows\Minidump`.

#### 4. Troubleshooting Knowledge Base Additions
* `knowledge/hardware/pnp-error-codes.md`: Exhaustive index of Device Manager error codes and diagnostic interpretation.
* `knowledge/hardware/network-troubleshooting.md`: Troubleshooting gateway reachability, DNS failures, and adapter states.
* `knowledge/storage/smart-health-monitoring.md`: Interpreting predictive drive failure flags and SMART attributes.
* `knowledge/readiness/pending-reboot-flags.md`: Guide to Windows reboot flags and how they block updates or installer operations.

---

## Milestone 3: Automated & Interactive Remediation Engine (`sysmgr fix`)

**Goal:** Turn diagnostic findings into safe, verifiable, and executable remediations that can be triggered interactively by administrators or invoked programmatically by an AI agent.

### Core Objectives
1. **Remediation Execution Engine (`src/sysmgr/remediations/`)**:
   - Central `RemediationRunner` that resolves and executes `RemediationAction` handlers.
   - Idempotency guarantees: Every fix verifies whether the issue is already resolved before taking action.
   - Post-remediation verification: Automatically re-runs the parent probe to confirm the fix resolved the condition.
2. **Safety & Privilege Governance**:
   - `SAFE`: Zero confirmation required in CLI; completely non-destructive (e.g., starting a stopped standard service).
   - `CONFIRMATION_REQUIRED`: Interactive prompt in CLI (`--yes` to bypass); warns about process interruptions (e.g., terminating high-I/O task).
   - `ELEVATED`: Detects UAC administrator status via `ctypes.windll.shell32.IsUserAnAdmin()`.
   - `--dry-run` flag: Previews actions, modified registry keys, and affected services without altering state.
3. **Executable Remediations**:
   - `start-bluetooth-service`: Starts or restarts `bthserv` / `BthHFSrv`.
   - `clean-temp-files`: Safely purges non-locked files in `%TEMP%` and `C:\Windows\Temp`.
   - `reset-bluetooth-device`: Executes PnP restart (`pnputil /restart-device <InstanceId>`) with admin check.
4. **CLI Integration**:
   - `sysmgr fix <action_id>` (executes a specific action by ID).
   - `sysmgr doctor --fix` (runs full diagnostics and interactively offers to resolve all detected issues).
