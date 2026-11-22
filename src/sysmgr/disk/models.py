from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class FileNode(BaseModel):
    name: str
    path: str
    size_bytes: int = 0
    is_dir: bool = False
    children: List["FileNode"] = Field(default_factory=list)


class DriveInfo(BaseModel):
    mountpoint: str
    device: str
    fstype: str = "NTFS"
    label: str = ""
    total_bytes: int = 0
    free_bytes: int = 0
    used_bytes: int = 0
    percent_used: float = 0.0


class ScanProgress(BaseModel):
    status: Literal["idle", "scanning", "completed", "failed"] = "idle"
    current_path: str = ""
    files_scanned: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None


class ActionRequest(BaseModel):
    action: Literal["open", "reveal", "terminal", "copy_path", "recycle", "properties"]
    path: str


class ActionResult(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None
