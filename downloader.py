"""Núcleo local y comprobable de BeeTales Video Downloader."""

from __future__ import annotations

import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlsplit, urlunsplit


SUPPORTED_HEIGHTS = (360, 480, 720, 1080, 1440, 2160)
SUPPORTED_BITRATES = (128, 192, 256, 320)
MAX_URL_LENGTH = 2048
MAX_DURATION_SECONDS = 2 * 60 * 60
MAX_FILESIZE_BYTES = 2 * 1024 * 1024 * 1024


class DownloaderError(RuntimeError):
    """Error seguro que puede mostrarse en la interfaz."""


class ValidationError(DownloaderError):
    """La solicitud del usuario no cumple los límites del programa."""


class DependencyError(DownloaderError):
    """Falta una herramienta local requerida."""


class DownloadCancelled(DownloaderError):
    """El usuario canceló una descarga activa."""


@dataclass(frozen=True)
class Platform:
    id: str
    label: str
    hosts: tuple[str, ...]


PLATFORMS = (
    Platform("youtube", "YouTube", ("youtube.com", "youtu.be", "youtube-nocookie.com")),
    Platform("tiktok", "TikTok", ("tiktok.com",)),
    Platform("instagram", "Instagram", ("instagram.com",)),
    Platform("x", "X", ("x.com", "twitter.com")),
)


@dataclass(frozen=True)
class ValidatedUrl:
    url: str
    platform: Platform


@dataclass(frozen=True)
class MediaInfo:
    source_url: str
    platform: Platform
    media_id: str
    title: str
    creator: str
    duration: int | None
    thumbnail: str | None
    qualities: tuple[int, ...]
    default_quality: int


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    output_type: Literal["video", "audio"]
    destination: Path
    quality: int = 1080
    audio_bitrate: int = 192


@dataclass(frozen=True)
class ProgressEvent:
    status: str
    percent: float
    speed: float | None = None
    eta: int | None = None
    filename: str = ""
    message: str = ""


@dataclass(frozen=True)
class ToolPaths:
    ffmpeg: Path | None
    ffprobe: Path | None
    deno: Path | None

    @property
    def ffmpeg_directory(self) -> Path | None:
        return self.ffmpeg.parent if self.ffmpeg else None


ProgressCallback = Callable[[ProgressEvent], None]


def application_root() -> Path:
    """Raíz del código o de los recursos extraídos por PyInstaller."""

    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _host_matches(hostname: str, allowed: str) -> bool:
    return hostname == allowed or hostname.endswith(f".{allowed}")


def validate_url(value: str) -> ValidatedUrl:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Pega primero un enlace público.")
    if len(value) > MAX_URL_LENGTH:
        raise ValidationError("El enlace es demasiado largo.")

    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as exc:
        raise ValidationError("El enlace no es válido.") from exc

    if parts.scheme.lower() != "https":
        raise ValidationError("Solo se aceptan enlaces HTTPS públicos.")
    if not parts.hostname or parts.username or parts.password or port not in (None, 443):
        raise ValidationError("El enlace incluye credenciales o un puerto no permitido.")

    hostname = parts.hostname.lower().rstrip(".")
    platform = next(
        (
            candidate
            for candidate in PLATFORMS
            if any(_host_matches(hostname, allowed) for allowed in candidate.hosts)
        ),
        None,
    )
    if platform is None:
        raise ValidationError("Usa un enlace de YouTube, TikTok, Instagram o X.")

    normalized = urlunsplit(("https", parts.netloc, parts.path or "/", parts.query, ""))
    return ValidatedUrl(normalized, platform)


def _find_executable(name: str, root: Path) -> Path | None:
    suffix = ".exe" if sys.platform == "win32" else ""
    for directory in ("bin", "vendor"):
        bundled = root / directory / f"{name}{suffix}"
        if bundled.is_file():
            return bundled
    discovered = shutil.which(name)
    return Path(discovered) if discovered else None


def detect_tools(root: Path | None = None) -> ToolPaths:
    base = root or application_root()
    return ToolPaths(
        ffmpeg=_find_executable("ffmpeg", base),
        ffprobe=_find_executable("ffprobe", base),
        deno=_find_executable("deno", base),
    )


def require_media_tools(paths: ToolPaths) -> None:
    missing = []
    if not paths.ffmpeg:
        missing.append("FFmpeg")
    if not paths.ffprobe:
        missing.append("FFprobe")
    if missing:
        raise DependencyError(
            f"Faltan herramientas incluidas en la aplicación: {', '.join(missing)}. "
            "Descarga nuevamente la versión oficial completa."
        )


def _common_options(paths: ToolPaths) -> dict:
    options: dict = {
        "noplaylist": True,
        "cachedir": False,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
        "trim_file_name": 150,
    }
    if paths.ffmpeg_directory:
        options["ffmpeg_location"] = str(paths.ffmpeg_directory)
    if paths.deno:
        options["js_runtimes"] = {"deno": {"path": str(paths.deno)}}
    return options


def build_analysis_options(paths: ToolPaths) -> dict:
    return {
        **_common_options(paths),
        "skip_download": True,
        "extract_flat": False,
        "playlistend": 1,
    }


def build_download_options(
    request: DownloadRequest,
    paths: ToolPaths,
    progress_hooks: list[Callable] | None = None,
    postprocessor_hooks: list[Callable] | None = None,
) -> dict:
    if request.output_type not in ("video", "audio"):
        raise ValidationError("Selecciona Video MP4 o Audio MP3.")
    quality = request.quality if request.quality in SUPPORTED_HEIGHTS else 1080
    bitrate = request.audio_bitrate if request.audio_bitrate in SUPPORTED_BITRATES else 192

    options = {
        **_common_options(paths),
        "paths": {"home": str(request.destination)},
        "outtmpl": {"default": "%(title).150B [%(id)s].%(ext)s"},
        "max_filesize": MAX_FILESIZE_BYTES,
        "continuedl": True,
        "overwrites": False,
        "concurrent_fragment_downloads": 4,
        "progress_hooks": progress_hooks or [],
        "postprocessor_hooks": postprocessor_hooks or [],
    }

    if request.output_type == "audio":
        options.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(bitrate),
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            }
        )
    else:
        options.update(
            {
                "format": (
                    f"bestvideo*[height<=?{quality}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[height<=?{quality}][ext=mp4]/"
                    f"bestvideo*[height<=?{quality}]+bestaudio/best[height<=?{quality}]"
                ),
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
            }
        )
    return options


def _load_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise DependencyError(
            "No se encontró yt-dlp. Instala las dependencias o usa la versión oficial compilada."
        ) from exc
    return yt_dlp


def _safe_text(value: object, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return "".join(character for character in value if character >= " ").strip()[:500]


def _normalize_info(info: dict, validated: ValidatedUrl) -> MediaInfo:
    if info.get("_type") in {"playlist", "multi_video"} and info.get("entries"):
        info = next((entry for entry in info["entries"] if entry), info)

    duration_value = info.get("duration")
    duration = round(duration_value) if isinstance(duration_value, (int, float)) else None
    if duration and duration > MAX_DURATION_SECONDS:
        raise ValidationError("El contenido supera el límite de dos horas.")

    qualities = tuple(
        sorted(
            {
                int(item.get("height"))
                for item in info.get("formats", [])
                if isinstance(item, dict)
                and isinstance(item.get("height"), (int, float))
                and int(item["height"]) in SUPPORTED_HEIGHTS
            }
        )
    )
    if not qualities:
        qualities = (360, 480, 720, 1080)
    preferred = [height for height in qualities if height <= 1080]
    default_quality = preferred[-1] if preferred else qualities[-1]
    thumbnail = info.get("thumbnail")
    if not isinstance(thumbnail, str) or not thumbnail.startswith("https://"):
        thumbnail = None

    return MediaInfo(
        source_url=validated.url,
        platform=validated.platform,
        media_id=_safe_text(info.get("id")),
        title=_safe_text(info.get("title"), "Contenido sin título"),
        creator=_safe_text(info.get("uploader") or info.get("channel") or info.get("creator")),
        duration=duration,
        thumbnail=thumbnail,
        qualities=qualities,
        default_quality=default_quality,
    )


def analyze_media(url: str, paths: ToolPaths | None = None) -> MediaInfo:
    validated = validate_url(url)
    yt_dlp = _load_yt_dlp()
    try:
        with yt_dlp.YoutubeDL(build_analysis_options(paths or detect_tools())) as client:
            info = client.extract_info(validated.url, download=False)
    except DownloaderError:
        raise
    except Exception as exc:
        raise DownloaderError(
            "No fue posible analizar el enlace. La plataforma puede haber cambiado o limitado el acceso."
        ) from exc
    if not isinstance(info, dict):
        raise DownloaderError("La plataforma no devolvió información utilizable.")
    return _normalize_info(info, validated)


def download_media(
    request: DownloadRequest,
    paths: ToolPaths | None = None,
    cancel_event: threading.Event | None = None,
    callback: ProgressCallback | None = None,
) -> None:
    validated = validate_url(request.url)
    tools = paths or detect_tools()
    require_media_tools(tools)
    request.destination.mkdir(parents=True, exist_ok=True)
    if not request.destination.is_dir():
        raise ValidationError("La carpeta de destino no es válida.")
    yt_dlp = _load_yt_dlp()
    cancellation = cancel_event or threading.Event()

    def notify(event: ProgressEvent) -> None:
        if callback:
            callback(event)

    def progress_hook(data: dict) -> None:
        if cancellation.is_set():
            raise DownloadCancelled("Descarga cancelada.")
        status = str(data.get("status", "downloading"))
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        downloaded = data.get("downloaded_bytes") or 0
        percent = (downloaded / total * 100) if total else 0.0
        if status == "finished":
            percent = 99.0
        notify(
            ProgressEvent(
                status=status,
                percent=max(0.0, min(99.0, float(percent))),
                speed=data.get("speed"),
                eta=data.get("eta"),
                filename=Path(str(data.get("filename", ""))).name,
            )
        )

    def postprocessor_hook(data: dict) -> None:
        if cancellation.is_set():
            raise DownloadCancelled("Descarga cancelada.")
        notify(
            ProgressEvent(
                status="processing",
                percent=99.0,
                message="Uniendo video y audio…" if request.output_type == "video" else "Convirtiendo a MP3…",
            )
        )

    options = build_download_options(
        DownloadRequest(
            url=validated.url,
            output_type=request.output_type,
            destination=request.destination,
            quality=request.quality,
            audio_bitrate=request.audio_bitrate,
        ),
        tools,
        [progress_hook],
        [postprocessor_hook],
    )
    try:
        notify(ProgressEvent("starting", 0.0, message="Preparando descarga…"))
        with yt_dlp.YoutubeDL(options) as client:
            result = client.download([validated.url])
        if result:
            raise DownloaderError("yt-dlp no pudo completar la descarga.")
        notify(ProgressEvent("finished", 100.0, message="Archivo listo."))
    except DownloadCancelled:
        raise
    except Exception as exc:
        if cancellation.is_set():
            raise DownloadCancelled("Descarga cancelada.") from exc
        raise DownloaderError(
            "La descarga no pudo completarse. La plataforma puede haber cambiado o limitado el acceso."
        ) from exc
