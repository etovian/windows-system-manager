# Specification: Directory Browser Header 2-Row Layout & Wrapping Breadcrumbs

## 1. Problem Statement & User Feedback
In the Directory Browser view (`#dir-browser-panel`), placing `[ ← All Drives ]`, the breadcrumb track, and the dynamic `[ ⚡ Scan "<folder>" ]` button in a single flex row causes significant layout issues:
- Folders with long names (e.g. Windows SID `S-1-5-21-2400324132-551446863-3097187856-1000`) cause the scan button to expand horizontally, severely compressing the breadcrumbs into a narrow squeezed box with an ugly horizontal scroller.
- The path becomes hard to read and navigate.

## 2. Proposed Architecture & Solution

### A. Two-Row Layout in Directory Browser
Split `.browser-header` into two distinct vertical sections:
1. **Row 1 - Full-Width Wrapping Breadcrumbs Track**:
   - Contains `#browser-breadcrumb-container` spanning 100% of the container width.
   - Breadcrumbs (`#browser-breadcrumbs`) use `flex-wrap: wrap;` with `gap: 6px 8px;`.
   - No horizontal clipping, no scrollbars (`overflow: visible;` or `overflow-x: unset;`).
   - Breadcrumbs wrap naturally onto subsequent lines when paths are deeply nested or contain long segment names.
2. **Row 2 - Actions Bar (`.browser-actions-bar`)**:
   - Placed directly beneath the breadcrumbs row.
   - Left side: `[ ← All Drives ]` (`#btn-browser-back`).
   - Right side: `[ ⚡ Scan this Directory ]` (`#btn-scan-current-dir`).
   - Display: `display: flex; justify-content: space-between; align-items: center; width: 100%;`.

### B. Hardcoded Scan Button Text
- Change `#btn-scan-current-dir` label to static hardcoded text:
  `<span class="icon">⚡</span> Scan this Directory`
- In `renderBrowserBreadcrumbs(dirPath)` in `app.js`, remove the dynamic name formatting (`leafName`), keeping the click handler bound to `startScan(dirPath)`.

### C. Styling Updates
In `src/sysmgr/disk/web/styles.css`:
- `.browser-header`: `display: flex; flex-direction: column; gap: 14px; width: 100%;`.
- `#browser-breadcrumb-container`: remove horizontal scrolling, enable `flex-wrap: wrap;`.
- `.browser-actions-bar`: full-width flex row containing the back button and scan button.
- Bump cache version to `v=6` in `index.html`.

## 3. Verification & Testing
1. Update tests in `tests/unit/disk/test_web_assets.py` to assert:
   - Presence of `browser-actions-bar` and hardcoded `Scan this Directory` button in HTML/JS.
   - Cache-busting version `v=6`.
2. Run test suite (`pytest tests/unit/disk/test_web_assets.py` and `pytest`).
3. Visual confirmation of 2-row layout with wrapping breadcrumbs.
