"""Exercise policy generation using mocks; never change this computer's firewall."""

import ipaddress
import json
import os
from pathlib import Path
import subprocess
import pytest


@pytest.mark.skipif(os.name != "nt", reason="PowerShell policy-generation check")
def test_network_ranges_and_restore_registration(tmp_path):
    source = (
        Path(__file__).resolve().parents[1]
        / "backend/app/assets/WindowsContestNetwork.ps1"
    )
    text = source.read_text(encoding="utf-8").replace(
        "#Requires -RunAsAdministrator", ""
    )
    isolated = tmp_path / "policy.ps1"
    isolated.write_text(text, encoding="utf-8")
    harness = tmp_path / "mock.ps1"
    harness.write_text(
        r"""
$ErrorActionPreference='Stop'
$global:registered=$false
$global:rules=[Collections.Generic.List[object]]::new()
function Get-NetFirewallRule {}
function Get-ScheduledTask {}
function Get-NetIPAddress { [pscustomobject]@{IPAddress='192.168.1.20'} }
function Get-NetFirewallProfile { [pscustomobject]@{Enabled='True';AllowLocalFirewallRules='True'} }
function New-ScheduledTaskAction {}
function New-ScheduledTaskTrigger {}
function New-ScheduledTaskSettingsSet {}
function Register-ScheduledTask { $global:registered=$true }
function Unregister-ScheduledTask { throw 'Unexpected restore in success path' }
function Remove-NetFirewallRule { throw 'Unexpected firewall deletion' }
function New-NetFirewallRule {
 param($DisplayName,$Group,$Direction,$Action,$RemoteAddress,$Profile)
 if(-not $global:registered){throw 'Restore was not scheduled first'}
 $global:rules.Add([pscustomobject]@{Group=$Group;Action=$Action;RemoteAddress=$RemoteAddress})
}
& $args[0] -Action Enable -ServerIPv4 192.168.1.10 -Minutes 30 | Out-Null
$global:rules | ConvertTo-Json -Depth 4 -Compress
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            str(isolated),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rules = json.loads(result.stdout)
    assert len(rules) == 2 and all(r["Action"] == "Block" for r in rules)
    ranges = [
        tuple(int(ipaddress.ip_address(v)) for v in entry.split("-"))
        for entry in rules[0]["RemoteAddress"]
    ]

    def blocked(ip):
        return any(a <= int(ipaddress.ip_address(ip)) <= b for a, b in ranges)

    assert blocked("8.8.8.8") and blocked("192.168.1.99")
    assert (
        not blocked("192.168.1.10")
        and not blocked("127.0.0.1")
        and not blocked("255.255.255.255")
    )
    assert rules[1]["RemoteAddress"] == "::/0"
