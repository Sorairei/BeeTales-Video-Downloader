"""Preferencias locales sin historial ni telemetría."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Settings:
    destination: str
    appearance: str = "Sistema"


def default_downloads_directory() -> Path:
    candidate = Path.home() / "Downloads"
    return candidate if candidate.parent.exists() else Path.home()


def settings_directory() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "BeeTales Video Downloader"


def settings_path() -> Path:
    return settings_directory() / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    target = path or settings_path()
    defaults = Settings(str(default_downloads_directory()))
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        destination = data.get("destination")
        appearance = data.get("appearance")
        if isinstance(destination, str) and destination:
            defaults.destination = destination
        if appearance in {"Sistema", "Claro", "Oscuro"}:
            defaults.appearance = appearance
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def save_settings(settings: Settings, path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
