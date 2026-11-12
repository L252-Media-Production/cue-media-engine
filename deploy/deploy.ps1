param([Parameter(Mandatory)][string]$Ref)
$ErrorActionPreference = 'Stop'
$Src = 'D:\Tools\CompanionPlayer-src'
$App = 'D:\Tools\companionplayer'      # the folder that holds run-player.bat and .venv

function Invoke-G {
    git.exe -C $Src @args
    if ($LASTEXITCODE -ne 0) { throw "git $args failed ($LASTEXITCODE)" }
}
function Mirror($from, $to) {
    robocopy $from $to /MIR /XD __pycache__ /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $from failed ($LASTEXITCODE)" }   # 0-7 means success
}

if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'player\.py' }) {
    throw "The player is still running. Stop it first, then run the deploy again."
}

Invoke-G fetch -q --tags --prune origin
Invoke-G checkout -q $Ref
git.exe -C $Src show-ref --verify --quiet "refs/remotes/origin/$Ref"
if ($LASTEXITCODE -eq 0) { Invoke-G reset -q --hard "origin/$Ref" }

Copy-Item "$Src\player.py","$Src\requirements.txt","$Src\run-player.bat" $App -Force
Mirror "$Src\static" "$App\static"
if (Test-Path "$Src\cpl") { Mirror "$Src\cpl" "$App\cpl" }
elseif (Test-Path "$App\cpl") { Remove-Item "$App\cpl" -Recurse -Force }
(git.exe -C $Src describe --tags --always) | Set-Content "$App\VERSION"
"Deployed $(Get-Content "$App\VERSION"). Start the player with run-player.bat when it is safe."