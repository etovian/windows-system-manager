from datetime import datetime, timezone
import logging
from pathlib import Path
import subprocess
from typing import Optional
from sysmgr.remediations.models import RollbackPlan

logger = logging.getLogger(__name__)


class RollbackManager:
    def __init__(self, rollback_dir: Optional[Path] = None):
        self.rollback_dir = rollback_dir or Path("docs/rollback")

    def save_and_commit(self, plan: RollbackPlan, dry_run: bool = False) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_name = f"{date_str}-{plan.action_id}-rollback.md"
        file_path = self.rollback_dir / file_name

        if dry_run:
            return file_path

        self.rollback_dir.mkdir(parents=True, exist_ok=True)

        # Write rollback markdown
        file_path.write_text(plan.to_markdown(), encoding="utf-8")

        # Stage and commit to git
        try:
            subprocess.run(
                ["git", "add", str(file_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", f"chore(rollback): record plan for {plan.action_id}", "--", str(file_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError) as e:
            # If git commit fails (e.g. running in testing sandbox without git identity,
            # or git not installed), ensure the file remains on disk as manual fallback.
            logger.warning("Failed to automatically commit rollback plan to git: %s", e)

        return file_path
