import asyncio
import socket
from typing import Any, Dict, List

import psutil

from sysmgr.core.engine import BaseProbe
from sysmgr.core.models import (
    DiagnosticResult,
    DiagnosticStatus,
    RemediationAction,
    RiskLevel,
)


class NetworkAdapterProbe(BaseProbe):
    """Probes network adapters for active link status, IP autoconfiguration (APIPA), and DNS resolution."""

    probe_id = "hardware.network"
    name = "Network Adapters & Connectivity"
    category = "hardware"
    description = (
        "Audits active network adapters, IP configuration, APIPA status, and DNS resolution."
    )
    requires_admin = False

    def _get_interfaces(self) -> List[Dict[str, Any]]:
        """Queries network interfaces using psutil, returning active non-loopback interfaces."""
        interfaces: List[Dict[str, Any]] = []
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
        except Exception:
            return []

        for nic_name, nic_stats in stats.items():
            if "loopback" in nic_name.lower():
                continue
            if not nic_stats.isup:
                continue

            nic_addrs = addrs.get(nic_name, [])
            ipv4_list: List[str] = []
            for addr in nic_addrs:
                if getattr(addr, "family", None) == socket.AF_INET:
                    ip = addr.address
                    if ip and not ip.startswith("127."):
                        ipv4_list.append(ip)

            if ipv4_list:
                interfaces.append({
                    "name": nic_name,
                    "is_up": nic_stats.isup,
                    "speed_mbps": nic_stats.speed,
                    "ips": ipv4_list,
                })

        return interfaces

    def _test_dns(self, host: str = "dns.google", port: int = 53, timeout: float = 3.0) -> bool:
        """Tests DNS resolution using the system resolver, with connection verification fallback."""
        try:
            res = socket.getaddrinfo(host, None)
            if res:
                return True
        except (socket.gaierror, OSError):
            pass

        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    async def check(self) -> DiagnosticResult:
        knowledge_refs = ["knowledge/hardware/network-troubleshooting.md"]
        interfaces = await asyncio.to_thread(self._get_interfaces)

        flush_dns_remediation = RemediationAction(
            id="flush-dns-cache",
            description="Flush the local DNS resolver cache",
            risk_level=RiskLevel.SAFE,
            requires_admin=False,
        )
        renew_dhcp_remediation = RemediationAction(
            id="renew-dhcp-lease",
            description="Release and renew DHCP leases across all network adapters",
            risk_level=RiskLevel.SAFE,
            requires_admin=False,
        )

        if not interfaces:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.FAIL,
                summary="No active network interfaces detected. Physical cable or Wi-Fi is disconnected.",
                details={"interfaces": [], "dns_resolution": False},
                remediations=[renew_dhcp_remediation],
                knowledge_refs=knowledge_refs,
            )

        all_ips = [ip for iface in interfaces for ip in iface.get("ips", [])]
        all_apipa = bool(all_ips) and all(ip.startswith("169.254.") for ip in all_ips)

        if all_apipa:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="Network interface is active but assigned APIPA (169.254.x.x). DHCP server or router is unreachable.",
                details={"interfaces": interfaces, "dns_resolution": False},
                remediations=[renew_dhcp_remediation],
                knowledge_refs=knowledge_refs,
            )

        dns_ok = await asyncio.to_thread(self._test_dns)

        if not dns_ok:
            return DiagnosticResult(
                probe_id=self.probe_id,
                category=self.category,
                status=DiagnosticStatus.WARN,
                summary="Network adapters have valid IP configuration, but DNS resolution failed.",
                details={"interfaces": interfaces, "dns_resolution": False},
                remediations=[flush_dns_remediation, renew_dhcp_remediation],
                knowledge_refs=knowledge_refs,
            )

        return DiagnosticResult(
            probe_id=self.probe_id,
            category=self.category,
            status=DiagnosticStatus.PASS,
            summary="Network adapters are online with valid IP configuration and DNS resolution.",
            details={"interfaces": interfaces, "dns_resolution": True},
            remediations=[],
            knowledge_refs=knowledge_refs,
        )
