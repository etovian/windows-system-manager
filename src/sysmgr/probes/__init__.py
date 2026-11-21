from sysmgr.core.engine import ProbeEngine
from sysmgr.probes.hardware.bluetooth import BluetoothProbe
from sysmgr.probes.hardware.device_manager import DeviceManagerProbe
from sysmgr.probes.hardware.network import NetworkAdapterProbe
from sysmgr.probes.readiness.hygiene import SystemHygieneProbe
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe
from sysmgr.probes.storage.disk_health import DiskHealthProbe
from sysmgr.probes.storage.disk_performance import DiskPerformanceProbe
from sysmgr.probes.storage.disk_space import DiskSpaceProbe


def create_default_engine() -> ProbeEngine:
    engine = ProbeEngine()
    engine.register(BluetoothProbe())
    engine.register(DeviceManagerProbe())
    engine.register(NetworkAdapterProbe())
    engine.register(DiskSpaceProbe())
    engine.register(DiskHealthProbe())
    engine.register(DiskPerformanceProbe())
    engine.register(TpmSecureBootProbe())
    engine.register(SystemHygieneProbe())
    return engine


__all__ = [
    "create_default_engine",
    "BluetoothProbe",
    "DeviceManagerProbe",
    "NetworkAdapterProbe",
    "DiskSpaceProbe",
    "DiskHealthProbe",
    "DiskPerformanceProbe",
    "TpmSecureBootProbe",
    "SystemHygieneProbe",
]
