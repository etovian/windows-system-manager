# Windows Disk Space & Cleanup Guidelines

## Overview
Storage exhaustion on Windows causes performance degradation, update failures (0x80070070), and system instability when the system partition (`C:`) drops below critical thresholds.

---

## Thresholds & Severity
- **PASS**: Free space >= 15% AND Free space >= 10 GB.
- **WARN**: Free space < 15% OR Free space < 10 GB. System updates or large temp files may fail.
- **FAIL**: Free space < 5% OR Free space < 3 GB. Severe risk of crash, disk lockup, or corrupted shadow copies.

---

## Safe vs. Risky Cleanup Targets

### 1. Safe Targets (Automated or Prompted)
- **User Temp**: `%TEMP%` (`C:\Users\<user>\AppData\Local\Temp`) - safe to clear files not locked by active processes.
- **Windows Temp**: `C:\Windows\Temp` - safe to clear stale files.
- **Recycle Bin**: `Clear-RecycleBin -Force`.
- **Delivery Optimization Cache**: `C:\Windows\SoftwareDistribution\DeliveryOptimization`.

### 2. Moderately Safe (Confirmation Required)
- **Windows Update Download Cache**: `C:\Windows\SoftwareDistribution\Download` (requires stopping `wuauserv` first).
- **Crash Dumps**: `C:\Windows\Minidump`, `C:\Windows\MEMORY.DMP`.

### 3. DO NOT Clean Manually (High Risk / Breaking)
- **`C:\Windows\WinSxS`**: NEVER delete files manually. Use DISM:
  ```powershell
  Dism.exe /online /Cleanup-Image /StartComponentCleanup /ResetBase
  ```
- **`C:\Windows\System32`**: Never touch.
- **Pagefile / Swapfile**: Managed by Windows Virtual Memory subsystem.

---

## sysmgr Diagnostic Contract
- **Probe ID**: `storage.disk_space`
- **Output Signals**:
  - `status`: `PASS`, `WARN`, `FAIL` per volume.
  - `details`: Per-partition total, used, free bytes, and utilization percentage.
  - `remediations`:
    - `clean-temp-files` (Risk: SAFE)
    - `dism-component-cleanup` (Risk: ELEVATED, Requires Admin)
