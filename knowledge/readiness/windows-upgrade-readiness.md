# Windows Upgrade & Security Readiness Runbook

## Overview
Windows 11 and enterprise security baselines mandate hardware-enforced isolation, cryptographic identity, and verified boot integrity. The foundational requirements are:
1. **Trusted Platform Module (TPM) 2.0**: Cryptographic coprocessor for BitLocker, Windows Hello, and credential protection.
2. **UEFI Firmware with Secure Boot**: Cryptographic verification of bootloaders and kernel drivers against unauthorized tampering.

---

## Diagnostic Verification

### 1. TPM 2.0 Verification
- **WMI Class**: `root\cimv2\Security\MicrosoftTpm:Win32_Tpm`
- **Signals**:
  - `IsActivated_InitialValue == True`
  - `IsEnabled_InitialValue == True`
  - `SpecVersion`: Must be `"2.0"` (1.2 is deprecated and incompatible with Windows 11).
- **Failure Modes**:
  - *TPM Not Found*: Firmware fTPM (Intel PTT or AMD fTPM) is disabled in BIOS/UEFI settings.
  - *TPM 1.2*: Legacy TPM installed; requires firmware update or motherboard upgrade.

### 2. Secure Boot & UEFI Mode
- **PowerShell Cmdlet**: `Confirm-SecureBootUEFI`
- **Signals**:
  - Returns `$true` when Secure Boot is actively enforcing signature validation.
  - Returns `$false` when Secure Boot is disabled in firmware setup.
  - Throws `CmdletNotSupportedOnThisPlatform` when booting in legacy BIOS (CSM) mode rather than native UEFI.
- **Remediation**:
  - Convert legacy MBR system drive to GPT (`mbr2gpt.exe /convert /allowFullOS`).
  - Reboot to UEFI firmware and enable Secure Boot.

---

## sysmgr Diagnostic Contract
- **Probe ID**: `readiness.tpm_secure_boot`
- **Output Signals**:
  - `status`: `PASS` (TPM 2.0 + Secure Boot active), `WARN` (TPM 2.0 present but Secure Boot disabled), `FAIL` (TPM missing/disabled or Legacy BIOS).
  - `details`: TPM manufacturer, spec version, Secure Boot state, firmware mode.
  - `remediations`:
    - `enable-tpm-in-bios` (Risk: ELEVATED, informational manual guidance)
    - `enable-secure-boot` (Risk: ELEVATED, informational manual guidance)
