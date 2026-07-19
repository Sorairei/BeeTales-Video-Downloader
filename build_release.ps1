$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:BUILD_PYTHON) { $env:BUILD_PYTHON } else { Join-Path $projectRoot ".venv-build\Scripts\python.exe" }
$vendor = Join-Path $projectRoot "vendor"
$executable = Join-Path $projectRoot "dist\BeeTales Video Downloader.exe"
$archive = Join-Path $projectRoot "dist\BeeTales-Video-Downloader-Windows-x64.zip"
$packageStaging = Join-Path $projectRoot "build\release-package"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No existe .venv-build. Crea el entorno con Python 3.12 e instala requirements.txt."
}

foreach ($tool in @("ffmpeg.exe", "ffprobe.exe", "deno.exe")) {
    if (-not (Test-Path -LiteralPath (Join-Path $vendor $tool))) {
        throw "Falta vendor\$tool. Usa herramientas oficiales antes de compilar."
    }
}

Push-Location $projectRoot
try {
    Write-Host "Verificando Tcl/Tk..."
    & $python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.update(); root.destroy()"
    if ($LASTEXITCODE -ne 0) { throw "Tcl/Tk no funciona." }

    Write-Host "Ejecutando pruebas..."
    & $python -m unittest -v test_downloader.py
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron." }

    Write-Host "Validando recursos y dependencias..."
    & $python app.py --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "La validación del código fuente falló." }

    Write-Host "Compilando BeeTales Video Downloader..."
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "BeeTales Video Downloader" `
        --icon "assets\beetales-app-icon.ico" `
        --version-file "version_info.txt" `
        --collect-all customtkinter `
        --collect-all yt_dlp `
        --collect-all yt_dlp_ejs `
        --collect-all curl_cffi `
        --add-data "assets;assets" `
        --add-binary "vendor\ffmpeg.exe;bin" `
        --add-binary "vendor\ffprobe.exe;bin" `
        --add-binary "vendor\deno.exe;bin" `
        app.py
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $executable)) {
        throw "No se pudo generar el ejecutable."
    }

    Write-Host "Validando el ejecutable compilado..."
    $process = Start-Process -FilePath $executable -ArgumentList "--smoke-test" -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "El ejecutable no superó la validación integral." }

    Write-Host "Creando paquete local..."
    New-Item -ItemType Directory -Path $packageStaging -Force | Out-Null
    Copy-Item -LiteralPath $executable -Destination $packageStaging -Force
    Copy-Item -LiteralPath "LICENSE", "THIRD_PARTY_NOTICES.md", "PRIVACY.md", "USAGE_POLICY.md" -Destination $packageStaging -Force
    Compress-Archive -Path (Join-Path $packageStaging "*") -DestinationPath $archive -Force
    $archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()

    Write-Host "Ejecutable listo: $executable"
    Write-Host "Paquete listo: $archive"
    Write-Host "SHA-256: $archiveHash"
}
finally {
    Pop-Location
}
