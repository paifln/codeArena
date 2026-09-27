# Managed classroom network restrictions

CodeArena has no remote endpoint agent and cannot switch off connectivity from a browser. The downloadable [Windows script](../backend/app/assets/WindowsContestNetwork.ps1) is for an institution's administrator, running locally on each managed student Windows PC. Do not run it on the CodeArena server, personal devices without their owner's agreement, or over a remote administration session that it would disconnect.

Use a literal private LAN IPv4 server address. Preview in an elevated PowerShell:

```powershell
.\WindowsContestNetwork.ps1 -Action Enable -ServerIPv4 192.168.1.10 -Minutes 120 -WhatIf
```

After reviewing the plan on a pilot PC, omit `-WhatIf` to apply. A SYSTEM scheduled task is registered before restrictions are applied. It removes only CodeArena's rules after 5–360 minutes; `StartWhenAvailable` handles missed triggers after reboot. An apply failure removes newly added rules. Existing firewall rules and profile defaults are retained.

```powershell
.\WindowsContestNetwork.ps1 -Action Status
.\WindowsContestNetwork.ps1 -Action Disable
```

The script blocks outbound IPv4 ranges except the server, loopback and DHCP broadcast; it also blocks outbound IPv6. It checks that firewall profiles are enabled and local firewall rules are permitted. Server access uses an IP because DNS is blocked. Use a stable address/lease for the contest: DHCP unicast renewal to another host is also restricted. Only the server is exempt, on all ports; do not operate a proxy or internet gateway on it. Already established connections may require closing applications before the contest.

Explicit Windows block rules override conflicting allow rules; creating a single block-all rule and an allow-server rule would therefore block the server too. The script instead generates non-overlapping remote-address ranges. See [Microsoft's firewall precedence documentation](https://learn.microsoft.com/windows/security/operating-system-security/network-security/windows-firewall/rules).

Before a real event, verify on the actual managed PC: CodeArena login/Run/Submit remain available, external IPv4/IPv6 destinations fail, the timer restores access, manual restore works, and reboot/missed-trigger recovery works. This repository checks syntax and the generated policy with mocked Windows commands; it does not claim a live institutional firewall acceptance test.

Local administrators can undo the policy. VPN drivers, managed domain policy, other devices and other networks require institutional controls. For a whole classroom, an exam VLAN/SSID with no WAN route and access only to CodeArena is preferable. It does not control personal mobile data. If the institution needs a centrally managed switch in CodeArena, it first needs an authenticated device agent or a supported router/MDM integration; none is installed by this release.
