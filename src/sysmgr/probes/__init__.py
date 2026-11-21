from sysmgr.core.engine import ProbeEngine
from sysmgr.probes.hardware.bluetooth import BluetoothProbe
from sysmgr.probes.storage.disk_space import DiskSpaceProbe
from sysmgr.probes.readiness.tpm_secure_boot import TpmSecureBootProbe


def create_default_engine() -> ProbeEngine:
    engine = ProbeEngine()
    engine.register(BluetoothProbe())
    engine.register(DiskSpaceProbe())
    engine.register(TpmSecureBootProbe())
    return engine


__all__ = ["create_default_engine", "BluetoothProbe", "DiskSpaceProbe", "TpmSecureBootProbe"]
