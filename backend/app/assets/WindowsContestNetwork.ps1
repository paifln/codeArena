#Requires -RunAsAdministrator
<#
CodeArena managed classroom network restriction. Run LOCALLY on a school-owned
Windows student PC, never on the CodeArena server or through a remote session.
Preview: .\WindowsContestNetwork.ps1 -Action Enable -ServerIPv4 192.168.1.10 -Minutes 120 -WhatIf
Apply:   .\WindowsContestNetwork.ps1 -Action Enable -ServerIPv4 192.168.1.10 -Minutes 120
Restore: .\WindowsContestNetwork.ps1 -Action Disable
Status:  .\WindowsContestNetwork.ps1 -Action Status

Blocks outbound IPv4 except the server, loopback and DHCP broadcast; blocks IPv6.
All existing firewall rules are retained. A SYSTEM scheduled task removes only
CodeArena's rules at expiry, including after a missed trigger/restart.
The server uses a literal IPv4 address (DNS is blocked). Existing connections may
need closing. Administrator users, proxies on the permitted server, VPN drivers,
another device or centrally enforced firewall policy can bypass this mechanism.
This is not kiosk software or a guarantee of exam integrity. Pilot on one managed
PC and verify server access, external access denial and automatic restoration.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Enable','Disable','Status')][string]$Action = 'Status',
    [string]$ServerIPv4,
    [ValidateRange(5,360)][int]$Minutes = 120
)
$ErrorActionPreference = 'Stop'
$ruleGroup = 'CodeArena-Contest-Network-v1'
$taskName = 'CodeArena-Network-AutoRestore'
if ($Action -eq 'Status') {
    Get-NetFirewallRule -Group $ruleGroup -ErrorAction SilentlyContinue | Select-Object DisplayName,Enabled,Direction,Action
    Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Get-ScheduledTaskInfo
    return
}
if ($Action -eq 'Disable') {
    if ($PSCmdlet.ShouldProcess('This PC', 'Remove CodeArena network restrictions')) {
        Get-NetFirewallRule -Group $ruleGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    return
}
if (Get-NetFirewallRule -Group $ruleGroup -ErrorAction SilentlyContinue) { throw 'Already enabled. Restore first.' }
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'An automatic restore task already exists.' }
$serverAddress = $null
if (-not [System.Net.IPAddress]::TryParse($ServerIPv4, [ref]$serverAddress) -or $serverAddress.AddressFamily -ne 'InterNetwork') { throw 'Supply a literal server IPv4 address.' }
$octets = $serverAddress.GetAddressBytes()
if (-not ($octets[0] -eq 10 -or ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or ($octets[0] -eq 192 -and $octets[1] -eq 168))) { throw 'Use a private LAN server address.' }
if (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $ServerIPv4) { throw 'Do not restrict the CodeArena server itself.' }
if (Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object { $_.Enabled -ne 'True' -or $_.AllowLocalFirewallRules -eq 'False' }) { throw 'Firewall must be enabled and local rules permitted on every profile.' }
function To-Number([byte[]]$parts) { return [long]$parts[0]*16777216 + [long]$parts[1]*65536 + [long]$parts[2]*256 + $parts[3] }
function To-Address([long]$number) { return '{0}.{1}.{2}.{3}' -f (($number -shr 24) -band 255),(($number -shr 16) -band 255),(($number -shr 8) -band 255),($number -band 255) }
$serverNumber = To-Number $octets
$allowed = @([pscustomobject]@{Start=$serverNumber;End=$serverNumber}, [pscustomobject]@{Start=2130706432L;End=2147483647L}, [pscustomobject]@{Start=4294967295L;End=4294967295L}) | Sort-Object { [long]$_.Start }
$ranges = @()
$cursor = 0L
foreach ($range in $allowed) {
    if ($range.Start -gt $cursor) { $ranges += "$(To-Address $cursor)-$(To-Address ($range.Start-1))" }
    $cursor = $range.End+1
}
Write-Output "Only CodeArena server $ServerIPv4 will remain reachable. Automatic restore in $Minutes minutes."
if (-not $PSCmdlet.ShouldProcess('This PC', 'Schedule automatic restore and apply outbound restrictions')) { return }
$restore = "Get-NetFirewallRule -Group '$ruleGroup' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false -ErrorAction SilentlyContinue"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($restore))
$taskAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand $encoded"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes($Minutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Settings $settings -User SYSTEM -RunLevel Highest | Out-Null
    New-NetFirewallRule -DisplayName 'CodeArena contest IPv4 restriction' -Group $ruleGroup -Direction Outbound -Action Block -RemoteAddress $ranges -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName 'CodeArena contest IPv6 restriction' -Group $ruleGroup -Direction Outbound -Action Block -RemoteAddress '::/0' -Profile Any | Out-Null
    Write-Output "Applied. Open http://${ServerIPv4}:8000 (or your configured port). Use -Action Disable to restore early."
} catch {
    Get-NetFirewallRule -Group $ruleGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    throw
}
