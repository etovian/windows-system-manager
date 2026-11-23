# Specification: Unify Breadcrumb Implementation Across Sysmgr Disk UI

## 1. Problem Statement
Currently, there are two distinct breadcrumb implementations in the Disk Visualizer:
1. **Directory Browser View** (`#dir-browser-panel`):
   - Uses `.browser-breadcrumbs`, raw text-button links (`.browser-crumb`), and unstyled browser scrollbars with visible arrows/track.
   - Inconsistent typography, lacks icons, and lacks the polished pill aesthetic.
2. **Scan Visualizer View** (`#visualizer-view`):
   - Uses `.breadcrumb-container` + `.breadcrumb-item` with rounded pill badges, icons (`💻`, `💽`, `📁`, `📄`), subtle borders, hover glow, and a sleek custom scrollbar.

The user requested that the second implementation (the scan results visualizer breadcrumbs) be used everywhere as the single unified breadcrumb implementation.

## 2. Proposed Architecture & Solution

### A. DOM Structure Unification
Update the Directory Browser header in `src/sysmgr/disk/web/index.html`:
Replace:
```html
<div class="browser-breadcrumbs" id="browser-breadcrumbs">
  <!-- Breadcrumbs generated dynamically -->
</div>
```
With:
```html
<nav class="breadcrumb-container" id="browser-breadcrumb-container">
  <div class="breadcrumb" id="browser-breadcrumbs">
    <!-- Breadcrumbs generated dynamically -->
  </div>
</nav>
```

### B. JavaScript Rendering Logic Unification
In `src/sysmgr/disk/web/app.js`:
- Update `renderBrowserBreadcrumbs(dirPath)` to produce `.breadcrumb-item` elements identical to the Visualizer's `renderBreadcrumb()`:
  - Computer crumb: `<button type="button" class="breadcrumb-item"><span class="crumb-icon">💻</span>Computer</button>`
  - Separators: `<span class="breadcrumb-separator">›</span>`
  - Folder crumbs: `<button type="button" class="breadcrumb-item ${isLast ? 'active' : ''}"><span class="crumb-icon">${icon}</span>${escapeHtml(part)}</button>` (with `💽` for drives and `📁` for directories).
  - Use `getPathAncestors(dirPath)` utility for path consistency.
  - Auto-scroll `browserBreadcrumbContainer` horizontally to the active pill.

### C. CSS Deprecation & Cleanup
In `src/sysmgr/disk/web/styles.css`:
- Remove legacy `.browser-breadcrumbs`, `.browser-crumb`, `.browser-crumb-sep` styles.
- Ensure `.breadcrumb-container` and `.breadcrumb-item` adapt gracefully to both the app header and the directory browser header.
- Bump cache query version to `v=5` in `index.html`.

## 3. Verification & Testing
1. Update `tests/unit/disk/test_web_assets.py` to assert:
   - Only unified `.breadcrumb-container` / `.breadcrumb-item` classes are used; deprecated `.browser-crumb` is eliminated.
   - Cache-busting version sync (`v=5`).
2. Run full test suite (`pytest`).
3. Verify visually in browser.
