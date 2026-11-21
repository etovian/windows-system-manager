# Network Adapter & Connectivity Troubleshooting Runbook

## Overview
Windows networking relies on physical and logical layers operating in concert:
1. **Physical / Link Layer**: Ethernet PHY/MAC link negotiation, Wi-Fi 802.11 association and radio state.
2. **Network Layer (IP Configuration)**: Dynamic Host Configuration Protocol (DHCP) negotiation or static IP assignment, default gateway routing.
3. **Transport & Name Resolution Layer**: DNS resolution (UDP/TCP port 53), LLMNR/mDNS fallbacks.

---

## Common Failure Modes & Diagnostic Trees

### 1. No Active Network Interfaces (Physical or Radio Disconnect)
- **Symptoms**: `_get_interfaces()` returns no active interfaces (`stats.isup` is False or no non-loopback interfaces found). Windows system tray displays disconnected globe icon.
- **Root Causes**:
  - Ethernet cable physically unplugged or bad patch cable.
  - Switch port disabled, shut down, or lack of PoE if required.
  - Wi-Fi radio disabled (Hardware RF kill switch, Airplane Mode, or disabled WLAN adapter).
  - PnP driver fault or device disabled in Device Manager.
- **Diagnostic Steps**:
  1. Verify physical cable connection and link LEDs on the NIC / switch port.
  2. Check Airplane Mode state (`Settings -> Network & internet -> Airplane mode`).
  3. Inspect interface states via PowerShell:
     ```powershell
     Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed
     ```
- **Remediation**:
  - Re-seat physical Ethernet cable or toggle Wi-Fi radio on.
  - Enable adapter: `Enable-NetAdapter -Name "<AdapterName>" -Confirm:$false`.

### 2. APIPA Autoconfiguration (`169.254.0.0/16` - Automatic Private IP Addressing)
- **Symptoms**: Interface `isup` is True, but IPv4 address falls within `169.254.0.0/16` (subnet mask `255.255.0.0`). No default gateway is assigned.
- **Root Causes**:
  - DHCP client timed out attempting to lease an IP address from local DHCP server/router (DORA process failed: Discover sent, no Offer received).
  - Rogue DHCP server filtering, VLAN misconfiguration (untagged/wrong PVID), or exhausted DHCP pool.
  - Firewall blocking UDP ports 67/68 (DHCP).
- **Diagnostic Steps**:
  1. Inspect IP configuration:
     ```powershell
     Get-NetIPAddress -InterfaceAlias "<AdapterName>" -AddressFamily IPv4
     ```
  2. Verify DHCP client service (`Dhcp`) is running:
     ```powershell
     Get-Service -Name "Dhcp"
     ```
- **Remediation**:
  - Release and renew DHCP lease:
    ```powershell
    ipconfig /release
    ipconfig /renew
    ```
  - Restart DHCP Client service:
    ```powershell
    Restart-Service -Name "Dhcp"
    ```
  - Check router/DHCP server connectivity and pool exhaustion.

### 3. Gateway Reachability & DNS Resolution Failure
- **Symptoms**: Interface has a valid routable private or public IP (e.g. `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`), but external DNS resolution fails (`_test_dns()` fails for `dns.google:53`).
- **Root Causes**:
  - Upstream WAN disconnect on the local router/gateway.
  - Misconfigured or unresponsive DNS servers assigned via DHCP or static setup.
  - DNS cache poisoning or stale local resolver cache.
  - Captive portal requiring browser authentication.
  - Corporate firewall or proxy blocking outbound port 53.
- **Diagnostic Steps**:
  1. Ping default gateway to verify L2/L3 reachability:
     ```powershell
     Test-NetConnection -ComputerName (Get-NetRoute -DestinationPrefix '0.0.0.0/0').NextHop
     ```
  2. Query DNS directly with `Resolve-DnsName`:
     ```powershell
     Resolve-DnsName -Name "dns.google" -Server "8.8.8.8"
     ```
- **Remediation**:
  - Flush DNS Resolver Cache:
    ```powershell
    Clear-DnsClientCache
    # or
    ipconfig /flushdns
    ```
  - Test alternative public DNS resolvers (e.g. Cloudflare `1.1.1.1`, Google `8.8.8.8`).
  - Run built-in Windows network diagnostics:
    ```powershell
    msdt.exe /id NetworkDiagnosticsNetworkAdapter
    ```

---

## Non-Destructive Resolution Steps
1. **Flush DNS Cache**: Safe non-destructive operation that clears temporary resolution failures.
   ```powershell
   ipconfig /flushdns
   ```
2. **DHCP Lease Renewal**: Requests an IP lease renewal from the network router.
   ```powershell
   ipconfig /renew
   ```
3. **Restart Network Adapter**: Disables and re-enables the adapter driver to reinitialize PHY and DHCP states.
   ```powershell
   Restart-NetAdapter -Name "<AdapterName>"
   ```

---

## sysmgr Diagnostic Contract
- **Probe ID**: `hardware.network`
- **Output Signals**:
  - `status`:
    - `PASS`: Active interfaces present with routable IPs and successful DNS resolution.
    - `WARN`: Active interface assigned APIPA (`169.254.x.x`) or routable IP with DNS resolution failure.
    - `FAIL`: No active non-loopback network interfaces detected.
  - `details`: Active interfaces (name, speed, IPs), DNS test result.
  - `remediations`:
    - `flush-dns-cache` (Risk: SAFE)
    - `renew-dhcp-lease` (Risk: SAFE)
