import pytest
from pathlib import Path
from starlette.testclient import TestClient

from sysmgr.disk.drives import get_system_drives
from sysmgr.disk.scanner import DiskScanner
from sysmgr.disk.server import create_disk_app
from sysmgr.disk.models import ActionRequest
from sysmgr.disk.actions import execute_file_action


@pytest.mark.asyncio
async def test_live_drive_discovery():
    drives = get_system_drives()
    assert len(drives) >= 1
    mounts = [d.mountpoint for d in drives]
    assert any("C:" in m for m in mounts)
    for d in drives:
        assert d.total_bytes > 0
        assert 0.0 <= d.percent_used <= 100.0


@pytest.mark.asyncio
async def test_live_folder_scan(tmp_path: Path):
    # Populate small test directory with nested subfolders
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "nested.bin").write_bytes(b"A" * 5000)
    (tmp_path / "root_file.txt").write_bytes(b"B" * 1500)

    scanner = DiskScanner()
    tree, progress = await scanner.scan(str(tmp_path))
    assert tree.size_bytes == 6500
    assert len(tree.children) == 2
    assert tree.children[0].name == "subfolder"
    assert tree.children[0].size_bytes == 5000
    assert progress[-1].status == "completed"


def test_live_server_endpoints_flow(tmp_path: Path):
    (tmp_path / "test.txt").write_text("sample content")

    app = create_disk_app()
    client = TestClient(app)

    # 1. Test Drives API
    drives_resp = client.get("/api/drives")
    assert drives_resp.status_code == 200
    assert len(drives_resp.json()) >= 1

    # 2. Test Scan API
    scan_resp = client.post("/api/scan", json={"path": str(tmp_path)})
    assert scan_resp.status_code == 200
    assert scan_resp.json()["status"] == "scan_started"

    # 3. Test Actions API (properties)
    action_resp = client.post(
        "/api/actions", json={"action": "properties", "path": str(tmp_path / "test.txt")}
    )
    assert action_resp.status_code == 200
    assert action_resp.json()["success"] is True
    assert action_resp.json()["details"]["size_bytes"] == len("sample content")

    # 4. Test Actions API (copy_path)
    copy_resp = client.post(
        "/api/actions", json={"action": "copy_path", "path": str(tmp_path / "test.txt")}
    )
    assert copy_resp.status_code == 200
    assert copy_resp.json()["success"] is True
