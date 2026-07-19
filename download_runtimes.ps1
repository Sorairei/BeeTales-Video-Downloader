$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$vendor = Join-Path $projectRoot "vendor"
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$downloads = [System.IO.Path]::GetFullPath(
    (Join-Path $tempRoot "beetales-video-downloader-runtimes")
)
if (-not $downloads.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "La carpeta temporal calculada no esta dentro del directorio temporal del sistema."
}

function Get-VerifiedReleaseAsset {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$AssetName,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $headers = @{
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent" = "BeeTales-Video-Downloader-Build"
    }
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repository/releases/latest" -Headers $headers
    $asset = $release.assets | Where-Object name -eq $AssetName | Select-Object -First 1
    if (-not $asset) {
        throw "No se encontro el recurso $AssetName en la ultima version de $Repository."
    }
    if (-not $asset.digest -or -not $asset.digest.StartsWith("sha256:")) {
        throw "GitHub no publico un hash SHA-256 para $Repository/$AssetName."
    }

    Invoke-WebRequest -Uri $asset.browser_download_url -Headers $headers -OutFile $Destination
    $expected = $asset.digest.Substring(7).ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "La verificacion SHA-256 fallo para $Repository/$AssetName."
    }
    Write-Host "Verificado: $AssetName ($actual)"
}

New-Item -ItemType Directory -Path $vendor -Force | Out-Null
New-Item -ItemType Directory -Path $downloads -Force | Out-Null

$ffmpegArchive = Join-Path $downloads "ffmpeg.zip"
$ffmpegExpanded = Join-Path $downloads "ffmpeg"
$denoArchive = Join-Path $downloads "deno.zip"
$denoExpanded = Join-Path $downloads "deno"

Get-VerifiedReleaseAsset `
    -Repository "yt-dlp/FFmpeg-Builds" `
    -AssetName "ffmpeg-master-latest-win64-gpl.zip" `
    -Destination $ffmpegArchive

if (Test-Path -LiteralPath $ffmpegExpanded) {
    Remove-Item -LiteralPath $ffmpegExpanded -Recurse -Force
}
Expand-Archive -LiteralPath $ffmpegArchive -DestinationPath $ffmpegExpanded
$ffmpeg = Get-ChildItem $ffmpegExpanded -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$ffprobe = Get-ChildItem $ffmpegExpanded -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $ffmpeg -or -not $ffprobe) {
    throw "El paquete de FFmpeg esta incompleto."
}
Copy-Item -LiteralPath $ffmpeg.FullName -Destination (Join-Path $vendor "ffmpeg.exe") -Force
Copy-Item -LiteralPath $ffprobe.FullName -Destination (Join-Path $vendor "ffprobe.exe") -Force

Get-VerifiedReleaseAsset `
    -Repository "denoland/deno" `
    -AssetName "deno-x86_64-pc-windows-msvc.zip" `
    -Destination $denoArchive

if (Test-Path -LiteralPath $denoExpanded) {
    Remove-Item -LiteralPath $denoExpanded -Recurse -Force
}
Expand-Archive -LiteralPath $denoArchive -DestinationPath $denoExpanded
$deno = Join-Path $denoExpanded "deno.exe"
if (-not (Test-Path -LiteralPath $deno)) {
    throw "El paquete de Deno esta incompleto."
}
Copy-Item -LiteralPath $deno -Destination (Join-Path $vendor "deno.exe") -Force

& (Join-Path $vendor "ffmpeg.exe") -version | Select-Object -First 1
& (Join-Path $vendor "ffprobe.exe") -version | Select-Object -First 1
& (Join-Path $vendor "deno.exe") --version | Select-Object -First 1
Write-Host "Herramientas locales listas en $vendor"
