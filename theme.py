"""Identidad visual centralizada de BeeTales Video Downloader."""

from __future__ import annotations

from typing import TypeAlias


Color: TypeAlias = str | tuple[str, str]

PRIMARY = "#78C82A"
PRIMARY_HOVER = "#5DAA20"
LIME = "#B9ED32"
ORANGE = "#FF8A1E"
SPONSOR = "#BF3989"
SPONSOR_HOVER = "#A62F77"
MIDNIGHT = "#07140C"
MIDNIGHT_RAISED = "#10251A"

APP_BACKGROUND: Color = ("#F3F6F1", "#070A08")
SURFACE: Color = ("#FFFFFF", "#111713")
SURFACE_ALT: Color = ("#F7FAF5", "#172019")
BORDER: Color = ("#DDE7D8", "#29362C")
TEXT: Color = ("#172018", "#F4F8F2")
TEXT_MUTED: Color = ("#637063", "#A8B3A7")
SIDEBAR_TEXT = "#F2F7EF"
SIDEBAR_MUTED = "#A8B8A3"
SUCCESS = "#2BAE75"
WARNING = "#D89B28"
DANGER = "#D95656"
DANGER_HOVER = "#B83F3F"
FONT_FAMILY = "Segoe UI"


def resolved(color: Color, appearance_mode: str) -> str:
    if isinstance(color, tuple):
        return color[1] if appearance_mode.lower() == "dark" else color[0]
    return color
