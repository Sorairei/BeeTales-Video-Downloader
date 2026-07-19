$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:BUILD_PYTHON) { $env:BUILD_PYTHON } else { Join-Path $projectRoot ".venv-build\Scripts\python.exe" }
$vendor = Join-Path $projectRoot "vendor"
$executable = Join-Path $projectRoot "dist\BeeTales Video Downloader.exe"
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
    $version = (& $python release_metadata.py version).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $version) { throw "No se pudo determinar la versión." }
    $archiveName = "BeeTales-Video-Downloader-v$version-Windows-x64.zip"
    $archive = Join-Path $projectRoot "dist\$archiveName"
    $manifest = Join-Path $projectRoot "dist\release-manifest-v$version.json"
    $checksums = Join-Path $projectRoot "dist\SHA256SUMS-v$version.txt"

    & $python release_metadata.py write-version-info version_info.txt
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron generar los metadatos de Windows." }

    Write-Host "Verificando Tcl/Tk..."
    & $python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.update(); root.destroy()"
    if ($LASTEXITCODE -ne 0) { throw "Tcl/Tk no funciona." }

    Write-Host "Ejecutando pruebas..."
    & $python -m unittest -v test_downloader.py
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron." }
    & $python -m py_compile accessibility.py app.py downloader.py queue_manager.py release_metadata.py settings.py release_smoke.py theme.py qa_visual.py
    if ($LASTEXITCODE -ne 0) { throw "La compilación sintáctica falló." }

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
    $productVersion = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
    if (-not $productVersion.StartsWith($version)) {
        throw "La versión del ejecutable ($productVersion) no coincide con $version."
    }

    Write-Host "Creando paquete local..."
    $buildRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "build"))
    $resolvedStaging = [IO.Path]::GetFullPath($packageStaging)
    if (-not $resolvedStaging.StartsWith($buildRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "La carpeta temporal de entrega está fuera de build/."
    }
    if (Test-Path -LiteralPath $resolvedStaging) {
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolvedStaging -Force | Out-Null
    Copy-Item -LiteralPath $executable -Destination $packageStaging -Force
    Copy-Item -LiteralPath "README.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "PRIVACY.md", "SECURITY.md", "USAGE_POLICY.md" -Destination $packageStaging -Force
    Set-Content -LiteralPath (Join-Path $packageStaging "VERSION.txt") -Value $version -Encoding ascii
    & $python release_metadata.py package $packageStaging $archive $manifest $checksums
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la entrega reproducible." }
    $archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()

    Write-Host "Versión: $version"
    Write-Host "Ejecutable listo: $executable"
    Write-Host "Paquete listo: $archive"
    Write-Host "Manifiesto: $manifest"
    Write-Host "Checksums: $checksums"
    Write-Host "SHA-256: $archiveHash"
}
finally {
    Pop-Location
}
