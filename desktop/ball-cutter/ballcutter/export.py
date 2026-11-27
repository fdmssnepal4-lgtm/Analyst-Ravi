"""Cutting clips, joining them into one reel, and writing CSV / Premiere EDL lists."""
from __future__ import annotations

import csv
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Callable

from .detect import Cancelled, Clip
from .ffmpeg_tools import VideoInfo, run

COPY_EXTS = {".mp4", ".mov", ".m4v", ".mkv"}


@dataclass
class ExportOptions:
    out_dir: str
    accurate: bool = False  # False: instant stream copy. True: re-encode, frame-exact cuts
    clips: bool = True
    reel: bool = True
    csv: bool = True
    edl: bool = True
    over_naming: bool = False  # Over 3 Ball 4 instead of Ball 017
    balls_per_over: int = 6
    prefix: str = ""


def fmt_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    if h >= 1:
        return f"{int(h)}:{int(m):02d}:{s:04.1f}"
    return f"{int(m):02d}:{s:04.1f}"


def ball_label(index: int, opts: ExportOptions) -> str:
    """index is 1-based."""
    if opts.over_naming:
        bpo = max(1, opts.balls_per_over)
        return f"Over{(index - 1) // bpo + 1:02d}_Ball{(index - 1) % bpo + 1}"
    return f"Ball_{index:03d}"


def safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", s).strip(" .") or "video"


def cut(src: str, start: float, end: float, out: str, info: VideoInfo, accurate: bool) -> None:
    dur = max(0.1, end - start)
    if accurate:
        base = ["-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{dur:.3f}",
                "-map", "0:v:0", "-map", "0:a:0?"]
        audio = ["-c:a", "aac", "-b:a", "160k"] if info.has_audio else ["-an"]
        tries = [
            ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"],
            ["-c:v", "mpeg4", "-q:v", "2"],
        ]
        last = ""
        for vcodec in tries:
            p = run(base + vcodec + audio + ["-movflags", "+faststart", out])
            if p.returncode == 0:
                return
            last = p.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"FFmpeg could not encode {os.path.basename(out)}:\n{last[-600:]}")
    p = run(["-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{dur:.3f}",
             "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-avoid_negative_ts", "make_zero", out])
    if p.returncode != 0:
        raise RuntimeError(f"FFmpeg could not cut {os.path.basename(out)}:\n"
                           + p.stderr.decode("utf-8", "replace")[-600:])


def out_ext(src: str, accurate: bool) -> str:
    ext = os.path.splitext(src)[1].lower()
    if not accurate and ext in COPY_EXTS:
        return ext
    return ".mp4"


def concat(files: list[str], out: str) -> None:
    fd, lst = tempfile.mkstemp(suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for p in files:
                f.write("file '" + os.path.abspath(p).replace("\\", "/").replace("'", "'\\''") + "'\n")
        mov = ["-movflags", "+faststart"] if out.lower().endswith((".mp4", ".mov", ".m4v")) else []
        p = run(["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                 "-c", "copy", *mov, out])
        if p.returncode != 0:
            raise RuntimeError("Could not join clips into one reel:\n" + p.stderr.decode("utf-8", "replace")[-600:])
    finally:
        os.remove(lst)


def _tc(t: float, fps: int) -> str:
    frames = int(round(t * fps))
    ff = frames % fps
    s = frames // fps
    return f"{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}:{ff:02d}"


def write_edl(path: str, src: str, clips: list[Clip], labels: list[str], fps: float, title: str) -> None:
    """CMX 3600 EDL. In Premiere: File > Import, pick the .edl, then link the media."""
    r = max(1, int(round(fps)))
    name = os.path.basename(src)
    reel = "AX"
    lines = [f"TITLE: {title[:60]}", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for n, (c, lab) in enumerate(zip(clips, labels), 1):
        d = c.end - c.start
        lines.append(f"{n:03d}  {reel:<8} V     C        {_tc(c.start, r)} {_tc(c.end, r)} "
                     f"{_tc(rec, r)} {_tc(rec + d, r)}")
        lines.append(f"* FROM CLIP NAME: {name}")
        lines.append(f"* COMMENT: {lab}")
        lines.append("")
        rec += d
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines))


def export_video(
    src: str,
    info: VideoInfo,
    clips: list[Clip],
    opts: ExportOptions,
    progress: Callable[[float, str], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> str:
    """Export one video's enabled clips. Returns the folder written to."""
    use = [c for c in sorted(clips, key=lambda c: c.start) if c.enabled]
    stem = safe_name((opts.prefix + " " if opts.prefix else "") + os.path.splitext(os.path.basename(src))[0])
    folder = os.path.join(opts.out_dir, stem)
    os.makedirs(folder, exist_ok=True)
    labels = [ball_label(i, opts) for i in range(1, len(use) + 1)]
    ext = out_ext(src, opts.accurate)
    files: list[str] = []
    steps = len(use) + (1 if opts.reel else 0) or 1
    need_files = opts.clips or opts.reel
    for i, (c, lab) in enumerate(zip(use, labels)):
        if cancel and cancel():
            raise Cancelled()
        if progress:
            progress(i / steps, f"{stem}: {lab} ({i + 1}/{len(use)})")
        if need_files:
            out = os.path.join(folder, f"{stem}_{lab}{ext}")
            cut(src, c.start, c.end, out, info, opts.accurate)
            files.append(out)
    if opts.reel and files:
        if progress:
            progress(len(use) / steps, f"{stem}: joining all balls into one reel")
        concat(files, os.path.join(folder, f"{stem}_ALL_BALLS{ext}"))
        if not opts.clips:
            for f in files:
                os.remove(f)
    if opts.csv:
        with open(os.path.join(folder, f"{stem}_balls.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["ball", "start", "end", "shot_moment", "start_seconds", "end_seconds",
                        "length_seconds", "confidence", "added_by_hand", "source_video"])
            for c, lab in zip(use, labels):
                w.writerow([lab, fmt_time(c.start), fmt_time(c.end), fmt_time(c.peak), f"{c.start:.2f}",
                            f"{c.end:.2f}", f"{c.length:.2f}", f"{c.score:.2f}", "yes" if c.manual else "no",
                            os.path.basename(src)])
    if opts.edl and use:
        write_edl(os.path.join(folder, f"{stem}_premiere.edl"), src, use, labels, info.fps, stem)
    if progress:
        progress(1.0, f"{stem}: done")
    return folder
