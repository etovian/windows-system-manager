# Milestone 2 Implementation Plan: Full Diagnostic Probes Suite (100% Read-Only)

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement 5 additional read-only diagnostic probes across hardware, networking, storage health, and system hygiene to complete the comprehensive, 8-probe Windows monitoring suite.

**Architecture:** Probes inherit from `BaseProbe` and return standard `DiagnosticResult` models without performing any state changes or mutations. Telemetry is collected using native Python libraries (`psutil`, `winreg`, `socket`) alongside server-side filtered Windows CIM queries for optimal performance. Curated runbooks in `knowledge/` document failure codes and interpretation trees.

**Tech Stack:** Python 3.11+, `psutil`, `winreg`, `socket`, `typer`, `rich`, `pytest`, `pytest-mock`, `pytest-asyncio`.

---

### Task 1: DeviceManagerProbe & PnP Error Codes Runbook

**Files:**
- Create: `knowledge/hardware/pnp-error-codes.md`
- Create: `tests/unit/probes/test_device_manager.py`
- Create: `src/sysmgr/probes/hardware/device_manager.py`

**Step 1: Write knowledge base runbook for PnP error codes**

Create `knowledge/hardware/pnp-error-codes.md` documenting:
- Windows PnP error codes (Code 10 cannot start, Code 19 registry corrupt, Code 22 disabled by user, Code 28 missing driver, Code 43 firmware/hardware crash).
- Server-side CIM query structure.
- Diagnostic interpretation and non-destructive resolution strategies.

**Step 2: Write failing test for DeviceManagerProbe**

```python
# tests/unit/probes/test_device_manager.py
import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.hardware.device_manager import DeviceManagerProbe


def test_device_manager_probe_all_healthy():
    async def _run():
        probe = DeviceManagerProbe()
        with patch.object(probe, "_query_error_devices", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "zero hardware error codes" in result.summary.lower()
            assert result.probe_id == "hardware.device_manager"

    asyncio.run(_run())


def test_device_manager_probe_hardware_crash():
    async def _run():
        probe = DeviceManagerProbe()
        mock_devices = [
            {
                "name": "NVIDIA GeForce RTX",
                "device_id": "PCI\\VEN_10DE",
                "pnp_class": "Display",
                "code": 43,
            }
        ]
        with patch.object(probe, "_query_error_devices", return_value=mock_devices):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "nvidia geforce rtx" in result.summary.lower()
            assert "code 43" in result.summary.lower()
            assert len(result.details["error_devices"]) == 1

    asyncio.run(_run())


def test_device_manager_probe_user_disabled_device():
    async def _run():
        probe = DeviceManagerProbe()
        mock_devices = [
            {
                "name": "Virtual Audio Device",
                "device_id": "ROOT\\MEDIA",
                "pnp_class": "Media",
                "code": 22,
            }
        ]
        with patch.object(probe, "_query_error_devices", return_value=mock_devices):
            result = await probe.check()
            assert result.status == DiagnosticStatus.INFO
            assert "disabled by user" in result.summary.lower()

    asyncio.run(_run())
```

**Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/probes/test_device_manager.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.probes.hardware.device_manager'`

**Step 4: Implement DeviceManagerProbe**

Implement `DeviceManagerProbe` in `src/sysmgr/probes/hardware/device_manager.py`.

**Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/probes/test_device_manager.py`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/hardware/pnp-error-codes.md src/sysmgr/probes/hardware/device_manager.py tests/unit/probes/test_device_manager.py
git commit -m "feat(hardware): implement DeviceManagerProbe and pnp error codes runbook"
```

---

### Task 2: NetworkAdapterProbe & Network Troubleshooting Runbook

**Files:**
- Create: `knowledge/hardware/network-troubleshooting.md`
- Create: `tests/unit/probes/test_network.py`
- Create: `src/sysmgr/probes/hardware/network.py`

**Step 1: Write knowledge base runbook for network troubleshooting**

Create `knowledge/hardware/network-troubleshooting.md` documenting:
- Link status, cable disconnects, Wi-Fi radio states.
- APIPA autoconfiguration (`169.254.0.0/16`) indicating DHCP failure.
- Gateway reachability and DNS resolution failure trees.

**Step 2: Write failing test for NetworkAdapterProbe**

```python
# tests/unit/probes/test_network.py
import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.hardware.network import NetworkAdapterProbe


def test_network_probe_healthy():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(
            probe,
            "_get_interfaces",
            return_value=[{"name": "Ethernet", "is_up": True, "speed_mbps": 1000, "ips": ["192.168.1.100"]}],
        ), patch.object(probe, "_test_dns", return_value=True):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "online" in result.summary.lower()

    asyncio.run(_run())


def test_network_probe_apipa_detected():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(
            probe,
            "_get_interfaces",
            return_value=[{"name": "Ethernet", "is_up": True, "speed_mbps": 1000, "ips": ["169.254.50.20"]}],
        ), patch.object(probe, "_test_dns", return_value=False):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "apipa" in result.summary.lower()

    asyncio.run(_run())


def test_network_probe_all_down():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(probe, "_get_interfaces", return_value=[]), patch.object(
            probe, "_test_dns", return_value=False
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "no active network interfaces" in result.summary.lower()

    asyncio.run(_run())
```

**Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/probes/test_network.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.probes.hardware.network'`

**Step 4: Implement NetworkAdapterProbe**

Implement `NetworkAdapterProbe` in `src/sysmgr/probes/hardware/network.py` using `psutil.net_if_stats()`, `psutil.net_if_addrs()`, and `socket.getaddrinfo()`.

**Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/probes/test_network.py`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/hardware/network-troubleshooting.md src/sysmgr/probes/hardware/network.py tests/unit/probes/test_network.py
git commit -m "feat(hardware): implement NetworkAdapterProbe and network runbook"
```

---

### Task 3: DiskHealthProbe (SMART) & SMART Runbook

**Files:**
- Create: `knowledge/storage/smart-health-monitoring.md`
- Create: `tests/unit/probes/test_disk_health.py`
- Create: `src/sysmgr/probes/storage/disk_health.py`

**Step 1: Write knowledge base runbook for SMART health**

Create `knowledge/storage/smart-health-monitoring.md` detailing:
- WMI `MSStorageDriver_FailurePredictStatus` predictive failure mechanism.
- Windows Storage Management `Get-PhysicalDisk` operational status codes.
- Critical SMART attributes (Reallocated Sector Count, Wear Level Indicator).

**Step 2: Write failing test for DiskHealthProbe**

```python
# tests/unit/probes/test_disk_health.py
import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.storage.disk_health import DiskHealthProbe


def test_disk_health_probe_healthy():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(
            probe,
            "_query_physical_disks",
            return_value=[
                {
                    "device_id": "0",
                    "model": "Samsung SSD 980 PRO 1TB",
                    "media_type": "SSD",
                    "status": "OK",
                    "predict_failure": False,
                }
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "all physical drives healthy" in result.summary.lower()

    asyncio.run(_run())


def test_disk_health_probe_predictive_failure():
    async def _run():
        probe = DiskHealthProbe()
        with patch.object(
            probe,
            "_query_physical_disks",
            return_value=[
                {
                    "device_id": "1",
                    "model": "Seagate Barracuda 2TB",
                    "media_type": "HDD",
                    "status": "Predictive Failure",
                    "predict_failure": True,
                }
            ],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "predictive failure" in result.summary.lower()
            assert len(result.remediations) > 0

    asyncio.run(_run())
```

**Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/probes/test_disk_health.py`
Expected: FAIL

**Step 4: Implement DiskHealthProbe**

Implement `DiskHealthProbe` in `src/sysmgr/probes/storage/disk_health.py`.

**Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/probes/test_disk_health.py`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/storage/smart-health-monitoring.md src/sysmgr/probes/storage/disk_health.py tests/unit/probes/test_disk_health.py
git commit -m "feat(storage): implement DiskHealthProbe with SMART monitoring and runbook"
```

---

### Task 4: DiskPerformanceProbe & I/O Bottlenecks Runbook

**Files:**
- Create: `knowledge/storage/disk-io-bottlenecks.md`
- Create: `tests/unit/probes/test_disk_performance.py`
- Create: `src/sysmgr/probes/storage/disk_performance.py`

**Step 1: Write knowledge base runbook for disk I/O bottlenecks**

Create `knowledge/storage/disk-io-bottlenecks.md` covering:
- Disk queue length, throughput vs latency.
- Diagnosing runaway disk writer processes (Windows Search indexing, anti-malware, loggers).

**Step 2: Write failing test for DiskPerformanceProbe**

```python
# tests/unit/probes/test_disk_performance.py
import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.storage.disk_performance import DiskPerformanceProbe


def test_disk_performance_probe_normal():
    async def _run():
        probe = DiskPerformanceProbe()
        with patch.object(
            probe,
            "_get_io_counters",
            return_value={"read_bytes": 10_000_000, "write_bytes": 5_000_000},
        ), patch.object(
            probe,
            "_get_top_io_processes",
            return_value=[{"pid": 100, "name": "explorer.exe", "read_mb": 5.0, "write_mb": 2.0}],
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "normal" in result.summary.lower()
            assert len(result.details["top_processes"]) == 1

    asyncio.run(_run())
```

**Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/probes/test_disk_performance.py`
Expected: FAIL

**Step 4: Implement DiskPerformanceProbe**

Implement `DiskPerformanceProbe` in `src/sysmgr/probes/storage/disk_performance.py` using `psutil.disk_io_counters()` and `psutil.process_iter()`.

**Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/probes/test_disk_performance.py`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/storage/disk-io-bottlenecks.md src/sysmgr/probes/storage/disk_performance.py tests/unit/probes/test_disk_performance.py
git commit -m "feat(storage): implement DiskPerformanceProbe and I/O bottlenecks runbook"
```

---

### Task 5: SystemHygieneProbe & Pending Reboot Runbook

**Files:**
- Create: `knowledge/readiness/pending-reboot-flags.md`
- Create: `tests/unit/probes/test_hygiene.py`
- Create: `src/sysmgr/probes/readiness/hygiene.py`

**Step 1: Write knowledge base runbook for pending reboot flags**

Create `knowledge/readiness/pending-reboot-flags.md` detailing:
- CBS `RebootPending` registry key.
- Windows Update `RebootRequired` registry key.
- `PendingFileRenameOperations` under Session Manager.
- System uptime thresholds and impact.

**Step 2: Write failing test for SystemHygieneProbe**

```python
# tests/unit/probes/test_hygiene.py
import asyncio
import pytest
from unittest.mock import patch
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.readiness.hygiene import SystemHygieneProbe


def test_hygiene_probe_clean():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(probe, "_check_pending_reboots", return_value=[]), patch.object(
            probe, "_get_uptime_days", return_value=3.5
        ), patch.object(probe, "_check_crash_dumps", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "clean" in result.summary.lower()

    asyncio.run(_run())


def test_hygiene_probe_reboot_pending():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(
            probe, "_check_pending_reboots", return_value=["Component Based Servicing (RebootPending)"]
        ), patch.object(probe, "_get_uptime_days", return_value=5.0), patch.object(
            probe, "_check_crash_dumps", return_value=[]
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "reboot pending" in result.summary.lower()

    asyncio.run(_run())


def test_hygiene_probe_long_uptime():
    async def _run():
        probe = SystemHygieneProbe()
        with patch.object(probe, "_check_pending_reboots", return_value=[]), patch.object(
            probe, "_get_uptime_days", return_value=45.0
        ), patch.object(probe, "_check_crash_dumps", return_value=[]):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "45" in result.summary.lower()
```

**Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/probes/test_hygiene.py`
Expected: FAIL

**Step 4: Implement SystemHygieneProbe**

Implement `SystemHygieneProbe` in `src/sysmgr/probes/readiness/hygiene.py` using `winreg` and `psutil.boot_time()`.

**Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/probes/test_hygiene.py`
Expected: PASS

**Step 6: Commit**

```bash
git add knowledge/readiness/pending-reboot-flags.md src/sysmgr/probes/readiness/hygiene.py tests/unit/probes/test_hygiene.py
git commit -m "feat(readiness): implement SystemHygieneProbe and pending reboot runbook"
```

---

### Task 6: Default Registry & CLI Update

**Files:**
- Modify: `src/sysmgr/probes/__init__.py`
- Modify: `tests/unit/test_cli.py`

**Step 1: Update create_default_engine() to register all 8 probes**

Register:
- `BluetoothProbe`
- `DeviceManagerProbe`
- `NetworkAdapterProbe`
- `DiskSpaceProbe`
- `DiskHealthProbe`
- `DiskPerformanceProbe`
- `TpmSecureBootProbe`
- `SystemHygieneProbe`

**Step 2: Run all unit tests**

Run: `.venv\Scripts\pytest tests/unit`
Expected: PASS

**Step 3: Commit**

```bash
git add src/sysmgr/probes/__init__.py tests/unit/test_cli.py
git commit -m "feat(probes): register all 8 probes in default engine"
```

---

### Task 7: Host Integration Smoke Tests & Verification

**Files:**
- Modify: `tests/integration/test_live_smoke.py`

**Step 1: Add live smoke tests for all 5 new probes**

Add live assertions verifying `DeviceManagerProbe`, `NetworkAdapterProbe`, `DiskHealthProbe`, `DiskPerformanceProbe`, and `SystemHygieneProbe` execute against the Windows host cleanly.

**Step 2: Run full test suite**

Run: `.venv\Scripts\pytest tests`
Expected: PASS (all tests pass)

**Step 3: Commit**

```bash
git add tests/integration/test_live_smoke.py
git commit -m "test(integration): add live host tests for all milestone 2 probes"
```
