from __future__ import annotations

import tempfile
import unittest
import json
import socket
from pathlib import Path
from unittest.mock import patch

from accessibility import KEYBOARD_SHORTCUTS, keyboard_help_text
from localization import (
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    TRANSLATIONS,
    appearance_labels,
    localize_engine_error,
    tr,
)
from downloader import (
    MAX_DURATION_SECONDS,
    DownloadRequest,
    ToolPaths,
    ValidationError,
    _normalize_info,
    build_analysis_options,
    build_download_options,
    safe_error_message,
    _validate_thumbnail_url,
    validate_url,
)
from settings import Settings, load_settings, save_settings
from theme import audited_contrast_pairs, contrast_ratio
from queue_manager import DuplicateJobError, QueueManager, request_identity
from release_metadata import (
    APP_VERSION,
    archive_name,
    create_reproducible_archive,
    render_windows_version_info,
    sha256_file,
    version_tuple,
    write_release_metadata,
)


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

    @patch("downloader.socket.getaddrinfo")
    def test_thumbnail_requires_public_https_address(self, getaddrinfo) -> None:
        getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        self.assertEqual(
            _validate_thumbnail_url("https://images.example.com/cover.jpg"),
            "https://images.example.com/cover.jpg",
        )
        getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with self.assertRaises(ValidationError):
            _validate_thumbnail_url("https://localhost/cover.jpg")


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

    def test_instagram_1280_prefers_combined_mp4_before_vp9_fallback(self) -> None:
        request = DownloadRequest(
            "https://www.instagram.com/reel/example/",
            "video",
            Path("C:/Downloads"),
            quality=1280,
        )
        format_selector = build_download_options(request, self.tools)["format"]
        combined = "best[height<=?1280][ext=mp4]"
        generic_split = "bestvideo*[height<=?1280][ext=mp4]+bestaudio[ext=m4a]"
        self.assertLess(format_selector.index(combined), format_selector.index(generic_split))

    def test_instagram_1920_preserves_high_resolution_fallback(self) -> None:
        request = DownloadRequest(
            "https://www.instagram.com/reel/example/",
            "video",
            Path("C:/Downloads"),
            quality=1920,
        )
        format_selector = build_download_options(request, self.tools)["format"]
        generic_split = "bestvideo*[height<=?1920][ext=mp4]+bestaudio[ext=m4a]"
        combined_fallback = "best[height<=?1920][ext=mp4]"
        self.assertLess(
            format_selector.index(generic_split), format_selector.index(combined_fallback)
        )

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
            expected = Settings("C:/Media", "dark", "pl")
            save_settings(expected, path)
            self.assertEqual(load_settings(path), expected)
            contents = path.read_text(encoding="utf-8")
            self.assertNotIn("url", contents.lower())
            self.assertNotIn("history", contents.lower())

    def test_legacy_spanish_appearance_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "settings.json"
            path.write_text(
                '{"destination": "C:/Media", "appearance": "Oscuro"}',
                encoding="utf-8",
            )
            settings = load_settings(path)
            self.assertEqual(settings.appearance, "dark")
            self.assertEqual(settings.language, "en")


class LocalizationTests(unittest.TestCase):
    def test_english_is_default_and_all_languages_are_complete(self) -> None:
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertEqual(tuple(LANGUAGE_NAMES), ("en", "es", "pl", "pt"))
        expected_keys = set(TRANSLATIONS["en"])
        for language, translations in TRANSLATIONS.items():
            with self.subTest(language=language):
                self.assertEqual(set(translations), expected_keys)

    def test_translations_and_appearance_labels_use_stable_codes(self) -> None:
        self.assertEqual(tr("heading"), "Download authorized media")
        self.assertEqual(tr("heading", "es"), "Descarga contenido autorizado")
        self.assertEqual(tr("heading", "pl"), "Pobierz autoryzowane multimedia")
        self.assertEqual(tr("heading", "pt"), "Baixe mídia autorizada")
        self.assertEqual(set(appearance_labels("pt")), {"system", "light", "dark"})

    def test_engine_errors_are_localized_without_raw_details(self) -> None:
        for language in LANGUAGE_NAMES:
            localized = localize_engine_error("This video is private; sign in", language)
            self.assertEqual(localized, tr("error_private", language))
            self.assertNotIn("sign in", localized.lower())


class QueueManagerTests(unittest.TestCase):
    def _request(self, destination: Path, quality: int = 720) -> DownloadRequest:
        return DownloadRequest("https://youtu.be/example", "video", destination, quality=quality)

    def test_duplicate_active_request_is_rejected(self) -> None:
        manager = QueueManager()
        request = self._request(Path("C:/Media"))
        manager.create("Example", request)
        with self.assertRaises(DuplicateJobError):
            manager.create("Example", request)
        self.assertEqual(manager.active_count, 1)

    def test_completed_request_can_be_added_again(self) -> None:
        manager = QueueManager()
        request = self._request(Path("C:/Media"))
        first = manager.create("Example", request)
        self.assertTrue(manager.start(first.job_id))
        manager.finish(first.job_id, "completed")
        second = manager.create("Example", request)
        self.assertNotEqual(first.job_id, second.job_id)

    def test_cancelled_queued_job_never_starts(self) -> None:
        manager = QueueManager()
        job = manager.create("Example", self._request(Path("C:/Media")))
        self.assertTrue(manager.cancel(job.job_id))
        self.assertFalse(manager.start(job.job_id))
        self.assertEqual(job.state, "cancelled")
        self.assertEqual(manager.active_count, 0)

    def test_cancel_all_signals_every_active_job(self) -> None:
        manager = QueueManager()
        first = manager.create("First", self._request(Path("C:/Media"), 720))
        second = manager.create("Second", self._request(Path("C:/Media"), 1080))
        self.assertTrue(manager.start(first.job_id))
        self.assertEqual(manager.cancel_all(), 2)
        self.assertTrue(first.cancel_event.is_set())
        self.assertTrue(second.cancel_event.is_set())
        self.assertEqual(manager.active_count, 2)

    def test_identity_normalizes_equivalent_destinations(self) -> None:
        first = self._request(Path("C:/Media/../Media"))
        second = self._request(Path("C:/Media"))
        self.assertEqual(request_identity(first), request_identity(second))

    def test_remove_finished_preserves_active_jobs(self) -> None:
        manager = QueueManager()
        completed = manager.create("Completed", self._request(Path("C:/Media"), 720))
        active = manager.create("Active", self._request(Path("C:/Media"), 1080))
        self.assertTrue(manager.start(completed.job_id))
        manager.finish(completed.job_id, "completed")
        self.assertTrue(manager.start(active.job_id))
        self.assertEqual(manager.remove_finished(), (completed.job_id,))
        self.assertIsNone(manager.get(completed.job_id))
        self.assertIs(manager.get(active.job_id), active)
        self.assertEqual(manager.total_count, 1)


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_is_consistent_across_release_metadata(self) -> None:
        self.assertEqual(version_tuple(), (0, 3, 0, 0))
        self.assertIn(f'ProductVersion", "{APP_VERSION}"', render_windows_version_info())
        self.assertEqual(
            archive_name(), f"BeeTales-Video-Downloader-v{APP_VERSION}-Windows-x64.zip"
        )

    def test_release_archive_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "package"
            source.mkdir()
            (source / "b.txt").write_text("second\n", encoding="utf-8")
            (source / "a.txt").write_text("first\n", encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            create_reproducible_archive(source, first)
            create_reproducible_archive(source, second)
            self.assertEqual(sha256_file(first), sha256_file(second))

    def test_manifest_and_checksum_describe_archive(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "package"
            source.mkdir()
            (source / "LICENSE").write_text("MIT\n", encoding="utf-8")
            archive = root / archive_name()
            manifest_path = root / "release-manifest.json"
            checksums_path = root / "SHA256SUMS.txt"
            create_reproducible_archive(source, archive)
            expected = write_release_metadata(archive, manifest_path, checksums_path)
            actual = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(actual, expected)
            self.assertEqual(actual["sha256"], sha256_file(archive))
            self.assertIn(archive.name, checksums_path.read_text(encoding="ascii"))


class AccessibilityTests(unittest.TestCase):
    def test_all_text_color_pairs_meet_wcag_aa(self) -> None:
        for name, ratio in audited_contrast_pairs().items():
            with self.subTest(pair=name):
                self.assertGreaterEqual(ratio, 4.5)

    def test_contrast_rejects_invalid_color_notation(self) -> None:
        with self.assertRaises(ValueError):
            contrast_ratio("green", "#000000")

    def test_keyboard_shortcuts_are_unique_and_documented(self) -> None:
        keys = [shortcut.keys for shortcut in KEYBOARD_SHORTCUTS]
        actions = [shortcut.action for shortcut in KEYBOARD_SHORTCUTS]
        help_text = keyboard_help_text()
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(actions), len(set(actions)))
        for shortcut in KEYBOARD_SHORTCUTS:
            self.assertIn(shortcut.keys, help_text)
        self.assertIn("Esc", keys)


if __name__ == "__main__":
    unittest.main()
