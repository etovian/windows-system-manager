from typing import List

from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope
from sysmgr.remediations.registry import remediation_handler


@remediation_handler(
    action_id="enable-tpm-in-bios",
    description="Guidance for enabling TPM 2.0 in motherboard UEFI/BIOS",
    scope=RemediationScope.MANUAL,
    risk_level=RiskLevel.SAFE,
    requires_admin=False,
    parent_probe_id="readiness.tpm_secure_boot",
)
async def enable_tpm_in_bios(ctx: RemediationContext) -> List[str]:
    """Provide step-by-step guidance to enable TPM in UEFI/BIOS."""
    return [
        "UEFI/BIOS TPM 2.0 Configuration Guidance:",
        "1. Restart computer and enter UEFI/BIOS setup (typically by pressing Del, F2, F10, or F12 during POST).",
        "2. Navigate to the Security, Advanced, or Trusted Computing settings tab.",
        "3. Locate the TPM device switch: 'Intel Platform Trust Technology (PTT)' for Intel CPUs or 'AMD fTPM' for AMD CPUs.",
        "4. Switch the setting from Disabled to Enabled.",
        "5. Verify disk partition style is GPT (use 'mbr2gpt.exe /validate /allowFullOS' before switching boot mode to UEFI).",
        "6. Save changes and reboot into Windows.",
    ]


@remediation_handler(
    action_id="enable-secure-boot",
    description="Guidance for enabling UEFI Secure Boot",
    scope=RemediationScope.MANUAL,
    risk_level=RiskLevel.SAFE,
    requires_admin=False,
    parent_probe_id="readiness.tpm_secure_boot",
)
async def enable_secure_boot(ctx: RemediationContext) -> List[str]:
    """Provide step-by-step guidance to enable UEFI Secure Boot."""
    return [
        "UEFI Secure Boot Configuration Guidance:",
        "1. Verify that Windows is booting via UEFI mode (not Legacy BIOS or CSM).",
        "2. Restart computer and press the BIOS key (Del, F2, F12) to enter UEFI setup.",
        "3. Locate the 'Secure Boot' option under the Boot, Authentication, or Security menu.",
        "4. Set 'Secure Boot' to Enabled. If grayed out, set a supervisor BIOS password or enroll factory default Secure Boot keys.",
        "5. Ensure CSM (Compatibility Support Module) is disabled.",
        "6. Save settings and reboot into Windows.",
    ]
