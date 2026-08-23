"""Centralized visual identity and design tokens for BeeTales Video Downloader."""

from __future__ import annotations

from typing import TypeAlias


Color: TypeAlias = str | tuple[str, str]

PRIMARY = "#00E5FF"
PRIMARY_HOVER = "#00B8CC"
ACCENT_TEXT: Color = ("#00606B", "#80F6FF")
# Slate blue and deep cyan buttons
SEGMENT_SELECTED: Color = (PRIMARY, "#0F2836")
SEGMENT_SELECTED_HOVER: Color = (PRIMARY_HOVER, "#153A4D")
LIME = "#00FFA3"
ORANGE = "#FF8A00"
SPONSOR = "#9D00FF"
SPONSOR_HOVER = "#7A00CC"
# Main background and surfaces: Midnight Neon / Cyberpunk
MIDNIGHT = "#05070D"
MIDNIGHT_RAISED = "#0A0D18"

APP_BACKGROUND: Color = ("#F0F3F8", "#05070D")
SURFACE: Color = ("#FFFFFF", "#0A0E1A")
SURFACE_ALT: Color = ("#F4F7FC", "#0F1426")
SURFACE_ELEVATED: Color = ("#FFFFFF", "#141A33")
BORDER: Color = ("#DEE4F0", "#1E2540")
BORDER_STRONG: Color = ("#CCD5E6", "#293256")
ACCENT_SOFT: Color = ("#E0F7FC", "#081B2B")
TEXT: Color = ("#10141D", "#FFFFFF")
TEXT_MUTED: Color = ("#606B82", "#8492B3")
SIDEBAR_TEXT = "#FFFFFF"
SIDEBAR_MUTED = "#8492B3"
SUCCESS: Color = ("#007A44", "#00FFA3")
WARNING = "#FFB300"
DANGER: Color = ("#C62828", "#FF2A55")
DANGER_HOVER = "#D80032"
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
