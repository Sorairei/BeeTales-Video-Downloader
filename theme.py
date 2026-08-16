"""Centralized visual identity and design tokens for BeeTales Video Downloader."""

from __future__ import annotations

from typing import TypeAlias


Color: TypeAlias = str | tuple[str, str]

PRIMARY = "#5AAD1E"
PRIMARY_HOVER = "#4A9018"
ACCENT_TEXT: Color = ("#2E5E0E", "#8ED62A")
SEGMENT_SELECTED: Color = (PRIMARY, "#2A6120")
SEGMENT_SELECTED_HOVER: Color = (PRIMARY_HOVER, "#336E27")
LIME = "#8ED62A"
ORANGE = "#FF8A1E"
SPONSOR = "#7B5EA7"
SPONSOR_HOVER = "#674E91"
MIDNIGHT = "#060E0A"
MIDNIGHT_RAISED = "#0E2016"

APP_BACKGROUND: Color = ("#F3F6F1", "#070A08")
SURFACE: Color = ("#FFFFFF", "#111713")
SURFACE_ALT: Color = ("#F7FAF5", "#172019")
SURFACE_ELEVATED: Color = ("#FFFFFF", "#141D17")
BORDER: Color = ("#DDE7D8", "#29362C")
BORDER_STRONG: Color = ("#C8D8C2", "#36503C")
ACCENT_SOFT: Color = ("#E7F5D8", "#17351F")
TEXT: Color = ("#172018", "#F4F8F2")
TEXT_MUTED: Color = ("#637063", "#A8B3A7")
SIDEBAR_TEXT = "#F2F7EF"
SIDEBAR_MUTED = "#A8B8A3"
SUCCESS: Color = ("#137A4C", "#4FD39A")
WARNING = "#D89B28"
DANGER: Color = ("#B4232D", "#FF7B7B")
DANGER_HOVER = "#B83F3F"
FONT_FAMILY = "Segoe UI"


def resolved(color: Color, appearance_mode: str) -> str:
    if isinstance(color, tuple):
        return color[1] if appearance_mode.lower() == "dark" else color[0]
    return color


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG relative-luminance contrast ratio for two hexadecimal colors."""

    def luminance(color: str) -> float:
        if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
            raise ValueError("Contrast colors must use six-digit hexadecimal notation.")
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def audited_contrast_pairs() -> dict[str, float]:
    """Ratios for every normal-size text pairing used by the interface."""

    colors: dict[str, tuple[str, str]] = {
        "sidebar_text": (SIDEBAR_TEXT, MIDNIGHT),
        "sidebar_muted": (SIDEBAR_MUTED, MIDNIGHT),
        "primary_button": ("#071008", PRIMARY),
        "sponsor_button": ("#FFFFFF", SPONSOR),
    }
    surfaces = {
        "background": APP_BACKGROUND,
        "surface": SURFACE,
        "surface_alt": SURFACE_ALT,
        "surface_elevated": SURFACE_ELEVATED,
    }
    for mode in ("light", "dark"):
        for surface_name, surface_color in surfaces.items():
            background = resolved(surface_color, mode)
            colors[f"text_{mode}_{surface_name}"] = (resolved(TEXT, mode), background)
            colors[f"muted_{mode}_{surface_name}"] = (resolved(TEXT_MUTED, mode), background)
        colors[f"accent_{mode}"] = (resolved(ACCENT_TEXT, mode), resolved(SURFACE, mode))
        colors[f"accent_soft_{mode}"] = (
            resolved(ACCENT_TEXT, mode),
            resolved(ACCENT_SOFT, mode),
        )
        colors[f"segment_selected_{mode}"] = (
            resolved(TEXT, mode),
            resolved(SEGMENT_SELECTED, mode),
        )
        colors[f"segment_unselected_{mode}"] = (
            resolved(TEXT, mode),
            resolved(SURFACE_ALT, mode),
        )
        colors[f"success_{mode}"] = (resolved(SUCCESS, mode), resolved(APP_BACKGROUND, mode))
        colors[f"danger_{mode}"] = (resolved(DANGER, mode), resolved(APP_BACKGROUND, mode))
    return {name: contrast_ratio(*pair) for name, pair in colors.items()}
