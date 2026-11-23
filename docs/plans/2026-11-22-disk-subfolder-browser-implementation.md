# Implementation Plan: Shallow Subfolder Browser & Explicit Drive Scan

**Document**: Implementation Specification  
**Date**: 2026-11-22  
**Branch**: `feat/disk-subfolder-browser`

---

## Proposed Work Breakdown

### Task 1: Backend Shallow Browse Endpoint
- **File**: `src/sysmgr/disk/server.py`
- Add route `GET /api/browse?path=...`.
- Safely inspect directory entries using non-recursive `os.scandir`.
- Return sorted items with `name`, `path`, `is_dir`, `access_denied`.
- Add comprehensive unit tests in `tests/unit/disk/test_server.py`.

### Task 2: HTML Structure for Directory Browser Panel
- **File**: `src/sysmgr/disk/web/index.html`
- Inside `#drives-view`:
  - Add `#dir-browser-panel` with:
    - Back button `[ ← All Drives ]`.
    - Breadcrumb container `#browser-breadcrumbs`.
    - Action button `#btn-scan-current-dir` (`⚡ Scan This Folder`).
    - Directory items list container `#browser-items-list`.

### Task 3: Styling for Drive Cards & Directory Browser
- **File**: `src/sysmgr/disk/web/styles.css`
- Update `.drive-card` layout to flex row with right-aligned `[Scan Drive]` button.
- Add styles for `.btn-scan-drive`, `#dir-browser-panel`, `.browser-header`, `.browser-row`, `.browser-item-icon`, and inline row `.btn-scan-folder`.

### Task 4: Frontend Directory Browser Logic
- **File**: `src/sysmgr/disk/web/app.js`
- Update `renderDrives`:
  - Attach click handler on `.btn-scan-drive` -> `startScan(drive.mountpoint)`.
  - Attach click handler on drive card body -> `openDirectoryBrowser(drive.mountpoint)`.
- Implement `openDirectoryBrowser(path)`:
  - Fetches `/api/browse?path=...`.
  - Renders breadcrumbs (`Computer > C:\ > ...`).
  - Renders directory items.
  - Clicking subfolder -> `openDirectoryBrowser(subfolder)`.
  - Clicking `[Scan]` on row or header -> `startScan(targetPath)`.
- Implement `closeDirectoryBrowser()` returning to `#drives-list`.

### Task 5: Unit Tests & Verification
- **Files**: `tests/unit/disk/test_server.py`, `tests/unit/disk/test_web_assets.py`
- Run full pytest test suite.
