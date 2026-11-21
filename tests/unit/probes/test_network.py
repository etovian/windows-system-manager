import asyncio
import socket
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes.hardware.network import NetworkAdapterProbe


def test_network_probe_healthy():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(
            probe,
            "_get_interfaces",
            return_value=[{"name": "Ethernet", "is_up": True, "speed_mbps": 1000, "ips": ["192.168.1.100"]}],
        ), patch.object(probe, "_test_dns", return_value=True):
            result = await probe.check()
            assert result.status == DiagnosticStatus.PASS
            assert "online" in result.summary.lower()
            assert result.details["dns_resolution"] is True
            assert len(result.details["interfaces"]) == 1
            assert "knowledge/hardware/network-troubleshooting.md" in result.knowledge_refs
            assert len(result.remediations) == 0

    asyncio.run(_run())


def test_network_probe_apipa_detected():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(
            probe,
            "_get_interfaces",
            return_value=[{"name": "Ethernet", "is_up": True, "speed_mbps": 1000, "ips": ["169.254.50.20"]}],
        ), patch.object(probe, "_test_dns", return_value=False):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "apipa" in result.summary.lower()
            assert any(r.id == "renew-dhcp-lease" for r in result.remediations)
            assert "knowledge/hardware/network-troubleshooting.md" in result.knowledge_refs

    asyncio.run(_run())


def test_network_probe_dns_failure_with_routable_ip():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(
            probe,
            "_get_interfaces",
            return_value=[{"name": "Wi-Fi", "is_up": True, "speed_mbps": 866, "ips": ["192.168.1.50"]}],
        ), patch.object(probe, "_test_dns", return_value=False):
            result = await probe.check()
            assert result.status == DiagnosticStatus.WARN
            assert "dns" in result.summary.lower()
            assert any(r.id == "flush-dns-cache" for r in result.remediations)
            assert any(r.id == "renew-dhcp-lease" for r in result.remediations)

    asyncio.run(_run())


def test_network_probe_all_down():
    async def _run():
        probe = NetworkAdapterProbe()
        with patch.object(probe, "_get_interfaces", return_value=[]), patch.object(
            probe, "_test_dns", return_value=False
        ):
            result = await probe.check()
            assert result.status == DiagnosticStatus.FAIL
            assert "no active network interfaces" in result.summary.lower()
            assert any(r.id == "renew-dhcp-lease" for r in result.remediations)

    asyncio.run(_run())


def test_network_probe_metadata():
    probe = NetworkAdapterProbe()
    assert probe.probe_id == "hardware.network"
    assert probe.category == "hardware"
    assert probe.name == "Network Adapters & Connectivity"
    assert probe.requires_admin is False


def test_get_interfaces_filtering():
    probe = NetworkAdapterProbe()

    SnicStats = namedtuple("SnicStats", ["isup", "duplex", "speed", "mtu", "flags"])
    SnicAddr = namedtuple("SnicAddr", ["family", "address", "netmask", "broadcast", "ptp"])

    mock_stats = {
        "Loopback Pseudo-Interface 1": SnicStats(isup=True, duplex=2, speed=1000, mtu=1500, flags=""),
        "Ethernet (Down)": SnicStats(isup=False, duplex=2, speed=0, mtu=1500, flags=""),
        "Ethernet (No IPv4)": SnicStats(isup=True, duplex=2, speed=1000, mtu=1500, flags=""),
        "Wi-Fi": SnicStats(isup=True, duplex=2, speed=866, mtu=1500, flags=""),
    }

    mock_addrs = {
        "Loopback Pseudo-Interface 1": [
            SnicAddr(family=socket.AF_INET, address="127.0.0.1", netmask="255.0.0.0", broadcast=None, ptp=None)
        ],
        "Ethernet (Down)": [
            SnicAddr(family=socket.AF_INET, address="192.168.1.50", netmask="255.255.255.0", broadcast=None, ptp=None)
        ],
        "Ethernet (No IPv4)": [
            SnicAddr(family=getattr(socket, "AF_INET6", 23), address="fe80::1", netmask=None, broadcast=None, ptp=None)
        ],
        "Wi-Fi": [
            SnicAddr(family=socket.AF_INET, address="192.168.1.100", netmask="255.255.255.0", broadcast=None, ptp=None),
            SnicAddr(family=getattr(socket, "AF_INET6", 23), address="fe80::2", netmask=None, broadcast=None, ptp=None),
        ],
    }

    with patch("psutil.net_if_stats", return_value=mock_stats), patch(
        "psutil.net_if_addrs", return_value=mock_addrs
    ):
        interfaces = probe._get_interfaces()
        assert len(interfaces) == 1
        assert interfaces[0]["name"] == "Wi-Fi"
        assert interfaces[0]["is_up"] is True
        assert interfaces[0]["speed_mbps"] == 866
        assert interfaces[0]["ips"] == ["192.168.1.100"]


def test_get_interfaces_psutil_exception():
    probe = NetworkAdapterProbe()
    with patch("psutil.net_if_stats", side_effect=RuntimeError("psutil error")):
        assert probe._get_interfaces() == []


def test_test_dns_success():
    probe = NetworkAdapterProbe()
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock()
        assert probe._test_dns() is True


def test_test_dns_fallback_getaddrinfo():
    probe = NetworkAdapterProbe()
    with patch("socket.create_connection", side_effect=OSError("connection refused")), patch(
        "socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 53))]
    ):
        assert probe._test_dns() is True


def test_test_dns_failure():
    probe = NetworkAdapterProbe()
    with patch("socket.create_connection", side_effect=OSError("network unreachable")), patch(
        "socket.getaddrinfo", side_effect=socket.gaierror("getaddrinfo failed")
    ):
        assert probe._test_dns() is False
