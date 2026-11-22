import asyncio
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from sysmgr.disk import DiskScanner
from sysmgr.disk.models import FileNode, ScanProgress


@pytest.mark.asyncio
async def test_scanner_traverses_directory_and_aggregates_sizes(tmp_path: Path):
    sub1 = tmp_path / "sub1"
    sub1.mkdir()
    (sub1 / "file1.dat").write_bytes(b"a" * 1024)

    sub2 = tmp_path / "sub2"
    sub2.mkdir()
    (sub2 / "file2.dat").write_bytes(b"b" * 2048)

    root_file = tmp_path / "root.txt"
    root_file.write_bytes(b"c" * 512)

    progress_events = []

    def on_progress(p: ScanProgress):
        progress_events.append(p)

    scanner = DiskScanner(min_size_ratio=0.01)
    tree, progress_history = await scanner.scan(str(tmp_path), progress_callback=on_progress)

    assert tree.is_dir is True
    assert tree.size_bytes == 1024 + 2048 + 512
    assert len(tree.children) == 3
    # Check children sorted by size descending
    assert tree.children[0].name == "sub2"
    assert tree.children[0].size_bytes == 2048
    assert len(progress_history) > 0
    assert progress_history[-1].status == "completed"
    assert len(progress_events) == len(progress_history)


@pytest.mark.asyncio
async def test_scanner_groups_small_files_into_other(tmp_path: Path):
    (tmp_path / "large.dat").write_bytes(b"x" * 10000)
    for i in range(8):
        (tmp_path / f"tiny_{i}.txt").write_bytes(b"y" * 10)

    scanner = DiskScanner(min_size_ratio=0.05)
    tree, _ = await scanner.scan(str(tmp_path))

    child_names = [c.name for c in tree.children]
    assert "large.dat" in child_names
    assert "Other files" in child_names
    other_node = next(c for c in tree.children if c.name == "Other files")
    assert other_node.size_bytes == 80


@pytest.mark.asyncio
async def test_scanner_handles_cancellation(tmp_path: Path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "file.dat").write_bytes(b"z" * 1024)

    scanner = DiskScanner()
    scanner.cancel()
    tree, history = await scanner.scan(str(tmp_path))
    assert scanner.is_cancelled is True


@pytest.mark.asyncio
async def test_scanner_handles_mid_scan_cancellation(tmp_path: Path):
    for i in range(10):
        (tmp_path / f"file_{i}.dat").write_bytes(b"x" * 100)

    scanner = DiskScanner()

    def cancel_on_progress(p: ScanProgress):
        if p.files_scanned >= 2:
            scanner.cancel()

    tree, history = await scanner.scan(str(tmp_path), progress_callback=cancel_on_progress)
    assert scanner.is_cancelled is True
    assert history[-1].status == "completed"


@pytest.mark.asyncio
async def test_scanner_handles_single_file(tmp_path: Path):
    file_path = tmp_path / "single.txt"
    file_path.write_bytes(b"hello" * 10)

    scanner = DiskScanner()
    node, history = await scanner.scan(str(file_path))

    assert node.is_dir is False
    assert node.name == "single.txt"
    assert node.size_bytes == 50
    assert history[-1].status == "completed"


@pytest.mark.asyncio
async def test_scanner_respects_max_depth(tmp_path: Path):
    # depth 0: root
    # depth 1: level1
    # depth 2: level2
    level1 = tmp_path / "level1"
    level1.mkdir()
    level2 = level1 / "level2"
    level2.mkdir()
    (level2 / "deep.txt").write_bytes(b"d" * 500)

    scanner = DiskScanner(max_depth=1)
    tree, _ = await scanner.scan(str(tmp_path))

    assert tree.size_bytes == 0
    assert len(tree.children) == 1
    # level1 was reached at depth 1, its children at depth 2 were skipped
    assert tree.children[0].name == "level1"
    assert tree.children[0].size_bytes == 0


@pytest.mark.asyncio
async def test_scanner_skips_symlinks(tmp_path: Path):
    # Mock scandir entries to simulate symlink without requiring OS privileges
    mock_symlink = MagicMock()
    mock_symlink.is_symlink.return_value = True
    mock_symlink.is_junction.return_value = False
    mock_symlink.name = "symlink_file.txt"

    mock_real = MagicMock()
    mock_real.is_symlink.return_value = False
    mock_real.is_junction.return_value = False
    mock_real.is_dir.return_value = False
    mock_real.name = "real_file.txt"
    mock_real.path = str(tmp_path / "real_file.txt")
    mock_stat = MagicMock()
    mock_stat.st_size = 1234
    mock_real.stat.return_value = mock_stat

    mock_context = MagicMock()
    mock_context.__enter__.return_value = [mock_symlink, mock_real]
    mock_context.__exit__.return_value = None

    with patch("os.scandir", return_value=mock_context):
        scanner = DiskScanner()
        tree, _ = await scanner.scan(str(tmp_path))

        child_names = [c.name for c in tree.children]
        assert "real_file.txt" in child_names
        assert "symlink_file.txt" not in child_names
        assert tree.size_bytes == 1234


@pytest.mark.asyncio
async def test_scanner_handles_permission_error_on_scandir(tmp_path: Path):
    with patch("os.scandir", side_effect=PermissionError("Access Denied")):
        scanner = DiskScanner()
        tree, history = await scanner.scan(str(tmp_path))
        assert tree.size_bytes == 0
        assert len(tree.children) == 0
        assert history[-1].status == "completed"


@pytest.mark.asyncio
async def test_scanner_handles_nonexistent_directory(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    scanner = DiskScanner()
    tree, history = await scanner.scan(str(nonexistent))
    assert tree.is_dir is True
    assert tree.size_bytes == 0
    assert len(tree.children) == 0
    assert len(history) > 0
