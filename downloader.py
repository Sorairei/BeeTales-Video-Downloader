"""Local, testable core engine for BeeTales Video Downloader."""

from __future__ import annotations

import concurrent.futures
import json
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import parse_qs, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SUPPORTED_HEIGHTS = (360, 480, 720, 1080, 1440, 2160)
SUPPORTED_BITRATES = (128, 192, 256, 320)
MAX_URL_LENGTH = 2048
MAX_DURATION_SECONDS = 2 * 60 * 60
MAX_FILESIZE_BYTES = 2 * 1024 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
# Maximum time allowed for an FFmpeg transcoding operation.
# Prevents indefinite blocking on very long content or a stalled FFmpeg process.
FFMPEG_TRANSCODE_TIMEOUT = 4 * 60 * 60  # 4 hours maximum

# Characters forbidden in URLs: C0 controls, zero-width codepoints, BOM.
_URL_FORBIDDEN_CHARS: frozenset[str] = frozenset(
    chr(c) for c in range(32)
) | frozenset(
    chr(c) for c in range(0x200B, 0x200F + 1)
) | {chr(0xFEFF)}


class DownloaderError(RuntimeError):
    """Safe error that can be shown directly in the user interface."""


class ValidationError(DownloaderError):
    """The user request does not meet the program's constraints."""


class DependencyError(DownloaderError):
    """A required local tool is missing."""


class DownloadCancelled(DownloaderError):
    """The user cancelled an active download."""


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
class FileMediaInfo:
    video_codec: str
    pixel_format: str
    audio_codec: str
    width: int | None
    height: int | None
    duration: float | None


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
    """Root directory of the source code or the PyInstaller-extracted bundle."""

    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _host_matches(hostname: str, allowed: str) -> bool:
    return hostname == allowed or hostname.endswith(f".{allowed}")


def _is_individual_media_url(platform: Platform, hostname: str, path: str, query: str) -> bool:
    segments = [segment for segment in path.split("/") if segment]
    if platform.id == "youtube":
        if _host_matches(hostname, "youtu.be"):
            return bool(segments)
        if len(segments) >= 2 and segments[0].lower() in {"shorts", "embed", "live"}:
            return True
        return path.rstrip("/").lower() == "/watch" and bool(parse_qs(query).get("v"))
    if platform.id == "tiktok":
        if hostname.startswith(("vm.", "vt.")):
            return bool(segments)
        return bool(
            re.fullmatch(r"/@[^/]+/video/\d+", path.rstrip("/"), flags=re.IGNORECASE)
            or (len(segments) >= 2 and segments[0].lower() == "t")
        )
    if platform.id == "instagram":
        return len(segments) >= 2 and segments[0].lower() in {"p", "reel", "reels", "tv"}
    if platform.id == "x":
        return bool(
            re.fullmatch(
                r"/(?:[^/]+/status|i/web/status)/\d+(?:/video/\d+)?",
                path.rstrip("/"),
                re.IGNORECASE,
            )
            or re.fullmatch(r"/i/broadcasts/[A-Za-z0-9]+", path.rstrip("/"))
        )
    return False


def validate_url(value: str) -> ValidatedUrl:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Pega primero un enlace público.")
    if len(value) > MAX_URL_LENGTH:
        raise ValidationError("El enlace es demasiado largo.")
    if any(ch in _URL_FORBIDDEN_CHARS for ch in value):
        raise ValidationError("El enlace contiene caracteres no permitidos.")

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
    if not _is_individual_media_url(platform, hostname, parts.path or "/", parts.query):
        raise ValidationError("El enlace debe apuntar a un video o publicación individual.")

    normalized = urlunsplit(("https", hostname, parts.path or "/", parts.query, ""))
    return ValidatedUrl(normalized, platform)


def _resolve_hostname_with_timeout(hostname: str, timeout: float = 5.0) -> list:
    """DNS lookup with an explicit timeout to prevent indefinite blocking.

    socket.getaddrinfo has no built-in timeout parameter. Wrapping it in a
    ThreadPoolExecutor lets us cancel the wait after *timeout* seconds so that
    a slow or unresponsive DNS server cannot stall the analysis worker thread.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            socket.getaddrinfo, hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise DownloaderError(
                "No fue posible localizar la portada pública (tiempo de espera agotado)."
            ) from exc


def _validate_thumbnail_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port
    except (TypeError, ValueError) as exc:
        raise ValidationError("La portada no utiliza un enlace válido.") from exc
    if (
        parts.scheme.lower() != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or port not in (None, 443)
    ):
        raise ValidationError("La portada debe usar un enlace HTTPS público.")
    try:
        addresses = _resolve_hostname_with_timeout(parts.hostname)
    except DownloaderError:
        raise
    except OSError as exc:
        raise DownloaderError("No fue posible localizar la portada pública.") from exc
    if not addresses:
        raise DownloaderError("La portada pública no tiene una dirección disponible.")
    for address in addresses:
        try:
            if not ipaddress.ip_address(address[4][0]).is_global:
                raise ValidationError("La portada apunta a una red no permitida.")
        except ValueError as exc:
            raise ValidationError("La portada contiene una dirección no válida.") from exc
    return value


class _PublicThumbnailRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_thumbnail_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_thumbnail(value: str | None) -> bytes | None:
    """Download a small public thumbnail without persisting it."""

    if not value:
        return None
    _validate_thumbnail_url(value)
    request = Request(value, headers={"User-Agent": _user_agent()})
    try:
        with build_opener(_PublicThumbnailRedirectHandler()).open(request, timeout=15) as response:
            _validate_thumbnail_url(response.geturl())
            content_type = str(response.headers.get("Content-Type", "")).lower()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_THUMBNAIL_BYTES:
                raise DownloaderError("La portada pública es demasiado grande.")
            if content_type and not content_type.startswith("image/"):
                raise DownloaderError("La portada pública no contiene una imagen.")
            payload = response.read(MAX_THUMBNAIL_BYTES + 1)
    except DownloaderError:
        raise
    except (OSError, ValueError) as exc:
        raise DownloaderError("No fue posible descargar la portada pública.") from exc
    if len(payload) > MAX_THUMBNAIL_BYTES:
        raise DownloaderError("La portada pública es demasiado grande.")
    return payload or None


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
    platform_id: str | None = None,
    progress_hooks: list[Callable] | None = None,
    postprocessor_hooks: list[Callable] | None = None,
) -> dict:
    """Build yt-dlp options for a download request.

    Args:
        platform_id: Pre-validated platform ID to avoid a second DNS
            resolution. If None, the URL is validated again internally.
    """
    if request.output_type not in ("video", "audio"):
        raise ValidationError("Selecciona Video MP4 o Audio MP3.")
    quality = (
        request.quality
        if isinstance(request.quality, int) and 144 <= request.quality <= 4320
        else 1080
    )
    bitrate = request.audio_bitrate if request.audio_bitrate in SUPPORTED_BITRATES else 192

    output_template = "%(title).150B [%(id)s].%(ext)s"
    if request.output_type == "audio":
        # Audio extraction deletes its downloaded source after conversion. A stable
        # suffix prevents that temporary source from ever matching an existing MP4.
        output_template = "%(title).142B [%(id)s] [audio].%(ext)s"

    options = {
        **_common_options(paths),
        "paths": {"home": str(request.destination)},
        "outtmpl": {"default": output_template},
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
        resolved_platform_id = platform_id or validate_url(request.url).platform.id
        instagram_combined = (
            f"best[height<=?{quality}][ext=mp4]/"
            if resolved_platform_id == "instagram" and quality <= 1280
            else ""
        )
        # yt-dlp format selection priority chain:
        # 1. Native H.264+AAC in MP4 — maximum compatibility, no transcoding needed.
        # 2. Best H.264 in MP4 with any compatible audio.
        # 3. Instagram: low-resolution combined MP4 (avoids VP9 inside MP4).
        # 4. Best MP4 video + best M4A audio — requires FFmpeg merge.
        # 5. Any available MP4 as a last-resort fallback.
        # 6. Best video + audio of any format — may require transcoding.
        format_priority = (
            f"bestvideo[height<=?{quality}][vcodec^=avc1][ext=mp4]"
            f"+bestaudio[acodec^=mp4a][ext=m4a]"
            f"/best[height<=?{quality}][vcodec^=avc1][acodec^=mp4a][ext=mp4]"
            f"/{instagram_combined}"
            f"bestvideo*[height<=?{quality}][ext=mp4]+bestaudio[ext=m4a]"
            f"/best[height<=?{quality}][ext=mp4]"
            f"/bestvideo*[height<=?{quality}]+bestaudio/best[height<=?{quality}]"
        )
        options.update(
            {
                "format": format_priority,
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            }
        )
    return options


def _user_agent() -> str:
    """Dynamic User-Agent string that reflects the current bundle version."""
    try:
        from release_metadata import APP_VERSION
        return f"BeeTales-Video-Downloader/{APP_VERSION}"
    except Exception:
        return "BeeTales-Video-Downloader/0"

def probe_media_file(path: Path, paths: ToolPaths) -> FileMediaInfo:
    if not paths.ffprobe:
        raise DependencyError("FFprobe no está disponible para validar el archivo final.")
    try:
        result = subprocess.run(
            [
                str(paths.ffprobe),
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,pix_fmt,width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        raise DownloaderError("No fue posible validar el archivo multimedia final.") from exc
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        raise DownloaderError("El archivo final no contiene pistas multimedia válidas.")
    video = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"),
        {},
    )
    audio = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"),
        {},
    )
    if not video:
        raise DownloaderError("El archivo final no contiene una pista de video válida.")
    duration_value = (payload.get("format") or {}).get("duration")
    try:
        duration = float(duration_value) if duration_value is not None else None
    except (TypeError, ValueError):
        duration = None
    return FileMediaInfo(
        video_codec=str(video.get("codec_name") or "").lower(),
        pixel_format=str(video.get("pix_fmt") or "").lower(),
        audio_codec=str(audio.get("codec_name") or "").lower(),
        width=int(video["width"]) if isinstance(video.get("width"), (int, float)) else None,
        height=int(video["height"]) if isinstance(video.get("height"), (int, float)) else None,
        duration=duration,
    )


def ensure_compatible_mp4(
    path: Path,
    paths: ToolPaths,
    callback: ProgressCallback | None = None,
) -> bool:
    """Transcode only when the final MP4 is not broadly compatible."""

    require_media_tools(paths)
    details = probe_media_file(path, paths)
    compatible_video = details.video_codec == "h264" and details.pixel_format in {
        "yuv420p",
        "yuvj420p",
    }
    compatible_audio = details.audio_codec in {"", "aac"}
    if compatible_video and compatible_audio:
        return False

    if callback:
        callback(
            ProgressEvent(
                "processing",
                99.0,
                message="Convirtiendo a H.264/AAC para máxima compatibilidad…",
            )
        )
    temporary = path.with_name(f".{path.stem}.beetales-compatible.mp4")
    temporary.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [
                str(paths.ffmpeg),
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-map_metadata",
                "0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(temporary),
            ],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TRANSCODE_TIMEOUT,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode:
            raise DownloaderError("FFmpeg no pudo crear un MP4 compatible con este contenido.")
        converted = probe_media_file(temporary, paths)
        if converted.video_codec != "h264" or converted.pixel_format != "yuv420p":
            raise DownloaderError("La validacion del MP4 compatible no fue satisfactoria.")
        if converted.audio_codec not in {"", "aac"}:
            raise DownloaderError("La pista de audio final no es compatible con MP4.")
        # Move the file BEFORE the except block can delete the temporary.
        # If os.replace fails, the except branch cleans up; the original file remains intact.
        os.replace(temporary, path)
        return True
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


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


def safe_error_message(error: Exception, action: str = "descarga") -> str:
    detail = str(error).lower()
    if "drm" in detail:
        return "El contenido está protegido con DRM y no puede procesarse."
    if "ffmpeg" in detail or "ffprobe" in detail:
        return "FFmpeg no pudo procesar este formato multimedia."
    if any(
        term in detail
        for term in (
            "private",
            "login required",
            "sign in",
            "authentication",
            "http error 401",
            "members-only",
            "age-restricted",
            "registered users",
        )
    ):
        return "El contenido es privado o requiere iniciar sesión; BeeTales no usa cuentas ni cookies."
    if any(term in detail for term in ("no video", "does not contain a video", "without video")):
        return "La publicación no contiene un video público descargable."
    if any(
        term in detail
        for term in ("unavailable", "deleted", "not found", "removed", "copyright")
    ):
        return "El contenido no está disponible, fue eliminado o el enlace dejó de ser válido."
    if any(term in detail for term in ("geo-restricted", "georestricted", "country", "region")):
        return "El contenido no está disponible en tu región."
    if any(term in detail for term in ("http error 429", "too many requests", "rate limit")):
        return "La plataforma limitó temporalmente las solicitudes. Espera unos minutos e inténtalo de nuevo."
    if any(term in detail for term in ("http error 403", "forbidden")):
        return "La plataforma rechazó el acceso público a este contenido."
    if any(term in detail for term in ("unsupported url", "no suitable extractor")):
        return "La plataforma no reconoce este tipo de enlace como contenido descargable."
    if any(term in detail for term in ("timed out", "timeout", "network", "connection", "dns")):
        return "No fue posible conectar con la plataforma. Revisa tu conexión e inténtalo nuevamente."
    if action == "análisis":
        return "No fue posible analizar el enlace. La plataforma puede haber cambiado o limitado el acceso."
    return "La descarga no pudo completarse. La plataforma puede haber cambiado o limitado el acceso."


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
                and 144 <= int(item["height"]) <= 4320
            }
        )
    )
    if not qualities:
        top_level_height = info.get("height")
        qualities = (
            (int(top_level_height),)
            if isinstance(top_level_height, (int, float))
            and 144 <= int(top_level_height) <= 4320
            else (720,)
        )
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
        raise DownloaderError(safe_error_message(exc, "análisis")) from exc
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
            if request.output_type == "video":
                from yt_dlp.postprocessor.common import PostProcessor

                class EnsureCompatibleMP4PostProcessor(PostProcessor):
                    def run(self, info: dict):
                        filepath = Path(str(info.get("filepath", "")))
                        if not filepath.is_file():
                            raise DownloaderError("No se encontró el archivo final para validarlo.")
                        ensure_compatible_mp4(filepath, tools, notify)
                        return [], info

                client.add_post_processor(
                    EnsureCompatibleMP4PostProcessor(client), when="after_move"
                )
            result = client.download([validated.url])
        if result:
            raise DownloaderError("yt-dlp no pudo completar la descarga.")
        notify(ProgressEvent("finished", 100.0, message="Archivo listo."))
    except DownloadCancelled:
        raise
    except DownloaderError:
        raise
    except Exception as exc:
        if cancellation.is_set():
            raise DownloadCancelled("Descarga cancelada.") from exc
        raise DownloaderError(safe_error_message(exc, "descarga")) from exc
