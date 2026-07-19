"""Local BeeTales desktop application."""

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
from localization import (
    LANGUAGE_NAMES,
    appearance_labels,
    language_from_label,
    localize_engine_error,
    tr,
)
from queue_manager import DuplicateJobError, QueueJob, QueueManager
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
)


SPONSOR_URL = "https://github.com/sponsors/Sorairei"
CARD_RADIUS = 16


def resource_path(relative: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / relative


def format_duration(seconds: int | None, language: str) -> str:
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
            self.status_label.configure(text=tr("completed", language), text_color=SUCCESS)
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
            self.status_label.configure(text=tr("cancelled", language), text_color=TEXT_MUTED)
            self.action.configure(text=tr("cancelled", language), state="disabled")
        elif state == "failed":
            message = (
                localize_engine_error(self.failure_message, language)
                if self.failure_message
                else tr("unexpected_download", language)
            )
            self.status_label.configure(text=message, text_color=DANGER)
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
        self.retranslate(self.language)

    def fail(self, message: str, cancelled: bool = False) -> None:
        self.failure_message = message
        if cancelled:
            self.job.state = "cancelled"
        self.retranslate(self.language)


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
        self.shutdown_polls = 0
        self.tools = detect_tools()

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

        identity = ctk.CTkFrame(
            sidebar,
            fg_color=MIDNIGHT_RAISED,
            border_width=1,
            border_color="#274732",
            corner_radius=14,
        )
        identity.grid(row=2, column=0, padx=16, pady=(6, 12), sticky="ew")
        self.sora_image = self._ctk_image("assets/sora-avatar.png", (78, 78))
        ctk.CTkLabel(identity, text="", image=self.sora_image).pack(pady=(12, 4))
        self.local_title_label = ctk.CTkLabel(
            identity,
            text="",
            text_color=SIDEBAR_TEXT,
            justify="center",
            wraplength=176,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
        )
        self.local_title_label.pack(padx=10)
        self.local_description_label = ctk.CTkLabel(
            identity, text="", text_color=SIDEBAR_MUTED, justify="center"
        )
        self.local_description_label.pack(padx=10, pady=(3, 12))

        sidebar_actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_actions.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")
        sidebar_actions.grid_columnconfigure(0, weight=1)
        ready = bool(self.tools.ffmpeg and self.tools.ffprobe)
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
            height=38,
            fg_color=SPONSOR,
            hover_color=SPONSOR_HOVER,
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

        header = ctk.CTkFrame(workspace, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(22, 14), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="w")
        self.heading_label = ctk.CTkLabel(
            heading,
            text="",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=28, weight="bold"),
        )
        self.heading_label.pack(anchor="w")
        self.subheading_label = ctk.CTkLabel(
            heading,
            text="",
            text_color=TEXT_MUTED,
            anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
        )
        self.subheading_label.pack(anchor="w", pady=(2, 0))

        assurance = ctk.CTkFrame(
            header,
            fg_color=ACCENT_SOFT,
            border_width=1,
            border_color=BORDER_STRONG,
            corner_radius=14,
        )
        assurance.grid(row=0, column=1, padx=(14, 0), sticky="e")
        self.header_mascot = self._ctk_image("assets/frog-mascot.png", (50, 50))
        ctk.CTkLabel(assurance, text="", image=self.header_mascot).grid(
            row=0, column=0, padx=(10, 4), pady=7
        )
        assurance_text = ctk.CTkFrame(assurance, fg_color="transparent")
        assurance_text.grid(row=0, column=1, padx=(0, 12), pady=7, sticky="w")
        self.local_badge_label = ctk.CTkLabel(
            assurance_text,
            text="",
            text_color=ACCENT_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
        )
        self.local_badge_label.pack(anchor="w")
        self.private_badge_label = ctk.CTkLabel(
            assurance_text, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
        )
        self.private_badge_label.pack(anchor="w")

        content = ctk.CTkFrame(workspace, fg_color="transparent")
        content.grid(row=1, column=0, padx=28, pady=(0, 10), sticky="nsew")
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

        queue_panel = ctk.CTkFrame(
            content,
            fg_color=SURFACE,
            border_width=1,
            border_color=BORDER,
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
        self.empty_queue = ctk.CTkLabel(
            self.queue_frame,
            text="",
            text_color=TEXT_MUTED,
            justify="center",
            wraplength=280,
        )
        self.empty_queue.grid(row=0, column=0, padx=18, pady=34)

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

    def _build_output_card(self) -> None:
        card = ctk.CTkFrame(
            self.workflow, fg_color=SURFACE, border_width=1, border_color=BORDER,
            corner_radius=CARD_RADIUS,
        )
        card.grid(row=2, column=0, pady=(0, 4), sticky="ew")
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
        self.empty_queue.grid_remove()
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
            self.empty_queue.grid(row=0, column=0, padx=18, pady=34)
        self._refresh_queue_header()
        if identifiers:
            self._set_status(
                tr("removed_finished", self.language, count=len(identifiers)), success=True
            )

    def _refresh_queue_header(self) -> None:
        total = self.queue_manager.total_count
        active = self.queue_manager.active_count
        finished = self.queue_manager.finished_count
        if not total:
            summary = tr("queue_empty_count", self.language)
        elif active:
            summary = tr("queue_active_count", self.language, active=active, finished=finished)
        else:
            summary = tr("queue_finished_count", self.language, finished=finished)
        self.queue_summary_label.configure(text=summary)
        self.clear_queue_button.configure(state="normal" if finished else "disabled")

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
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
        operations = self.queue_manager.active_count + int(
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
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=message, text_color=color)

    def _apply_appearance(self, value: str) -> None:
        ctk.set_appearance_mode({"system": "System", "light": "Light", "dark": "Dark"}.get(value, "System"))

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
        self.local_title_label.configure(text=tr("local_title", self.language))
        self.local_description_label.configure(text=tr("local_description", self.language))
        ready = bool(self.tools.ffmpeg and self.tools.ffprobe)
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
        self.local_badge_label.configure(text=tr("local_badge", self.language))
        self.private_badge_label.configure(text=tr("private_badge", self.language))
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
        for card in self.queue_cards.values():
            card.retranslate(self.language)
        if self.analyzing:
            self._set_status(tr("checking_public", self.language))
        elif self.media:
            self._set_status(tr("link_ready", self.language), success=True)
        else:
            self._set_status(tr("ready", self.language))


def main() -> None:
    ctk.set_default_color_theme("blue")
    app = BeeTalesDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
