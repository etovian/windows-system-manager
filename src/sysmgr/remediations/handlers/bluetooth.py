import json
import subprocess
from typing import List

from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope, RollbackPlan
from sysmgr.remediations.registry import remediation_handler, remediation_rollback


@remediation_handler(
    action_id="start-bluetooth-service",
    description="Start Windows Bluetooth support service (bthserv)",
    scope=RemediationScope.PERSISTENT,
    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    requires_admin=True,
    parent_probe_id="hardware.bluetooth",
)
async def start_bluetooth_service(ctx: RemediationContext) -> List[str]:
    """Start the Windows Bluetooth support service."""
    if ctx.dry_run:
        return ["[Dry Run] Would start Windows Bluetooth service (bthserv)"]

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Start-Service -Name bthserv -ErrorAction Stop"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return ["Started Windows Bluetooth support service (bthserv)."]


@remediation_rollback("start-bluetooth-service")
async def start_bluetooth_service_rollback() -> RollbackPlan:
    """Generate rollback plan to restore bthserv to stopped state if needed."""
    pre_state = {"service": "bthserv", "status": "Stopped", "start_type": "Demand"}
    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Service -Name bthserv | Select-Object Status, StartType) | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout and res.stdout.strip():
            parsed = json.loads(res.stdout)
            if isinstance(parsed, dict):
                pre_state = parsed
    except Exception:
        pass

    return RollbackPlan(
        action_id="start-bluetooth-service",
        title="Rollback Windows Bluetooth Support Service",
        target_subsystem="services",
        pre_state=pre_state,
        reversal_commands=[
            "powershell -NoProfile -Command \"Stop-Service -Name bthserv -Force\"",
        ],
        safe_mode_instructions=[
            "sc.exe stop bthserv",
            "sc.exe config bthserv start= demand",
        ],
    )
