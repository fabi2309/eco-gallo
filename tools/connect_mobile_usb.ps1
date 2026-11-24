param([string]$Serial)
$ErrorActionPreference = 'Stop'
try {
    $sdkPath = $env:ANDROID_HOME
    if (-not $sdkPath) { $sdkPath = $env:ANDROID_SDK_ROOT }
    if (-not $sdkPath) { $sdkPath = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    $adbPath = Join-Path $sdkPath 'platform-tools\adb.exe'
    if (-not (Test-Path -LiteralPath $adbPath)) { throw 'No se encontró ADB. Revisa la instalación de Android SDK.' }
    if ($Serial -and $Serial -notmatch '^[A-Za-z0-9_.:-]+$') { throw 'Identificador de dispositivo inválido.' }
    $health = Invoke-RestMethod 'http://127.0.0.1:8080/api/health' -TimeoutSec 5
    if ($health.ok -ne $true) { throw 'El servidor no responde correctamente.' }
    $devices = @(& $adbPath devices)
    if ($LASTEXITCODE -ne 0) { throw 'ADB no pudo listar dispositivos.' }
    $ready = @($devices | ForEach-Object { if ($_ -match '^(\S+)\s+device$') { $Matches[1] } })
    if (-not $Serial) {
        if ($ready.Count -ne 1) {
            $devices | Write-Host
            throw 'Conecta y autoriza un teléfono. Si hay varios dispositivos, usa conectar_movil_usb.bat SERIAL.'
        }
        $Serial = $ready[0]
    }
    & $adbPath -s $Serial reverse tcp:8080 tcp:8080
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el túnel. Desbloquea el teléfono y autoriza la depuración USB.' }
    Write-Host 'Conexión USB lista. No se instaló ni compiló la aplicación.'
    Write-Host 'Abre ECO-GALLO > Configurar conexión > http://127.0.0.1:8080 > Conectar.'
    Write-Host 'Repite este script al reconectar el cable o reiniciar el teléfono.'
} catch {
    Write-Host "No se pudo conectar: $($_.Exception.Message)"
    Write-Host 'Enciende el servidor con servidor_movil.bat y acepta la depuración USB en el teléfono.'
    exit 1
}
