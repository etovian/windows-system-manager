import os
import time
from pathlib import Path
from typing import List

from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope, RollbackPlan
from sysmgr.remediations.registry import remediation_handler, remediation_rollback


@remediation_handler(
    action_id="clean-temp-files",
    description="Clean temporary files older than 24 hours from %TEMP%",
    scope=RemediationScope.PERSISTENT,
    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    requires_admin=False,
    parent_probe_id="storage.disk_space",
)
async def clean_temp_files(ctx: RemediationContext) -> List[str]:
    """Inspect %TEMP% directory and remove temporary files older than 24 hours."""
    temp_env = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp_env:
        return ["No TEMP or TMP directory found in environment; skipped cleaning."]

    temp_path = Path(temp_env)
    if not temp_path.exists() or not temp_path.is_dir():
        return [f"Temporary directory '{temp_path}' does not exist; skipped cleaning."]

    cutoff_time = time.time() - 86400  # 24 hours
    cleaned_count = 0
    freed_bytes = 0

    if ctx.dry_run:
        for entry in temp_path.iterdir():
            try:
                if entry.is_file():
                    stat = entry.stat()
                    if stat.st_mtime < cutoff_time:
                        cleaned_count += 1
                        freed_bytes += stat.st_size
            except (PermissionError, OSError):
                continue
        return [
            f"[Dry Run] Would clean {cleaned_count} temporary files ({freed_bytes / (1024 * 1024):.2f} MB) older than 24h from {temp_path}"
        ]

    for entry in temp_path.iterdir():
        try:
            if entry.is_file():
                stat = entry.stat()
                if stat.st_mtime < cutoff_time:
                    entry.unlink(missing_ok=True)
                    cleaned_count += 1
                    freed_bytes += stat.st_size
        except (PermissionError, OSError):
            continue

    return [
        f"Cleaned {cleaned_count} temporary files ({freed_bytes / (1024 * 1024):.2f} MB freed) older than 24 hours from {temp_path}."
    ]


@remediation_rollback("clean-temp-files")
async def clean_temp_files_rollback() -> RollbackPlan:
    """Generate rollback plan documenting purged transient files."""
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or r"C:\Windows\Temp"
    return RollbackPlan(
        action_id="clean-temp-files",
        title="Rollback Clean Temporary Files",
        target_subsystem="storage",
        pre_state={"temp_dir": temp_dir, "purge_policy": "older_than_24h"},
        reversal_commands=[
            "# Transient file purge: Deleted temporary files cannot be restored automatically."
        ],
        safe_mode_instructions=[
            "Boot into Safe Mode if application instability occurs.",
            "Temporary files are regenerated automatically by applications on restart.",
        ],
    )
