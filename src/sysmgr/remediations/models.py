from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sysmgr.core.models import DiagnosticResult, RiskLevel


class RemediationScope(str, Enum):
    TRANSIENT = "TRANSIENT"       # Memory/cache only, no persistent change
    PERSISTENT = "PERSISTENT"     # Services, registry, file mutation (requires git rollback)
    MANUAL = "MANUAL"             # Hardware/BIOS guidance, cannot be fixed via OS CLI


class RemediationContext(BaseModel):
    dry_run: bool = False
    auto_confirm: bool = False
    elevated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RollbackPlan(BaseModel):
    action_id: str
    title: str
    target_subsystem: str
    pre_state: Dict[str, Any] = Field(default_factory=dict)
    reversal_commands: List[str] = Field(default_factory=list)
    safe_mode_instructions: List[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_markdown(self) -> str:
        lines = [
            f"# Rollback Plan: {self.title}",
            "",
            f"- **Action ID:** `{self.action_id}`",
            f"- **Target Subsystem:** `{self.target_subsystem}`",
            f"- **Timestamp:** `{self.created_at}`",
            "",
            "## Pre-Change Baseline State",
            "```json",
            f"{self.pre_state}",
            "```",
            "",
            "## Automated Reversal Commands",
            "```powershell",
        ]
        for cmd in self.reversal_commands:
            lines.append(cmd)
        lines.extend([
            "```",
            "",
            "## Safe Mode Manual Execution Instructions",
            "> [!IMPORTANT]",
            "> If the system fails to boot or behaves abnormally, boot into Safe Mode with Command Prompt and run:",
            "",
        ])
        for inst in self.safe_mode_instructions:
            lines.append(f"- {inst}")
        lines.append("")
        return "\n".join(lines)


class RemediationResult(BaseModel):
    action_id: str
    success: bool
    changes_made: List[str] = Field(default_factory=list)
    rollback_file: Optional[str] = None
    error: Optional[str] = None
    post_check: Optional[DiagnosticResult] = None
