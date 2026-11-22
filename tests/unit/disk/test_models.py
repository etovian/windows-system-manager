import pytest
from pydantic import ValidationError
from sysmgr.disk.models import ActionRequest, ActionResult, DriveInfo, FileNode, ScanProgress


def test_file_node_hierarchy_and_size():
    child1 = FileNode(name="file1.txt", path="C:\\test\\file1.txt", size_bytes=1000, is_dir=False)
    child2 = FileNode(name="file2.txt", path="C:\\test\\file2.txt", size_bytes=2000, is_dir=False)
    parent = FileNode(
        name="test",
        path="C:\\test",
        size_bytes=3000,
        is_dir=True,
        children=[child1, child2],
    )
    assert parent.size_bytes == 3000
    assert len(parent.children) == 2
    assert parent.children[0].name == "file1.txt"

    # Test round-trip JSON serialization
    json_data = parent.model_dump_json()
    reconstructed = FileNode.model_validate_json(json_data)
    assert reconstructed.name == "test"
    assert len(reconstructed.children) == 2
    assert reconstructed.children[1].size_bytes == 2000


def test_drive_info_model():
    drive = DriveInfo(
        mountpoint="C:\\",
        device="C:",
        fstype="NTFS",
        label="Windows OS",
        total_bytes=500_000_000_000,
        free_bytes=200_000_000_000,
        used_bytes=300_000_000_000,
        percent_used=60.0,
    )
    assert drive.percent_used == 60.0
    assert drive.free_bytes == 200_000_000_000

    dump = drive.model_dump()
    assert dump["mountpoint"] == "C:\\"
    assert dump["device"] == "C:"


def test_scan_progress_model():
    progress = ScanProgress(
        status="scanning",
        current_path="C:\\test",
        files_scanned=150,
        total_bytes=45000000,
        elapsed_seconds=1.2,
    )
    assert progress.status == "scanning"
    assert progress.files_scanned == 150


def test_action_request_and_result():
    req = ActionRequest(action="reveal", path="C:\\test\\file.txt")
    res = ActionResult(success=True, message="Revealed in explorer", details={"pid": 1234})
    assert req.action == "reveal"
    assert res.success is True
    assert res.details == {"pid": 1234}


def test_action_request_validation_error():
    with pytest.raises(ValidationError):
        ActionRequest(action="invalid_action", path="C:\\test\\file.txt")  # type: ignore
