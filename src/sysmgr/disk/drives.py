"""System drive and storage partition discovery utilities."""

import os
import sys
from typing import List
import psutil
from sysmgr.disk.models import DriveInfo

try:
    import ctypes
except ImportError:
    ctypes = None  # type: ignore


def _get_volume_label(mountpoint: str, default_label: str) -> str:
    """Attempts to retrieve the volume label on Windows via Win32 API."""
    if sys.platform != "win32" or ctypes is None:
        return default_label

    try:
        root_path = mountpoint if mountpoint.endswith("\\") else f"{mountpoint}\\"
        volume_name = ctypes.create_unicode_buffer(1024)
        fs_name = ctypes.create_unicode_buffer(1024)
        result = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root_path),
            volume_name,
            1024,
            None,
            None,
            None,
            fs_name,
            1024,
        )
        if result != 0 and volume_name.value:
            return volume_name.value
    except Exception:
        pass

    return default_label


def get_system_drives() -> List[DriveInfo]:
    """Inspects all active partitions and returns structured DriveInfo records."""
    drives: List[DriveInfo] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        return drives

    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
            label = _get_volume_label(part.mountpoint, part.device)

            drives.append(
                DriveInfo(
                    mountpoint=part.mountpoint,
                    device=part.device,
                    fstype=getattr(part, "fstype", "NTFS"),
                    label=label or part.device,
                    total_bytes=usage.total,
                    free_bytes=usage.free,
                    used_bytes=usage.used,
                    percent_used=usage.percent,
                )
            )
        except (PermissionError, OSError, psutil.Error):
            continue

    return drives
