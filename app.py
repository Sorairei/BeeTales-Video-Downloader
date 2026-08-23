"""Local BeeTales desktop application."""

from __future__ import annotations

import logging
import math
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

if "--smoke-test" in sys.argv:
    try:
        from release_smoke import run_release_smoke_test

        result = run_release_smoke_test()
        print(f"Release validation passed: {result}")
    except Exception as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
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
from formatters import format_duration, format_speed
from localization import (
    LANGUAGE_NAMES,
    appearance_labels,
    language_from_label,
    localize_engine_error,
    tr,
)
from queue_manager import DuplicateJobError, QueueCounts, QueueJob, QueueManager
from release_metadata import APP_VERSION
from settings import load_settings, save_settings
from theme import (
    ACCENT_SOFT,
    ACCENT_TEXT,
    APP_BACKGROUND,
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
    resolved,
)


SPONSOR_URL = "https://github.com/sponsors/Sorairei"
CARD_RADIUS = 24
_DRAW_DEBOUNCE_MS = 80        # Debounce delay for canvas redraws on resize (ms)
_SHUTDOWN_TIMEOUT_MS = 8_000  # Hard deadline for workers to stop on close (ms)

logger = logging.getLogger(__name__)


def resource_path(relative: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / relative


def open_directory(directory: Path, language: str) -> None:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(directory)], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(directory)], shell=False)
        else:
            subprocess.Popen(["xdg-open", str(directory)], shell=False)
    except OSError:
        messagebox.showerror(
            tr("open_error_title", language),
            tr("open_error_body", language, directory=directory),
        )


class QueueCard(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        job: QueueJob,
        cancel_command: Any,
        language: str,
    ) -> None:
        super().__init__(
            master,
            fg_color=SURFACE_ELEVATED,
            border_width=1,
            border_color=BORDER_STRONG,
            corner_radius=14,
        )
        self.job = job
        self.language = language
        self.cancel_command = cancel_command
        self.destination: Path | None = None
        self.failure_message = ""
        self.last_progress: ProgressEvent | None = None
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=job.title,
            anchor="w",
            text_color=TEXT,
            wraplength=250,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, padx=(14, 8), pady=(11, 0), sticky="ew")
        self.status_label = ctk.CTkLabel(self, text="", anchor="w", text_color=TEXT_MUTED)
        self.status_label.grid(row=1, column=0, padx=(14, 8), pady=(1, 7), sticky="ew")
        self.progress = ctk.CTkProgressBar(
            self, height=7, progress_color=PRIMARY, fg_color=BORDER
        )
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=(14, 8), pady=(0, 12), sticky="ew")
        self.action = ctk.CTkButton(
            self,
            text="",
            width=92,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=cancel_command,
        )
        self.action.grid(row=0, column=1, rowspan=3, padx=(0, 12), pady=12)
        self.retranslate(language)

    def _output_label(self) -> str:
        key = "video_mp4" if self.job.request.output_type == "video" else "audio_mp3"
        return tr(key, self.language)

    def retranslate(self, language: str) -> None:
        self.language = language
        state = self.job.state
        if state == "completed":
            self.status_label.configure(
                text=f"{self._output_label()} · {tr('completed', language)}",
                text_color=SUCCESS,
            )
            self.action.configure(
                text=tr("open_folder", language),
                state="normal",
                fg_color=PRIMARY,
                hover_color=PRIMARY_HOVER,
                text_color="#071008",
                border_width=0,
                command=lambda: open_directory(self.destination or self.job.request.destination, language),
            )
        elif state == "cancelled":
            self.status_label.configure(
                text=f"{self._output_label()} · {tr('cancelled', language)}",
                text_color=TEXT_MUTED,
            )
            self.action.configure(text=tr("cancelled", language), state="disabled")
        elif state == "failed":
            message = (
                localize_engine_error(self.failure_message, language)
                if self.failure_message
                else tr("unexpected_download", language)
            )
            self.status_label.configure(
                text=f"{self._output_label()} · {message}", text_color=DANGER
            )
            self.action.configure(text=tr("error", language), state="disabled")
        elif state == "cancelling":
            self.status_label.configure(text=tr("cancelling", language), text_color=TEXT_MUTED)
            self.action.configure(text=tr("cancel", language), state="disabled")
        elif self.last_progress:
            self.update_progress(self.last_progress)
        else:
            self.status_label.configure(
                text=f"{self._output_label()} · {tr('queue_state', language)}",
                text_color=TEXT_MUTED,
            )
            self.action.configure(
                text=tr("cancel", language),
                state="normal",
                fg_color="transparent",
                hover_color=BORDER,
                text_color=TEXT,
                border_width=1,
                command=self.cancel_command,
            )

    def update_progress(self, event: ProgressEvent) -> None:
        self.last_progress = event
        self.progress.set(event.percent / 100)
        # Change progress bar color based on download state for immediate visual feedback
        if event.status == "processing":
            self.progress.configure(progress_color=ORANGE)
        else:
            self.progress.configure(progress_color=PRIMARY)
        if event.status == "starting":
            details = tr("preparing", self.language)
        elif event.status == "processing":
            if "H.264" in event.message:
                details = tr("processing_compatible", self.language)
            elif self.job.request.output_type == "audio":
                details = tr("processing_audio", self.language)
            else:
                details = tr("processing_video", self.language)
        else:
            parts = [f"{event.percent:.0f}%"]
            speed = format_speed(event.speed)
            if speed:
                parts.append(speed)
            if event.eta is not None:
                parts.append(tr("remaining", self.language, seconds=event.eta))
            details = " · ".join(parts)
        self.status_label.configure(text=details, text_color=TEXT_MUTED)

    def finish(self, destination: Path) -> None:
        self.destination = destination
        self.progress.set(1)
        self.progress.configure(progress_color=PRIMARY)
        self.retranslate(self.language)

    def fail(self, message: str, cancelled: bool = False) -> None:
        self.failure_message = message
        if cancelled:
            self.job.state = "cancelled"
        self.retranslate(self.language)
        # If there is a real error message, show a Details button so the user can inspect it
        if message and not cancelled:
            self.progress.configure(progress_color=DANGER)
            self.action.configure(
                text="Details",
                state="normal",
                fg_color="transparent",
                border_width=1,
                border_color=DANGER,
                text_color=DANGER,
                hover_color=BORDER,
                command=lambda m=message: messagebox.showerror(
                    "Error detail", m
                ),
            )


class SplashScreen(tk.Toplevel):
    """Loading window displayed while the application initialises."""

    _STEPS = [
        (0.20, "Loading tools..."),
        (0.55, "Initializing workspace..."),
        (0.85, "Applying preferences..."),
        (1.00, "Ready"),
    ]
    _STEP_MS = 380

    def __init__(self, root: tk.Tk, logo_path: Path) -> None:
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(bg="#060E0A")
        self.attributes("-topmost", True)

        width, height = 500, 280
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Subtle border
        outer = tk.Frame(self, bg="#1A3025", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#060E0A")
        inner.pack(fill="both", expand=True)

        # Logo
        try:
            pil_img = Image.open(logo_path)
            pil_img = pil_img.resize((320, 92), Image.LANCZOS)
            self._logo_tk = ctk.CTkImage(
                light_image=pil_img, dark_image=pil_img, size=(320, 92)
            )
            logo_lbl = ctk.CTkLabel(inner, image=self._logo_tk, text="", bg_color="#060E0A")
            logo_lbl.pack(pady=(32, 6))
        except Exception:
            tk.Label(
                inner, text="BeeTales", fg="#8ED62A", bg="#060E0A",
                font=("Segoe UI", 22, "bold")
            ).pack(pady=(32, 6))

        # Subtitulo
        tk.Label(
            inner, text="Video Downloader",
            fg="#5D7A65", bg="#060E0A",
            font=("Segoe UI", 11),
        ).pack()

        # Progress bar container
        bar_frame = tk.Frame(inner, bg="#060E0A")
        bar_frame.pack(fill="x", padx=48, pady=(28, 6))

        track = tk.Frame(bar_frame, bg="#1A3025", height=4)
        track.pack(fill="x")
        track.pack_propagate(False)
        self._fill = tk.Frame(track, bg="#5AAD1E", height=4)
        self._fill.place(x=0, y=0, relheight=1, relwidth=0)

        # Status text label
        self._status_var = tk.StringVar(value="Starting...")
        tk.Label(
            inner, textvariable=self._status_var,
            fg="#4A6B52", bg="#060E0A",
            font=("Segoe UI", 9),
        ).pack()

        self._step_index = 0
        self._done_event = threading.Event()
        self.after(120, self._advance)

    def _advance(self) -> None:
        if self._step_index >= len(self._STEPS):
            return
        target_ratio, label = self._STEPS[self._step_index]
        self._fill.place(relwidth=target_ratio)
        self._status_var.set(label)
        self._step_index += 1
        if self._step_index < len(self._STEPS):
            self.after(self._STEP_MS, self._advance)
        else:
            # Wait for tool detection to finish (max 2 s)
            self.after(200, self._wait_for_tools)

    def _wait_for_tools(self) -> None:
        if self._done_event.is_set():
            self.after(150, self.destroy)
        else:
            self.after(80, self._wait_for_tools)

    def signal_ready(self) -> None:
        """Called from the tool-detection thread when detection is complete."""
        self._done_event.set()


class BeeTalesDownloaderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.preferences = load_settings()
        self.language = self.preferences.language
        self.media: MediaInfo | None = None
        self.analyzed_input = ""
        self.events: queue.Queue[tuple] = queue.Queue()
        self.download_queue: queue.Queue[QueueJob | None] = queue.Queue()
        self.queue_manager = QueueManager()
        self.queue_cards: dict[int, QueueCard] = {}
        self.analyzing = False
        self.analysis_generation = 0
        self.analysis_thread: threading.Thread | None = None
        self.closing = False
        self._draw_pending: str | None = None
        self._shutdown_deadline: str | None = None
        self.tools: Any = None

        self.title(f"{tr('app_title', self.language)} v{APP_VERSION}")
        self.geometry("1320x820")
        self.minsize(1100, 720)
        self.configure(fg_color=APP_BACKGROUND)
        self._set_icon()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._apply_appearance(self.preferences.appearance)
        self._build_sidebar()
        self._build_workspace()
        self._bind_keyboard_shortcuts()
        self._apply_translations()
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

    @staticmethod
    def _ctk_image(path: str, size: tuple[int, int]) -> ctk.CTkImage:
        with Image.open(resource_path(path)) as source:
            image = source.copy()
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=236, corner_radius=0, fg_color=MIDNIGHT)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(3, weight=1)

        self.logo_image = self._ctk_image("assets/thebeetales-logo.png", (198, 57))
        ctk.CTkLabel(sidebar, text="", image=self.logo_image).grid(
            row=0, column=0, padx=18, pady=(18, 2), sticky="ew"
        )
        self.sidebar_product_label = ctk.CTkLabel(
            sidebar,
            text="",
            text_color=LIME,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        )
        self.sidebar_product_label.grid(row=1, column=0, padx=20, pady=(0, 12))

        # Identity frame removed

        sidebar_actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_actions.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")
        sidebar_actions.grid_columnconfigure(0, weight=1)
        ready = bool(self.tools and self.tools.ffmpeg and self.tools.ffprobe)
        self.tools_label = ctk.CTkLabel(
            sidebar_actions,
            text="",
            text_color=SUCCESS if ready else ORANGE,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        self.tools_label.grid(row=0, column=0, pady=(0, 9), sticky="w")
        self.sponsor_button = ctk.CTkButton(
            sidebar_actions,
            text="",
            height=34,
            fg_color="transparent",
            border_width=1,
            border_color=SPONSOR,
            text_color=SPONSOR,
            hover_color=MIDNIGHT_RAISED,
            command=lambda: webbrowser.open(SPONSOR_URL),
        )
        self.sponsor_button.grid(row=1, column=0, pady=(0, 14), sticky="ew")

        preferences = ctk.CTkFrame(sidebar_actions, fg_color="transparent")
        preferences.grid(row=2, column=0, sticky="ew")
        preferences.grid_columnconfigure(1, weight=1)
        self.language_label = ctk.CTkLabel(preferences, text="", text_color=SIDEBAR_MUTED)
        self.language_label.grid(row=0, column=0, pady=(0, 8), sticky="w")
        self.language_menu = ctk.CTkOptionMenu(
            preferences,
            values=list(LANGUAGE_NAMES.values()),
            width=112,
            fg_color=MIDNIGHT_RAISED,
            button_color="#294934",
            button_hover_color="#365E43",
            command=self._change_language,
        )
        self.language_menu.set(LANGUAGE_NAMES[self.language])
        self.language_menu.grid(row=0, column=1, pady=(0, 8), sticky="e")
        self.appearance_label = ctk.CTkLabel(preferences, text="", text_color=SIDEBAR_MUTED)
        self.appearance_label.grid(row=1, column=0, sticky="w")
        self.appearance_menu = ctk.CTkOptionMenu(
            preferences,
            values=["System", "Light", "Dark"],
            width=112,
            fg_color=MIDNIGHT_RAISED,
            button_color="#294934",
            button_hover_color="#365E43",
            command=self._change_appearance,
        )
        self.appearance_menu.grid(row=1, column=1, sticky="e")
        self.version_label = ctk.CTkLabel(
            sidebar,
            text="",
            text_color=SIDEBAR_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
        )
        self.version_label.grid(row=5, column=0, padx=16, pady=(0, 10))

    def _build_workspace(self) -> None:
        workspace = ctk.CTkFrame(self, fg_color=APP_BACKGROUND, corner_radius=0)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(1, weight=1)

        # High-tech background grid and audio waves
        self.bg_canvas = tk.Canvas(
            workspace,
            bg=resolved(APP_BACKGROUND, self.preferences.appearance),
            bd=0,
            highlightthickness=0
        )
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._schedule_draw_background)


        header = ctk.CTkFrame(workspace, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(32, 20), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="w")
        
        self.sora_image = self._ctk_image("assets/sora-avatar.png", (56, 56))
        sora_icon = ctk.CTkLabel(heading, text="", image=self.sora_image)
        sora_icon.grid(row=0, column=0, rowspan=2, padx=(0, 16))

        self.heading_label = ctk.CTkLabel(
            heading,
            text="",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=32, weight="bold"),
        )
        self.heading_label.grid(row=0, column=1, sticky="sw")
        self.subheading_label = ctk.CTkLabel(
            heading,
            text="",
            text_color=TEXT_MUTED,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
        )
        self.subheading_label.grid(row=1, column=1, sticky="nw", pady=(2, 0))

        # Assurance frame removed

        content = ctk.CTkFrame(workspace, fg_color="transparent")
        content.grid(row=1, column=0, padx=40, pady=(0, 20), sticky="nsew")
        content.grid_columnconfigure(0, weight=7, uniform="workspace")
        content.grid_columnconfigure(1, weight=4, uniform="workspace")
        content.grid_rowconfigure(0, weight=1)

        self.workflow = ctk.CTkScrollableFrame(
            content, fg_color="transparent", corner_radius=0
        )
        self.workflow.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        self.workflow.grid_columnconfigure(0, weight=1)
        self._build_source_card()
        self._build_preview_card()
        self._build_output_card()
        self._build_local_flow_card()

        queue_panel = ctk.CTkFrame(
            content,
            fg_color=SURFACE,
            border_width=0,
            corner_radius=CARD_RADIUS,
        )
        queue_panel.grid(row=0, column=1, sticky="nsew")
        queue_panel.grid_columnconfigure(0, weight=1)
        queue_panel.grid_rowconfigure(2, weight=1)
        queue_header = ctk.CTkFrame(queue_panel, fg_color="transparent")
        queue_header.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="ew")
        queue_header.grid_columnconfigure(0, weight=1)
        self.queue_heading_label = ctk.CTkLabel(
            queue_header,
            text="",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
        )
        self.queue_heading_label.grid(row=0, column=0, sticky="w")
        self.queue_summary_label = ctk.CTkLabel(
            queue_header,
            text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        self.queue_summary_label.grid(row=1, column=0, pady=(1, 0), sticky="w")
        queue_commands = ctk.CTkFrame(queue_panel, fg_color="transparent")
        queue_commands.grid(row=1, column=0, padx=16, pady=(7, 10), sticky="ew")
        queue_commands.grid_columnconfigure(0, weight=1)
        self.clear_queue_button = ctk.CTkButton(
            queue_commands,
            text="",
            height=30,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            text_color_disabled=TEXT_MUTED,
            hover_color=BORDER,
            state="disabled",
            command=self._clear_finished_jobs,
        )
        self.clear_queue_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.help_button = ctk.CTkButton(
            queue_commands,
            text="",
            width=94,
            height=30,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._show_keyboard_help,
        )
        self.help_button.grid(row=0, column=1)
        self.queue_frame = ctk.CTkScrollableFrame(
            queue_panel, fg_color=SURFACE_ALT, corner_radius=12
        )
        self.queue_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.queue_frame.grid_columnconfigure(0, weight=1)
        # Empty state: mascot image + descriptive text
        self._empty_queue_container = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
        self._empty_queue_container.grid(row=0, column=0, padx=18, pady=28)
        self._mascot_image = self._ctk_image("assets/frog-mascot.png", (52, 52))
        ctk.CTkLabel(
            self._empty_queue_container, image=self._mascot_image, text=""
        ).pack()
        self.empty_queue = ctk.CTkLabel(
            self._empty_queue_container,
            text="",
            text_color=TEXT_MUTED,
            justify="center",
            wraplength=240,
        )
        self.empty_queue.pack(pady=(8, 0))

        status_bar = ctk.CTkFrame(
            workspace, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10
        )
        status_bar.grid(row=2, column=0, padx=28, pady=(0, 18), sticky="ew")
        self.status_dot = ctk.CTkLabel(status_bar, text="●", text_color=SUCCESS, width=18)
        self.status_dot.pack(side="left", padx=(12, 2), pady=7)
        self.status_label = ctk.CTkLabel(
            status_bar, text="", text_color=TEXT_MUTED, anchor="w"
        )
        self.status_label.pack(side="left", padx=(0, 12), pady=7, fill="x", expand=True)

    def _build_source_card(self) -> None:
        card = ctk.CTkFrame(
            self.workflow, fg_color=SURFACE, border_width=1, border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        card.grid(row=0, column=0, pady=(0, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self.step_link_label = ctk.CTkLabel(
            card, text="", text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        )
        self.step_link_label.grid(row=0, column=0, columnspan=4, padx=16, pady=(15, 6), sticky="w")
        self.url_entry = ctk.CTkEntry(
            card, height=44, border_color=BORDER_STRONG, fg_color=SURFACE_ALT
        )
        self.url_entry.grid(row=1, column=0, padx=(16, 6), pady=(0, 16), sticky="ew")
        self.url_entry.bind("<Return>", self._shortcut_analyze)
        self.url_entry.bind("<KeyRelease>", self._url_changed)
        self.clear_link_button = ctk.CTkButton(
            card,
            text="×",
            width=42,
            height=44,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_MUTED,
            hover_color=BORDER,
            state="disabled",
            command=self._clear_source,
            font=ctk.CTkFont(family=FONT_FAMILY, size=20),
        )
        self.clear_link_button.grid(row=1, column=1, padx=(0, 6), pady=(0, 16))
        self.paste_button = ctk.CTkButton(
            card,
            text="",
            width=72,
            height=44,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._paste_url,
        )
        self.paste_button.grid(row=1, column=2, padx=(0, 6), pady=(0, 16))
        self.analyze_button = ctk.CTkButton(
            card,
            text="",
            width=96,
            height=44,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="#071008",
            command=self._start_analysis,
        )
        self.analyze_button.grid(row=1, column=3, padx=(0, 16), pady=(0, 16))

    def _build_preview_card(self) -> None:
        self.media_card = ctk.CTkFrame(
            self.workflow, fg_color=SURFACE, border_width=1, border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        self.media_card.grid_columnconfigure(1, weight=1)
        with Image.open(resource_path("assets/media-atmosphere.png")) as source:
            placeholder = ImageOps.fit(source.convert("RGB"), (188, 106))
        self.thumbnail_placeholder = ctk.CTkImage(
            light_image=placeholder, dark_image=placeholder, size=(188, 106)
        )
        self.thumbnail_image = self.thumbnail_placeholder
        self.thumbnail_label = ctk.CTkLabel(
            self.media_card, text="", image=self.thumbnail_placeholder, corner_radius=10
        )
        self.thumbnail_label.grid(row=0, column=0, rowspan=3, padx=14, pady=14)
        self.platform_label = ctk.CTkLabel(
            self.media_card, text="", text_color=ACCENT_TEXT, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
        )
        self.platform_label.grid(row=0, column=1, padx=(0, 14), pady=(15, 1), sticky="w")
        self.media_title = ctk.CTkLabel(
            self.media_card, text="", text_color=TEXT, anchor="w", justify="left",
            wraplength=380, font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
        )
        self.media_title.grid(row=1, column=1, padx=(0, 14), sticky="ew")
        self.media_meta = ctk.CTkLabel(
            self.media_card, text="", text_color=TEXT_MUTED, anchor="w"
        )
        self.media_meta.grid(row=2, column=1, padx=(0, 14), pady=(2, 15), sticky="w")
        # Hidden until a link has been successfully analysed
        self.media_card.grid_remove()

    def _build_output_card(self) -> None:
        card = ctk.CTkFrame(
            self.workflow, fg_color=SURFACE, border_width=1, border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        card.grid(row=2, column=0, pady=(0, 4), sticky="ew")
        self._output_card = card
        card.grid_columnconfigure(1, weight=1)
        self.step_output_label = ctk.CTkLabel(
            card, text="", text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        )
        self.step_output_label.grid(row=0, column=0, columnspan=2, padx=16, pady=(15, 4), sticky="w")
        self.format_label = ctk.CTkLabel(card, text="", text_color=TEXT)
        self.format_label.grid(row=1, column=0, padx=(16, 12), pady=7, sticky="w")
        self.output_type = ctk.CTkSegmentedButton(
            card,
            values=["Video MP4", "Audio MP3"],
            selected_color=SEGMENT_SELECTED,
            selected_hover_color=SEGMENT_SELECTED_HOVER,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=BORDER,
            text_color=TEXT,
            command=lambda _value: self._refresh_format_controls(),
        )
        self.output_type.set("Video MP4")
        self.output_type.grid(row=1, column=1, padx=(0, 16), pady=7, sticky="ew")
        self.quality_label = ctk.CTkLabel(card, text="", text_color=TEXT)
        self.quality_label.grid(row=2, column=0, padx=(16, 12), pady=7, sticky="w")
        self.quality_menu = ctk.CTkOptionMenu(
            card,
            values=["1080p", "720p", "480p", "360p"],
            fg_color=SURFACE_ALT,
            button_color="#294934",
            button_hover_color="#365E43",
            text_color=TEXT,
        )
        self.quality_menu.set("1080p")
        self.quality_menu.grid(row=2, column=1, padx=(0, 16), pady=7, sticky="ew")
        self.save_label = ctk.CTkLabel(card, text="", text_color=TEXT)
        self.save_label.grid(row=3, column=0, padx=(16, 12), pady=7, sticky="w")
        destination_row = ctk.CTkFrame(card, fg_color="transparent")
        destination_row.grid(row=3, column=1, padx=(0, 16), pady=7, sticky="ew")
        destination_row.grid_columnconfigure(0, weight=1)
        self.destination_entry = ctk.CTkEntry(
            destination_row, border_color=BORDER, fg_color=SURFACE_ALT
        )
        self.destination_entry.insert(0, self.preferences.destination)
        self.destination_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.choose_button = ctk.CTkButton(
            destination_row,
            text="",
            width=76,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._choose_destination,
        )
        self.choose_button.grid(row=0, column=1)
        self.rights_checkbox = ctk.CTkCheckBox(
            card,
            text="",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            border_color=BORDER,
            text_color=TEXT_MUTED,
            command=self._refresh_download_state,
        )
        self.rights_checkbox.grid(row=4, column=0, columnspan=2, padx=16, pady=(10, 7), sticky="w")
        self.download_button = ctk.CTkButton(
            card,
            text="",
            height=44,
            fg_color=SURFACE_ALT,
            hover_color=SURFACE_ALT,
            text_color=TEXT,
            text_color_disabled=TEXT_MUTED,
            state="disabled",
            command=self._enqueue_download,
        )
        self.download_button.grid(row=5, column=0, columnspan=2, padx=16, pady=(4, 16), sticky="ew")
        # Hidden until a link has been successfully analysed
        card.grid_remove()

    def _build_local_flow_card(self) -> None:
        card = ctk.CTkFrame(
            self.workflow,
            fg_color=ACCENT_SOFT,
            border_width=1,
            border_color=BORDER_STRONG,
            corner_radius=CARD_RADIUS,
        )
        card.grid(row=3, column=0, pady=(8, 4), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkFrame(card, fg_color="transparent")
        heading.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        heading.grid_columnconfigure(0, weight=1)
        self.local_flow_heading = ctk.CTkLabel(
            heading,
            text="",
            text_color=ACCENT_TEXT,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        )
        self.local_flow_heading.grid(row=0, column=0, sticky="w")
        self.local_flow_platforms = ctk.CTkLabel(
            heading,
            text="YouTube  ·  TikTok  ·  Instagram  ·  X",
            text_color=TEXT_MUTED,
            anchor="e",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
        )
        self.local_flow_platforms.grid(row=0, column=1, padx=(12, 0), sticky="e")

        flow = ctk.CTkFrame(card, fg_color="transparent")
        flow.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        for column in (0, 2, 4):
            flow.grid_columnconfigure(column, weight=1, uniform="local-flow")

        self.local_flow_steps: list[tuple[ctk.CTkLabel, ctk.CTkLabel]] = []
        for column in (0, 2, 4):
            step = ctk.CTkFrame(
                flow,
                fg_color=SURFACE,
                border_width=1,
                border_color=BORDER,
                corner_radius=10,
            )
            step.grid(row=0, column=column, sticky="nsew")
            title = ctk.CTkLabel(
                step,
                text="",
                text_color=TEXT,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            )
            title.pack(anchor="w", padx=11, pady=(9, 1))
            description = ctk.CTkLabel(
                step,
                text="",
                text_color=TEXT_MUTED,
                anchor="w",
                justify="left",
                wraplength=165,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            )
            description.pack(anchor="w", padx=11, pady=(0, 9))
            self.local_flow_steps.append((title, description))

        for column in (1, 3):
            ctk.CTkLabel(
                flow,
                text="→",
                width=24,
                text_color=ACCENT_TEXT,
                font=ctk.CTkFont(family=FONT_FAMILY, size=17, weight="bold"),
            ).grid(row=0, column=column, padx=5)

    def _bind_keyboard_shortcuts(self) -> None:
        self.bind_all("<Control-l>", self._focus_url)
        self.bind_all("<Control-o>", self._shortcut_destination)
        self.bind_all("<Control-Return>", self._shortcut_enqueue)
        self.bind_all("<Escape>", self._clear_source)
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
        messagebox.showinfo(
            tr("help_title", self.language), keyboard_help_text(self.language)
        )
        return "break"

    def _url_changed(self, _event: Any = None) -> None:
        current = self.url_entry.get().strip()
        self.clear_link_button.configure(state="normal" if current else "disabled")
        if self.media and current != self.analyzed_input:
            self._reset_source_state(preserve_entry=True, announce=False)

    def _paste_url(self) -> None:
        try:
            value = self.clipboard_get().strip()
        except Exception:
            self._set_status(tr("clipboard_empty", self.language), error=True)
            return
        self._reset_source_state(preserve_entry=False, announce=False)
        self.url_entry.insert(0, value)
        self._url_changed()

    def _clear_source(self, _event: Any = None) -> str:
        self._reset_source_state(preserve_entry=False, announce=True)
        self.url_entry.focus_set()
        return "break"

    def _reset_source_state(self, preserve_entry: bool, announce: bool) -> None:
        self.analysis_generation += 1
        self.analyzing = False
        self.media = None
        self.analyzed_input = ""
        if not preserve_entry:
            self.url_entry.delete(0, "end")
        self.media_card.grid_forget()
        self._output_card.grid_remove()
        self.thumbnail_image = self.thumbnail_placeholder
        self.thumbnail_label.configure(image=self.thumbnail_placeholder)
        self.platform_label.configure(text="")
        self.media_title.configure(text="")
        self.media_meta.configure(text="")
        self.rights_checkbox.deselect()
        self.analyze_button.configure(state="normal", text=tr("analyze", self.language))
        self.clear_link_button.configure(
            state="normal" if self.url_entry.get().strip() else "disabled"
        )
        self._refresh_format_controls()
        self._refresh_download_state()
        if announce:
            self._set_status(tr("link_cleared", self.language), success=True)

    def _start_analysis(self) -> None:
        if self.analyzing:
            return
        url = self.url_entry.get().strip()
        if not url:
            self._set_status(tr("url_required", self.language), error=True)
            return
        self.analysis_generation += 1
        generation = self.analysis_generation
        self.analyzing = True
        self.analyzed_input = url
        self.analyze_button.configure(state="disabled", text=tr("analyzing", self.language))
        self.download_button.configure(
            state="disabled", fg_color=SURFACE_ALT, hover_color=SURFACE_ALT
        )
        self.media = None
        self.media_card.grid_forget()
        self._output_card.grid_remove()
        self._set_status(tr("checking_public", self.language))
        self.analysis_thread = threading.Thread(
            target=self._analyze_worker, args=(url, generation), daemon=True
        )
        self.analysis_thread.start()

    def _analyze_worker(self, url: str, generation: int) -> None:
        try:
            media = analyze_media(url, self.tools)
            try:
                thumbnail = fetch_thumbnail(media.thumbnail)
            except DownloaderError:
                thumbnail = None
            self.events.put(("analysis_ok", generation, media, thumbnail))
        except DownloaderError as exc:
            self.events.put(("analysis_error", generation, str(exc)))
        except Exception:
            logger.error("Unexpected error in analysis worker:\n%s", traceback.format_exc())
            self.events.put(("analysis_unexpected", generation))

    def _show_media(self, media: MediaInfo, thumbnail: bytes | None = None) -> None:
        self.media = media
        self._show_thumbnail(thumbnail)
        self.platform_label.configure(text=media.platform.label.upper())
        self.media_title.configure(text=media.title)
        meta = " · ".join(
            item for item in (media.creator, format_duration(media.duration, self.language)) if item
        )
        self.media_meta.configure(text=meta)
        self.media_card.grid(row=1, column=0, pady=(0, 12), sticky="ew")
        self._output_card.grid(row=2, column=0, pady=(0, 4), sticky="ew")
        values = [f"{height}p" for height in reversed(media.qualities)]
        self.quality_menu.configure(values=values)
        self.quality_menu.set(f"{media.default_quality}p")
        self._refresh_download_state()
        self._set_status(tr("link_ready", self.language), success=True)

    def _show_thumbnail(self, payload: bytes | None) -> None:
        if payload:
            try:
                with Image.open(BytesIO(payload)) as source:
                    if source.width * source.height > 20_000_000:
                        raise ValueError("Thumbnail dimensions are too large")
                    prepared = ImageOps.fit(source.convert("RGB"), (188, 106))
                self.thumbnail_image = ctk.CTkImage(
                    light_image=prepared, dark_image=prepared, size=(188, 106)
                )
            except (OSError, ValueError, Image.DecompressionBombError):
                self.thumbnail_image = self.thumbnail_placeholder
        else:
            self.thumbnail_image = self.thumbnail_placeholder
        self.thumbnail_label.configure(image=self.thumbnail_image)

    def _current_output_kind(self) -> str:
        return "audio" if self.output_type.get() == tr("audio_mp3", self.language) else "video"

    def _refresh_download_state(self) -> None:
        ready = self.media is not None and bool(self.rights_checkbox.get())
        self.download_button.configure(
            state="normal" if ready else "disabled",
            fg_color=PRIMARY if ready else SURFACE_ALT,
            hover_color=PRIMARY_HOVER if ready else SURFACE_ALT,
            text_color="#071008" if ready else TEXT,
        )

    def _refresh_format_controls(self) -> None:
        if self._current_output_kind() == "audio":
            self.quality_label.configure(text=tr("audio_quality", self.language))
            self.quality_menu.configure(values=["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
            self.quality_menu.set("192 kbps")
        else:
            self.quality_label.configure(text=tr("video_quality", self.language))
            if self.media:
                values = [f"{height}p" for height in reversed(self.media.qualities)]
                self.quality_menu.configure(values=values)
                self.quality_menu.set(f"{self.media.default_quality}p")
            else:
                self.quality_menu.configure(values=["1080p", "720p", "480p", "360p"])
                self.quality_menu.set("1080p")

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            title=tr("destination_dialog", self.language),
            initialdir=self.destination_entry.get(),
        )
        if selected:
            self.destination_entry.delete(0, "end")
            self.destination_entry.insert(0, selected)
            self.preferences.destination = selected
            save_settings(self.preferences)

    def _enqueue_download(self) -> None:
        if not self.media:
            self._set_status(tr("analyze_first", self.language), error=True)
            return
        if not self.rights_checkbox.get():
            self._set_status(tr("confirm_permission", self.language), error=True)
            return
        destination_text = self.destination_entry.get().strip()
        if not destination_text:
            self._set_status(tr("choose_destination", self.language), error=True)
            return
        destination = Path(destination_text).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._set_status(tr("destination_write_error", self.language), error=True)
            return
        if not destination.is_dir():
            self._set_status(tr("destination_invalid", self.language), error=True)
            return
        self.preferences.destination = str(destination)
        save_settings(self.preferences)

        selection = self.quality_menu.get()
        output_type = self._current_output_kind()
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
        except DuplicateJobError:
            self._set_status(tr("duplicate", self.language), error=True)
            return
        self._empty_queue_container.grid_remove()
        card = QueueCard(
            self.queue_frame,
            job,
            lambda job_id=job.job_id: self._cancel_job(job_id),
            self.language,
        )
        card.grid(row=job.job_id, column=0, pady=(0, 8), sticky="ew")
        self.queue_cards[job.job_id] = card
        self.download_queue.put(job)
        self._refresh_queue_header()
        self.rights_checkbox.deselect()
        self._refresh_download_state()
        self._set_status(tr("queued", self.language), success=True)

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
                logger.error("Unexpected error in download worker:\n%s", traceback.format_exc())
                self.queue_manager.finish(job.job_id, "failed")
                self.events.put(("failed_unexpected", job.job_id))
            finally:
                self.download_queue.task_done()

    def _cancel_job(self, job_id: int) -> None:
        card = self.queue_cards.get(job_id)
        if card and self.queue_manager.cancel(job_id):
            card.retranslate(self.language)

    def _clear_finished_jobs(self) -> None:
        identifiers = self.queue_manager.remove_finished()
        for job_id in identifiers:
            card = self.queue_cards.pop(job_id, None)
            if card:
                card.destroy()
        if not self.queue_cards:
            self._empty_queue_container.grid(row=0, column=0, padx=18, pady=28)
        self._refresh_queue_header()
        if identifiers:
            self._set_status(
                tr("removed_finished", self.language, count=len(identifiers)), success=True
            )

    def _refresh_queue_header(self) -> None:
        # Single lock acquisition to read all three counters atomically
        c: QueueCounts = self.queue_manager.counts()
        if not c.total:
            summary = tr("queue_empty_count", self.language)
        elif c.active:
            summary = tr("queue_active_count", self.language, active=c.active, finished=c.finished)
        else:
            summary = tr("queue_finished_count", self.language, finished=c.finished)
        self.queue_summary_label.configure(text=summary)
        self.clear_queue_button.configure(state="normal" if c.finished else "disabled")

    _MAX_EVENTS_PER_TICK = 20

    def _process_events(self) -> None:
        processed = 0
        try:
            while processed < self._MAX_EVENTS_PER_TICK:
                event = self.events.get_nowait()
                processed += 1
                kind = event[0]
                if kind.startswith("analysis_"):
                    if event[1] != self.analysis_generation:
                        continue
                    self.analyzing = False
                    self.analyze_button.configure(state="normal", text=tr("analyze", self.language))
                    if kind == "analysis_ok":
                        self._show_media(event[2], event[3])
                    elif kind == "analysis_error":
                        self._set_status(
                            localize_engine_error(event[2], self.language), error=True
                        )
                    else:
                        self._set_status(tr("unexpected_analysis", self.language), error=True)
                elif kind == "progress":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.update_progress(event[2])
                elif kind == "finished":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.finish(event[2])
                    self._set_status(tr("download_complete", self.language), success=True)
                    self._refresh_queue_header()
                elif kind == "cancelled":
                    card = self.queue_cards.get(event[1])
                    if card:
                        card.fail("", cancelled=True)
                    self._refresh_queue_header()
                elif kind in {"failed", "failed_unexpected"}:
                    card = self.queue_cards.get(event[1])
                    message = (
                        localize_engine_error(event[2], self.language)
                        if kind == "failed"
                        else tr("unexpected_download", self.language)
                    )
                    if card:
                        card.failure_message = event[2] if kind == "failed" else ""
                        card.retranslate(self.language)
                    self._set_status(message, error=True)
                    self._refresh_queue_header()
        except queue.Empty:
            pass
        if not self.closing:
            self.after(100, self._process_events)

    def _request_close(self) -> None:
        if self.closing:
            return
        # Single atomic read — avoids acquiring the queue lock multiple times
        c = self.queue_manager.counts()
        operations = c.active + int(
            bool(self.analysis_thread and self.analysis_thread.is_alive())
        )
        if operations and not messagebox.askyesno(
            tr("close_title", self.language), tr("close_question", self.language)
        ):
            return
        self.closing = True
        self.queue_manager.cancel_all()
        self.download_queue.put(None)
        self.analyze_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self._set_status(tr("closing", self.language))
        # Hard deadline: destroy even if workers are still alive after the timeout
        self._shutdown_deadline = self.after(_SHUTDOWN_TIMEOUT_MS, self._force_destroy)
        self._wait_for_shutdown()

    def _force_destroy(self) -> None:
        """Force application exit when workers do not stop within the shutdown timeout."""
        logger.warning("Shutdown deadline reached — forcing application exit.")
        self.destroy()

    def _wait_for_shutdown(self) -> None:
        analysis_running = bool(self.analysis_thread and self.analysis_thread.is_alive())
        if not self.download_worker.is_alive() and not analysis_running:
            # Workers finished cleanly — cancel the hard deadline before destroying
            if self._shutdown_deadline:
                self.after_cancel(self._shutdown_deadline)
                self._shutdown_deadline = None
            self.destroy()
            return
        self.after(100, self._wait_for_shutdown)

    def _set_status(self, message: str, error: bool = False, success: bool = False) -> None:
        color = DANGER if error else SUCCESS if success else TEXT_MUTED
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=message, text_color=color)

    def _apply_appearance(self, value: str) -> None:
        mode = {"system": "System", "light": "Light", "dark": "Dark"}.get(value, "System")
        ctk.set_appearance_mode(mode)
        if hasattr(self, "bg_canvas"):
            self.after(50, self._update_canvas_theme)

    def _update_canvas_theme(self) -> None:
        resolved_mode = ctk.get_appearance_mode()
        bg_color = resolved(APP_BACKGROUND, resolved_mode)
        self.bg_canvas.configure(bg=bg_color)
        self._schedule_draw_background()

    def _change_appearance(self, label: str) -> None:
        labels = appearance_labels(self.language)
        self.preferences.appearance = next(
            (code for code, translated in labels.items() if translated == label), "system"
        )
        self._apply_appearance(self.preferences.appearance)
        save_settings(self.preferences)

    def _change_language(self, label: str) -> None:
        output_kind = self._current_output_kind()
        self.language = language_from_label(label)
        self.preferences.language = self.language
        save_settings(self.preferences)
        self._apply_translations(output_kind)

    def _apply_translations(self, output_kind: str | None = None) -> None:
        if output_kind is None:
            output_kind = self._current_output_kind() if hasattr(self, "output_type") else "video"
        self.title(f"{tr('app_title', self.language)} v{APP_VERSION}")
        self.sidebar_product_label.configure(text=tr("sidebar_product", self.language))
        ready = bool(self.tools and self.tools.ffmpeg and self.tools.ffprobe)
        self.tools_label.configure(text=tr("tools_ready" if ready else "tools_missing", self.language))
        self.sponsor_button.configure(text=tr("sponsor", self.language))
        self.language_label.configure(text=tr("language", self.language))
        self.appearance_label.configure(text=tr("appearance", self.language))
        self.version_label.configure(text=tr("version", self.language, version=APP_VERSION))
        self.language_menu.set(LANGUAGE_NAMES[self.language])
        labels = appearance_labels(self.language)
        self.appearance_menu.configure(values=list(labels.values()))
        self.appearance_menu.set(labels[self.preferences.appearance])
        self.heading_label.configure(text=tr("heading", self.language))
        self.subheading_label.configure(text=tr("subheading", self.language))
        self.step_link_label.configure(text=f"{tr('step_link', self.language)}  ·  Ctrl+L")
        self.url_entry.configure(placeholder_text=tr("url_placeholder", self.language))
        self.paste_button.configure(text=tr("paste", self.language))
        self.clear_link_button.configure(
            text="×", state="normal" if self.url_entry.get().strip() else "disabled"
        )
        self.analyze_button.configure(
            text=tr("analyzing" if self.analyzing else "analyze", self.language)
        )
        self.step_output_label.configure(text=tr("step_output", self.language))
        self.format_label.configure(text=tr("format", self.language))
        values = [tr("video_mp4", self.language), tr("audio_mp3", self.language)]
        self.output_type.configure(values=values)
        self.output_type.set(values[1] if output_kind == "audio" else values[0])
        self.save_label.configure(text=tr("save_to", self.language))
        self.choose_button.configure(text=tr("choose", self.language))
        self.rights_checkbox.configure(text=tr("rights", self.language))
        self.download_button.configure(text=tr("add_queue", self.language))
        self.local_flow_heading.configure(text=tr("local_flow_heading", self.language))
        flow_keys = ("public_link", "local_processing", "your_folder")
        for index, ((title, description), key) in enumerate(
            zip(self.local_flow_steps, flow_keys, strict=True), start=1
        ):
            title.configure(text=f"{index:02}  {tr(f'flow_{key}', self.language)}")
            description.configure(text=tr(f"flow_{key}_description", self.language))
        self.queue_heading_label.configure(text=tr("step_queue", self.language))
        self.help_button.configure(text=tr("keyboard_help", self.language))
        self.clear_queue_button.configure(text=tr("clear_finished", self.language))
        self.empty_queue.configure(text=tr("queue_empty", self.language))
        self._refresh_format_controls()
        self._refresh_queue_header()
        if self.media:
            meta = " · ".join(
                item
                for item in (
                    self.media.creator,
                    format_duration(self.media.duration, self.language),
                )
                if item
            )
            self.media_meta.configure(text=meta)
        # Defer retranslation to the next event-loop tick: prevents a stall when
        # many queue cards exist (each configure() call holds the main thread).
        _lang = self.language
        _cards = list(self.queue_cards.values())

        def _retranslate() -> None:
            for card in _cards:
                card.retranslate(_lang)

        self.after(0, _retranslate)
        if self.analyzing:
            self._set_status(tr("checking_public", self.language))
        elif self.media:
            self._set_status(tr("link_ready", self.language), success=True)
        else:
            self._set_status(tr("ready", self.language))

    def _schedule_draw_background(self, event: Any = None) -> None:
        """Debounce canvas redraws to prevent UI freeze on rapid resize/restore events."""
        if self._draw_pending:
            self.after_cancel(self._draw_pending)
        self._draw_pending = self.after(_DRAW_DEBOUNCE_MS, self._draw_background)

    def _draw_background(self, event: Any = None) -> None:
        """Render a subtle high-tech dot grid and audio waves on the workspace background canvas."""
        self._draw_pending = None
        canvas = self.bg_canvas
        canvas.delete("all")

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        resolved_mode = ctk.get_appearance_mode().lower()
        is_dark = resolved_mode == "dark"
        # Midnight Neon aesthetic
        grid_color = "#0B1021" if is_dark else "#E5ECF6"
        neon_cyan = "#00E5FF" if is_dark else "#00B8CC"
        neon_purple = "#9D00FF" if is_dark else "#7A00CC"

        # 1. Subtle, sparse grid lines for a digital/cyberpunk feel
        grid_spacing = 64
        for x in range(0, w, grid_spacing):
            canvas.create_line(x, 0, x, h, fill=grid_color, dash=(2, 4))
        for y in range(0, h, grid_spacing):
            canvas.create_line(0, y, w, y, fill=grid_color, dash=(2, 4))

        # 2. Render sharp neon laser curves (sine waves)
        # math is imported at module level — no per-call import overhead
        points1 = []
        points2 = []
        points3 = []
        for x in range(0, w, 10):
            # Electric Purple wave
            y1 = (h * 0.85) + math.sin(x * 0.003) * 60 + math.cos(x * 0.015) * 10
            points1.append((x, y1))
            # Neon Cyan wave
            y2 = (h * 0.80) + math.sin(x * 0.005 + 1.0) * 45 - math.cos(x * 0.008) * 15
            points2.append((x, y2))
            # Secondary subtle cyan wave
            y3 = (h * 0.90) + math.sin(x * 0.002 + 0.5) * 30
            points3.append((x, y3))

        if len(points1) > 1:
            canvas.create_line(points1, fill=neon_purple, width=3, smooth=True, capstyle="round")
        if len(points2) > 1:
            canvas.create_line(points2, fill=neon_cyan, width=2, smooth=True, capstyle="round")
        if len(points3) > 1:
            canvas.create_line(points3, fill=neon_cyan, width=1, smooth=True, stipple="gray50")


def main() -> None:
    ctk.set_default_color_theme("blue")

    # Hidden root required so that Toplevel works before CTk is initialised
    _root = tk.Tk()
    _root.withdraw()

    logo_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets/thebeetales-logo.png"
    splash = SplashScreen(_root, logo_path)
    splash.update()

    # Detect tools in a background thread while the splash screen is visible
    _tools_result: list[Any] = []

    def _detect() -> None:
        _tools_result.append(detect_tools())
        splash.signal_ready()

    threading.Thread(target=_detect, daemon=True).start()

    # Actively wait until the splash animation finishes and tools have been detected
    while splash.winfo_exists():
        try:
            _root.update()
            time.sleep(0.016)  # ~60 fps cap — prevents 100% CPU during splash
        except tk.TclError:
            break

    _root.destroy()

    app = BeeTalesDownloaderApp()
    # Assign the already-detected tools before building the main window
    if _tools_result:
        app.tools = _tools_result[0]
    else:
        app.tools = detect_tools()
    app._apply_translations()
    app.mainloop()


if __name__ == "__main__":
    main()
