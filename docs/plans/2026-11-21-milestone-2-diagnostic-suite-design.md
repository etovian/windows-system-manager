# Milestone 2 Design Specification: Full Diagnostic Probes Suite (100% Read-Only)

**Date:** 2026-11-21  
**Status:** Approved  
**Author:** Antigravity & User  
**Scope:** 100% Observational & Read-Only (Zero Mutations)  

---

## 1. Overview & Objectives

Milestone 2 expands `sysmgr` from its initial 3 baseline probes to a comprehensive, 8-probe diagnostic and reporting suite covering all key Windows subsystems:
- **Hardware & Peripherals**: System-wide PnP Device Manager audit, Network adapter link state & DNS.
- **Storage & Disks**: Physical drive SMART health & predictive failure, Disk I/O throughput & process attribution.
- **System Hygiene & Readiness**: Pending reboot flags, long system uptime, and BSOD crash dump history.
- **Knowledge Base Expansion**: Detailed troubleshooting runbooks for each domain in `knowledge/`.

All diagnostics in Milestone 2 are strictly **read-only**. They observe and report telemetry with suggested advisory remediations, without applying any state changes to the system.

---

## 2. Architecture & Probe Roster

The full probe roster after Milestone 2:

| Probe ID | Category | Class | Primary Telemetry Source |
| :--- | :--- | :--- | :--- |
| `hardware.bluetooth` | `hardware` | `BluetoothProbe` (M1) | PnP & `bthserv` service |
| `hardware.device_manager` | `hardware` | `DeviceManagerProbe` *(New)* | Server-side filtered CIM (`Win32_PnPEntity`) |
| `hardware.network` | `hardware` | `NetworkAdapterProbe` *(New)* | `psutil.net_if_*`, `socket.getaddrinfo` |
| `storage.disk_space` | `storage` | `DiskSpaceProbe` (M1) | `psutil.disk_partitions`, `psutil.disk_usage` |
| `storage.disk_health` | `storage` | `DiskHealthProbe` *(New)* | `Get-PhysicalDisk`, WMI `MSStorageDriver_FailurePredictStatus` |
| `storage.disk_performance` | `storage` | `DiskPerformanceProbe` *(New)* | `psutil.disk_io_counters`, `psutil.process_iter` |
| `readiness.tpm_secure_boot` | `readiness` | `TpmSecureBootProbe` (M1) | `Win32_Tpm`, `Confirm-SecureBootUEFI` |
| `readiness.hygiene` | `readiness` | `SystemHygieneProbe` *(New)* | Python `winreg`, `psutil.boot_time()`, minidumps |

---

## 3. Detailed Component Specifications

### 3.1 `DeviceManagerProbe` (`src/sysmgr/probes/hardware/device_manager.py`)
- **Query**: Server-side filtered CIM query:
  ```powershell
  Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object Name, DeviceID, PNPClass, ConfigManagerErrorCode
  ```
- **Evaluation**:
  - `PASS`: No devices returning non-zero error codes.
  - `INFO`: Devices disabled deliberately by user (Code 22).
  - `FAIL`: Devices reporting hardware crashes (Code 43), start failures (Code 10), driver issues (Code 28), or registry corruption (Code 19).
- **Runbook**: `knowledge/hardware/pnp-error-codes.md`.

### 3.2 `NetworkAdapterProbe` (`src/sysmgr/probes/hardware/network.py`)
- **Query**:
  - Network interfaces and link state via `psutil.net_if_stats()`.
  - IP addresses and subnets via `psutil.net_if_addrs()`.
  - DNS resolution check via `socket.getaddrinfo("dns.google", 53)`.
- **Evaluation**:
  - `PASS`: At least one primary interface is up, has a routable IP, and resolves DNS.
  - `WARN`: Active interface has APIPA address (`169.254.x.x`) or DNS resolution fails.
  - `FAIL`: All physical/Wi-Fi network interfaces are disconnected or disabled.
- **Runbook**: `knowledge/hardware/network-troubleshooting.md`.

### 3.3 `DiskHealthProbe` (`src/sysmgr/probes/storage/disk_health.py`)
- **Query**:
  - Windows Storage Management (`Get-PhysicalDisk`) for `DeviceID`, `FriendlyName`, `MediaType`, and `OperationalStatus`.
  - WMI `MSStorageDriver_FailurePredictStatus` for `PredictFailure` boolean.
- **Evaluation**:
  - `PASS`: All physical drives report `PredictFailure == False` and `OperationalStatus == 'OK'`.
  - `WARN`: Drive reports degraded status or transient warnings.
  - `FAIL`: Drive reports `PredictFailure == True` or non-recoverable error states.
- **Runbook**: `knowledge/storage/smart-health-monitoring.md`.

### 3.4 `DiskPerformanceProbe` (`src/sysmgr/probes/storage/disk_performance.py`)
- **Query**:
  - System-wide cumulative read/write counts and bytes via `psutil.disk_io_counters()`.
  - Process I/O iteration via `psutil.process_iter(['pid', 'name', 'io_counters'])` to rank the top 5 highest cumulative I/O processes.
- **Evaluation**:
  - `PASS`: Normal disk operation.
  - `WARN`: Disk shows heavy saturation or a runaway process consuming extreme I/O.
- **Runbook**: `knowledge/storage/disk-io-bottlenecks.md`.

### 3.5 `SystemHygieneProbe` (`src/sysmgr/probes/readiness/hygiene.py`)
- **Query**:
  - Windows Registry queries via Python `winreg` (zero process spawn overhead):
    - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending`
    - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired`
    - `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager` (`PendingFileRenameOperations`)
  - Continuous system uptime via `psutil.boot_time()`.
  - Minidump inspection in `C:\Windows\Minidump` for crashes in the last 7 days.
- **Evaluation**:
  - `PASS`: Zero pending reboot flags, uptime < 30 days, zero recent minidumps.
  - `WARN`: Pending reboot flag detected, uptime exceeds 30 days, or crash dump found.
- **Runbook**: `knowledge/readiness/pending-reboot-flags.md`.

---

## 4. Testing Strategy

1. **Mocked Unit Tests**:
   - `tests/unit/probes/test_device_manager.py` (CIM error codes Code 10, 28, 43 vs clean)
   - `tests/unit/probes/test_network.py` (Mocked network adapters, APIPA IPs, DNS failures)
   - `tests/unit/probes/test_disk_health.py` (Mocked SMART predictive failure vs healthy drive)
   - `tests/unit/probes/test_disk_performance.py` (Mocked I/O counters and top process ranking)
   - `tests/unit/probes/test_hygiene.py` (Mocked registry keys for CBS/WindowsUpdate reboot pending, uptime)
2. **Integration Tests against Host**:
   - Live read-only smoke tests in `tests/integration/test_live_smoke.py` verifying real system execution on the Windows host.
