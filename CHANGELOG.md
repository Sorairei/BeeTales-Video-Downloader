# Changelog

All notable changes to BeeTales Video Downloader are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Additional platform compatibility maintenance as public sites evolve.

### Added

- Documented keyboard shortcuts for URL focus, analysis, queueing, destination selection, and help.
- Automated WCAG AA contrast validation for normal-size text in light and dark themes.
- In-memory public thumbnail previews for YouTube, TikTok, Instagram, and X.
- A queue cleanup action that removes completed, cancelled, and failed items without affecting active jobs.
- Final MP4 probing and automatic local H.264/AAC compatibility conversion when required.
- Complete English, Spanish, Polish, and Portuguese interfaces with English as the default and fallback.
- A source-link clear action and `Esc` shortcut that reset analysis without changing queued jobs.
- A private local workflow card highlighting the public link, local processing, and local destination steps.

### Changed

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

[Unreleased]: https://github.com/Sorairei/BeeTales-Video-Downloader/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Sorairei/BeeTales-Video-Downloader/releases/tag/v0.3.0
