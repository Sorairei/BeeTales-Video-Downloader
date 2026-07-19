from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from downloader import (
    MAX_DURATION_SECONDS,
    DownloadRequest,
    ToolPaths,
    ValidationError,
    _normalize_info,
    build_analysis_options,
    build_download_options,
    safe_error_message,
    validate_url,
)
from settings import Settings, load_settings, save_settings


class UrlValidationTests(unittest.TestCase):
    def test_supported_platforms(self) -> None:
        cases = {
            "https://youtu.be/example": "youtube",
            "https://www.youtube.com/shorts/example": "youtube",
            "https://vm.tiktok.com/example": "tiktok",
            "https://www.instagram.com/reel/example/": "instagram",
            "https://x.com/user/status/123": "x",
            "https://x.com/user/status/123/video/1": "x",
            "https://x.com/i/web/status/123": "x",
            "https://x.com/i/broadcasts/1PKqrEDEPNLGb": "x",
            "https://mobile.twitter.com/user/status/123": "x",
        }
        for url, platform in cases.items():
            with self.subTest(url=url):
                self.assertEqual(validate_url(url).platform.id, platform)

    def test_rejects_unsupported_or_unsafe_urls(self) -> None:
        cases = (
            "http://youtube.com/watch?v=x",
            "https://youtube.com.example.org/watch?v=x",
            "https://spotify.com/track/x",
            "https://user:pass@x.com/status/1",
            "https://127.0.0.1/video",
            "https://youtube.com/",
            "https://youtube.com/playlist?list=example",
            "https://instagram.com/example-profile/",
            "https://x.com/example-user",
            "https://tiktok.com/@example-user",
            "https://youtu.be/video\nmalformed",
        )
        for url in cases:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_url(url)

    def test_normalizes_fragment_and_default_port(self) -> None:
        result = validate_url("https://WWW.YouTube.com:443/watch?v=example#comments")
        self.assertEqual(result.url, "https://www.youtube.com/watch?v=example")


class OptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = ToolPaths(
            Path("C:/BeeTales/bin/ffmpeg.exe"),
            Path("C:/BeeTales/bin/ffprobe.exe"),
            Path("C:/BeeTales/bin/deno.exe"),
        )

    def test_analysis_is_single_item_and_has_no_cache(self) -> None:
        options = build_analysis_options(self.tools)
        self.assertTrue(options["noplaylist"])
        self.assertFalse(options["cachedir"])
        self.assertEqual(options["playlistend"], 1)
        self.assertEqual(options["js_runtimes"]["deno"]["path"], "C:\\BeeTales\\bin\\deno.exe")

    def test_video_prefers_mp4_with_requested_quality(self) -> None:
        request = DownloadRequest("https://youtu.be/x", "video", Path("C:/Downloads"), quality=720)
        options = build_download_options(request, self.tools)
        self.assertIn("height<=?720", options["format"])
        self.assertIn("vcodec^=avc1", options["format"])
        self.assertIn("acodec^=mp4a", options["format"])
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertEqual(options["postprocessors"][1]["key"], "FFmpegMetadata")

    def test_nonstandard_platform_height_is_preserved(self) -> None:
        request = DownloadRequest("https://youtu.be/x", "video", Path("C:/Downloads"), quality=640)
        options = build_download_options(request, self.tools)
        self.assertIn("height<=?640", options["format"])

    def test_audio_uses_mp3_and_selected_bitrate(self) -> None:
        request = DownloadRequest(
            "https://youtu.be/x", "audio", Path("C:/Downloads"), audio_bitrate=320
        )
        options = build_download_options(request, self.tools)
        processor = options["postprocessors"][0]
        self.assertEqual(processor["preferredcodec"], "mp3")
        self.assertEqual(processor["preferredquality"], "320")

    def test_unknown_values_fall_back_safely(self) -> None:
        request = DownloadRequest(
            "https://youtu.be/x", "audio", Path("C:/Downloads"), quality=9999, audio_bitrate=1
        )
        options = build_download_options(request, self.tools)
        self.assertEqual(options["postprocessors"][0]["preferredquality"], "192")


class MediaInfoTests(unittest.TestCase):
    def test_real_nonstandard_qualities_are_reported(self) -> None:
        validated = validate_url("https://www.instagram.com/reel/example/")
        media = _normalize_info(
            {
                "id": "example",
                "title": "Vertical video",
                "formats": [{"height": 360}, {"height": 640}, {"height": 1280}],
            },
            validated,
        )
        self.assertEqual(media.qualities, (360, 640, 1280))
        self.assertEqual(media.default_quality, 640)

    def test_top_level_height_is_used_without_formats(self) -> None:
        validated = validate_url("https://x.com/user/status/123")
        media = _normalize_info({"id": "123", "height": 576}, validated)
        self.assertEqual(media.qualities, (576,))
        self.assertEqual(media.default_quality, 576)

    def test_duration_limit_is_enforced(self) -> None:
        validated = validate_url("https://youtu.be/example")
        with self.assertRaises(ValidationError):
            _normalize_info({"id": "example", "duration": MAX_DURATION_SECONDS + 1}, validated)


class SafeErrorTests(unittest.TestCase):
    def test_error_categories_are_safe_and_actionable(self) -> None:
        cases = {
            "This video is private; sign in": "privado",
            "This content is protected by DRM": "DRM",
            "Video unavailable": "disponible",
            "No video could be found in this tweet": "no contiene",
            "Connection timed out": "conectar",
            "Unsupported URL": "enlace",
            "ffmpeg exited with code 1": "FFmpeg",
            "HTTP Error 429: Too Many Requests": "temporalmente",
            "This video is age-restricted": "sesión",
        }
        for detail, expected in cases.items():
            with self.subTest(detail=detail):
                message = safe_error_message(RuntimeError(detail))
                self.assertIn(expected, message)
                self.assertNotIn(detail, message)


class SettingsTests(unittest.TestCase):
    def test_settings_roundtrip_without_urls_or_history(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "settings.json"
            expected = Settings("C:/Media", "Oscuro")
            save_settings(expected, path)
            self.assertEqual(load_settings(path), expected)
            contents = path.read_text(encoding="utf-8")
            self.assertNotIn("url", contents.lower())
            self.assertNotIn("history", contents.lower())


if __name__ == "__main__":
    unittest.main()
