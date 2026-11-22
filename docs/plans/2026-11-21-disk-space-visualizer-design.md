# Disk Space Management & DaisyDisk-Style Visualizer Design

**Date**: 2026-11-21  
**Status**: Validated Design (Brainstorming Complete)  
**Author**: Antigravity & User  
**Target Subsystem**: `sysmgr.disk`

---

## 1. Overview & Goal

The goal is to build an interactive, high-fidelity disk space analyzer and visualizer integrated directly into `sysmgr`. Operating similarly to macOS's **DaisyDisk**, it presents a fluid, multi-ring radial sunburst diagram that visualizes disk usage across drives, folders, and files.

Users can explore large files and directories through smooth drill-down navigation, inspect file metadata, reveal items in Windows File Explorer, launch files in default applications, and safely reclaim storage using Windows Recycle Bin operations or built-in `sysmgr` remediations.

---

## 2. Architectural Decisions & Tech Stack

Following collaborative brainstorming, the core architectural choices are:

1. **Self-Contained Local Web UI (Approach 1)**:
   - Backend: Async server (`Starlette` / `Uvicorn` or lightweight ASGI) served on `127.0.0.1:<port>`.
   - Frontend: Polished single-page application with bundled D3.js v7, HTML5, and CSS3 embedded directly in `src/sysmgr/disk/web/`.
   - **Zero Node.js runtime**: No npm, Vite, or external JS toolchain required at runtime or build time.
2. **Real-Time Streaming via Server-Sent Events (SSE)**:
   - Live updates during directory scanning (scanned file counts, current directory, total bytes) streamed over an SSE connection to keep the UI responsive.
3. **Dual Invocation Modes**:
   - `sysmgr disk`: Spawns the local web server and automatically opens the user's default browser.
   - `sysmgr disk --cli` (or `sysmgr disk scan <path>`): Outputs an immediate, non-interactive Rich terminal summary table of top storage consumers.
4. **Interactive Exploration + Safe Remediation**:
   - Rich file actions (Open, Reveal, Copy Path, Terminal).
   - Safe deletion defaults to moving items to the Windows Recycle Bin (`send2trash` or Windows Shell API) with explicit confirmation modals.

---

## 3. Subsystem Layout & Components

```
sysmgr/
├── src/sysmgr/
│   ├── cli.py                     # Adds `sysmgr disk` command
│   ├── disk/                      # Disk visualizer and management module
│   │   ├── __init__.py
│   │   ├── models.py              # FileNode, DriveInfo, ScanProgress, ActionRequest
│   │   ├── scanner.py             # Multi-threaded async disk indexer with streaming events
│   │   ├── server.py              # Local ASGI server hosting REST + SSE endpoints
│   │   ├── actions.py             # Windows shell execution handlers (open, reveal, recycle)
│   │   └── web/                   # Embedded static assets
│   │       ├── index.html         # Single-page dashboard layout
│   │       ├── styles.css         # Dark theme DaisyDisk styling & animations
│   │       ├── app.js             # D3.js v7 sunburst, breadcrumb navigation, SSE client
│   │       └── d3.min.js          # Bundled D3.js v7 library
│   └── remediations/              # Existing sysmgr cleanup integrations
```

---

## 4. Detailed Component Design

### 4.1 Data Models (`sysmgr.disk.models`)
```python
from typing import List, Literal, Optional
from pydantic import BaseModel

class FileNode(BaseModel):
    name: str
    path: str
    size_bytes: int
    is_dir: bool
    children: List["FileNode"] = []

class DriveInfo(BaseModel):
    mountpoint: str          # e.g. "C:\\"
    device: str              # e.g. "C:"
    fstype: str              # e.g. "NTFS"
    label: str               # e.g. "Windows SSD"
    total_bytes: int
    free_bytes: int
    used_bytes: int
    percent_used: float

class ScanProgress(BaseModel):
    status: Literal["idle", "scanning", "completed", "failed"]
    current_path: str
    files_scanned: int
    total_bytes: int
    elapsed_seconds: float
```

### 4.2 Multi-Threaded Scanner (`sysmgr.disk.scanner`)
1. **Parallel Traversal**: Employs a bounded `ThreadPoolExecutor` using `os.scandir()` to bypass GIL constraints during Windows filesystem stat and directory enumeration.
2. **Aggregated Hierarchy**: Directory sizes are aggregated bottom-up. Items below a relative threshold (< 0.1% of parent size or < 1 MB) are grouped into an `"Other files"` leaf to keep DOM node count low and D3 rendering smooth.
3. **Throttled Streaming**: Emits `ScanProgress` snapshots every 100ms through an `asyncio.Queue` to the SSE endpoint.
4. **Safety & Loop Avoidance**: Skips NTFS reparse points, junctions, and symlink loops. Gracefully skips permission-denied directories (e.g. `System Volume Information`) without halting the scan.

### 4.3 Web UI & DaisyDisk Sunburst Visualizer (`sysmgr.disk.web`)
1. **Drive Selector Home Screen**:
   - Lists all detected drives (`C:\`, `D:\`, etc.) with progress bars showing used/free capacity.
   - Includes custom directory picker for targeted scanning (e.g., `C:\dev` or `C:\Users\<user>`).
2. **Sunburst Radial Chart (D3.js)**:
   - Visualizes folder hierarchy as concentric rings (up to 4–5 levels rendered simultaneously).
   - Arc angle corresponds to proportional byte size.
   - Central circle displays focused path size (e.g., `456.3 GB`) and folder name.
   - Clicking a slice smoothly animates and zooms into that subfolder, updating the root.
3. **Breadcrumb Trail (Top Bar)**:
   - Clickable breadcrumbs (`C:\` > `Users` > `Michael Green` > `dev`) allowing instant jump to any parent level.
   - Quick "Rescan" and "Scan Another Source" buttons.
4. **Top List Panel (Right Sidebar)**:
   - Color-coded indicators matching the sunburst sectors.
   - Descending sorted list of largest files/folders with human-readable formatting (`GB`, `MB`).
   - Bidirectional hover linking: hovering an item in the sidebar highlights the matching arc in the sunburst and vice versa.

### 4.4 File Actions & Context Menu (`sysmgr.disk.actions`)
Right-clicking or clicking the action menu (`...`) on any file or folder provides power-user utilities:

| Action | Technical Implementation | Purpose |
| :--- | :--- | :--- |
| **Open with Default App** | `os.startfile(path)` | Opens videos in media players, docs in editors, etc. |
| **Reveal in File Explorer** | `explorer.exe /select,"<path>"` | Launches Windows Explorer with the item selected. |
| **Open Terminal Here** | `wt.exe -d "<dir>"` or PowerShell | Opens a shell in the target directory. |
| **Copy Path** | Clipboard API in browser / API | Copies absolute path to clipboard. |
| **Properties & Metadata** | `os.stat(path)` via API modal | Inspects timestamps, attributes, permissions. |
| **Move to Recycle Bin** | `send2trash` / `SHFileOperation` | Safely recycles item with confirmation prompt. |

### 4.5 Safety Gates & Remediation Invariants
- **Recycle Bin Default**: Files are sent to the Windows Recycle Bin by default to ensure non-destructive reversibility.
- **Protected Paths**: Deletions targeting core OS directories (`C:\Windows`, `C:\Program Files`, pagefile, hiberfil, system root) or active git metadata directories (`.git`) are strictly prohibited in the UI.
- **Integrated System Cleanups**: Quick-action buttons trigger existing `sysmgr` remediations:
  - `clean-temp-files` (safe user/system temp directory purge).
  - `dism-component-cleanup` (tracked WinSxS cleanup).

---

## 5. Verification & Testing Plan

1. **Unit Tests**:
   - `test_disk_scanner.py`: Test `os.scandir` tree construction, size aggregation, and junction skipping against temporary directory fixtures (`tmp_path`).
   - `test_disk_models.py`: Validate Pydantic models and serialization formats.
   - `test_disk_actions.py`: Test action dispatchers (ensuring protected path blocks and safe argument escaping).
   - `test_disk_server.py`: Test REST API routes (`/api/drives`, `/api/scan`, `/api/progress`, `/api/actions`) using `TestClient`.
2. **Integration & Smoke Tests**:
   - `test_disk_live.py`: Real-world smoke test verifying local drive discovery and reading sample folder trees without errors.
   - CLI verification: Validate `sysmgr disk --help` and `--cli` output formatting.
