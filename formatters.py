"""Presentation formatting helpers for the BeeTales user interface."""

from __future__ import annotations


def format_duration(seconds: int | None, language: str) -> str:
    """Format a duration in seconds as M:SS or H:MM:SS."""
    from localization import tr

    if seconds is None:
        return tr("duration_unknown", language)
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return (
        f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
        if hours
        else f"{minutes}:{remaining_seconds:02d}"
    )


def format_speed(value: float | None) -> str:
    """Format a bytes-per-second speed value with an automatic unit suffix."""
    if not value:
        return ""
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    amount = float(value)
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    return f"{amount:.1f} {unit}"
