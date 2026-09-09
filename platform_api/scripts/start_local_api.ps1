<#
Yerel Çarpan merkezi API'sini yalnız bu bilgisayarda başlatır.

platform.env Git dışındaki local_data dizininden okunur; gizli değerler ekrana
yazılmaz. API 127.0.0.1 dışından erişilemez.
#>
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8010
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$apiRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $apiRoot
$environmentPath = Join-Path $projectRoot "local_data\carpan_platform\platform.env"

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "Yerel platform ayarı bulunamadı. Önce initialize_local_platform.py çalıştırılmalı."
}

Get-Content -LiteralPath $environmentPath | ForEach-Object {
    if ($_ -match '^([^#=][^=]*)=(.*)$') {
        Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2]
    }
}

Push-Location $apiRoot
try {
    Write-Host "Yerel Çarpan API hazır: http://127.0.0.1:$Port/health"
    & python -m uvicorn carpan_platform.main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
