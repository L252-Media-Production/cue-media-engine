# Usage: deploy\deploy.ps1 -Ref <tag|branch> [-App <install folder>]
#   Source clone:   the repository that holds this script (the parent of deploy\); the environment variable CUEME_SRC overrides it.
#   Install folder: the folder that holds run-player.bat and .venv. Chosen in this order: -App, then the environment variable
#                   CUEME_APP, then C:\Apps\CueME. A folder given by -App or CUEME_APP must exist; only the default is created.
#   Make your own folder permanent with:  setx CUEME_APP <folder>
param(
    [Parameter(Mandatory)][string]$Ref,
    [string]$App = ''
)
$DefaultApp = 'C:\Apps\CueME'
$Src = if ($env:CUEME_SRC) { $env:CUEME_SRC } else { Split-Path -Parent $PSScriptRoot }
if ($App) { $Rule = 'set by -App' }
elseif ($env:CUEME_APP) { $App = $env:CUEME_APP; $Rule = 'set by CUEME_APP' }
else { $App = $DefaultApp; $Rule = 'default' }
$Origin = try { git.exe -C $Src remote get-url origin 2>$null } catch { $null }
if (-not $Origin) { $Origin = '(none)' }
Write-Output "Source folder:  $Src"
Write-Output "Source origin:  $Origin"
Write-Output "Install folder: $App ($Rule)"
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $App -PathType Container)) {
    if ($Rule -ne 'default') {
        throw "Stopped: the install folder $App does not exist ($Rule). Check the path or create the folder first. Nothing was changed."
    }
    New-Item -ItemType Directory -Path $App | Out-Null
    Write-Output "First deploy: created $App."
}

function Invoke-G {
    git.exe -C $Src @args
    if ($LASTEXITCODE -ne 0) { throw "git $args failed ($LASTEXITCODE)" }
}
function Mirror($from, $to) {
    robocopy $from $to /MIR /XD __pycache__ /XF elevenlabs.key /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $from failed ($LASTEXITCODE)" }   # 0-7 means success
}

if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'player\.py' }) {
    throw "The player is still running. Stop it first, then run the deploy again."
}

Invoke-G fetch -q --tags --prune origin
Invoke-G checkout -q $Ref
git.exe -C $Src show-ref --verify --quiet "refs/remotes/origin/$Ref"
if ($LASTEXITCODE -eq 0) { Invoke-G reset -q --hard "origin/$Ref" }

# Only these files and the two mirrored folders are written: config.json, state.json, playlists.json, media and the
# ElevenLabs key (elevenlabs.key) in $App are never touched (tests/test_deploy_keeps_data.py)
Copy-Item "$Src\player.py","$Src\requirements.txt","$Src\run-player.bat" $App -Force
Mirror "$Src\static" "$App\static"
if (Test-Path "$Src\cpl") { Mirror "$Src\cpl" "$App\cpl" }
elseif (Test-Path "$App\cpl") { Remove-Item "$App\cpl" -Recurse -Force }
(git.exe -C $Src describe --tags --always) | Set-Content "$App\VERSION"
"Deployed $(Get-Content "$App\VERSION"). Start the player with run-player.bat when it is safe."
if (-not (Test-Path "$App\.venv")) {
    "There is no .venv in $App yet. run-player.bat creates it on its first start, or create it now with:"
    "  py -3 -m venv `"$App\.venv`""
    "  `"$App\.venv\Scripts\python.exe`" -m pip install -r `"$App\requirements.txt`""
}
