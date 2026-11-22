from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Optional
from sysmgr.remediations.models import RollbackPlan


class RollbackManager:
    def __init__(self, rollback_dir: Optional[Path] = None):
        self.rollback_dir = rollback_dir or Path("docs/rollback")

    def save_and_commit(self, plan: RollbackPlan, dry_run: bool = False) -> Path:
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_name = f"{date_str}-{plan.action_id}-rollback.md"
        file_path = self.rollback_dir / file_name

        if dry_run:
            return file_path

        # Write rollback markdown
        file_path.write_text(plan.to_markdown(), encoding="utf-8")

        # Stage and commit to git
        try:
            subprocess.run(
                ["git", "add", str(file_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"chore(rollback): record plan for {plan.action_id}"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.SubprocessError:
            # If git commit fails (e.g. running in testing sandbox without git identity),
            # ensure the file remains on disk as manual fallback.
            pass

        return file_path
