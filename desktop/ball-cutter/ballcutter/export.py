"""Cutting clips, joining them into one reel, and writing CSV / Premiere EDL lists."""
from __future__ import annotations

import csv
import io
import shutil
import json
import os
import zipfile
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
    by_player: bool = True  # also sort the clips into a folder per batter and per bowler
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
        who = " ".join(x for x in (c.batter and f"batter {c.batter}", c.bowler and f"bowler {c.bowler}") if x)
        lines.append(f"* COMMENT: {lab}" + (f" {who}" if who else ""))
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
    """Export one video's enabled clips. Returns the folder written to and, for each clip file made,
    (path, clip) so the files can also be sorted by player."""
    use = [c for c in sorted(clips, key=lambda c: c.start) if c.enabled]
    stem = video_stem(src, opts)
    folder = os.path.join(opts.out_dir, stem)
    os.makedirs(folder, exist_ok=True)
    labels = [ball_label(i, opts) for i in range(1, len(use) + 1)]
    ext = out_ext(src, opts.accurate)
    files: list[str] = []
    steps = len(use) + (1 if opts.reel else 0) or 1
    need_files = opts.clips or opts.reel or opts.by_player
    made: list[tuple[str, Clip]] = []
    for i, (c, lab) in enumerate(zip(use, labels)):
        if cancel and cancel():
            raise Cancelled()
        if progress:
            progress(i / steps, f"{stem}: {lab} ({i + 1}/{len(use)})")
        if need_files:
            out = os.path.join(folder, f"{stem}_{lab}{player_suffix(c)}{ext}")
            cut(src, c.start, c.end, out, info, opts.accurate)
            files.append(out)
            made.append((out, c))
    if opts.reel and files:
        if progress:
            progress(len(use) / steps, f"{stem}: joining all balls into one reel")
        concat(files, os.path.join(folder, f"{stem}_ALL_BALLS{ext}"))
    if opts.csv:
        with open(os.path.join(folder, f"{stem}_balls.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["ball", "batter", "bowler", "start", "end", "shot_moment", "start_seconds", "end_seconds",
                        "length_seconds", "confidence", "added_by_hand", "source_video"])
            for c, lab in zip(use, labels):
                w.writerow([lab, c.batter, c.bowler, fmt_time(c.start), fmt_time(c.end), fmt_time(c.peak),
                            f"{c.start:.2f}",
                            f"{c.end:.2f}", f"{c.length:.2f}", f"{c.score:.2f}", "yes" if c.manual else "no",
                            os.path.basename(src)])
    if opts.edl and use:
        write_edl(os.path.join(folder, f"{stem}_premiere.edl"), src, use, labels, info.fps, stem)
    if progress:
        progress(1.0, f"{stem}: done")
    return folder, made


def video_stem(src: str, opts: ExportOptions) -> str:
    return safe_name((opts.prefix + " " if opts.prefix else "") + os.path.splitext(os.path.basename(src))[0])


def player_suffix(c: Clip) -> str:
    parts = []
    if c.batter:
        parts.append(c.batter)
    if c.bowler:
        parts.append(("bowled_" if not c.batter else "vs_") + c.bowler)
    return ("_" + "_".join(safe_name(p).replace(" ", "-") for p in parts)) if parts else ""


def remove_clip_files(made: list[tuple[str, Clip]]) -> None:
    for path, _ in made:
        try:
            os.remove(path)
        except OSError:
            pass


def _link_or_copy(src: str, dst: str) -> None:
    """Hard link when possible (no extra disk space), otherwise copy."""
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def export_players(
    made: list[tuple[str, Clip]],
    out_dir: str,
    reels: bool = True,
    progress: Callable[[float, str], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> tuple[str, list[str]]:
    """Sort clip files into Players/Batter - <name> and Players/Bowler - <name>, each with that player's
    clips and (if reels) one video of all their balls. Returns the Players folder and any warnings."""
    groups: dict[str, list[str]] = {}
    for path, c in made:
        if c.batter:
            groups.setdefault(f"Batter - {safe_name(c.batter)}", []).append(path)
        if c.bowler:
            groups.setdefault(f"Bowler - {safe_name(c.bowler)}", []).append(path)
    root = os.path.join(out_dir, "Players")
    warnings: list[str] = []
    if not groups:
        return root, ["No batter or bowler names were set, so no player folders were made."]
    os.makedirs(root, exist_ok=True)
    rows = []
    for k, (name, files) in enumerate(sorted(groups.items())):
        if cancel and cancel():
            raise Cancelled()
        if progress:
            progress(k / len(groups), f"Player folders: {name} ({len(files)} balls)")
        d = os.path.join(root, name)
        os.makedirs(d, exist_ok=True)
        for f in files:
            _link_or_copy(f, os.path.join(d, os.path.basename(f)))
        reel = ""
        if reels and len(files) > 1:
            ext = os.path.splitext(files[0])[1]
            reel = os.path.join(d, f"{name} - all balls{ext}")
            same_type = all(os.path.splitext(f)[1] == ext for f in files)
            try:
                if not same_type:
                    raise RuntimeError("clips are of different file types")
                concat(files, reel)
            except Exception:
                reel = ""
                warnings.append(f"{name}: could not join the clips into one video (the videos were "
                                "probably recorded with different settings; 'Exact frame' export fixes this). "
                                "The separate clips are there.")
        rows.append((name, len(files), os.path.basename(reel)))
    with open(os.path.join(root, "players_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["player", "balls", "joined_video"])
        w.writerows(rows)
    if progress:
        progress(1.0, "Player folders done")
    return root, warnings


def write_report(path: str, motion, clips: list[Clip], params, version: str) -> None:
    """A zip with the motion grid (no images) and the reviewed ball list, for tuning the tracker."""
    import numpy as np

    buf = io.BytesIO()
    np.savez_compressed(buf, cells=motion.cells, fps=motion.fps)
    info = motion.info
    meta = {
        "app_version": version,
        "video": {"name": os.path.basename(info.path), "duration": info.duration, "fps": info.fps,
                  "width": info.width, "height": info.height},
        "params": params.to_dict(),
        "balls": [{"start": round(c.start, 2), "end": round(c.end, 2), "shot": round(c.peak, 2),
                   "score": round(c.score, 3), "kept": c.enabled, "added_by_hand": c.manual,
                   "batter": c.batter, "bowler": c.bowler}
                  for c in sorted(clips, key=lambda c: c.peak)],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("motion.npz", buf.getvalue())
        z.writestr("review.json", json.dumps(meta, indent=1))
