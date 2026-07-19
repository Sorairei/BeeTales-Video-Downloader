from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from downloader import (
    DownloadRequest,
    ToolPaths,
    ValidationError,
    build_analysis_options,
    build_download_options,
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
        )
        for url in cases:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_url(url)


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
        self.assertEqual(options["merge_output_format"], "mp4")

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
