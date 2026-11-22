"""Data models for disk space visualizer, directory scanner, and file actions."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FileNode(BaseModel):
    """Represents a file or directory node in the disk usage hierarchy."""

    name: str
    path: str
    size_bytes: int = 0
    is_dir: bool = False
    children: List["FileNode"] = Field(default_factory=list)


class DriveInfo(BaseModel):
    """Telemetry and capacity metrics for a mounted storage partition."""

    mountpoint: str
    device: str
    fstype: str = "NTFS"
    label: str = ""
    total_bytes: int = 0
    free_bytes: int = 0
    used_bytes: int = 0
    percent_used: float = 0.0


class ScanProgress(BaseModel):
    """Real-time progress update emitted during disk scanning."""

    status: Literal["idle", "scanning", "completed", "failed"] = "idle"
    current_path: str = ""
    files_scanned: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None


class ActionRequest(BaseModel):
    """Request payload to perform a file operation or remediation."""

    action: Literal["open", "reveal", "terminal", "copy_path", "recycle", "properties"]
    path: str


class ActionResult(BaseModel):
    """Result status and payload returned after executing a file action."""

    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
