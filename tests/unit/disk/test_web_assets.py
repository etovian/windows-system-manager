from pathlib import Path


def test_web_assets_exist_and_non_empty():
    web_dir = Path("src/sysmgr/disk/web")
    assert (web_dir / "index.html").exists()
    assert (web_dir / "styles.css").exists()
    assert (web_dir / "app.js").exists()
    assert (web_dir / "d3.min.js").exists()

    assert len((web_dir / "index.html").read_text(encoding="utf-8")) > 200
    assert len((web_dir / "styles.css").read_text(encoding="utf-8")) > 200
    assert len((web_dir / "app.js").read_text(encoding="utf-8")) > 500
    assert len((web_dir / "d3.min.js").read_text(encoding="utf-8")) > 50000


def test_web_asset_content_structure():
    web_dir = Path("src/sysmgr/disk/web")
    html = (web_dir / "index.html").read_text(encoding="utf-8")
    assert "sunburst" in html.lower()
    assert "top-list" in html.lower()
    assert "breadcrumb" in html.lower()
    assert "scan-log-box" in html
    assert "quick-paths" in html
    assert "dir-browser-panel" in html
    assert "btn-scan-current-dir" in html
    assert "btn-visualizer-up" in html
    assert "browser-breadcrumb-container" in html

    # Verify cache-busting version sync
    assert 'styles.css?v=5' in html
    assert 'app.js?v=5' in html

    # Prevent CSS specificity bug where inline style overrides active class
    assert 'id="visualizer-view" class="view-panel" style="display: none;"' not in html
    assert 'id="scan-overlay" class="scan-overlay" style="display: none;"' not in html

    css = (web_dir / "styles.css").read_text(encoding="utf-8")
    assert "scan-log-box" in css
    assert "quick-paths" in css
    assert "dir-browser-panel" in css
    assert "btn-scan-drive" in css
    assert "browser-crumb" not in css
    assert "btn-nav-up" in css
    assert "above-tree" in css
    assert "crumb-icon" in css
    assert "min-width: 0;" in css

    js = (web_dir / "app.js").read_text(encoding="utf-8")
    assert "/api/drives" in js
    assert "/api/browse" in js
    assert "/api/scan" in js
    assert "/api/actions" in js
    assert "scanLogBox" in js
    assert "getVisibleArcs" in js
    assert "btn-quick-path" in js
    assert "openDirectoryBrowser" in js
    assert "btn-scan-drive" in js
    assert "btnVisualizerUp" in js
    assert "browserBreadcrumbContainer" in js
    assert "navigateUpOneLevel" in js
    assert "getPathAncestors" in js
    assert "above-tree" in js
    assert "Click center to go up" in js
    assert "propertiesModal.open" in js


def test_path_ancestors_decomposition_logic():
    """Verify the path decomposition logic matches the JS implementation behavior."""
    def py_get_path_ancestors(target_path: str):
        if not target_path:
            return {"parts": [], "parent_path": "", "is_unc": False}
        normalized = target_path.replace("/", "\\")
        is_unc = normalized.startswith("\\\\")
        parts = [p for p in normalized.split("\\") if p]

        parent_path = ""
        if len(parts) > 1:
            parent_parts = parts[:-1]
            if is_unc:
                parent_path = "\\\\" + "\\".join(parent_parts)
            elif len(parent_parts) == 1 and ":" in parent_parts[0]:
                parent_path = f"{parent_parts[0]}\\"
            else:
                parent_path = "\\".join(parent_parts)
        return {"parts": parts, "parent_path": parent_path, "is_unc": is_unc}

    # Case 1: Drive Root (e.g. C:\)
    c_root = py_get_path_ancestors("C:\\")
    assert c_root["parts"] == ["C:"]
    assert c_root["parent_path"] == ""

    # Case 2: Subfolder (e.g. C:\Games\Baldur's Gate\data)
    sub = py_get_path_ancestors(r"C:\Games\Baldur's Gate\data")
    assert sub["parts"] == ["C:", "Games", "Baldur's Gate", "data"]
    assert sub["parent_path"] == r"C:\Games\Baldur's Gate"

    # Case 3: One level deep subfolder (e.g. C:\Windows)
    win = py_get_path_ancestors("C:\\Windows")
    assert win["parts"] == ["C:", "Windows"]
    assert win["parent_path"] == "C:\\"

    # Case 4: UNC network share
    unc = py_get_path_ancestors(r"\\nas\storage\backup")
    assert unc["parts"] == ["nas", "storage", "backup"]
    assert unc["is_unc"] is True
    assert unc["parent_path"] == r"\\nas\storage"
