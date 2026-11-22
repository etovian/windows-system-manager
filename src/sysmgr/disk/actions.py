"""Windows file operations and safety gates for disk management."""

import os
import subprocess
from typing import Any, Dict

from sysmgr.disk.models import ActionRequest, ActionResult


def is_protected_system_path(path: str) -> bool:
    """Check if the given path is a protected Windows system path or critical folder."""
    if not path or not path.strip():
        return True

    normalized = os.path.normpath(path).strip()
    drive, rest = os.path.splitdrive(normalized)

    clean_rest = rest.replace("/", "\\").strip("\\")
    # Drive roots like "C:\" or "C:"
    if not clean_rest:
        return True

    parts = [p.lower() for p in clean_rest.split("\\") if p]
    if not parts:
        return True

    # Check for version control repositories anywhere in the path hierarchy
    if any(p in (".git", ".svn", ".hg") for p in parts):
        return True

    # Protected root directory branches
    protected_roots = {
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "$recycle.bin",
        "system volume information",
        "recovery",
        "boot",
    }
    if parts[0] in protected_roots:
        return True

    # Critical root files
    protected_root_files = {
        "pagefile.sys",
        "swapfile.sys",
        "hiberfil.sys",
        "bootmgr",
        "bootnxt",
    }
    if len(parts) == 1 and parts[0] in protected_root_files:
        return True

    # Check Windows environment variables if defined
    for var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        env_val = os.environ.get(var)
        if env_val:
            norm_env = os.path.normcase(os.path.normpath(env_val))
            norm_curr = os.path.normcase(normalized)
            if norm_curr == norm_env or norm_curr.startswith(norm_env + os.sep):
                return True

    return False


def execute_file_action(request: ActionRequest) -> ActionResult:
    """Execute a file or directory operation on Windows with safety gates."""
    norm_path = os.path.normpath(request.path)

    if not os.path.exists(norm_path):
        return ActionResult(
            success=False,
            message=f"Path does not exist: {norm_path}",
        )

    action = request.action

    if action == "recycle":
        if is_protected_system_path(norm_path):
            return ActionResult(
                success=False,
                message=f"Path is a protected system path and cannot be recycled: {norm_path}",
            )

        is_dir = os.path.isdir(norm_path)
        method = "DeleteDirectory" if is_dir else "DeleteFile"
        ps_cmd = (
            f"Add-Type -AssemblyName Microsoft.VisualBasic; "
            f"[Microsoft.VisualBasic.FileIO.FileSystem]::{method}('{norm_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
        )
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            return ActionResult(
                success=True,
                message=f"Moved to Recycle Bin: {norm_path}",
                details={"path": norm_path},
            )
        except subprocess.CalledProcessError as e:
            return ActionResult(
                success=False,
                message=f"Failed to recycle {norm_path}: {e.stderr or str(e)}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to recycle {norm_path}: {e}",
            )

    elif action == "open":
        try:
            if hasattr(os, "startfile"):
                os.startfile(norm_path)
            else:
                subprocess.Popen(["cmd.exe", "/c", "start", "", norm_path])
            return ActionResult(
                success=True,
                message=f"Opened {norm_path}",
                details={"path": norm_path},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to open {norm_path}: {e}",
            )

    elif action == "reveal":
        try:
            subprocess.Popen(["explorer.exe", f"/select,{norm_path}"])
            return ActionResult(
                success=True,
                message=f"Revealed {norm_path} in Explorer",
                details={"path": norm_path},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to reveal {norm_path}: {e}",
            )

    elif action == "terminal":
        try:
            cwd = norm_path if os.path.isdir(norm_path) else os.path.dirname(norm_path) or norm_path
            subprocess.Popen(["powershell.exe"], cwd=cwd)
            return ActionResult(
                success=True,
                message=f"Opened terminal at {cwd}",
                details={"path": cwd},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to open terminal at {norm_path}: {e}",
            )

    elif action == "copy_path":
        try:
            subprocess.run(["clip"], input=norm_path, text=True, timeout=5, check=False)
        except Exception:
            pass
        return ActionResult(
            success=True,
            message=f"Copied path to clipboard: {norm_path}",
            details={"path": norm_path},
        )

    elif action == "properties":
        try:
            stat_res = os.stat(norm_path)
            is_dir = os.path.isdir(norm_path)
            details: Dict[str, Any] = {
                "path": norm_path,
                "size_bytes": stat_res.st_size,
                "is_dir": is_dir,
                "created_time": stat_res.st_ctime,
                "modified_time": stat_res.st_mtime,
            }
            return ActionResult(
                success=True,
                message=f"Retrieved properties for {norm_path}",
                details=details,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to retrieve properties for {norm_path}: {e}",
            )

    return ActionResult(
        success=False,
        message=f"Unsupported file action: {action}",
    )
