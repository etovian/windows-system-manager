# Storage Physical Disk SMART & Health Monitoring Runbook

## Overview

Self-Monitoring, Analysis, and Reporting Technology (SMART) is a monitoring system included in computer hard disk drives (HDDs) and solid-state drives (SSDs) that detects and reports various indicators of drive reliability. The intent is to anticipate impending hardware failures before catastrophic data loss occurs.

On Windows, physical disk health and SMART predictive failure status are accessible through two primary subsystems:
1. **Windows Storage Management PowerShell Cmdlets (`Get-PhysicalDisk`)**: High-level storage abstraction reporting operational status and health across SATA, NVMe, SAS, and USB drives.
2. **WMI / CIM Storage Driver Interface (`MSStorageDriver_FailurePredictStatus`)**: Direct query into `root/wmi` querying ATA/SCSI miniporter failure prediction flags reported by device firmware.

---

## Predictive Failure Detection Mechanisms

### 1. WMI `MSStorageDriver_FailurePredictStatus`

Located under the `root/wmi` CIM namespace, `MSStorageDriver_FailurePredictStatus` queries the underlying storage driver stack for predictive failure status.

```powershell
Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_FailurePredictStatus | Select-Object InstanceName, PredictFailure, Reason
```

- **`PredictFailure`**: A boolean flag (`True` / `False`). When `True`, the drive firmware has detected that one or more critical SMART health thresholds have been breached, indicating imminent hardware failure.
- **`Reason`**: Vendor-specific failure code corresponding to the breached SMART attribute.

### 2. Windows Storage Management `Get-PhysicalDisk`

Windows Storage Management provides standardized operational and health status across all storage buses:

```powershell
Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, HealthStatus, OperationalStatus
```

#### Operational Status Codes:
- **`OK`**: The drive is operating normally with no detected faults.
- **`Predictive Failure`**: SMART telemetry indicates that the drive has exceeded error thresholds and is nearing failure.
- **`Degraded`**: The physical drive is functional but performance or reliability is impaired (e.g., thermal throttling, transient bus errors, degraded array member).
- **`Lost Communication`**: The operating system has lost connectivity with the storage controller or disk.
- **`Error`**: A fatal non-recoverable error condition occurred on the physical device.

---

## Critical SMART Attributes

While NVMe drives provide standardized health logs (percentage used, critical warning bitmask) and SATA/AHCI drives expose numbered SMART attributes, the following indicators are the most critical predictors of drive failure:

### 1. Reallocated Sectors Count (ID 05)
- **Mechanism**: When a hard drive encounters a read/write/verification error on a sector, it marks the sector as bad and reallocates it to a spare reserve track.
- **Impact**: A non-zero or rapidly growing reallocated sector count indicates physical media degradation. Once spare sectors are exhausted, bad sectors cause unrecoverable read errors.

### 2. Reported Uncorrectable Errors (ID BB / 187)
- **Mechanism**: Tracks read errors that could not be recovered using hardware error correction code (ECC).
- **Impact**: Uncorrectable read errors directly result in I/O timeouts, frozen processes, and corrupt files. Any non-zero count is a strong indicator of drive failure.

### 3. SSD Wear Level / Percentage Used Indicator (ID E7 / NVMe byte 5)
- **Mechanism**: Monitors flash memory endurance cycles and remaining spare blocks.
- **Impact**: Flash memory has finite program/erase (P/E) cycles. When wear indicators reach 100% or remaining life drops near 0%, the drive enters read-only protection or suffers cell exhaustion.

---

## Remediation & Recovery Guidelines

When a drive enters `Predictive Failure`, `Degraded`, or `Error` state, follow these immediate, non-destructive recommendations:

### Step 1: Immediate Critical Data Backup (Priority 1)
- **Do NOT run intensive write operations, disk defragmentation, or heavy benchmarking** on a failing drive; stressful I/O can trigger total drive failure.
- Immediately back up critical files, user profiles, credentials, and work repositories to an external drive, network-attached storage (NAS), or cloud storage (OneDrive, Google Drive, Azure/AWS).
- If creating an image backup, prioritize file-level extraction of critical assets first in case the drive dies mid-imaging.

### Step 2: Diagnostic Verification
- Run manufacturer-specific diagnostic tools (e.g., Samsung Magician, Crucial Storage Executive, Western Digital Dashboard, Seagate SeaTools) to verify drive firmware updates and detailed SMART telemetry.
- Run non-destructive file system scans:
  ```cmd
  chkdsk <DriveLetter>: /scan
  ```
  *(Note: The `/scan` flag runs online in read-only mode without taking the drive offline or forcing destructive repairs).*

### Step 3: Drive Replacement Planning
- Provision a replacement drive matching or exceeding the current drive's interface speed and capacity (e.g., PCIe Gen4 M.2 NVMe).
- Plan scheduled downtime for disk replacement and system image restore.
- Safely decommission and securely sanitize the retiring drive in accordance with data privacy standards once migration is complete.
