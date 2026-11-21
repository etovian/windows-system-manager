import subprocess
import json
from typing import Any, Dict
from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class TpmSecureBootProbe(BaseProbe):
    probe_id = "readiness.tpm_secure_boot"
    name = "TPM 2.0 & Secure Boot Verification"
    category = "readiness"
    description = (
        "Verifies presence and activation of TPM 2.0 security coprocessor and UEFI Secure Boot state."
    )
    requires_admin = False

    def _check_tpm(self) -> Dict[str, Any]:
        """Queries TPM status using Windows CIM MicrosoftTpm namespace."""
        ps_cmd = (
            "try { "
            "  $t = Get-CimInstance -Namespace 'root/cimv2/Security/MicrosoftTpm' -ClassName Win32_Tpm -ErrorAction Stop; "
            "  [PSCustomObject]@{ "
            "    Present = ($null -ne $t); "
            "    SpecVersion = ($t.SpecVersion -split ',')[0].Trim(); "
            "    Enabled = [bool]$t.IsEnabled_InitialValue; "
            "    Manufacturer = [string]$t.ManufacturerIdTxt; "
            "  } | ConvertTo-Json -Compress "
            "} catch { "
            "  [PSCustomObject]@{ Present = $false; SpecVersion = $null; Enabled = $false; Manufacturer = $null } | ConvertTo-Json -Compress "
            "}"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                return {
                    "present": bool(data.get("Present", False)),
                    "spec_version": data.get("SpecVersion"),
                    "enabled": bool(data.get("Enabled", False)),
                    "manufacturer": data.get("Manufacturer"),
                }
        except Exception:
            pass

        return {"present": False, "spec_version": None, "enabled": False, "manufacturer": None}

    def _check_secure_boot(self) -> Dict[str, Any]:
        """Checks Secure Boot state via Confirm-SecureBootUEFI."""
        ps_cmd = (
            "try { "
            "  $sb = Confirm-SecureBootUEFI -ErrorAction Stop; "
            "  [PSCustomObject]@{ Uefi = $true; SecureBoot = [bool]$sb } | ConvertTo-Json -Compress "
            "} catch { "
            "  if ($_.Exception.Message -like '*not supported*') { "
            "    [PSCustomObject]@{ Uefi = $false; SecureBoot = $false } | ConvertTo-Json -Compress "
            "  } else { "
            "    [PSCustomObject]@{ Uefi = $true; SecureBoot = $false } | ConvertTo-Json -Compress "
            "  } "
            "}"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                return {
                    "uefi": bool(data.get("Uefi", True)),
                    "secure_boot_enabled": bool(data.get("SecureBoot", False)),
                }
        except Exception:
            pass

        return {"uefi": True, "secure_boot_enabled": False}

    async def check() -> DiagnosticResult:  # type: ignore[override]
        pass

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/readiness/windows-upgrade-readiness.md"]
        tpm = self._check_tpm()
        sb = self._check_secure_boot()

        details = {
            "tpm": tpm,
            "firmware": sb,
        }

        remediations = []

        if not sb.get("uefi", True):
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.FAIL,
                summary="System booted in Legacy BIOS mode instead of UEFI. Secure Boot and modern OS features cannot be enabled.",
                details=details,
                remediations=[
                    RemediationAction(
                        id="convert-mbr-to-gpt",
                        description="Convert system disk to GPT and switch motherboard firmware to UEFI mode",
                        risk_level=RiskLevel.ELEVATED,
                        requires_admin=True,
                    )
                ],
                knowledge_refs=knowledge_refs,
            )

        has_tpm2 = tpm.get("present") and str(tpm.get("spec_version", "")).startswith("2.0") and tpm.get("enabled")
        has_sb = sb.get("secure_boot_enabled", False)

        if not has_tpm2:
            remediations.append(
                RemediationAction(
                    id="enable-tpm-in-bios",
                    description="Enable firmware TPM (Intel PTT / AMD fTPM) in UEFI/BIOS settings",
                    risk_level=RiskLevel.ELEVATED,
                    requires_admin=False,
                )
            )

        if not has_sb:
            remediations.append(
                RemediationAction(
                    id="enable-secure-boot",
                    description="Enable UEFI Secure Boot in motherboard firmware settings",
                    risk_level=RiskLevel.ELEVATED,
                    requires_admin=False,
                )
            )

        if not has_tpm2:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.FAIL,
                summary="TPM 2.0 security coprocessor is missing, legacy (1.2), or disabled in firmware.",
                details=details,
                remediations=remediations,
                knowledge_refs=knowledge_refs,
            )

        if not has_sb:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="TPM 2.0 is active, but UEFI Secure Boot is disabled.",
                details=details,
                remediations=remediations,
                knowledge_refs=knowledge_refs,
            )

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="TPM 2.0 and Secure Boot are enabled and operational.",
            details=details,
            remediations=[],
            knowledge_refs=knowledge_refs,
        )
