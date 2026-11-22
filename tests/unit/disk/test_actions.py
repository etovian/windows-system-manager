"""Tests for Windows file operations and safety gates."""

import os
from unittest.mock import MagicMock, patch

import pytest

from sysmgr.disk.actions import execute_file_action, is_protected_system_path
from sysmgr.disk.models import ActionRequest


def test_protected_system_paths():
    assert is_protected_system_path("C:\\Windows") is True
    assert is_protected_system_path("C:\\Windows\\System32\\cmd.exe") is True
    assert is_protected_system_path("C:\\Program Files\\app") is True
    assert is_protected_system_path("C:\\Users\\user\\project\\.git\\config") is True
    assert is_protected_system_path("C:\\") is True
    assert is_protected_system_path("C:\\Users\\user\\Downloads\\bigfile.zip") is False


def test_recycle_blocked_on_protected_path():
    with patch("os.path.exists", return_value=True):
        req = ActionRequest(action="recycle", path="C:\\Windows\\notepad.exe")
        res = execute_file_action(req)
        assert res.success is False
        assert "protected" in res.message.lower()


def test_open_file_calls_startfile():
    with patch("os.path.exists", return_value=True), patch(
        "os.startfile", create=True
    ) as mock_start:
        req = ActionRequest(action="open", path="C:\\test\\doc.pdf")
        res = execute_file_action(req)
        assert res.success is True
        mock_start.assert_called_once_with(os.path.normpath("C:\\test\\doc.pdf"))


def test_reveal_file_calls_explorer():
    with patch("os.path.exists", return_value=True), patch(
        "subprocess.Popen"
    ) as mock_popen:
        req = ActionRequest(action="reveal", path="C:\\test\\doc.pdf")
        res = execute_file_action(req)
        assert res.success is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "explorer.exe" in args[0]
        assert "/select," in args[1]


def test_terminal_action():
    with patch("os.path.exists", return_value=True), patch(
        "subprocess.Popen"
    ) as mock_popen:
        req = ActionRequest(action="terminal", path="C:\\test")
        res = execute_file_action(req)
        assert res.success is True
        mock_popen.assert_called_once()


def test_copy_path_action():
    with patch("os.path.exists", return_value=True):
        req = ActionRequest(action="copy_path", path="C:\\test\\file.txt")
        res = execute_file_action(req)
        assert res.success is True
        assert res.details["path"] == os.path.normpath("C:\\test\\file.txt")


def test_properties_action(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello")
    req = ActionRequest(action="properties", path=str(f))
    res = execute_file_action(req)
    assert res.success is True
    assert res.details["size_bytes"] == 5
    assert res.details["is_dir"] is False


def test_nonexistent_path_returns_error():
    req = ActionRequest(action="open", path="C:\\nonexistent_file_xyz_123.bin")
    res = execute_file_action(req)
    assert res.success is False
    assert "not exist" in res.message.lower()


def test_recycle_success(tmp_path):
    target = tmp_path / "torecycle.txt"
    target.write_text("delete me")
    with patch("subprocess.run") as mock_run:
        req = ActionRequest(action="recycle", path=str(target))
        res = execute_file_action(req)
        assert res.success is True
