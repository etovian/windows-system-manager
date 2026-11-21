# System Manager (`sysmgr`) High-Level Roadmap & Milestones

**Status:** Living Roadmap  
**Current State:** Milestone 1 Complete & Shipped on `master`  
**Remote:** [https://github.com/etovian/windows-system-manager](https://github.com/etovian/windows-system-manager)  

---

## Roadmap Overview

This document outlines the high-level roadmap for each upcoming milestone of `sysmgr`. Each milestone will go through our standard engineering lifecycle: **Brainstorming → Spec/Design Review → Test-Driven Implementation → Review & Merge**.

```
┌────────────────────────────────┐
│ Milestone 1: Core Foundation   │ ──► [COMPLETED & SHIPPED]
│ - Engine, Typer CLI, Initial   │
│   Probes (BT, Space, TPM)      │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 2: Remediation Engine│ ──► [UP NEXT]
│ - `sysmgr fix`, Safety Tiers,  │
│   Dry-Run, Service/Temp Fixes  │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 3: Hardware & Device │
│ - Device Manager (All PnP),    │
│   Network Adapters, Audio      │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 4: Storage & SMART   │
│ - SMART Health, Disk Queue/IO, │
│   Top IO Process Attribution   │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Milestone 5: System Hygiene    │
│ - Pending Reboots, CBS Keys,   │
│   Event Log Correlation        │
└────────────────────────────────┘
```

---

## Milestone 2: Automated & Interactive Remediation Engine (`sysmgr fix`)

**Goal:** Turn diagnostic findings into safe, verifiable, and executable remediations that can be triggered interactively by administrators or invoked programmatically by an AI agent.

### Core Objectives
1. **Remediation Execution Engine (`src/sysmgr/remediations/`)**:
   - Central `RemediationRunner` that resolves and executes `RemediationAction` handlers.
   - Idempotency guarantees: Every fix verifies whether the issue is already resolved before taking action.
   - Post-remediation verification: Automatically re-runs the parent probe to confirm the fix resolved the condition.
2. **Safety & Privilege Governance**:
   - `SAFE`: Zero confirmation required in CLI; completely non-destructive (e.g., starting a stopped standard service).
   - `CONFIRMATION_REQUIRED`: Interactive prompt in CLI (`--yes` to bypass); warns about process interruptions (e.g., terminating high-I/O task).
   - `ELEVATED`: Detects UAC administrator status via `ctypes.windll.shell32.IsUserAnAdmin()`. If not elevated, provides clear elevation instructions or launches an elevated PowerShell worker if requested.
   - `--dry-run` flag: Previews actions, modified registry keys, and affected services without altering state.
3. **Initial Executable Remediations**:
   - `start-bluetooth-service`: Starts or restarts `bthserv` / `BthHFSrv`.
   - `clean-temp-files`: Safely purges non-locked files in `%TEMP%` and `C:\Windows\Temp`.
   - `reset-bluetooth-device`: Executes PnP restart (`pnputil /restart-device <InstanceId>`) with admin check.
4. **CLI Integration**:
   - `sysmgr fix <action_id>` (executes a specific action by ID).
   - `sysmgr doctor --fix` (runs full diagnostics and interactively offers to resolve all detected issues).

---

## Milestone 3: Deep Hardware & Peripheral Diagnostics

**Goal:** Provide comprehensive, system-wide hardware monitoring to catch failing drivers, misconfigured adapters, and hardware crashes.

### Core Objectives
1. **`DeviceManagerProbe` (`sysmgr.probes.hardware.device_manager`)**:
   - Scans all active and disconnected PnP devices via CIM/WMI (`Win32_PnPEntity`).
   - Flags all devices reporting `ConfigManagerErrorCode != 0`.
   - Identifies missing drivers (Code 28), device start failures (Code 10), and firmware crashes (Code 43).
2. **`NetworkAdapterProbe` (`sysmgr.probes.hardware.network`)**:
   - Evaluates physical Ethernet and Wi-Fi interface statuses, IP configuration, and link speed.
   - Validates gateway reachability via low-latency ICMP ping and DNS resolution.
   - Detects disconnected media, APIPA self-assigned IPs (169.254.x.x), and broken DNS servers.
3. **`AudioSubsystemProbe` (`sysmgr.probes.hardware.audio`)**:
   - Verifies Windows Audio services (`Audiosrv`, `AudioEndpointBuilder`).
   - Inspects default playback and recording endpoint states and muted states.
4. **Knowledge Base Runbooks**:
   - `knowledge/hardware/pnp-error-codes.md`: Exhaustive index of Device Manager codes and specific recovery steps.
   - `knowledge/hardware/network-troubleshooting.md`: Decision trees for gateway loss, DNS failure, and Wi-Fi adapter resets.

---

## Milestone 4: Storage Health, SMART, and I/O Telemetry

**Goal:** Move beyond partition space to detect physical drive failure indicators and identify I/O performance bottlenecks.

### Core Objectives
1. **`DiskHealthProbe` (`sysmgr.probes.storage.health`)**:
   - Queries physical drive health status via Windows Storage Management APIs (`Get-PhysicalDisk`) and WMI `MSStorageDriver_FailurePredictStatus`.
   - Inspects operational status (`OK`, `Degraded`, `Error`) and predictive failure warnings.
   - Flags SSD wear level or media errors where exposed by NVMe/SATA drivers.
2. **`DiskPerformanceProbe` (`sysmgr.probes.storage.performance`)**:
   - Tracks active disk queue lengths and read/write latency spikes.
   - Identifies the top 5 processes consuming disk I/O in real time via `psutil`.
3. **Interactive Cleanup Candidate Explorer (`sysmgr storage analyze`)**:
   - Discovers large directory bloat (e.g. node_modules, build artifacts, package caches) without modifying them.
4. **Knowledge Base Runbooks**:
   - `knowledge/storage/smart-health-monitoring.md`: Interpreting predictive failures, bad sectors, and NTFS event logs.
   - `knowledge/storage/disk-io-bottlenecks.md`: Troubleshooting disk queue saturation and runaway disk writers.

---

## Milestone 5: System Hygiene & Upgrade Readiness Deep Dive

**Goal:** Detect subtle system degradation factors, pending restart flags, and OS upgrade barriers.

### Core Objectives
1. **`SystemHygieneProbe` (`sysmgr.probes.readiness.hygiene`)**:
   - Detects pending reboot states across Windows registry locations:
     - Component-Based Servicing (`RebootPending`)
     - Windows Update (`RebootRequired`)
     - `PendingFileRenameOperations`
   - Evaluates system uptime (flags systems running without reboot > 30 days).
   - Scans for recent Blue Screen of Death (BSOD) minidumps in `C:\Windows\Minidump`.
2. **`HardwareBaselineProbe` (`sysmgr.probes.readiness.hardware_baseline`)**:
   - Inspects CPU architecture, generation, core counts, and required instruction set extensions (SSE4.2, PopCnt).
   - Validates total physical RAM against modern OS baseline requirements.
3. **Event Log Correlation Engine (`sysmgr.utils.eventlog`)**:
   - Queries Windows Event Log (`System` / `Application`) for critical hardware and OS events:
     - Event ID 41 (Kernel-Power unexpected shutdown)
     - Event ID 55 (NTFS filesystem corruption)
     - Event ID 1001 (BugCheck / BSOD)
4. **Knowledge Base Runbooks**:
   - `knowledge/readiness/pending-reboot-flags.md`: Why pending reboots lock installations and how to safely inspect them.
   - `knowledge/readiness/bsod-triage.md`: Analyzing bugcheck stop codes and minidump locations.

---

## Suggested Milestone Progression
We will proceed through each milestone in order:
1. **Milestone 2 (Remediation Engine)**: Completes the loop on the existing probes so detected issues can be resolved.
2. **Milestone 3 (Hardware & Peripherals)**: Expands device troubleshooting capabilities.
3. **Milestone 4 (Storage & SMART)**: Adds physical disk health and I/O monitoring.
4. **Milestone 5 (Hygiene & Readiness)**: Adds pending reboots, event logs, and baseline checks.
