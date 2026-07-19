# Security Policy

## Reporting a vulnerability

Report vulnerabilities through the repository's private **Security advisories** feature. Do not publish personal, private, authenticated, or protected media URLs in an issue.

Include the affected version, Windows version, reproduction steps, expected result, and observed result. Remove usernames, tokens, URLs, filenames, and downloaded media from logs or screenshots before submitting them.

## Security boundaries

- Only HTTPS URLs for supported individual YouTube, TikTok, Instagram, and X media routes are accepted.
- Credentials, cookies, custom ports, local-network targets, profiles, and playlists are rejected.
- User URLs are passed through the yt-dlp Python API and are never inserted into shell commands.
- BeeTales does not operate a public API, processing backend, proxy, database, or download server.
- Preferences contain no URLs, credentials, tokens, cookies, or download history.
- Private content, authenticated sessions, DRM bypasses, and artificial watermark removal are outside scope.
- Release packages include FFmpeg, FFprobe, and Deno runtimes obtained from their official projects.

## Release verification

Download releases only from `github.com/Sorairei/BeeTales-Video-Downloader`. Compare the archive with its matching `SHA256SUMS-vX.Y.Z.txt` or `release-manifest-vX.Y.Z.json` entry before running it.

The current Windows executable is not digitally signed. Embedded `FileVersion` and `ProductVersion` resources identify the build but are not a certificate and do not prove authenticity by themselves.

Third-party tools and platform extractors have independent security lifecycles. Update dependencies deliberately and rerun the complete local validation before publishing a new version.
