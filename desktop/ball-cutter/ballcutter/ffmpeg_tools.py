"""Finding and running FFmpeg, and reading basic facts about a video file."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


def ffmpeg_exe() -> str:
    """Path to an FFmpeg binary: the one bundled with the app first, then PATH."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError(
        "FFmpeg was not found. Reinstall Ball Cutter, or install FFmpeg and add it to PATH."
    )


def popen_kwargs() -> dict:
    """Keep Windows from flashing a console window for every FFmpeg call."""
    if os.name == "nt":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def run(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        **popen_kwargs(),
    )


@dataclass
class VideoInfo:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool


_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VID = re.compile(r"Stream #\S+.*?Video:.*?(\d{2,5})x(\d{2,5})")
_FPS = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_TBR = re.compile(r"(\d+(?:\.\d+)?)\s*tbr")


def probe(path: str) -> VideoInfo:
    proc = run(["-i", path], timeout=60)
    text = proc.stderr.decode("utf-8", errors="replace")
    vid_line = next((l for l in text.splitlines() if "Video:" in l and "Stream #" in l), None)
    if vid_line is None:
        raise RuntimeError(f"No video stream found in {os.path.basename(path)}")
    duration = 0.0
    m = _DUR.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    width = height = 0
    m = _VID.search(vid_line)
    if m:
        width, height = int(m.group(1)), int(m.group(2))
    fps = 0.0
    m = _FPS.search(vid_line) or _TBR.search(vid_line)
    if m:
        fps = float(m.group(1))
    if not (1.0 <= fps <= 1000.0):
        fps = 30.0
    has_audio = any("Audio:" in l and "Stream #" in l for l in text.splitlines())
    return VideoInfo(path, duration, fps, width, height, has_audio)


def extract_frame(path: str, t: float, out_png: str, width: int = 320) -> bool:
    proc = run(
        ["-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path,
         "-frames:v", "1", "-vf", f"scale={width}:-2", out_png],
        timeout=60,
    )
    return proc.returncode == 0 and os.path.exists(out_png)


def open_with_system_player(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
