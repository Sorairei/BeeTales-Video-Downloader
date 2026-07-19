# Contributing

Focused fixes, tests, accessibility improvements, documentation corrections, and platform compatibility reports are welcome through GitHub Issues and pull requests.

## Development requirements

1. Create a branch for each focused change.
2. Run `python -m unittest -v test_downloader.py` locally.
3. Run `python -m py_compile accessibility.py app.py downloader.py localization.py queue_manager.py release_metadata.py settings.py release_smoke.py theme.py` locally.
4. Run `build_release.ps1` before proposing a release-related change.
5. Do not include cookies, tokens, downloaded media, personal URLs, or private filenames in tests or reports.
6. Preserve the separation between interface, localization, queue, media engine, settings, and release metadata.
7. Preserve WCAG AA text contrast and keep keyboard actions documented and tested.
8. Do not add DRM bypasses, authentication evasion, private downloads, Spotify extraction, or artificial watermark removal.
9. Keep the application free of advertising, telemetry, premium functions, and preferential sponsor access.

Platform-specific extractors belong to yt-dlp. Avoid duplicating them in BeeTales unless there is a documented technical reason and focused automated coverage.

## Pull request checklist

- Tests and compilation checks pass locally.
- User-facing documentation is written in English.
- Interface behavior remains understandable without relying on color alone.
- All interface languages contain the complete English reference key set.
- New persisted settings contain no URL, history, credential, or media data.
- Release metadata and third-party notices are updated when dependencies or packaging change.
