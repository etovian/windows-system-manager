# Disk Space Management & DaisyDisk-Style Visualizer Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a DaisyDisk-style interactive disk space visualizer and explorer in `sysmgr` with an embedded local web UI, multi-ring radial D3.js sunburst, fast streaming directory scanner, rich file actions, and safe Recycle Bin remediation.

**Architecture:** A multi-threaded `DiskScanner` using `os.scandir` streams progress snapshots over Server-Sent Events (SSE) while assembling a hierarchical `FileNode` tree with threshold rollups. A lightweight local ASGI server (`sysmgr.disk.server`) serves REST APIs and a self-contained single-page web app with bundled D3.js sunburst, breadcrumbs, and Top List sidebar. File actions (open in default app, reveal in explorer, open terminal, copy path, recycle bin) are dispatched via `sysmgr.disk.actions` with strict OS path protection gates.

**Tech Stack:** Python 3.11+, Typer, Rich, Pydantic, psutil, asyncio, starlette / uvicorn, D3.js v7 (bundled offline), Windows Shell APIs / `send2trash`.

---

### Task 1: Disk Models & Serialization

**Files:**
- Create: `src/sysmgr/disk/models.py`
- Create: `src/sysmgr/disk/__init__.py`
- Test: `tests/unit/disk/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_models.py
import pytest
from sysmgr.disk.models import FileNode, DriveInfo, ScanProgress, ActionRequest, ActionResult

def test_file_node_hierarchy_and_size():
    child1 = FileNode(name="file1.txt", path="C:\\test\\file1.txt", size_bytes=1000, is_dir=False)
    child2 = FileNode(name="file2.txt", path="C:\\test\\file2.txt", size_bytes=2000, is_dir=False)
    parent = FileNode(
        name="test",
        path="C:\\test",
        size_bytes=3000,
        is_dir=True,
        children=[child1, child2]
    )
    assert parent.size_bytes == 3000
    assert len(parent.children) == 2
    assert parent.children[0].name == "file1.txt"

def test_drive_info_model():
    drive = DriveInfo(
        mountpoint="C:\\",
        device="C:",
        fstype="NTFS",
        label="Windows OS",
        total_bytes=500_000_000_000,
        free_bytes=200_000_000_000,
        used_bytes=300_000_000_000,
        percent_used=60.0
    )
    assert drive.percent_used == 60.0
    assert drive.free_bytes == 200_000_000_000

def test_scan_progress_model():
    progress = ScanProgress(
        status="scanning",
        current_path="C:\\test",
        files_scanned=150,
        total_bytes=45000000,
        elapsed_seconds=1.2
    )
    assert progress.status == "scanning"
    assert progress.files_scanned == 150

def test_action_request_and_result():
    req = ActionRequest(action="reveal", path="C:\\test\\file.txt")
    res = ActionResult(success=True, message="Revealed in explorer")
    assert req.action == "reveal"
    assert res.success is True
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_models.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.disk'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/disk/__init__.py
"""Disk space visualizer and management module for sysmgr."""

# src/sysmgr/disk/models.py
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
```

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_models.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/ tests/unit/disk/
git commit -m "feat(disk): add core data models for disk visualizer and scanner"
```

---

### Task 2: Drive & Partition Inspection

**Files:**
- Create: `src/sysmgr/disk/drives.py`
- Test: `tests/unit/disk/test_drives.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_drives.py
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
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_drives.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.disk.drives'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/disk/drives.py
import os
import psutil
from typing import List
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
            # On Windows, try to get volume label if available
            try:
                import ctypes
                volume_name = ctypes.create_unicode_buffer(1024)
                fs_name = ctypes.create_unicode_buffer(1024)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(part.mountpoint),
                    volume_name, 1024, None, None, None, fs_name, 1024
                )
                label = volume_name.value
            except Exception:
                label = part.device

            drives.append(DriveInfo(
                mountpoint=part.mountpoint,
                device=part.device,
                fstype=getattr(part, "fstype", "NTFS"),
                label=label or part.device,
                total_bytes=usage.total,
                free_bytes=usage.free,
                used_bytes=usage.used,
                percent_used=usage.percent
            ))
        except (PermissionError, OSError):
            continue

    return drives
```

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_drives.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/drives.py tests/unit/disk/test_drives.py
git commit -m "feat(disk): implement system drive discovery and capacity inspection"
```

---

### Task 3: Streaming Directory Scanner Engine

**Files:**
- Create: `src/sysmgr/disk/scanner.py`
- Test: `tests/unit/disk/test_scanner.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_scanner.py
import pytest
import os
import asyncio
from pathlib import Path
from sysmgr.disk.scanner import DiskScanner
from sysmgr.disk.models import FileNode

@pytest.mark.asyncio
async def test_scanner_traverses_directory_and_aggregates_sizes(tmp_path: Path):
    # Setup test directory tree
    sub1 = tmp_path / "sub1"
    sub1.mkdir()
    (sub1 / "file1.dat").write_bytes(b"a" * 1024)  # 1 KB

    sub2 = tmp_path / "sub2"
    sub2.mkdir()
    (sub2 / "file2.dat").write_bytes(b"b" * 2048)  # 2 KB

    root_file = tmp_path / "root.txt"
    root_file.write_bytes(b"c" * 512)              # 512 B

    scanner = DiskScanner(min_size_ratio=0.01)
    tree, progress_history = await scanner.scan(str(tmp_path))

    assert tree.is_dir is True
    assert tree.size_bytes == 1024 + 2048 + 512
    assert len(tree.children) == 3
    # Check children sorted by size descending
    assert tree.children[0].name == "sub2"
    assert tree.children[0].size_bytes == 2048

@pytest.mark.asyncio
async def test_scanner_groups_small_files_into_other(tmp_path: Path):
    # Create one large file and multiple tiny files
    (tmp_path / "large.dat").write_bytes(b"x" * 10000)
    for i in range(5):
        (tmp_path / f"tiny_{i}.txt").write_bytes(b"y" * 10)

    scanner = DiskScanner(min_size_ratio=0.05)  # Items < 5% of parent get rolled up
    tree, _ = await scanner.scan(str(tmp_path))

    child_names = [c.name for c in tree.children]
    assert "large.dat" in child_names
    assert "Other files" in child_names
    other_node = next(c for c in tree.children if c.name == "Other files")
    assert other_node.size_bytes == 50
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_scanner.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.disk.scanner'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/disk/scanner.py
import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Callable, Tuple, List
from sysmgr.disk.models import FileNode, ScanProgress

class DiskScanner:
    def __init__(self, min_size_ratio: float = 0.005, max_depth: int = 10):
        self.min_size_ratio = min_size_ratio
        self.max_depth = max_depth
        self.is_cancelled = False

    async def scan(
        self,
        target_path: str,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None
    ) -> Tuple[FileNode, List[ScanProgress]]:
        self.is_cancelled = False
        target_path = os.path.abspath(target_path)
        progress_history: List[ScanProgress] = []
        files_scanned = 0
        total_bytes = 0
        start_time = time.time()
        last_progress_time = start_time

        def emit_progress(curr_path: str, status: str = "scanning"):
            nonlocal last_progress_time
            now = time.time()
            if now - last_progress_time >= 0.1 or status != "scanning":
                last_progress_time = now
                p = ScanProgress(
                    status=status,
                    current_path=curr_path,
                    files_scanned=files_scanned,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(now - start_time, 2)
                )
                progress_history.append(p)
                if progress_callback:
                    progress_callback(p)

        def scan_dir(dir_path: str, depth: int) -> FileNode:
            nonlocal files_scanned, total_bytes
            if self.is_cancelled or depth > self.max_depth:
                return FileNode(name=os.path.basename(dir_path) or dir_path, path=dir_path, is_dir=True)

            children: List[FileNode] = []
            dir_total = 0

            try:
                with os.scandir(dir_path) as it:
                    entries = list(it)
            except (PermissionError, OSError):
                return FileNode(name=os.path.basename(dir_path) or dir_path, path=dir_path, is_dir=True, size_bytes=0)

            for entry in entries:
                if self.is_cancelled:
                    break
                try:
                    # Skip symlinks/reparse points to avoid loops
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        child_node = scan_dir(entry.path, depth + 1)
                        dir_total += child_node.size_bytes
                        children.append(child_node)
                    else:
                        stat = entry.stat(follow_symlinks=False)
                        size = stat.st_size
                        files_scanned += 1
                        total_bytes += size
                        dir_total += size
                        children.append(FileNode(
                            name=entry.name,
                            path=entry.path,
                            size_bytes=size,
                            is_dir=False
                        ))
                    emit_progress(entry.path)
                except (PermissionError, OSError):
                    continue

            # Sort children descending by size
            children.sort(key=lambda c: c.size_bytes, reverse=True)

            # Roll up small items into "Other files" if above threshold
            if dir_total > 0 and len(children) > 5:
                threshold = dir_total * self.min_size_ratio
                primary_children: List[FileNode] = []
                other_size = 0
                for c in children:
                    if c.size_bytes < threshold:
                        other_size += c.size_bytes
                    else:
                        primary_children.append(c)

                if other_size > 0:
                    primary_children.append(FileNode(
                        name="Other files",
                        path=os.path.join(dir_path, "_other_"),
                        size_bytes=other_size,
                        is_dir=False
                    ))
                children = primary_children

            return FileNode(
                name=os.path.basename(dir_path) or dir_path,
                path=dir_path,
                size_bytes=dir_total,
                is_dir=True,
                children=children
            )

        emit_progress(target_path, "scanning")
        # Run CPU/disk bound scan in default executor to keep event loop free
        loop = asyncio.get_running_loop()
        root_node = await loop.run_in_executor(None, scan_dir, target_path, 0)
        emit_progress(target_path, "completed")
        return root_node, progress_history
```

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_scanner.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/scanner.py tests/unit/disk/test_scanner.py
git commit -m "feat(disk): implement multi-threaded streaming directory scanner"
```

---

### Task 4: Windows File Actions & Safety Gates

**Files:**
- Create: `src/sysmgr/disk/actions.py`
- Test: `tests/unit/disk/test_actions.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_actions.py
import pytest
import os
from unittest.mock import patch, MagicMock
from sysmgr.disk.actions import execute_file_action, is_protected_system_path
from sysmgr.disk.models import ActionRequest

def test_protected_system_paths():
    assert is_protected_system_path("C:\\Windows") is True
    assert is_protected_system_path("C:\\Windows\\System32\\cmd.exe") is True
    assert is_protected_system_path("C:\\Program Files\\app") is True
    assert is_protected_system_path("C:\\Users\\user\\project\\.git\\config") is True
    assert is_protected_system_path("C:\\Users\\user\\Downloads\\bigfile.zip") is False

def test_recycle_blocked_on_protected_path():
    req = ActionRequest(action="recycle", path="C:\\Windows\\notepad.exe")
    res = execute_file_action(req)
    assert res.success is False
    assert "protected" in res.message.lower()

def test_open_file_calls_startfile():
    with patch("os.startfile", create=True) as mock_start:
        req = ActionRequest(action="open", path="C:\\test\\doc.pdf")
        res = execute_file_action(req)
        assert res.success is True
        mock_start.assert_called_once_with("C:\\test\\doc.pdf")

def test_reveal_file_calls_explorer():
    with patch("subprocess.Popen") as mock_popen:
        req = ActionRequest(action="reveal", path="C:\\test\\doc.pdf")
        res = execute_file_action(req)
        assert res.success is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "explorer.exe" in args[0]
        assert "/select," in args[1]
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_actions.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.disk.actions'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/disk/actions.py
import os
import subprocess
from typing import Set
from sysmgr.disk.models import ActionRequest, ActionResult

PROTECTED_PREFIXES: Set[str] = {
    os.environ.get("SystemRoot", "C:\\Windows").lower(),
    os.environ.get("ProgramFiles", "C:\\Program Files").lower(),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)").lower(),
    os.environ.get("ProgramData", "C:\\ProgramData").lower(),
}

def is_protected_system_path(path: str) -> bool:
    norm_path = os.path.normpath(path).lower()
    # Check OS root drives (e.g. "c:\")
    if norm_path in ("c:\\", "c:", "\\"):
        return True
    for prefix in PROTECTED_PREFIXES:
        if norm_path == prefix or norm_path.startswith(prefix + os.sep):
            return True
    # Protect git repositories from accidental deletion via visualizer
    if ".git" in norm_path.split(os.sep):
        return True
    return False

def execute_file_action(request: ActionRequest) -> ActionResult:
    target_path = os.path.normpath(request.path)
    if not os.path.exists(target_path):
        return ActionResult(success=False, message=f"Path does not exist: {target_path}")

    try:
        if request.action == "open":
            if hasattr(os, "startfile"):
                os.startfile(target_path)
            else:
                subprocess.Popen(["explorer.exe", target_path])
            return ActionResult(success=True, message=f"Opened {os.path.basename(target_path)}")

        elif request.action == "reveal":
            subprocess.Popen(["explorer.exe", f"/select,{target_path}"])
            return ActionResult(success=True, message=f"Revealed in File Explorer")

        elif request.action == "terminal":
            dir_to_open = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
            # Try wt.exe (Windows Terminal), fallback to powershell.exe
            try:
                subprocess.Popen(["wt.exe", "-d", dir_to_open])
            except Exception:
                subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f"Set-Location '{dir_to_open}'"])
            return ActionResult(success=True, message="Opened terminal")

        elif request.action == "copy_path":
            return ActionResult(success=True, message="Path retrieved", details={"path": target_path})

        elif request.action == "properties":
            stat = os.stat(target_path)
            return ActionResult(
                success=True,
                message="File metadata retrieved",
                details={
                    "path": target_path,
                    "size_bytes": stat.st_size,
                    "created": stat.st_ctime,
                    "modified": stat.st_mtime,
                    "is_dir": os.path.isdir(target_path)
                }
            )

        elif request.action == "recycle":
            if is_protected_system_path(target_path):
                return ActionResult(success=False, message=f"Cannot delete protected system path: {target_path}")

            # Use send2trash or PowerShell Shell.Application to move to Windows Recycle Bin
            try:
                import send2trash
                send2trash.send2trash(target_path)
            except ImportError:
                # Windows COM fallback via PowerShell
                ps_cmd = (
                    f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                    f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('{target_path}', "
                    f"'OnlyErrorDialogs', 'SendToRecycleBin')"
                    if os.path.isdir(target_path) else
                    f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                    f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{target_path}', "
                    f"'OnlyErrorDialogs', 'SendToRecycleBin')"
                )
                subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], check=True, timeout=15)

            return ActionResult(success=True, message=f"Moved to Recycle Bin: {os.path.basename(target_path)}")

        return ActionResult(success=False, message=f"Unknown action: {request.action}")

    except Exception as exc:
        return ActionResult(success=False, message=f"Action '{request.action}' failed: {exc}")
```

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_actions.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/actions.py tests/unit/disk/test_actions.py
git commit -m "feat(disk): implement Windows file actions and safety gates"
```

---

### Task 5: Local Server & REST/SSE Endpoints

**Files:**
- Create: `src/sysmgr/disk/server.py`
- Test: `tests/unit/disk/test_server.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_server.py
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock
from sysmgr.disk.server import create_disk_app
from sysmgr.disk.models import DriveInfo

@pytest.fixture
def client():
    app = create_disk_app()
    return TestClient(app)

def test_api_drives_endpoint(client):
    mock_drives = [
        DriveInfo(
            mountpoint="C:\\",
            device="C:",
            label="OS",
            total_bytes=1000,
            free_bytes=400,
            used_bytes=600,
            percent_used=60.0
        )
    ]
    with patch("sysmgr.disk.server.get_system_drives", return_value=mock_drives):
        resp = client.get("/api/drives")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["mountpoint"] == "C:\\"

def test_api_actions_endpoint(client):
    with patch("sysmgr.disk.server.execute_file_action") as mock_action:
        mock_action.return_value = MagicMock(success=True, message="Success", details=None)
        resp = client.post("/api/actions", json={"action": "open", "path": "C:\\test\\doc.txt"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_server.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'sysmgr.disk.server'`

**Step 3: Write minimal implementation**

```python
# src/sysmgr/disk/server.py
import os
import json
import asyncio
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.staticfiles import StaticFiles

from sysmgr.disk.drives import get_system_drives
from sysmgr.disk.models import ActionRequest, ScanProgress, FileNode
from sysmgr.disk.scanner import DiskScanner
from sysmgr.disk.actions import execute_file_action

# In-memory scan state
_current_scan_tree: dict = {}
_latest_progress: ScanProgress = ScanProgress()
_active_scanner: DiskScanner = None

async def api_drives(request):
    drives = get_system_drives()
    return JSONResponse([d.model_dump() for d in drives])

async def api_scan(request):
    global _active_scanner, _latest_progress, _current_scan_tree
    body = await request.json()
    target_path = body.get("path")
    if not target_path or not os.path.exists(target_path):
        return JSONResponse({"error": "Invalid or missing path"}, status_code=400)

    _active_scanner = DiskScanner()
    
    def on_progress(p: ScanProgress):
        global _latest_progress
        _latest_progress = p

    async def run_scan():
        global _current_scan_tree
        tree, _ = await _active_scanner.scan(target_path, on_progress)
        _current_scan_tree = tree.model_dump()

    asyncio.create_task(run_scan())
    return JSONResponse({"status": "scan_started", "path": target_path})

async def api_scan_tree(request):
    return JSONResponse(_current_scan_tree)

async def api_scan_progress(request):
    async def event_generator():
        while True:
            data = json.dumps(_latest_progress.model_dump())
            yield f"data: {data}\n\n"
            if _latest_progress.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.15)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def api_actions(request):
    body = await request.json()
    req = ActionRequest(**body)
    result = execute_file_action(req)
    return JSONResponse(result.model_dump())

def create_disk_app() -> Starlette:
    web_dir = Path(__file__).parent / "web"
    routes = [
        Route("/api/drives", api_drives, methods=["GET"]),
        Route("/api/scan", api_scan, methods=["POST"]),
        Route("/api/scan/progress", api_scan_progress, methods=["GET"]),
        Route("/api/scan/tree", api_scan_tree, methods=["GET"]),
        Route("/api/actions", api_actions, methods=["POST"]),
    ]
    if web_dir.exists():
        routes.append(Mount("/", StaticFiles(directory=str(web_dir), html=True), name="static"))

    return Starlette(debug=True, routes=routes)
```

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_server.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/server.py tests/unit/disk/test_server.py
git commit -m "feat(disk): implement local Starlette server with REST and SSE endpoints"
```

---

### Task 6: DaisyDisk Web Dashboard (HTML/CSS/D3.js)

**Files:**
- Create: `src/sysmgr/disk/web/index.html`
- Create: `src/sysmgr/disk/web/styles.css`
- Create: `src/sysmgr/disk/web/app.js`
- Create: `src/sysmgr/disk/web/d3.min.js`
- Test: `tests/unit/disk/test_web_assets.py`

**Step 1: Write the failing test**

```python
# tests/unit/disk/test_web_assets.py
from pathlib import Path

def test_web_assets_exist_and_non_empty():
    web_dir = Path("src/sysmgr/disk/web")
    assert (web_dir / "index.html").exists()
    assert (web_dir / "styles.css").exists()
    assert (web_dir / "app.js").exists()
    assert (web_dir / "d3.min.js").exists()

    assert len((web_dir / "index.html").read_text(encoding="utf-8")) > 100
    assert len((web_dir / "styles.css").read_text(encoding="utf-8")) > 100
    assert len((web_dir / "app.js").read_text(encoding="utf-8")) > 100
    assert len((web_dir / "d3.min.js").read_text(encoding="utf-8")) > 50000
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_web_assets.py -v`  
Expected: FAIL with `AssertionError: assert False` (files do not exist yet)

**Step 3: Write minimal implementation**

1. Create `index.html` with:
   - Header with DaisyDisk title and Breadcrumb bar.
   - Home screen: Drive cards showing capacity bars and a path input folder scanner.
   - Scan view: SVG sunburst container (`<svg id="sunburst"></svg>`), center circular readout, and right-hand Top List panel (`<div id="top-list"></div>`).
   - Context action modal (`Open`, `Reveal`, `Terminal`, `Recycle Bin`).
   - Progress bar overlay for active scans.
2. Create `styles.css` with dark theme (`#121316`, `#1e2025`, `#2b2d35`), smooth arc hover transitions, and badge colors.
3. Bundle `d3.min.js` (D3 v7 minified).
4. Implement `app.js` with:
   - Drive loading and selection.
   - SSE connection listening to `/api/scan/progress`.
   - D3 partition & arc layout rendering concentric rings.
   - Drilldown click transitions and breadcrumb navigation.
   - Context menu trigger on right click / menu button calling `/api/actions`.

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/disk/test_web_assets.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/disk/web/ tests/unit/disk/test_web_assets.py
git commit -m "feat(disk): add embedded DaisyDisk dark-theme web dashboard with D3.js sunburst"
```

---

### Task 7: CLI Integration (`sysmgr disk`)

**Files:**
- Modify: `src/sysmgr/cli.py`
- Test: `tests/unit/test_cli_disk.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_cli_disk.py
from typer.testing import CliRunner
from unittest.mock import patch
from sysmgr.cli import app

runner = CliRunner()

def test_disk_command_help():
    result = runner.invoke(app, ["disk", "--help"])
    assert result.exit_code == 0
    assert "disk" in result.output.lower()
    assert "--cli" in result.output
    assert "--port" in result.output

def test_disk_cli_summary_mode():
    with patch("sysmgr.disk.drives.get_system_drives") as mock_drives:
        mock_drives.return_value = []
        result = runner.invoke(app, ["disk", "--cli"])
        assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\pytest tests/unit/test_cli_disk.py -v`  
Expected: FAIL (No such command 'disk')

**Step 3: Write minimal implementation**

Add `disk` command to `src/sysmgr/cli.py`:
- Arguments: `path: Optional[str] = None`, `--cli: bool = False`, `--port: int = 8765`, `--no-browser: bool = False`.
- In `--cli` mode: Print drive summary and scan top items via Rich Table.
- In default mode: Launch `uvicorn.run(create_disk_app(), host="127.0.0.1", port=port)` and open `http://127.0.0.1:port` in `webbrowser.open()`.

**Step 4: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/unit/test_cli_disk.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/sysmgr/cli.py tests/unit/test_cli_disk.py
git commit -m "feat(cli): register sysmgr disk command with web and headless CLI modes"
```

---

### Task 8: Integration & Smoke Verification

**Files:**
- Create: `tests/integration/test_disk_integration.py`

**Step 1: Write test**

```python
# tests/integration/test_disk_integration.py
import pytest
from sysmgr.disk.drives import get_system_drives
from sysmgr.disk.scanner import DiskScanner
from pathlib import Path

@pytest.mark.asyncio
async def test_live_drive_discovery():
    drives = get_system_drives()
    assert len(drives) >= 1
    mounts = [d.mountpoint for d in drives]
    assert any("C:" in m for m in mounts)

@pytest.mark.asyncio
async def test_live_folder_scan(tmp_path: Path):
    # Populate small test directory
    for i in range(10):
        (tmp_path / f"test_{i}.bin").write_bytes(b"0" * 1024)
    
    scanner = DiskScanner()
    tree, progress = await scanner.scan(str(tmp_path))
    assert tree.size_bytes == 10240
    assert len(tree.children) == 10
```

**Step 2: Run test to verify it passes**

Run: `& .\.venv\Scripts\pytest tests/integration/test_disk_integration.py -v`  
Expected: PASS

**Step 3: Run full regression test suite**

Run: `& .\.venv\Scripts\pytest`  
Expected: All tests pass.

**Step 4: Commit**

```bash
git add tests/integration/test_disk_integration.py
git commit -m "test(disk): add live smoke and integration tests for disk subsystem"
```
