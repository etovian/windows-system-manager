"""Drive and partition discovery and capacity inspection."""

from typing import List
import psutil

from sysmgr.disk.models import DriveInfo


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
            label = ""
            try:
                import ctypes

                volume_name = ctypes.create_unicode_buffer(1024)
                fs_name = ctypes.create_unicode_buffer(1024)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(part.mountpoint),
                    volume_name,
                    1024,
                    None,
                    None,
                    None,
                    fs_name,
                    1024,
                )
                label = volume_name.value
            except Exception:
                label = part.device

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
        except (PermissionError, OSError):
            continue

    return drives
