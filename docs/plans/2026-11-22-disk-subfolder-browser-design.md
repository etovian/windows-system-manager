# Disk Visualizer: Shallow Subfolder Browser & Explicit Drive Scan

**Document**: Design Specification  
**Date**: 2026-11-22  
**Status**: Approved  
**Branch**: `feat/disk-subfolder-browser`

---

## 1. Problem Statement
Previously, clicking the `C:\` drive card in the Source Selection screen immediately triggered a recursive, full-volume scan across hundreds of thousands of files. Because full OS drives can take minutes to scan, users who only wished to inspect a specific subdirectory (such as `C:\dev` or `C:\Users`) were locked into an unintended full-disk scan.

## 2. Requirements & Goals
1. **Explicit Drive Scan Button**: Drive cards must feature an explicit `[Scan Whole Drive]` button to initiate full volume scans.
2. **Interactive Subfolder Navigation**: Clicking anywhere else on the drive card must navigate into a shallow directory browser for that drive instead of scanning.
3. **Drill-Down Explorer**: Users can traverse down into subfolders (`Computer > C:\ > Users > ...`) with breadcrumb navigation.
4. **Targeted Folder Scanning**: Users can scan the currently active directory via `[Scan This Folder]`, or scan any specific subdirectory via an inline `[Scan]` button on each folder row.
5. **Instant Response**: Subfolder directory listing must be shallow (non-recursive `os.scandir`), responding in <10ms without disk scanning overhead.

---

## 3. Architecture & API Design

### 3.1 Backend: Shallow Browse Endpoint
- **Route**: `GET /api/browse?path=<folder_path>`
- **Handler**: `browse_directory(request: Request) -> JSONResponse`
- **Logic**:
  1. Validate `path` parameter (must be non-empty, absolute, existing directory).
  2. Perform single-level `os.scandir(path)` (not recursive).
  3. Sort entries: directories first (alphabetical, case-insensitive), followed by files.
  4. Protect against permission errors on individual entries or directories (`PermissionError`, `OSError`).
  5. Compute `parent_path` (e.g. `C:\` for `C:\Users`, or `None` if at root mountpoint).
- **Response Schema**:
  ```json
  {
    "current_path": "C:\\Users",
    "parent_path": "C:\\",
    "items": [
      {
        "name": "Michael Green",
        "path": "C:\\Users\\Michael Green",
        "is_dir": true,
        "size_bytes": 0,
        "access_denied": false
      },
      {
        "name": "Public",
        "path": "C:\\Users\\Public",
        "is_dir": true,
        "size_bytes": 0,
        "access_denied": false
      }
    ]
  }
  ```

---

## 4. Frontend Design & User Flow

### 4.1 Drive Card Layout (`#drives-list`)
- Left section: Drive Mount (`C:\`), volume label (`Windows`), usage progress bar, and stats (`39.6% used | 1.1 TB free of 1.8 TB`).
- Right section: A standalone button:
  ```html
  <button type="button" class="btn btn-primary btn-scan-drive" title="Scan entire C:\ drive">
    ⚡ Scan Drive
  </button>
  ```
- Clicking `.btn-scan-drive` immediately runs `startScan(drive.mountpoint)`.
- Clicking anywhere else on the drive card calls `openDirectoryBrowser(drive.mountpoint)`.

### 4.2 Directory Browser Panel (`#dir-browser-panel`)
Replaces the `#drives-list` view inside `#drives-view` when active:
- **Header**:
  - `[ ← All Drives ]` button to return to the mounted drives grid.
  - **Clickable Breadcrumbs**: `Computer > C:\ > Users > Michael Green`
  - `[ ⚡ Scan This Folder ]` button to immediately scan the current folder.
- **Directory List**:
  - Rows for subdirectories and files with icons (`📁`, `📄`).
  - Clicking a directory row drills down into that directory.
  - Row action: An inline `[Scan]` button on each directory row to scan that target immediately.
  - Inaccessible directories show a locked icon (`🔒 Access Denied`) and are disabled.

---

## 5. Verification & Testing Strategy
1. **Unit Tests**:
   - `tests/unit/disk/test_server.py`: Test `/api/browse` with valid directory, invalid path, file path, and permission errors.
   - `tests/unit/disk/test_web_assets.py`: Verify markup for `.btn-scan-drive`, `#dir-browser-panel`, and breadcrumbs.
2. **Live Browser Smoke**:
   - Verify clicking `[Scan Drive]` triggers scan on `C:\`.
   - Verify clicking `C:\` card opens browser with `Users`, `Program Files`, etc.
   - Verify clicking `Users` navigates into `C:\Users`.
   - Verify clicking `[Scan This Folder]` scans `C:\Users`.
