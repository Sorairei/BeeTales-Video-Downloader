"""Testable accessibility metadata shared by the desktop interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyboardShortcut:
    keys: str
    action: str
    description: str


KEYBOARD_SHORTCUTS = (
    KeyboardShortcut("Ctrl+L", "focus_url", "Enfocar y seleccionar el enlace público"),
    KeyboardShortcut("Enter", "analyze", "Analizar el enlace desde el campo de URL"),
    KeyboardShortcut("Ctrl+Enter", "enqueue", "Agregar la descarga preparada a la cola"),
    KeyboardShortcut("Ctrl+O", "destination", "Elegir la carpeta de destino"),
    KeyboardShortcut("F1", "help", "Mostrar esta ayuda de teclado"),
)


def keyboard_help_text() -> str:
    rows = ["Atajos de teclado de BeeTales", ""]
    rows.extend(f"{item.keys}: {item.description}" for item in KEYBOARD_SHORTCUTS)
    rows.extend(
        (
            "",
            "Los estados también se describen con texto; el color nunca es el único indicador.",
        )
    )
    return "\n".join(rows)
