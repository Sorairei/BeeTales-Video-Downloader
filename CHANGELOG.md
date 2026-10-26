# Changelog

All notable changes to BeeTales Video Downloader are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Additional platform compatibility maintenance as public sites evolve.

## [0.5.0] - 2026-10-25

### Added

- Adaptive layout for narrower application windows.
- Download progress coalescing and correct progress/post-processing hook registration.
- Offline compatibility checks for supported platform routes, yt-dlp extractors, and synthetic MP4 formats.
- Weekly CI compatibility checks and clearer localized guidance for unavailable formats or outdated media engines.
- Offline compatibility matrix checks for supported platform URL routes against the installed yt-dlp extractors.
- Weekly CI runs to detect extractor and format-selection regressions as yt-dlp evolves.
- Documented keyboard shortcuts for URL focus, analysis, queueing, destination selection, and help.
- Automated WCAG AA contrast validation for normal-size text in light and dark themes.
- In-memory public thumbnail previews for YouTube, TikTok, Instagram, and X.
- A queue cleanup action that removes completed, cancelled, and failed items without affecting active jobs.
- Final MP4 probing and automatic local H.264/AAC compatibility conversion when required.
- Complete English, Spanish, Polish, and Portuguese interfaces with English as the default and fallback.
- A source-link clear action and `Esc` shortcut that reset analysis without changing queued jobs.
- A private local workflow card highlighting the public link, local processing, and local destination steps.

### Changed

- Replaced the timed splash-screen animation and manual event loop with actual local tool detection.
- Enforced the thumbnail DNS lookup timeout without waiting for a blocked resolver thread.
- Classified unsupported-format and outdated-engine failures with localized recovery guidance.
- Expanded and standardized privacy, security, acceptable-use, and contribution documentation in English.
- Improved success and error colors with theme-specific accessible variants.
- Reorganized the desktop workspace into a clearer three-step premium BeeTales experience.
- Preferred Instagram's combined H.264/AAC formats at compatible vertical resolutions to avoid VP9-in-MP4 playback issues.
- Replaced the single scrolling workspace with an enterprise two-zone workflow and persistent queue panel.
- Migrated appearance preferences to stable internal codes and added a persistent language preference.

### Fixed

- Prevented MP3 extraction from reusing and deleting an existing same-title MP4 by isolating audio output filenames.
- Kept the selected output format visible on completed, cancelled, and failed queue items.

### Security

- Restricted thumbnail retrieval to public HTTPS addresses, validated every redirect, limited responses to 5 MB, and kept image data in memory only.

## [0.4.0] - 2026-08-16

### Added
- **Visual Overhaul (Cyber Neon Studio)**: Deep slate obsidian backgrounds (`#08090E`), vibrant electric cyan primary colors (`#00F0FF`), and violet neon highlights (`#BD00FF`) matching modern audio/video suites.
- **Dynamic Background Grid & Audio Waves**: Rendered a high-tech dot grid pattern and smooth fluorescent stereo sine waves flowing dynamically on the workspace background canvas.
- **Visual Format Indicators**: Included graphics and text symbols (`▶`, `♫`, `⚡`) to identify MP4 video, MP3 audio, and step selections.
- **Splash Screen on Startup**: Sleek, borderless window displaying the BeeTales logo, loading progress steps, and animated status text with parallel tool detection.
- **Interactive Error Details**: Added a "Details" action button to failed queue items, opening a dialog showing the exact engine error.
- **Progress Bar States**: ProgressBar color contextually shifts from green (downloading) to orange (FFmpeg processing) and red (failure).
- **Mascot Empty Queue State**: Replaced the plain empty queue label with an illustrated frog mascot image and instructions.

### Changed
- Translated all Spanish code comments and docstrings in Python modules to English.
- Decoupled media formatting helpers into a dedicated `formatters.py` module.
- Hidden the media preview and output format cards on startup until a link is successfully analyzed.
- Subdued the GitHub Sponsors button to a subtle violet outline style.
- Removed hard borders on the download queue panel for a clean card design.
- Increased card corner radius to 18 px for a premium feel.

### Fixed
- **FFmpeg Transcode Hangs**: Set a maximum transcode timeout (4 hours) on subprocess operations.
- **Atomic Operations**: Made MP4 replacement atomic to preserve original files on write failures.
- **Resource Lock Mitigation**: Consolidated download queue total, active, and finished counter queries using a single lock snapshot.
- **Event-Loop Throttling**: Limited GUI event consumption to a maximum of 20 events per tick.
- **Duplicate URL Resolutions**: Avoided double URL parsing and DNS lookups when generating yt-dlp options.

## [0.3.0] - 2026-07-19

### Added

- Local Windows desktop application with the BeeTales visual identity.
- Authorized public-media analysis for YouTube, TikTok, Instagram, and X.
- MP4 downloads with detected source heights and MP3 conversion at four bitrates.
- Sequential in-memory queue with progress, speed, remaining time, and cancellation.
- Active duplicate protection and controlled application shutdown.
- Optional GitHub Sponsors button without advertising or premium functionality.
- Fully local unit, multimedia, compiled smoke, and visual validation workflows.
- Versioned release archives, SHA-256 checksums, and machine-readable release manifests.

### Changed

- Migrated the original web and centralized API prototype to a local desktop architecture.
- Hardened public URL validation to accept only individual supported-media routes.
- Improved MP4 compatibility by preferring H.264 video and AAC audio.
- Preserved real platform-specific and non-standard video heights.
- Reworked the complete README in English using the shared BeeTales documentation style.

### Security

- Rejected credentials, custom ports, non-HTTPS URLs, playlists, profiles, and unsupported hosts.
- Added safe error categories without exposing raw source details.
- Kept URLs and queue history out of persistent preferences.
- Excluded private content, cookies, account sessions, DRM bypasses, and artificial watermark removal.

[Unreleased]: https://github.com/Sorairei/BeeTales-Video-Downloader/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Sorairei/BeeTales-Video-Downloader/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Sorairei/BeeTales-Video-Downloader/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Sorairei/BeeTales-Video-Downloader/releases/tag/v0.3.0
