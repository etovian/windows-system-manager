import subprocess
from typing import List

from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope
from sysmgr.remediations.registry import remediation_handler


@remediation_handler(
    action_id="flush-dns-cache",
    description="Flush DNS resolver cache",
    scope=RemediationScope.TRANSIENT,
    risk_level=RiskLevel.SAFE,
    requires_admin=False,
    parent_probe_id="hardware.network",
)
async def flush_dns_cache(ctx: RemediationContext) -> List[str]:
    """Flush the Windows DNS resolver cache using ipconfig /flushdns."""
    if ctx.dry_run:
        return ["[Dry Run] Would flush DNS cache with 'ipconfig /flushdns'"]

    subprocess.run(
        ["ipconfig", "/flushdns"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return ["Flushed DNS resolver cache using 'ipconfig /flushdns'."]


@remediation_handler(
    action_id="renew-dhcp-lease",
    description="Renew DHCP lease for network adapters",
    scope=RemediationScope.TRANSIENT,
    risk_level=RiskLevel.CONFIRMATION_REQUIRED,
    requires_admin=True,
    parent_probe_id="hardware.network",
)
async def renew_dhcp_lease(ctx: RemediationContext) -> List[str]:
    """Renew DHCP lease for all active adapters using ipconfig /renew."""
    if ctx.dry_run:
        return ["[Dry Run] Would renew DHCP lease with 'ipconfig /renew'"]

    subprocess.run(
        ["ipconfig", "/renew"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return ["Renewed DHCP lease for network adapters using 'ipconfig /renew'."]
