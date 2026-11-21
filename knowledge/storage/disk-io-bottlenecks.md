# Storage Disk I/O Performance & Bottlenecks Runbook

## Overview

Disk input/output (I/O) saturation occurs when storage subsystems are inundated with read and write requests faster than the physical media (HDD or SSD) can service them. This results in elevated disk queue lengths, severe request latency (response times exceeding 20-50 ms on SSDs or 100+ ms on mechanical HDDs), and overall operating system unresponsiveness, freezing, or sluggish UI performance.

This runbook outlines the key metrics for measuring disk throughput and queuing, details common runaway background processes that saturate I/O on Windows systems, and provides safe, non-destructive triage procedures.

---

## Key Performance Indicators & Thresholds

### 1. Disk Read & Write Throughput
- **Measurement**: Aggregated transfer rate in Megabytes per Second (MB/s) and cumulative bytes transferred.
- **PSUtil Metric**: `psutil.disk_io_counters()` reporting `read_bytes`, `write_bytes`, `read_count`, and `write_count`.
- **Baseline Expectations**:
  - Idle / Typical Desktop Workload: < 10-25 MB/s aggregate.
  - Active File Transfer / Compilation: Bursting up to 500 MB/s (SATA SSD) or 3,000-7,000 MB/s (NVMe Gen4 SSD).
  - Sustained saturation by a single process generating > 100 GB (100,000 MB) cumulative I/O or saturating transfer bandwidth warrants investigation for runaway loops or memory-to-disk thrashing.

### 2. Disk Queue Length & Latency
- **Current Disk Queue Length**: Number of pending I/O requests queued up waiting for disk service. A sustained queue length greater than 2 per physical disk spindle (or > 10-20 on high-queue-depth NVMe drives) indicates a storage bottleneck.
- **Disk Response Time (Average Latency)**:
  - `< 10 ms`: Excellent performance.
  - `10 - 25 ms`: Acceptable during heavy bursts.
  - `> 50 ms`: Bottleneck threshold (perceptible user delay).
  - `> 100 - 500 ms`: Severe storage starvation; UI freezes and application hangs occur.

---

## Common Runaway Background Processes

When high disk I/O occurs on Windows, specific system services and third-party software are frequently the culprit:

### 1. Windows Search Indexer (`SearchIndexer.exe`)
- **Role**: Indexes local files, emails, and filesystem properties to enable fast desktop search.
- **Failure Mode**: When corrupted indexing databases (`Windows.edb`) occur or when indexing dense source code trees, node_modules directories, or virtual machine images, the indexer can consume 100% disk activity for hours.

### 2. Microsoft Defender Antivirus / Antimalware Service Executable (`MsMpEng.exe`)
- **Role**: Real-time antimalware file scanning and behavior analysis.
- **Failure Mode**: Scans massive directories containing thousands of small files (such as build artifact directories, git object stores, or databases) synchronously as files are touched.

### 3. Windows Compatibility Telemetry & Update Services (`CompatTelRunner.exe`, `TiWorker.exe`, `TrustedInstaller.exe`)
- **Role**: App and driver compatibility diagnostics, Windows Update servicing operations.
- **Failure Mode**: Scheduled maintenance triggers deep scans of the filesystem and component store (`WinSxS`), driving high disk read/write throughput during user working hours.

### 4. Runaway Electron, Database, or Logging Applications
- **Role**: Development environments, local databases (Docker containers, WSL2 virtual disks `vhd`), or communication tools (Slack, Teams, Discord).
- **Failure Mode**: Runaway debug log loops writing continuous uncapped log files, or unindexed database queries performing full table scans over multiple gigabytes.

---

## Non-Destructive Triage & Investigation Steps

### Step 1: Real-Time Process Inspection via Resource Monitor & Process Explorer

1. Launch Windows **Resource Monitor**:
   ```cmd
   resmon.exe
   ```
2. Navigate to the **Disk** tab.
3. Review:
   - **Processes with Disk Activity**: Sort by `Total (B/sec)` to pinpoint the exact processes consuming bandwidth.
   - **Disk Activity**: Inspect the target file paths being accessed. Identifying the specific files being read or written reveals the source of the load (e.g., a specific log file or `.git` directory).
4. Alternatively, use Sysinternals **Process Explorer**:
   - Add column `I/O Delta Total Bytes` or `I/O Read Bytes` / `I/O Write Bytes`.
   - Identify the PID and parent process hierarchy.

### Step 2: Inspecting and Lowering Process I/O Priority

Windows supports I/O Priority levels (`Very Low / Background`, `Low`, `Normal`, `High`, `Critical`). Processes set to Background I/O yield disk access to interactive applications:

- **Check or Adjust I/O Priority**:
  Using Process Explorer, right-click the offending process -> **I/O Priority** -> set to **Low** or **Background**.
  *Note: This mitigates UI starvation without terminating the process.*

### Step 3: Safe Triage of Common System Culprits

#### For `SearchIndexer.exe`:
- Pause indexing temporarily:
  ```powershell
  Stop-Service "WSearch"
  ```
- Exclude large development and build folders (e.g., `node_modules`, `.venv`, `.git`, target build directories) from Indexing Options in Control Panel.
- If the index is corrupt, rebuild the index via **Indexing Options** -> **Advanced** -> **Rebuild Index**.

#### For `MsMpEng.exe` (Defender):
- Safely add process or path exclusions in Windows Security for project development directories or trusted build outputs rather than disabling protection entirely.
- Verify through PowerShell:
  ```powershell
  Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
  ```

#### For Suspicious or Runaway Applications:
- If a user-mode background process has written tens or hundreds of gigabytes of logs in error:
  - Check the application's configuration or log folder.
  - Gracefully restart the service or application.

---

## sysmgr Diagnostic Contract

- **Probe ID**: `storage.disk_performance`
- **Category**: `storage`
- **Output Signals**:
  - `status`:
    - `PASS`: Normal aggregate disk I/O activity, no runaway processes detected.
    - `WARN`: Excessive disk I/O volume detected (e.g., top process exceeding 100 GB cumulative I/O) or unable to query I/O counters.
  - `details`:
    - `io_counters`: Cumulative system read/write bytes and read/write operation counts.
    - `top_processes`: List of top processes by cumulative I/O with `pid`, `name`, `read_mb`, `write_mb`, and `total_mb`.
  - `remediations`:
    - `inspect-io-process`: Advisory action to inspect the top I/O consumer (Risk: `SAFE`, Requires Admin: `False`).
