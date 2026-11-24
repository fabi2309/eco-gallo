# Run explicitly in an Administrator PowerShell. Never disables the firewall.
$ErrorActionPreference = 'Stop'
$pythonPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'))
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'No existe el Python del proyecto.' }
$ruleName = 'ECO-GALLO-Tesina-8080-Private'
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    Write-Host 'La regla ya existe. No se cambió el firewall.'
    exit 0
}
New-NetFirewallRule -Name $ruleName -DisplayName 'ECO-GALLO tesina - red privada local' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 `
    -Profile Private -RemoteAddress LocalSubnet -Program $pythonPath | Out-Null
Write-Host 'Permitido TCP 8080 solo para Python del proyecto, subred local y perfil Privado.'
