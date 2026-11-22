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

__all__ = [
    "ActionRequest",
    "ActionResult",
    "DiskScanner",
    "DriveInfo",
    "FileNode",
    "ScanProgress",
    "execute_file_action",
    "get_system_drives",
    "is_protected_system_path",
]
