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

    # Prevent CSS specificity bug where inline style overrides active class
    assert 'id="visualizer-view" class="view-panel" style="display: none;"' not in html
    assert 'id="scan-overlay" class="scan-overlay" style="display: none;"' not in html

    css = (web_dir / "styles.css").read_text(encoding="utf-8")
    assert "scan-log-box" in css
    assert "quick-paths" in css

    js = (web_dir / "app.js").read_text(encoding="utf-8")
    assert "/api/drives" in js
    assert "/api/scan" in js
    assert "/api/actions" in js
    assert "scanLogBox" in js
    assert "computeGeometry" in js
    assert "btn-quick-path" in js
