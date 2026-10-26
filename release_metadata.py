"""Single source of version and deterministic local release metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


APP_VERSION = "0.5.0"
PRODUCT_NAME = "BeeTales Video Downloader"
WINDOWS_PLATFORM = "windows-x64"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def version_tuple(version: str = APP_VERSION) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version)
    if not match:
        raise ValueError("The application version must use stable semantic versioning.")
    return (*(int(value) for value in match.groups()), 0)


def archive_name(version: str = APP_VERSION) -> str:
    version_tuple(version)
    return f"BeeTales-Video-Downloader-v{version}-Windows-x64.zip"


def render_windows_version_info(version: str = APP_VERSION) -> str:
    numeric = version_tuple(version)
    return f'''VSVersionInfo(
    ffi=FixedFileInfo(
        filevers={numeric},
        prodvers={numeric},
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "The BeeTales Agency"),
                        StringStruct("FileDescription", "Local authorized video and audio downloader"),
                        StringStruct("FileVersion", "{version}"),
                        StringStruct("InternalName", "BeeTalesVideoDownloader"),
                        StringStruct("LegalCopyright", "Copyright 2026 The BeeTales Agency - Sorairei"),
                        StringStruct("OriginalFilename", "BeeTales Video Downloader.exe"),
                        StringStruct("ProductName", "{PRODUCT_NAME}"),
                        StringStruct("ProductVersion", "{version}"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)
'''


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_reproducible_archive(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError("The release source must be a directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if path.suffix.lower() == ".exe" else 0o644
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def write_release_metadata(
    archive: Path, manifest_path: Path, checksums_path: Path, version: str = APP_VERSION
) -> dict[str, str | int]:
    expected_name = archive_name(version)
    if archive.name != expected_name or not archive.is_file():
        raise ValueError(f"Expected the completed release archive {expected_name}.")
    digest = sha256_file(archive)
    manifest: dict[str, str | int] = {
        "schema_version": 1,
        "product": PRODUCT_NAME,
        "version": version,
        "platform": WINDOWS_PLATFORM,
        "archive": archive.name,
        "sha256": digest,
        "size_bytes": archive.stat().st_size,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    checksums_path.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return manifest


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version")
    info = commands.add_parser("write-version-info")
    info.add_argument("destination", type=Path)
    package = commands.add_parser("package")
    package.add_argument("source", type=Path)
    package.add_argument("archive", type=Path)
    package.add_argument("manifest", type=Path)
    package.add_argument("checksums", type=Path)
    arguments = parser.parse_args()

    if arguments.command == "version":
        print(APP_VERSION)
    elif arguments.command == "write-version-info":
        arguments.destination.write_text(render_windows_version_info(), encoding="utf-8")
    else:
        create_reproducible_archive(arguments.source, arguments.archive)
        manifest = write_release_metadata(arguments.archive, arguments.manifest, arguments.checksums)
        print(json.dumps(manifest, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
