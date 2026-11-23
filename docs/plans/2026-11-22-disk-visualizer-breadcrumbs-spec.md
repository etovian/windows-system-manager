# Specification: Full Filesystem Breadcrumbs & Up-Navigation in Disk Visualizer

## 1. Problem Statement & Root Cause
In the `sysmgr` Disk Visualizer view, the breadcrumb trail is currently populated exclusively from `state.focusedNode.ancestors()`.
When a user scans a subfolder (e.g., `C:\Games\Baldur's Gate\data`), `state.rootNode` is the root of the D3 hierarchy, and its `.parent` is `null`. Consequently:
- The breadcrumb trail only renders `[ data ]` instead of the full directory path hierarchy (`Computer › C: › Games › Baldur's Gate › data`).
- The user has no visibility into the parent directory path and no breadcrumb pills to navigate or move up directories.
- Clicking the center circle (`sunburstCenter`) when at the scan root does nothing because `state.focusedNode.parent` is null.

## 2. Proposed Architecture & Solution

### A. Full Path Breadcrumbs Hierarchy
Instead of only inspecting in-tree D3 ancestors, `renderBreadcrumb()` will resolve the full path from the filesystem down to the currently focused node:
1. **Retrieve Current Path**:
   - `currentPath = state.focusedNode.data.path`
   - `rootScanPath = state.rootNode.data.path`
2. **Decompose into Segments**:
   - Split `currentPath` into ancestor path segments from `Computer` / Drive letter (e.g. `C:\`) down through all folders.
3. **Partition Segments into Two Zones**:
   - **Above-Tree Ancestors** (folders above `rootScanPath`):
     - Path segments between the drive root and the scanned folder (e.g., `Computer`, `C:`, `Games`, `Baldur's Gate`).
     - Rendered with a folder icon cue (e.g. `📁 Baldur's Gate`).
     - Clicking navigates up into that directory using the shallow directory browser (`openDirectoryBrowser(ancestorPath)`), allowing the user to inspect sister folders, move anywhere else, or click `⚡ Scan This Folder`.
   - **In-Tree Ancestors** (from `rootScanPath` down to `state.focusedNode`):
     - Nodes that exist within the current scan hierarchy (e.g., `data`, `subfolder`).
     - Clicking instantly zooms the radial wheel and updates the top list (`state.zoomTo(treeNode)`).
     - The currently focused node receives the `.active` styling.

### B. Dedicated "Up One Level" Navigation
1. **Header "⬆ Up" Action**:
   - Add an explicit `[ ⬆ Up ]` button in the visualizer header right before the breadcrumb track.
   - Behavior:
     - If `state.focusedNode.parent` exists: calls `state.zoomTo(state.focusedNode.parent)` (drills up one level in the wheel).
     - If at scan root (`state.focusedNode === state.rootNode`):
       - If a parent directory exists (e.g. `parentPath = dirname(rootScanPath)`): switches to the directory browser at `parentPath` (`openDirectoryBrowser(parentPath)`).
       - If at drive root (e.g. `C:\`): switches back to the Drives view (`switchToDrives()`).
2. **Center Circle Badge "Click to go up"**:
   - When at scan root, update `elements.centerMeta` to show `Click center to go up to parent` (instead of static `Directory Root`).
   - Clicking center circle when at scan root triggers the same parent navigation as the `[ ⬆ Up ]` button.

### C. Visualizer Header Layout & Styling
- Add smooth horizontal scrolling for long paths with left/right scroll hints if needed.
- Distinguish above-tree ancestors (navigates to folder browser) from in-tree nodes (drills wheel).
- Add tooltip showing full path on each breadcrumb segment.

## 3. Verification & Testing
1. Unit tests in `tests/unit/disk/test_web_assets.py` to verify:
   - Path decomposition helper handling Windows paths (`C:\foo\bar`, network paths, and drive roots).
   - Breadcrumb DOM rendering and event listeners for both in-tree and above-tree items.
   - "Up" button state and action dispatching.
2. Full test suite run (`pytest`).
3. Visual verification in browser.
