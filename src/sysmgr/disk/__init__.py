"""Disk space visualizer and management module for sysmgr."""

from sysmgr.disk.actions import execute_file_action, is_protected_system_path
from sysmgr.disk.drives import get_system_drives
from sysmgr.disk.models import (
    ActionRequest,
    ActionResult,
    DriveInfo,
    FileNode,
    ScanProgress,
)
from sysmgr.disk.scanner import DiskScanner
from sysmgr.disk.server import create_disk_app

__all__ = [
    "ActionRequest",
    "ActionResult",
    "DiskScanner",
    "DriveInfo",
    "FileNode",
    "ScanProgress",
    "create_disk_app",
    "execute_file_action",
    "get_system_drives",
    "is_protected_system_path",
]
