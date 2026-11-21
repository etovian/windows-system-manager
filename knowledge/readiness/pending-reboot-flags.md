# Windows System Hygiene & Pending Reboot Flags Runbook

## Overview
Pending reboot conditions and prolonged system uptime create hidden failure states on Windows systems. When Windows updates, driver installations, or service packs defer file replacements until the next reboot, critical subsystem states become locked. Similarly, unchecked system uptimes exceed typical stability windows, increasing risk of memory fragmentation, kernel pool exhaustion, unpatched vulnerabilities, and silent driver degradation.

---

## Pending Reboot Registry Indicators

Windows tracks pending system restarts across three primary registry locations:

### 1. Component-Based Servicing (CBS)
- **Registry Key**: `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending`
- **Source**: Servicing stack updates (SSU), cumulative updates (LCU), and Windows feature installation/uninstallation.
- **Impact**: When this key exists, the TrustedInstaller service (`TrustedInstaller.exe`) restricts further package servicing and feature state changes.

### 2. Windows Update (Auto Update)
- **Registry Key**: `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired`
- **Source**: Windows Update client (WUA) downloads and stages patches requiring a system restart to finalize deployment.
- **Impact**: Prevents subsequent update rollouts and triggers user-facing or scheduled restart deadlines.

### 3. Session Manager (Pending File Rename Operations)
- **Registry Key**: `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager`
- **Value Name**: `PendingFileRenameOperations` (`REG_MULTI_SZ`)
- **Source**: MSI installers, application updaters, and kernel-mode driver installers that attempt to overwrite locked DLLs or binaries. The kernel Session Manager subsystem (`smss.exe`) processes these file renames and deletions early in the boot cycle.
- **Impact**: MSI installers (`msiexec`) return error code 1618 (`ERROR_INSTALL_ALREADY_RUNNING`) or fail installation pre-checks while file rename operations remain queued.

---

## Operational Impacts of Pending Reboots
- **Installer Service Lockouts**: Windows Installer (`msiexec`) and Windows Servicing Stack refuse new software installations or rollouts.
- **Configuration Staging Inconsistency**: Staged assemblies and manifest files operate in dual-state limbo, leading to runtime version mismatches or unpredictable service behavior.
- **Corrupted Rollback Recovery**: Interrupting or stacking multiple installers atop unresolved reboot flags can corrupt the component store (`WinSxS`).

---

## System Uptime & Stability Thresholds
- **Recommended Maximum Uptime**: Continuous uptime exceeding **30 days** risks driver memory leaks (non-paged pool exhaustion), stale handle leaks, and out-of-sync security patches.
- **Enterprise Baselines**: Standard hygiene policies target regular weekly or monthly maintenance reboots aligned with Patch Tuesday cycles.

---

## Crash Dump Triage (Minidumps)
- **Default Directory**: `C:\Windows\Minidump`
- **File Format**: `*.dmp` files (e.g., `052126-12345-01.dmp`)
- **Triage Window**: Minidumps created or modified within the past **7 days** indicate recent Blue Screen of Death (BSOD) kernel bug checks.
- **Triage Recommendations**:
  - Inspect dump files using `dumpcheck.exe` or WinDbg (`!analyze -v`).
  - Identify failing driver modules (e.g., `ntoskrnl.exe`, GPU display drivers, third-party filter drivers).

---

## Non-Destructive Triage Recommendations
1. **Inspect Pending File Renames Before Rebooting**:
   - Query `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations` to ensure legitimate files are queued and no malicious persistence hooks exist.
2. **Schedule Controlled Restart**:
   - Issue a controlled, grace-period reboot to give active services and user applications time to close cleanly:
     ```cmd
     shutdown /r /t 60 /c "System Manager: Scheduled restart to clear pending servicing flags"
     ```
3. **Abort Accidental Restart**:
   - If active jobs need completion before reboot:
     ```cmd
     shutdown /a
     ```

---

## sysmgr Diagnostic Contract
- **Probe ID**: `readiness.hygiene`
- **Category**: `readiness`
- **Name**: `System Hygiene & Reboot State`
- **Status Evaluation**:
  - `PASS`: Zero pending reboot flags, uptime <= 30 days, zero crash dumps in the last 7 days.
  - `WARN`: Any pending reboot detected, continuous uptime > 30 days, or recent crash dump found in `C:\Windows\Minidump`.
- **Remediations**:
  - `schedule-system-reboot`: Advisory action (`RiskLevel.SAFE`, non-admin) planning a system restart.
- **Knowledge Ref**: `knowledge/readiness/pending-reboot-flags.md`
