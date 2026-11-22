import pytest
from unittest.mock import patch, MagicMock
from sysmgr.disk.drives import get_system_drives


def test_get_system_drives_success():
    mock_partition = MagicMock()
    mock_partition.mountpoint = "C:\\"
    mock_partition.device = "C:"
    mock_partition.fstype = "NTFS"

    mock_usage = MagicMock()
    mock_usage.total = 500 * (1024**3)
    mock_usage.free = 200 * (1024**3)
    mock_usage.used = 300 * (1024**3)
    mock_usage.percent = 60.0

    with patch("psutil.disk_partitions", return_value=[mock_partition]), \
         patch("psutil.disk_usage", return_value=mock_usage):
        drives = get_system_drives()
        assert len(drives) == 1
        assert drives[0].mountpoint == "C:\\"
        assert drives[0].percent_used == 60.0
        assert drives[0].total_bytes == mock_usage.total


def test_get_system_drives_handles_unready_drive():
    mock_part1 = MagicMock(mountpoint="C:\\", device="C:", fstype="NTFS")
    mock_part2 = MagicMock(mountpoint="D:\\", device="D:", fstype="CDFS")

    def mock_usage_fn(path):
        if path == "C:\\":
            return MagicMock(total=1000, free=400, used=600, percent=60.0)
        raise PermissionError("Drive not ready")

    with patch("psutil.disk_partitions", return_value=[mock_part1, mock_part2]), \
         patch("psutil.disk_usage", side_effect=mock_usage_fn):
        drives = get_system_drives()
        assert len(drives) == 1
        assert drives[0].mountpoint == "C:\\"


def test_get_system_drives_handles_partition_enumeration_error():
    with patch("psutil.disk_partitions", side_effect=RuntimeError("WMI error")):
        drives = get_system_drives()
        assert drives == []
