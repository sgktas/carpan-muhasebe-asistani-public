<#
Yerel geliştirme PostgreSQL kümesinde ilk firma ve yönetici hesabını oluşturur.

Bağlantı parolası Git dışındaki platform.env dosyasından alınır. Yönetici
parolası bu komut çalışırken güvenli parola istemine girilir; kaynağa veya
komut geçmişine yazılmaz.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$CompanyCode,

    [Parameter(Mandatory)]
    [string]$CompanyName,

    [Parameter(Mandatory)]
    [string]$Username,

    [Parameter(Mandatory)]
    [string]$DisplayName
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

# İlk firma yalnız şema sahibinin sınırlı kurulum bağlantısıyla oluşturulabilir.
# Bu değer ekrana basılmaz ve komut tamamlanınca süreçle birlikte kaybolur.
$env:CARPAN_DATABASE_URL = $env:CARPAN_OWNER_DATABASE_URL

Push-Location $apiRoot
try {
    & python scripts/bootstrap_company.py `
        --company-code $CompanyCode `
        --company-name $CompanyName `
        --username $Username `
        --display-name $DisplayName
}
finally {
    Pop-Location
}
