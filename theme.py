"""Centralized visual identity and design tokens for BeeTales Video Downloader."""

from __future__ import annotations

from typing import TypeAlias


Color: TypeAlias = str | tuple[str, str]

PRIMARY = "#1D9BF0"
PRIMARY_HOVER = "#1A8CD8"
ACCENT_TEXT: Color = ("#005A94", "#1D9BF0")
# Segment buttons
SEGMENT_SELECTED: Color = (PRIMARY, "#16202A")
SEGMENT_SELECTED_HOVER: Color = (PRIMARY_HOVER, "#192734")
LIME = "#00BA7C"
ORANGE = "#FF7A00"
SPONSOR = "#C20E5F"
SPONSOR_HOVER = "#A30C50"
# Main background and surfaces: Social Minimalist (X / YouTube Dark)
MIDNIGHT = "#0F0F0F"
MIDNIGHT_RAISED = "#16181C"

APP_BACKGROUND: Color = ("#F0F3F8", "#0F0F0F")
SURFACE: Color = ("#FFFFFF", "#16181C")
SURFACE_ALT: Color = ("#F4F7FC", "#202327")
SURFACE_ELEVATED: Color = ("#FFFFFF", "#2F3336")
BORDER: Color = ("#DEE4F0", "#2F3336")
BORDER_STRONG: Color = ("#CCD5E6", "#3E4144")
ACCENT_SOFT: Color = ("#E0F7FC", "#16202A")
TEXT: Color = ("#0F1419", "#F7F9F9")
TEXT_MUTED: Color = ("#536471", "#AAB8C2")
SIDEBAR_TEXT = "#F7F9F9"
SIDEBAR_MUTED = "#AAB8C2"
SUCCESS: Color = ("#007348", "#00BA7C")
WARNING = "#FFD400"
DANGER: Color = ("#C81423", "#F4212E")
DANGER_HOVER = "#DC1E29"
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
