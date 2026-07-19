"""Aplicación de escritorio local BeeTales Video Downloader."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import webbrowser
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

if "--smoke-test" in sys.argv:
    try:
        from release_smoke import run_release_smoke_test

        result = run_release_smoke_test()
        print(f"Validación correcta: {result}")
    except Exception as exc:
        print(f"Validación de entrega fallida: {exc}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)

import customtkinter as ctk
from PIL import Image, ImageOps

from accessibility import keyboard_help_text
from downloader import (
    DownloadCancelled,
    DownloadRequest,
    DownloaderError,
    MediaInfo,
    ProgressEvent,
    analyze_media,
    detect_tools,
    download_media,
    fetch_thumbnail,
)
from settings import Settings, load_settings, save_settings
from queue_manager import DuplicateJobError, QueueJob, QueueManager
from release_metadata import APP_VERSION
from theme import (
    APP_BACKGROUND,
    ACCENT_TEXT,
    ACCENT_SOFT,
    BORDER,
    BORDER_STRONG,
    DANGER,
    DANGER_HOVER,
    FONT_FAMILY,
    LIME,
    MIDNIGHT,
    MIDNIGHT_RAISED,
    ORANGE,
    PRIMARY,
    PRIMARY_HOVER,
    SEGMENT_SELECTED,
    SEGMENT_SELECTED_HOVER,
    SIDEBAR_MUTED,
    SIDEBAR_TEXT,
    SPONSOR,
    SPONSOR_HOVER,
    SUCCESS,
    SURFACE,
    SURFACE_ALT,
    SURFACE_ELEVATED,
    TEXT,
    TEXT_MUTED,
)


SPONSOR_URL = "https://github.com/sponsors/Sorairei"
CARD_RADIUS = 16


def resource_path(relative: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / relative


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "Duración desconocida"
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{remaining_seconds:02d}" if hours else f"{minutes}:{remaining_seconds:02d}"


def format_speed(value: float | None) -> str:
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


class QueueCard(ctk.CTkFrame):
    def __init__(self, master: Any, job: QueueJob, cancel_command: Any) -> None:
        super().__init__(
            master,
            fg_color=SURFACE_ELEVATED,
            border_width=1,
            border_color=BORDER_STRONG,
            corner_radius=14,
        )
        self.job = job
        self.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            self,
            text=job.title,
            anchor="w",
            text_color=TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, padx=(14, 8), pady=(11, 0), sticky="ew")
        output = "Video MP4" if job.request.output_type == "video" else "Audio MP3"
        self.status_label = ctk.CTkLabel(
            self, text=f"{output} · En cola", anchor="w", text_color=TEXT_MUTED
        )
        self.status_label.grid(row=1, column=0, padx=(14, 8), pady=(1, 7), sticky="ew")
        self.progress = ctk.CTkProgressBar(
            self, height=8, progress_color=PRIMARY, fg_color=BORDER
        )
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=(14, 8), pady=(0, 12), sticky="ew")
        self.action = ctk.CTkButton(
            self,
            text="Cancelar",
            width=90,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=cancel_command,
        )
        self.action.grid(row=0, column=1, rowspan=3, padx=(0, 12), pady=12)

    def update_progress(self, event: ProgressEvent) -> None:
        self.progress.set(event.percent / 100)
        details = event.message
        if not details:
            parts = [f"{event.percent:.0f}%"]
            speed = format_speed(event.speed)
            if speed:
                parts.append(speed)
            if event.eta is not None:
                parts.append(f"{event.eta}s restantes")
            details = " · ".join(parts)
        self.status_label.configure(text=details)

    def finish(self, destination: Path) -> None:
        self.progress.set(1)
        self.status_label.configure(text="Completado", text_color=SUCCESS)
        self.action.configure(
            text="Abrir carpeta",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="#071008",
            border_width=0,
            command=lambda: open_directory(destination),
        )

    def fail(self, message: str, cancelled: bool = False) -> None:
        self.status_label.configure(
            text="Cancelado" if cancelled else message,
            text_color=TEXT_MUTED if cancelled else DANGER,
        )
        self.action.configure(state="disabled", text="Cancelado" if cancelled else "Error")


def open_directory(directory: Path) -> None:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(directory)], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(directory)], shell=False)
        else:
            subprocess.Popen(["xdg-open", str(directory)], shell=False)
    except OSError:
        messagebox.showerror("No se pudo abrir", f"Abre manualmente esta carpeta:\n{directory}")


class BeeTalesDownloaderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.preferences = load_settings()
        self.media: MediaInfo | None = None
        self.events: queue.Queue[tuple] = queue.Queue()
        self.download_queue: queue.Queue[QueueJob | None] = queue.Queue()
        self.queue_manager = QueueManager()
        self.queue_cards: dict[int, QueueCard] = {}
        self.analyzing = False
        self.analysis_thread: threading.Thread | None = None
        self.closing = False
        self.shutdown_polls = 0

        self.title(f"BeeTales Video Downloader v{APP_VERSION}")
        self.geometry("1240x800")
        self.minsize(1040, 700)
        self.configure(fg_color=APP_BACKGROUND)
        self._set_icon()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._apply_appearance(self.preferences.appearance)
        self._build_sidebar()
        self._build_workspace()
        self._bind_keyboard_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self.after(100, self._process_events)
        self.after(150, self._focus_url)
        self.download_worker = threading.Thread(target=self._download_worker, daemon=True)
        self.download_worker.start()

    def _set_icon(self) -> None:
        try:
            self.iconbitmap(str(resource_path("assets/beetales-app-icon.ico")))
        except Exception:
            pass

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=268, corner_radius=0, fg_color=MIDNIGHT)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        with Image.open(resource_path("assets/thebeetales-logo.png")) as source:
            logo = source.copy()
            self.logo_image = ctk.CTkImage(
                light_image=logo,
                dark_image=logo,
                size=(228, 65),
            )
        ctk.CTkLabel(sidebar, text="", image=self.logo_image).grid(
            row=0, column=0, padx=18, pady=(20, 4), sticky="ew"
        )
        ctk.CTkLabel(
            sidebar,
            text="VIDEO DOWNLOADER",
            text_color=LIME,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
        ).grid(row=1, column=0, padx=24, pady=(0, 12))

        info = ctk.CTkFrame(sidebar, fg_color=MIDNIGHT_RAISED, border_width=1, border_color="#274732")
        info.grid(row=2, column=0, padx=20, pady=12, sticky="new")
        with Image.open(resource_path("assets/sora-avatar.png")) as source:
            avatar = source.copy()
            self.sora_image = ctk.CTkImage(
                light_image=avatar,
                dark_image=avatar,
                size=(110, 110),
            )
        ctk.CTkLabel(info, text="", image=self.sora_image).pack(pady=(14, 6))
        ctk.CTkLabel(
            info,
            text="Sora procesa todo localmente",
            text_color=SIDEBAR_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        ).pack(padx=16)
        ctk.CTkLabel(
            info,
            text="Sin cuentas, publicidad, telemetría\nni servidores de BeeTales.",
            text_color=SIDEBAR_MUTED,
            justify="center",
        ).pack(padx=16, pady=(3, 15))

        self.tools = detect_tools()
        ready = bool(self.tools.ffmpeg and self.tools.ffprobe)
        self.tools_label = ctk.CTkLabel(
            sidebar,
            text="● Herramientas listas" if ready else "● FFmpeg no encontrado",
            text_color=SUCCESS if ready else ORANGE,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        self.tools_label.grid(row=3, column=0, padx=24, pady=(4, 12))

        ctk.CTkButton(
            sidebar,
            text="♥  Patrocinar en GitHub",
            height=40,
            fg_color=SPONSOR,
            hover_color=SPONSOR_HOVER,
            command=lambda: webbrowser.open(SPONSOR_URL),
        ).grid(row=4, column=0, padx=20, pady=(0, 14), sticky="ew")

        appearance = ctk.CTkFrame(sidebar, fg_color="transparent")
        appearance.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="ew")
        appearance.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(appearance, text="Apariencia", text_color=SIDEBAR_MUTED).grid(
            row=0, column=0, sticky="w"
        )
        self.appearance_menu = ctk.CTkOptionMenu(
            appearance,
            values=["Sistema", "Claro", "Oscuro"],
            width=105,
            fg_color=MIDNIGHT_RAISED,
            button_color="#294934",
            button_hover_color="#365E43",
            command=self._change_appearance,
        )
        self.appearance_menu.set(self.preferences.appearance)
        self.appearance_menu.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            sidebar,
            text=f"Version {APP_VERSION}",
            text_color=SIDEBAR_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
        ).grid(row=6, column=0, padx=20, pady=(0, 12))

    def _build_workspace(self) -> None:
        workspace = ctk.CTkScrollableFrame(self, fg_color=APP_BACKGROUND, corner_radius=0)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(workspace, fg_color="transparent")
        header.grid(row=0, column=0, padx=30, pady=(24, 14), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            heading,
            text="Descarga contenido autorizado",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=29, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            heading,
            text="YouTube, TikTok, Instagram y X · Video MP4 o Audio MP3",
            text_color=TEXT_MUTED,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
        ).pack(anchor="w", pady=(3, 0))

        assurance = ctk.CTkFrame(
            header,
            fg_color=ACCENT_SOFT,
            border_width=1,
            border_color=BORDER_STRONG,
            corner_radius=14,
        )
        assurance.grid(row=0, column=1, padx=(18, 0), sticky="e")
        with Image.open(resource_path("assets/frog-mascot.png")) as source:
            mascot = source.copy()
            self.header_mascot = ctk.CTkImage(
                light_image=mascot,
                dark_image=mascot,
                size=(58, 58),
            )
        ctk.CTkLabel(assurance, text="", image=self.header_mascot).grid(
            row=0, column=0, padx=(10, 4), pady=8
        )
        assurance_text = ctk.CTkFrame(assurance, fg_color="transparent")
        assurance_text.grid(row=0, column=1, padx=(0, 13), pady=8, sticky="w")
        ctk.CTkLabel(
            assurance_text,
            text="100% LOCAL",
            text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            assurance_text,
            text="Privado · Sin anuncios",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        ).pack(anchor="w")

        input_card = ctk.CTkFrame(
            workspace,
            fg_color=SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        input_card.grid(row=1, column=0, padx=30, pady=(0, 14), sticky="ew")
        input_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            input_card,
            text="01  PEGA UN ENLACE PÚBLICO  ·  Ctrl+L",
            text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=18, pady=(16, 6), sticky="w")
        self.url_entry = ctk.CTkEntry(
            input_card,
            height=44,
            placeholder_text="https://www.youtube.com/watch?v=...",
            border_color=BORDER,
            fg_color=SURFACE_ALT,
        )
        self.url_entry.grid(row=1, column=0, padx=(18, 8), pady=(0, 16), sticky="ew")
        self.url_entry.bind("<Return>", self._shortcut_analyze)
        ctk.CTkButton(
            input_card,
            text="Pegar",
            width=74,
            height=44,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._paste_url,
        ).grid(row=1, column=1, padx=(0, 8), pady=(0, 16))
        self.analyze_button = ctk.CTkButton(
            input_card,
            text="Analizar",
            width=100,
            height=44,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="#071008",
            command=self._start_analysis,
        )
        self.analyze_button.grid(row=1, column=2, padx=(0, 18), pady=(0, 16))

        self.media_card = ctk.CTkFrame(
            workspace,
            fg_color=SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        self.media_card.grid_columnconfigure(1, weight=1)
        with Image.open(resource_path("assets/media-atmosphere.png")) as source:
            placeholder = ImageOps.fit(source.convert("RGB"), (196, 110))
        self.thumbnail_placeholder = ctk.CTkImage(
            light_image=placeholder,
            dark_image=placeholder,
            size=(196, 110),
        )
        self.thumbnail_image = self.thumbnail_placeholder
        self.thumbnail_label = ctk.CTkLabel(
            self.media_card,
            text="",
            image=self.thumbnail_placeholder,
            corner_radius=10,
        )
        self.thumbnail_label.grid(row=0, column=0, rowspan=3, padx=16, pady=16)
        self.platform_label = ctk.CTkLabel(
            self.media_card, text="", text_color=ACCENT_TEXT, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        self.platform_label.grid(row=0, column=1, padx=(0, 18), pady=(16, 1), sticky="w")
        self.media_title = ctk.CTkLabel(
            self.media_card, text="", text_color=TEXT, anchor="w", justify="left", wraplength=720,
            font=ctk.CTkFont(family=FONT_FAMILY, size=17, weight="bold")
        )
        self.media_title.grid(row=1, column=1, padx=(0, 18), sticky="ew")
        self.media_meta = ctk.CTkLabel(self.media_card, text="", text_color=TEXT_MUTED, anchor="w")
        self.media_meta.grid(row=2, column=1, padx=(0, 18), pady=(2, 16), sticky="w")

        options = ctk.CTkFrame(
            workspace,
            fg_color=SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        options.grid(row=3, column=0, padx=30, pady=(0, 14), sticky="ew")
        options.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            options,
            text="02  CONFIGURA LA SALIDA",
            text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(15, 4), sticky="w")
        ctk.CTkLabel(options, text="Formato", text_color=TEXT).grid(
            row=1, column=0, padx=(18, 12), pady=8, sticky="w"
        )
        self.output_type = ctk.CTkSegmentedButton(
            options,
            values=["Video MP4", "Audio MP3"],
            selected_color=SEGMENT_SELECTED,
            selected_hover_color=SEGMENT_SELECTED_HOVER,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=BORDER,
            text_color=TEXT,
            command=lambda _value: self._refresh_format_controls(),
        )
        self.output_type.set("Video MP4")
        self.output_type.grid(row=1, column=1, padx=(0, 18), pady=8, sticky="ew")

        self.quality_label = ctk.CTkLabel(options, text="Calidad", text_color=TEXT)
        self.quality_label.grid(row=2, column=0, padx=(18, 12), pady=8, sticky="w")
        self.quality_menu = ctk.CTkOptionMenu(
            options,
            values=["1080p"],
            fg_color=SURFACE_ALT,
            button_color="#294934",
            button_hover_color="#365E43",
            text_color=TEXT,
        )
        self.quality_menu.grid(row=2, column=1, padx=(0, 18), pady=8, sticky="ew")

        ctk.CTkLabel(options, text="Guardar en · Ctrl+O", text_color=TEXT).grid(
            row=3, column=0, padx=(18, 12), pady=8, sticky="w"
        )
        destination_row = ctk.CTkFrame(options, fg_color="transparent")
        destination_row.grid(row=3, column=1, padx=(0, 18), pady=8, sticky="ew")
        destination_row.grid_columnconfigure(0, weight=1)
        self.destination_entry = ctk.CTkEntry(destination_row, border_color=BORDER, fg_color=SURFACE_ALT)
        self.destination_entry.insert(0, self.preferences.destination)
        self.destination_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            destination_row,
            text="Elegir",
            width=76,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._choose_destination,
        ).grid(row=0, column=1)

        self.rights_checkbox = ctk.CTkCheckBox(
            options,
            text="Confirmo que tengo permiso para descargar este contenido.",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            border_color=BORDER,
            text_color=TEXT_MUTED,
            command=self._refresh_download_state,
        )
        self.rights_checkbox.grid(row=4, column=0, columnspan=2, padx=18, pady=(10, 8), sticky="w")
        self.download_button = ctk.CTkButton(
            options,
            text="Agregar a la cola · Ctrl+Enter",
            height=44,
            fg_color=SURFACE_ALT,
            hover_color=SURFACE_ALT,
            text_color=TEXT,
            text_color_disabled=TEXT_MUTED,
            state="disabled",
            command=self._enqueue_download,
        )
        self.download_button.grid(row=5, column=0, columnspan=2, padx=18, pady=(4, 18), sticky="ew")

        queue_header = ctk.CTkFrame(workspace, fg_color="transparent")
        queue_header.grid(row=4, column=0, padx=30, pady=(4, 7), sticky="ew")
        ctk.CTkLabel(
            queue_header,
            text="03  Cola de descargas",
            text_color=TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=17, weight="bold"),
        ).pack(side="left")
        self.queue_summary_label = ctk.CTkLabel(
            queue_header,
            text="Sin elementos",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        self.queue_summary_label.pack(side="left", padx=(12, 0))
        ctk.CTkButton(
            queue_header,
            text="Atajos (F1)",
            width=92,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._show_keyboard_help,
        ).pack(side="right")
        self.clear_queue_button = ctk.CTkButton(
            queue_header,
            text="Limpiar finalizadas",
            width=126,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            text_color_disabled=TEXT_MUTED,
            hover_color=BORDER,
            state="disabled",
            command=self._clear_finished_jobs,
        )
        self.clear_queue_button.pack(side="right", padx=(0, 8))
        self.queue_frame = ctk.CTkScrollableFrame(workspace, height=180, fg_color="transparent")
        self.queue_frame.grid(row=5, column=0, padx=30, pady=(0, 12), sticky="ew")
        self.queue_frame.grid_columnconfigure(0, weight=1)
        self.empty_queue = ctk.CTkLabel(
            self.queue_frame,
            text="Las descargas aparecerán aquí. Los enlaces no se guardan en el historial.",
            text_color=TEXT_MUTED,
        )
        self.empty_queue.grid(row=0, column=0, pady=22)

        self.status_label = ctk.CTkLabel(
            workspace,
            text="Listo. Pega un enlace público para comenzar.",
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=6, column=0, padx=30, pady=(0, 24), sticky="ew")

    def _bind_keyboard_shortcuts(self) -> None:
        self.bind_all("<Control-l>", self._focus_url)
        self.bind_all("<Control-o>", self._shortcut_destination)
        self.bind_all("<Control-Return>", self._shortcut_enqueue)
        self.bind_all("<F1>", self._show_keyboard_help)

    def _focus_url(self, _event: Any = None) -> str:
        if not self.closing:
            self.url_entry.focus_set()
            self.url_entry.select_range(0, "end")
            self.url_entry.icursor("end")
        return "break"

    def _shortcut_analyze(self, _event: Any = None) -> str:
        if not self.closing and not self.analyzing:
            self._start_analysis()
        return "break"

    def _shortcut_destination(self, _event: Any = None) -> str:
        if not self.closing:
            self._choose_destination()
        return "break"

    def _shortcut_enqueue(self, _event: Any = None) -> str:
        if not self.closing and self.download_button.cget("state") == "normal":
            self._enqueue_download()
        return "break"

    def _show_keyboard_help(self, _event: Any = None) -> str:
        messagebox.showinfo("Accesibilidad y teclado", keyboard_help_text())
        return "break"

    def _paste_url(self) -> None:
        try:
            value = self.clipboard_get().strip()
        except Exception:
            self._set_status("No se encontró texto en el portapapeles.", error=True)
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, value)

    def _start_analysis(self) -> None:
        if self.analyzing:
            return
        url = self.url_entry.get().strip()
        self.analyzing = True
        self.analyze_button.configure(state="disabled", text="Analizando…")
        self.download_button.configure(
            state="disabled", fg_color=SURFACE_ALT, hover_color=SURFACE_ALT
        )
        self.media = None
        self.media_card.grid_forget()
        self._set_status("Consultando información pública…")
        self.analysis_thread = threading.Thread(
            target=self._analyze_worker, args=(url,), daemon=True
        )
        self.analysis_thread.start()

    def _analyze_worker(self, url: str) -> None:
        try:
            media = analyze_media(url, self.tools)
            try:
                thumbnail = fetch_thumbnail(media.thumbnail)
            except DownloaderError:
                thumbnail = None
            self.events.put(("analysis_ok", media, thumbnail))
        except DownloaderError as exc:
            self.events.put(("analysis_error", str(exc)))
        except Exception:
            self.events.put(("analysis_error", "Ocurrió un error inesperado al analizar el enlace."))

    def _show_media(self, media: MediaInfo, thumbnail: bytes | None = None) -> None:
        self.media = media
        self._show_thumbnail(thumbnail)
        self.platform_label.configure(text=media.platform.label.upper())
        self.media_title.configure(text=media.title)
        meta = " · ".join(item for item in (media.creator, format_duration(media.duration)) if item)
        self.media_meta.configure(text=meta)
        self.media_card.grid(row=2, column=0, padx=30, pady=(0, 14), sticky="ew")
        values = [f"{height}p" for height in reversed(media.qualities)]
        self.quality_menu.configure(values=values)
        self.quality_menu.set(f"{media.default_quality}p")
        self._refresh_download_state()
        self._set_status("Enlace listo para agregar a la cola.", success=True)

    def _show_thumbnail(self, payload: bytes | None) -> None:
        if payload:
            try:
                with Image.open(BytesIO(payload)) as source:
                    if source.width * source.height > 20_000_000:
                        raise ValueError("Thumbnail dimensions are too large")
                    prepared = ImageOps.fit(source.convert("RGB"), (196, 110))
                self.thumbnail_image = ctk.CTkImage(
                    light_image=prepared,
                    dark_image=prepared,
                    size=(196, 110),
                )
            except (OSError, ValueError, Image.DecompressionBombError):
                self.thumbnail_image = self.thumbnail_placeholder
        else:
            self.thumbnail_image = self.thumbnail_placeholder
        self.thumbnail_label.configure(image=self.thumbnail_image)

    def _refresh_download_state(self) -> None:
        ready = self.media is not None and bool(self.rights_checkbox.get())
        self.download_button.configure(
            state="normal" if ready else "disabled",
            fg_color=PRIMARY if ready else SURFACE_ALT,
            hover_color=PRIMARY_HOVER if ready else SURFACE_ALT,
            text_color="#071008" if ready else TEXT,
        )

    def _refresh_format_controls(self) -> None:
        if self.output_type.get() == "Audio MP3":
            self.quality_label.configure(text="Calidad de audio")
            self.quality_menu.configure(values=["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
            self.quality_menu.set("192 kbps")
        else:
            self.quality_label.configure(text="Calidad de video")
            if self.media:
                values = [f"{height}p" for height in reversed(self.media.qualities)]
                self.quality_menu.configure(values=values)
                self.quality_menu.set(f"{self.media.default_quality}p")
            else:
                self.quality_menu.configure(values=["1080p", "720p", "480p", "360p"])
                self.quality_menu.set("1080p")

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            title="Elegir carpeta de descargas", initialdir=self.destination_entry.get()
        )
        if selected:
            self.destination_entry.delete(0, "end")
            self.destination_entry.insert(0, selected)
            self.preferences.destination = selected
            save_settings(self.preferences)

    def _enqueue_download(self) -> None:
        if not self.media:
            self._set_status("Analiza primero un enlace.", error=True)
            return
        if not self.rights_checkbox.get():
            self._set_status("Confirma que tienes permiso para descargar el contenido.", error=True)
            return
        destination_text = self.destination_entry.get().strip()
        if not destination_text:
            self._set_status("Elige una carpeta de destino.", error=True)
            return
        destination = Path(destination_text).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._set_status("No se puede escribir en la carpeta seleccionada.", error=True)
            return
        if not destination.is_dir():
            self._set_status("La ruta de destino no es una carpeta.", error=True)
            return
        self.preferences.destination = str(destination)
        save_settings(self.preferences)

        selection = self.quality_menu.get()
        output_type = "audio" if self.output_type.get() == "Audio MP3" else "video"
        numeric = int("".join(character for character in selection if character.isdigit()))
        request = DownloadRequest(
            self.media.source_url,
            output_type,
            destination,
            quality=numeric if output_type == "video" else 1080,
            audio_bitrate=numeric if output_type == "audio" else 192,
        )
        try:
            job = self.queue_manager.create(self.media.title, request)
        except DuplicateJobError as exc:
            self._set_status(str(exc), error=True)
            return
        if self.empty_queue.winfo_exists():
            self.empty_queue.grid_remove()
        card = QueueCard(self.queue_frame, job, lambda job_id=job.job_id: self._cancel_job(job_id))
        card.grid(row=job.job_id, column=0, pady=(0, 8), sticky="ew")
        self.queue_cards[job.job_id] = card
        self.download_queue.put(job)
        self._refresh_queue_header()
        self.rights_checkbox.deselect()
        self._refresh_download_state()
        self._set_status("Descarga agregada a la cola.", success=True)

    def _download_worker(self) -> None:
        while True:
            job = self.download_queue.get()
            if job is None:
                self.download_queue.task_done()
                return
            if not self.queue_manager.start(job.job_id):
                self.events.put(("cancelled", job.job_id))
                self.download_queue.task_done()
                continue
            try:
                download_media(
                    job.request,
                    self.tools,
                    job.cancel_event,
                    lambda event, job_id=job.job_id: self.events.put(("progress", job_id, event)),
                )
                self.queue_manager.finish(job.job_id, "completed")
                self.events.put(("finished", job.job_id, job.request.destination))
            except DownloadCancelled:
                self.queue_manager.finish(job.job_id, "cancelled")
                self.events.put(("cancelled", job.job_id))
            except DownloaderError as exc:
                self.queue_manager.finish(job.job_id, "failed")
                self.events.put(("failed", job.job_id, str(exc)))
            except Exception:
                self.queue_manager.finish(job.job_id, "failed")
                self.events.put(("failed", job.job_id, "Ocurrió un error inesperado."))
            finally:
                self.download_queue.task_done()

    def _cancel_job(self, job_id: int) -> None:
        card = self.queue_cards.get(job_id)
        if card and self.queue_manager.cancel(job_id):
            card.status_label.configure(text="Cancelando…")
            card.action.configure(state="disabled")

    def _clear_finished_jobs(self) -> None:
        identifiers = self.queue_manager.remove_finished()
        for job_id in identifiers:
            card = self.queue_cards.pop(job_id, None)
            if card:
                card.destroy()
        if not self.queue_cards:
            self.empty_queue.grid(row=0, column=0, pady=22)
        self._refresh_queue_header()
        if identifiers:
            count = len(identifiers)
            self._set_status(
                f"Se retiraron {count} elemento{'s' if count != 1 else ''} finalizado{'s' if count != 1 else ''}.",
                success=True,
            )

    def _refresh_queue_header(self) -> None:
        total = self.queue_manager.total_count
        active = self.queue_manager.active_count
        finished = self.queue_manager.finished_count
        if not total:
            summary = "Sin elementos"
        elif active:
            summary = f"{active} activa{'s' if active != 1 else ''} · {finished} finalizada{'s' if finished != 1 else ''}"
        else:
            summary = f"{finished} finalizada{'s' if finished != 1 else ''}"
        self.queue_summary_label.configure(text=summary)
        self.clear_queue_button.configure(state="normal" if finished else "disabled")

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "analysis_ok":
                    self.analyzing = False
                    self.analyze_button.configure(state="normal", text="Analizar")
                    self._show_media(event[1], event[2])
                elif kind == "analysis_error":
                    self.analyzing = False
                    self.analyze_button.configure(state="normal", text="Analizar")
                    self._set_status(event[1], error=True)
                elif kind == "progress":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.update_progress(event[2])
                elif kind == "finished":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.finish(event[2])
                    self._set_status("Descarga completada.", success=True)
                    self._refresh_queue_header()
                elif kind == "cancelled":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.fail("", cancelled=True)
                    self._refresh_queue_header()
                elif kind == "failed":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.fail(event[2])
                    self._set_status(event[2], error=True)
                    self._refresh_queue_header()
        except queue.Empty:
            pass
        if not self.closing:
            self.after(100, self._process_events)

    def _request_close(self) -> None:
        if self.closing:
            return
        operations = self.queue_manager.active_count + int(
            bool(self.analysis_thread and self.analysis_thread.is_alive())
        )
        if operations and not messagebox.askyesno(
            "Salir de BeeTales",
            "Hay operaciones activas. ¿Quieres cancelarlas y cerrar la aplicación?",
        ):
            return
        self.closing = True
        self.queue_manager.cancel_all()
        self.download_queue.put(None)
        self.analyze_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self._set_status("Cerrando operaciones locales de forma segura…")
        self._wait_for_shutdown()

    def _wait_for_shutdown(self) -> None:
        analysis_running = bool(self.analysis_thread and self.analysis_thread.is_alive())
        if (not self.download_worker.is_alive() and not analysis_running) or self.shutdown_polls >= 250:
            self.destroy()
            return
        self.shutdown_polls += 1
        self.after(100, self._wait_for_shutdown)

    def _set_status(self, message: str, error: bool = False, success: bool = False) -> None:
        color = DANGER if error else SUCCESS if success else TEXT_MUTED
        self.status_label.configure(text=message, text_color=color)

    def _apply_appearance(self, value: str) -> None:
        mapping = {"Sistema": "System", "Claro": "Light", "Oscuro": "Dark"}
        ctk.set_appearance_mode(mapping.get(value, "System"))

    def _change_appearance(self, value: str) -> None:
        self.preferences.appearance = value
        self._apply_appearance(value)
        save_settings(self.preferences)


def main() -> None:
    ctk.set_default_color_theme("blue")
    app = BeeTalesDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
