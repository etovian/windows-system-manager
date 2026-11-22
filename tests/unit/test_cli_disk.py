from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from sysmgr.cli import app
from sysmgr.disk.models import DriveInfo, FileNode

runner = CliRunner()


def test_disk_command_help():
    result = runner.invoke(app, ["disk", "--help"])
    assert result.exit_code == 0
    assert "disk" in result.output.lower()
    assert "--cli" in result.output
    assert "--port" in result.output


def test_disk_cli_summary_mode_drives():
    mock_drives = [
        DriveInfo(
            mountpoint="C:\\",
            device="C:",
            fstype="NTFS",
            label="System SSD",
            total_bytes=500_000_000_000,
            free_bytes=200_000_000_000,
            used_bytes=300_000_000_000,
            percent_used=60.0,
        )
    ]
    with patch("sysmgr.disk.drives.get_system_drives", return_value=mock_drives):
        result = runner.invoke(app, ["disk", "--cli"])
        assert result.exit_code == 0
        assert "System SSD" in result.output or "C:" in result.output


def test_disk_cli_summary_mode_folder(tmp_path):
    (tmp_path / "big_file.dat").write_bytes(b"x" * 2048)
    result = runner.invoke(app, ["disk", str(tmp_path), "--cli"])
    assert result.exit_code == 0
    assert "big_file.dat" in result.output


def test_disk_web_mode_invokes_uvicorn():
    with patch("uvicorn.run") as mock_uvicorn, \
         patch("webbrowser.open") as mock_browser:
        result = runner.invoke(app, ["disk", "--port", "9999", "--no-browser"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once()
        assert mock_browser.call_count == 0


def test_disk_web_mode_opens_browser():
    with patch("uvicorn.run") as mock_uvicorn, \
         patch("webbrowser.open") as mock_browser:
        result = runner.invoke(app, ["disk", "--port", "8765"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once()
        mock_browser.assert_called_once_with("http://127.0.0.1:8765")
