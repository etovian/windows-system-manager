# Bluetooth Subsystem Troubleshooting Runbook

## Overview
The Windows Bluetooth subsystem relies on:
1. **Physical/Radio Hardware & Firmware**: USB or PCIe-attached Bluetooth radio.
2. **Windows Services**:
   - `bthserv` (Bluetooth Support Service): Manages discovery and associations.
   - `BthHFSrv` (Bluetooth Handsfree Service): Audio profile management.
3. **PnP Drivers & Stack**: `bthport.sys`, `bthusb.sys`, vendor radio driver (Intel, Realtek, Qualcomm).

---

## Common Failure Modes & Error Codes

### 1. Code 43 ("Windows has stopped this device because it has reported problems")
- **Cause**: The Bluetooth controller firmware crashed, encountered an unrecoverable USB bus error, or failed to return from a low-power D3 state.
- **Symptoms**: Bluetooth toggle vanishes from Windows Quick Settings and Settings app; Device Manager shows a yellow warning triangle under Bluetooth.
- **Diagnostic Signals**:
  - `ConfigManagerErrorCode == 43` on Bluetooth radio device in WMI/CIM (`Win32_PnPEntity`).
  - Windows Event Log (`System`): Source `BTHUSB`, Event ID 17 ("The local Bluetooth adapter has failed an initialization step").
- **Remediation**:
  1. Safe: Restart `bthserv` service.
  2. Elevated: Disable and re-enable the PnP device (`pnputil /restart-device <InstanceId>`).
  3. Physical Cold Reset: If software reset fails, power cycle / clear static charge (often resolves internal USB hub freeze on laptops).

### 2. Code 10 ("This device cannot start")
- **Cause**: Driver incompatibility or corrupted registry state (`UpperFilters`/`LowerFilters`).
- **Remediation**: Reinstall vendor Bluetooth drivers or rollback driver update.

### 3. Service Stoppage / Disabled
- **Cause**: `bthserv` stopped or set to Disabled.
- **Symptoms**: Existing paired devices fail to connect; cannot scan for new devices.
- **Remediation**: Set `bthserv` start type to `Manual` or `Automatic` and start the service:
  ```powershell
  Start-Service -Name "bthserv"
  ```

---

## sysmgr Diagnostic Contract
- **Probe ID**: `hardware.bluetooth`
- **Output Signals**:
  - `status`: `PASS` (Radio active, code 0, service running), `WARN` (service stopped but hardware OK), `FAIL` (Code 43 / 10 or radio missing).
  - `details`: Device name, PnP device ID, error code, service status.
  - `remediations`:
    - `restart-bluetooth-service` (Risk: SAFE)
    - `reset-bluetooth-device` (Risk: CONFIRMATION_REQUIRED, Requires Admin)
