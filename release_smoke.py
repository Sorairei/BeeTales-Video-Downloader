"""Validación integral no destructiva para entregas de BeeTales Video Downloader."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from accessibility import KEYBOARD_SHORTCUTS
from downloader import (
    DownloadRequest,
    ToolPaths,
    build_analysis_options,
    build_download_options,
    detect_tools,
    require_media_tools,
    validate_url,
)
from settings import Settings, load_settings, save_settings
from release_metadata import APP_VERSION, archive_name, render_windows_version_info
from theme import audited_contrast_pairs


REQUIRED_ASSETS = (
    "beetales-app-icon.ico",
    "beetales-app-icon-square.png",
    "beetales-app-icon.png",
    "frog-mascot.png",
    "media-atmosphere.png",
    "sora-avatar.png",
    "thebeetales-logo.png",
)


class ReleaseSmokeError(RuntimeError):
    pass


def packaged_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseSmokeError(message)


def _validate_assets(root: Path) -> None:
    assets = root / "assets"
    for filename in REQUIRED_ASSETS:
        target = assets / filename
        _require(target.is_file(), f"Falta assets/{filename}")
        try:
            with Image.open(target) as image:
                image.verify()
        except (OSError, SyntaxError) as exc:
            raise ReleaseSmokeError(f"Imagen inválida: assets/{filename}") from exc


def _validate_dependencies() -> None:
    for module in ("tkinter", "customtkinter", "PIL", "yt_dlp"):
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise ReleaseSmokeError(f"Falta la dependencia {module}") from exc


def _validate_executable(path: Path | None, argument: str, expected: str) -> None:
    _require(path is not None, f"Falta la herramienta local {expected}")
    try:
        result = subprocess.run(
            [str(path), argument],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReleaseSmokeError(f"No se pudo ejecutar {expected}") from exc
    combined = f"{result.stdout}\n{result.stderr}".lower()
    _require(result.returncode == 0, f"{expected} terminó con un error")
    _require(expected.lower() in combined, f"La identidad de {expected} no pudo verificarse")


def _run_tool(arguments: list[str], label: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReleaseSmokeError(f"No se pudo ejecutar la prueba local de {label}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-500:]
        raise ReleaseSmokeError(f"La prueba local de {label} fallo: {detail}")
    return result


def _validate_media_pipeline(tools: ToolPaths) -> None:
    _require(tools.ffmpeg is not None and tools.ffprobe is not None, "Faltan FFmpeg o FFprobe")
    with tempfile.TemporaryDirectory(prefix="beetales_media_smoke_") as name:
        directory = Path(name)
        video = directory / "synthetic.mp4"
        audio = directory / "synthetic.mp3"
        _run_tool(
            [
                str(tools.ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x180:rate=24:duration=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:duration=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(video),
            ],
            "creacion MP4",
        )
        _run_tool(
            [
                str(tools.ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(audio),
            ],
            "conversion MP3",
        )
        probe = _run_tool(
            [
                str(tools.ffprobe),
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name",
                "-of",
                "json",
                str(audio),
            ],
            "verificacion MP3",
        )
        streams = json.loads(probe.stdout).get("streams", [])
        _require(
            any(item.get("codec_type") == "audio" and item.get("codec_name") == "mp3" for item in streams),
            "La conversion sintetica no produjo audio MP3",
        )


def run_release_smoke_test(root: str | Path | None = None) -> dict[str, Any]:
    release_root = Path(root) if root else packaged_root()
    _validate_assets(release_root)
    _validate_dependencies()
    tools = detect_tools(release_root)
    require_media_tools(tools)
    _require(tools.deno is not None, "Falta el runtime local Deno")
    _validate_executable(tools.ffmpeg, "-version", "ffmpeg")
    _validate_executable(tools.ffprobe, "-version", "ffprobe")
    _validate_executable(tools.deno, "--version", "deno")
    _validate_media_pipeline(tools)
    _require(APP_VERSION in render_windows_version_info(), "Los metadatos de versión no coinciden")
    _require(archive_name().startswith("BeeTales-Video-Downloader-v"), "Nombre de entrega inválido")
    _require(len(KEYBOARD_SHORTCUTS) >= 5, "Faltan atajos de accesibilidad")
    _require(
        all(ratio >= 4.5 for ratio in audited_contrast_pairs().values()),
        "El tema contiene texto con contraste inferior a WCAG AA",
    )

    validated = validate_url("https://www.youtube.com/watch?v=beetales-test")
    _require(validated.platform.id == "youtube", "La validación de plataforma falló")
    analysis = build_analysis_options(tools)
    _require(analysis.get("noplaylist") is True, "El análisis permitiría playlists")

    video = build_download_options(
        DownloadRequest(validated.url, "video", Path("C:/BeeTales Smoke"), quality=720),
        tools,
    )
    audio = build_download_options(
        DownloadRequest(validated.url, "audio", Path("C:/BeeTales Smoke"), audio_bitrate=192),
        tools,
    )
    _require("height<=?720" in video["format"], "La calidad de video no se aplicó")
    _require(audio["postprocessors"][0]["preferredcodec"] == "mp3", "La salida MP3 no se configuró")

    with tempfile.TemporaryDirectory(prefix="beetales_downloader_smoke_") as name:
        settings_file = Path(name) / "settings.json"
        expected = Settings(str(Path(name) / "Descargas"), "Oscuro")
        save_settings(expected, settings_file)
        _require(load_settings(settings_file) == expected, "Las preferencias locales no son consistentes")

    return {
        "assets": len(REQUIRED_ASSETS),
        "platform": validated.platform.id,
        "ffmpeg": tools.ffmpeg.name if tools.ffmpeg else "",
        "deno": tools.deno.name if tools.deno else "",
        "version": APP_VERSION,
    }
