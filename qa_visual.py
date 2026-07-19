"""Captura local automatizada de la ventana compilada para control visual."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab


WM_CLOSE = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def process_name(process_id: int) -> str:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)


def close_window_process(window_handle: int, process_id: int) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.PostMessageW(window_handle, WM_CLOSE, 0, 0)
    process_handle = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, process_id)
    if not process_handle:
        return
    try:
        if kernel32.WaitForSingleObject(process_handle, 5000) == WAIT_TIMEOUT:
            kernel32.TerminateProcess(process_handle, 1)
            kernel32.WaitForSingleObject(process_handle, 5000)
    finally:
        kernel32.CloseHandle(process_handle)


def find_windows(executable_name: str) -> list[tuple[int, int, Rect]]:
    user32 = ctypes.windll.user32
    matches: list[tuple[int, int, Rect]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(handle: int, _parameter: int) -> bool:
        window_process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(window_process_id))
        if (
            not user32.IsWindowVisible(handle)
            or process_name(window_process_id.value).casefold() != executable_name.casefold()
        ):
            return True
        length = user32.GetWindowTextLengthW(handle)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, title, length + 1)
        bounds = Rect()
        if "BeeTales Video Downloader" in title.value and user32.GetWindowRect(handle, ctypes.byref(bounds)):
            matches.append((handle, window_process_id.value, bounds))
        return True

    user32.EnumWindows(callback, 0)
    return matches


def capture(executable: Path, output: Path, timeout: float = 30.0) -> dict[str, object]:
    if sys.platform != "win32":
        raise RuntimeError("Esta prueba visual solo funciona en Windows.")
    if not executable.is_file():
        raise FileNotFoundError(executable)

    ctypes.windll.user32.SetProcessDPIAware()
    existing_handles = {item[0] for item in find_windows(executable.name)}
    process = subprocess.Popen([str(executable)])
    window: tuple[int, int, Rect] | None = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            candidates = [
                item for item in find_windows(executable.name) if item[0] not in existing_handles
            ]
            if len(candidates) == 1:
                window = candidates[0]
                break
            time.sleep(0.25)
        if not window:
            raise RuntimeError("La ventana principal no aparecio dentro del tiempo esperado.")

        handle, window_process_id, bounds = window
        ctypes.windll.user32.ShowWindow(handle, 5)
        ctypes.windll.user32.BringWindowToTop(handle)
        ctypes.windll.user32.SetForegroundWindow(handle)
        time.sleep(1.0)
        output.parent.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(window=handle, include_layered_windows=True)
        image.save(output, format="PNG")
        return {
            "path": str(output.resolve()),
            "width": image.width,
            "height": image.height,
            "loader_process_id": process.pid,
            "window_process_id": window_process_id,
        }
    finally:
        if window:
            close_window_process(window[0], window[1])
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--executable",
        type=Path,
        default=Path("dist/BeeTales Video Downloader.exe"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/qa/beetales-window.png"),
    )
    arguments = parser.parse_args()
    print(capture(arguments.executable, arguments.output))


if __name__ == "__main__":
    main()
