# Windows Plug and Play (PnP) Error Codes Runbook

## Overview
Windows Plug and Play (PnP) subsystem automatically detects, identifies, and configures hardware attached to the system. When a hardware device encounters a problem during initialization, resource allocation, or runtime communication, the Windows Configuration Manager assigns a non-zero `ConfigManagerErrorCode` to the device entity (`Win32_PnPEntity`).

---

## Server-Side CIM Query Structure

To audit all hardware devices reporting errors without fetching thousands of healthy entities into memory, execute a server-side filtered CIM query:

```powershell
Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object Name, DeviceID, PNPClass, ConfigManagerErrorCode | ConvertTo-Json -Compress
```

### Key Attributes:
- **`Name`**: Human-readable device label (e.g. "NVIDIA GeForce RTX", "Realtek High Definition Audio").
- **`DeviceID`**: Hardware instance identifier path (e.g. `PCI\VEN_10DE&DEV_...`).
- **`PNPClass`**: Functional device classification (e.g. `Display`, `Media`, `Net`, `USB`).
- **`ConfigManagerErrorCode`**: Numeric error code defining the hardware or driver failure state.

---

## Common PnP Error Codes & Diagnostic Interpretation

### 1. Code 10 (`CM_PROB_FAILED_START` - "This device cannot start")
- **Description**: The device driver failed during device startup (`IRP_MN_START_DEVICE`).
- **Cause**: Incompatible driver, resource conflict, or device hardware failed to initialize.
- **Diagnostic Interpretation**: Device driver is loaded but cannot establish communication with the hardware.
- **Non-destructive Resolution**:
  - Restart the device via `pnputil /restart-device <InstanceId>`.
  - Check device driver updates via Windows Update or vendor package.
  - Reinstall the device driver stack.

### 2. Code 19 (`CM_PROB_REGISTRY_QUERIES_FAIL` - "Windows cannot start this hardware device because its configuration information in the registry is incomplete or damaged")
- **Description**: Corrupted driver configuration or filter drivers in the registry.
- **Cause**: Invalid or corrupt `UpperFilters` or `LowerFilters` keys in `HKLM\SYSTEM\CurrentControlSet\Control\Class\{DeviceClassGUID}`.
- **Diagnostic Interpretation**: Registry misconfiguration prevents driver filter stack from binding to device.
- **Non-destructive Resolution**:
  - Export class registry key for backup before inspection.
  - Remove offending third-party filter driver values from `UpperFilters` / `LowerFilters`.
  - Reinstall the official vendor driver package.

### 3. Code 22 (`CM_PROB_DISABLED` - "This device is disabled")
- **Description**: The device was disabled by the user or an administrator in Device Manager.
- **Cause**: Deliberate administrative action, battery saver policy, or user preference (e.g. integrated webcam/audio disabled).
- **Diagnostic Interpretation**: Benign / Expected configuration unless unintended. Evaluated as `INFO` rather than `FAIL`.
- **Non-destructive Resolution**:
  - Re-enable the device via PowerShell or PnPUtil:
    ```powershell
    pnputil /enable-device "<InstanceId>"
    ```

### 4. Code 28 (`CM_PROB_FAILED_INSTALL` - "The drivers for this device are not installed")
- **Description**: Device has no compatible driver installed.
- **Cause**: Fresh OS installation, newly connected peripheral, or missing vendor chipset driver.
- **Diagnostic Interpretation**: Hardware detected on bus, but no matched INF package is registered in DriverStore.
- **Non-destructive Resolution**:
  - Run Windows Update driver scan: `usoclient StartInteractiveScan`.
  - Install vendor INF packages using `pnputil /add-driver <path.inf> /install`.

### 5. Code 43 (`CM_PROB_FAILED_POST_START` - "Windows has stopped this device because it has reported problems")
- **Description**: Device crashed or firmware reported a fatal fault to the driver after starting.
- **Cause**: Unrecoverable hardware bus error, firmware lockup, PCIe link degradation, or power state failure.
- **Diagnostic Interpretation**: Critical hardware fault requiring reset or driver reset.
- **Non-destructive Resolution**:
  - Soft PnP reset:
    ```powershell
    pnputil /restart-device "<InstanceId>"
    ```
  - Driver service reset (e.g. graphics driver restart `Win + Ctrl + Shift + B`).
  - Cold boot / power drain: Power cycle system to discharge motherboard and peripheral controller capacitors.

---

## sysmgr Diagnostic Contract

- **Probe ID**: `hardware.device_manager`
- **Category**: `hardware`
- **Output Signals**:
  - `PASS`: Zero hardware error codes detected across all PnP devices (`ConfigManagerErrorCode == 0`).
  - `INFO`: All reported non-running devices are deliberately disabled by user (Code 22 only).
  - `FAIL`: One or more devices report unhandled hardware crashes (Code 43), start failures (Code 10), missing drivers (Code 28), registry corruption (Code 19), or other non-zero error codes.
- **Advisory Remediations**:
  - `restart-pnp-device`: PnP device restart recommendation (`pnputil /restart-device`).
  - `enable-pnp-device`: Enable user-disabled device (`pnputil /enable-device`).
  - `update-device-driver`: Update or reinstall missing device drivers.
