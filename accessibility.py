"""Testable accessibility metadata shared by the desktop interface."""

from __future__ import annotations

from dataclasses import dataclass

from localization import DEFAULT_LANGUAGE, tr


@dataclass(frozen=True)
class KeyboardShortcut:
    keys: str
    action: str
    description_key: str


KEYBOARD_SHORTCUTS = (
    KeyboardShortcut("Ctrl+L", "focus_url", "shortcut_focus"),
    KeyboardShortcut("Enter", "analyze", "shortcut_analyze"),
    KeyboardShortcut("Esc", "clear_url", "shortcut_clear"),
    KeyboardShortcut("Ctrl+Enter", "enqueue", "shortcut_enqueue"),
    KeyboardShortcut("Ctrl+O", "destination", "shortcut_destination"),
    KeyboardShortcut("F1", "help", "shortcut_help"),
)


def keyboard_help_text(language: str = DEFAULT_LANGUAGE) -> str:
    rows = [tr("help_heading", language), ""]
    rows.extend(
        f"{item.keys}: {tr(item.description_key, language)}" for item in KEYBOARD_SHORTCUTS
    )
    rows.extend(("", tr("help_note", language)))
    return "\n".join(rows)
