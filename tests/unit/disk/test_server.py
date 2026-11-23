import os
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from sysmgr.disk.models import ActionResult, DriveInfo, FileNode, ScanProgress
from sysmgr.disk.server import create_disk_app, execute_scan
import sysmgr.disk.server as server_module


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
            percent_used=60.0,
        )
    ]
    with patch("sysmgr.disk.server.get_system_drives", return_value=mock_drives):
        resp = client.get("/api/drives")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["mountpoint"] == "C:\\"


def test_api_scan_endpoint_validation(client):
    resp = client.post("/api/scan", json={"path": "C:\\nonexistent_dir_987654321"})
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_api_scan_endpoint_missing_path(client):
    resp = client.post("/api/scan", json={})
    assert resp.status_code == 400

    resp_invalid_json = client.post(
        "/api/scan",
        content="not-json",
        headers={"content-type": "application/json"},
    )
    assert resp_invalid_json.status_code == 400


def test_api_scan_endpoint_success(client, tmp_path):
    resp = client.post("/api/scan", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    assert resp.json()["status"] == "scan_started"


def test_api_scan_consecutive_restarts(client, tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()

    resp1 = client.post("/api/scan", json={"path": str(dir1)})
    assert resp1.status_code == 200

    resp2 = client.post("/api/scan", json={"path": str(dir2)})
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "scan_started"


def test_api_scan_cancel_endpoint(client):
    resp = client.post("/api/scan/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "scan_cancelled"


def test_api_actions_endpoint(client):
    with patch("sysmgr.disk.server.execute_file_action", autospec=True) as mock_action:
        mock_action.return_value = ActionResult(success=True, message="Success", details=None)
        resp = client.post("/api/actions", json={"action": "open", "path": "C:\\test\\doc.txt"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify single ActionRequest object passed
        assert mock_action.call_count == 1
        call_arg = mock_action.call_args[0][0]
        assert call_arg.action == "open"
        assert call_arg.path == "C:\\test\\doc.txt"


def test_api_actions_endpoint_invalid_payload(client):
    resp = client.post("/api/actions", json={"action": "invalid_action", "path": "C:\\test"})
    assert resp.status_code == 400


def test_api_scan_tree_endpoint(client):
    resp = client.get("/api/scan/tree")
    assert resp.status_code == 200

    # Test with populated tree
    server_module._current_scan_tree = FileNode(
        name="root",
        path="C:\\root",
        size_bytes=1000,
        is_dir=True,
    )
    resp = client.get("/api/scan/tree")
    assert resp.status_code == 200
    assert resp.json()["name"] == "root"
    assert resp.json()["size_bytes"] == 1000
    server_module._current_scan_tree = None


def test_api_scan_progress_sse(client, tmp_path):
    (tmp_path / "hello.txt").write_text("world", encoding="utf-8")
    resp = client.post("/api/scan", json={"path": str(tmp_path)})
    assert resp.status_code == 200

    with client.stream("GET", "/api/scan/progress") as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        lines = []
        for line in stream_resp.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 1:
                break
        assert any("data:" in line for line in lines)


def test_static_files_mount(tmp_path):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    index_file = web_dir / "index.html"
    index_file.write_text("<html><body>DaisyDisk Visualizer</body></html>", encoding="utf-8")

    app = create_disk_app(web_dir=str(web_dir))
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    assert "DaisyDisk Visualizer" in resp.text


def test_api_browse_endpoint_missing_path(client):
    resp = client.get("/api/browse")
    assert resp.status_code == 400
    assert "required" in resp.json()["error"].lower()


def test_api_browse_endpoint_nonexistent_path(client):
    resp = client.get("/api/browse?path=C:\\nonexistent_dir_12345")
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["error"]


def test_api_browse_endpoint_file_path(client, tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello", encoding="utf-8")
    resp = client.get(f"/api/browse?path={f}")
    assert resp.status_code == 400
    assert "not a directory" in resp.json()["error"]


def test_api_browse_endpoint_success(client, tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("content", encoding="utf-8")

    resp = client.get(f"/api/browse?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_path"] == str(tmp_path)
    assert data["access_denied"] is False
    assert len(data["items"]) == 2
    # Directories sorted first
    assert data["items"][0]["name"] == "subdir"
    assert data["items"][0]["is_dir"] is True
    assert data["items"][1]["name"] == "file.txt"
    assert data["items"][1]["is_dir"] is False

