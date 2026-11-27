"""Motion analysis and ball-by-ball detection.

How it works
------------
1. FFmpeg decodes the video at a low sample rate (10 frames/s), shrinks each
   frame to 192x144 grey pixels and pipes it here.
2. For each pair of frames we count which pixels changed, per cell of a 16x12
   grid. That grid is kept (and cached on disk), so the detection area can be
   changed later without decoding the video again.
3. A delivery shows up as a short, sharp burst of motion (run-up, release,
   shot, ball through to the keeper) standing out from the slow background
   movement between balls (batter walking around, fielders, wind). We
   subtract a rolling baseline, then pick the strongest peaks that are at
   least `min_gap` seconds apart. Each peak becomes one clip.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import pattern
from .ffmpeg_tools import VideoInfo, ffmpeg_exe, popen_kwargs, probe

GRID_W, GRID_H = 16, 12
AW, AH = 192, 144  # analysis frame size; 12x12-pixel cells
SAMPLE_FPS = 10.0
PIXEL_THRESHOLD = 18  # grey levels a pixel must change by to count as motion
CACHE_VERSION = 2


@dataclass
class Motion:
    """Per-sample, per-cell fraction of changed pixels (0-255)."""

    cells: np.ndarray  # shape (n, GRID_H, GRID_W), uint8
    fps: float
    info: VideoInfo
    patterns: dict = field(default_factory=dict)  # detection area -> learned delivery pattern

    @property
    def n(self) -> int:
        return int(self.cells.shape[0])

    @property
    def duration(self) -> float:
        if self.info.duration > 0:
            return self.info.duration
        return self.n / self.fps


@dataclass
class Params:
    sensitivity: float = 6.0  # 1 (only big movements) .. 10 (catch everything)
    min_gap: float = 4.0  # seconds between two balls, at least
    pre_roll: float = 3.5  # seconds kept before the moment of the shot
    post_roll: float = 3.0  # seconds kept after it
    auto_extend: bool = False  # grow the clip to cover the whole burst of motion
    max_clip: float = 20.0
    roi: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1 (0..1)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["roi"] = list(self.roi) if self.roi else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Params":
        p = cls()
        for k, v in d.items():
            if hasattr(p, k):
                setattr(p, k, tuple(v) if k == "roi" and v else v)
        return p


PRESETS: dict[str, Params] = {
    "Batter view (camera above/side of batter)": Params(
        sensitivity=6, min_gap=4, pre_roll=3.5, post_roll=3.0, auto_extend=False
    ),
    "Behind the bowler (end-on)": Params(
        sensitivity=6, min_gap=4, pre_roll=6.0, post_roll=3.5, auto_extend=True
    ),
}


@dataclass
class Clip:
    start: float
    end: float
    peak: float
    score: float = 0.0  # peak height / threshold; >1 means detected
    enabled: bool = True
    manual: bool = False
    uid: int = field(default_factory=lambda: Clip._next())
    batter: str = ""
    bowler: str = ""

    _counter = 0

    @staticmethod
    def _next() -> int:
        Clip._counter += 1
        return Clip._counter

    @property
    def length(self) -> float:
        return self.end - self.start


class Cancelled(Exception):
    pass


# --------------------------------------------------------------------------- analysis

def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "BallCutter", "cache")
    os.makedirs(d, exist_ok=True)
    return d


def _cache_path(path: str) -> str:
    st = os.stat(path)
    key = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}|{CACHE_VERSION}"
    return os.path.join(cache_dir(), hashlib.sha1(key.encode("utf-8")).hexdigest() + ".npz")


def analyze(
    path: str,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    use_cache: bool = True,
) -> Motion:
    info = probe(path)
    cpath = _cache_path(path)
    if use_cache and os.path.exists(cpath):
        try:
            data = np.load(cpath)
            if progress:
                progress(1.0)
            return Motion(data["cells"], float(data["fps"]), info)
        except Exception:
            pass

    cmd = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "0",
        "-i", path, "-an", "-sn", "-dn",
        "-vf", f"fps={SAMPLE_FPS},scale={AW}:{AH}:flags=area,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=AW * AH * 32, **popen_kwargs()
    )
    frame_bytes = AW * AH
    expected = max(1, int(info.duration * SAMPLE_FPS))
    rows: list[np.ndarray] = [np.zeros((GRID_H, GRID_W), np.uint8)]
    prev = None
    count = 0
    ch, cw = AH // GRID_H, AW // GRID_W
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            cur = np.frombuffer(buf, np.uint8).reshape(AH, AW).astype(np.int16)
            if prev is not None:
                d = cur - prev
                d -= int(np.median(d))  # ignore whole-frame brightness changes (clouds, auto-exposure)
                changed = np.abs(d) > PIXEL_THRESHOLD
                frac = changed.reshape(GRID_H, ch, GRID_W, cw).mean(axis=(1, 3))
                rows.append((frac * 255).astype(np.uint8))
            prev = cur
            count += 1
            if progress and count % 25 == 0:
                progress(min(0.999, count / expected))
            if cancel and cancel():
                raise Cancelled()
    except Cancelled:
        proc.kill()
        proc.wait()
        raise
    finally:
        if proc.stdout:
            proc.stdout.close()
    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    proc.wait()
    if count < 2:
        raise RuntimeError(f"Could not read video frames from {os.path.basename(path)}.\n{err[-800:]}")

    cells = np.stack(rows)
    try:
        np.savez_compressed(cpath, cells=cells, fps=SAMPLE_FPS)
    except Exception:
        pass
    if progress:
        progress(1.0)
    return Motion(cells, SAMPLE_FPS, info)


# --------------------------------------------------------------------------- detection

def roi_mask(roi) -> np.ndarray:
    mask = np.zeros((GRID_H, GRID_W), bool)
    if not roi:
        mask[:] = True
        return mask
    x0, y0, x1, y1 = roi
    xs = (np.arange(GRID_W) + 0.5) / GRID_W
    ys = (np.arange(GRID_H) + 0.5) / GRID_H
    mask[np.ix_((ys >= min(y0, y1)) & (ys <= max(y0, y1)), (xs >= min(x0, x1)) & (xs <= max(x0, x1)))] = True
    if not mask.any():  # area smaller than one cell: take the nearest cell
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        mask[min(GRID_H - 1, int(cy * GRID_H)), min(GRID_W - 1, int(cx * GRID_W))] = True
    return mask


def _smooth(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x
    k = np.ones(win) / win
    return np.convolve(x, k, mode="same")


def _rolling_baseline(x: np.ndarray, fps: float, block_s: float = 5.0, span_blocks: int = 3) -> np.ndarray:
    n = len(x)
    b = max(1, int(block_s * fps))
    nb = (n + b - 1) // b
    centers = np.empty(nb)
    vals = np.empty(nb)
    for j in range(nb):
        lo = max(0, (j - span_blocks) * b)
        hi = min(n, (j + span_blocks + 1) * b)
        vals[j] = np.percentile(x[lo:hi], 50)
        centers[j] = min(n - 1, j * b + b / 2)
    return np.interp(np.arange(n), centers, vals)


@dataclass
class Signal:
    excess: np.ndarray  # detection curve, per sample (pattern similarity, or motion above baseline)
    threshold: float
    fps: float
    mode: str = "motion"  # "pattern" = learned delivery pattern, "motion" = plain movement bursts
    templates: int = 0


def _pattern(motion: Motion, roi):
    """Learned delivery pattern for this video and detection area (cached on the Motion object)."""
    key = tuple(roi) if roi else None
    if key not in motion.patterns:
        try:
            F = pattern.features(motion.cells, roi_mask(roi), motion.fps)
            motion.patterns[key] = pattern.learn(F, motion.fps, GRID_W)
        except Exception:
            motion.patterns[key] = None
    return motion.patterns[key]


def _motion_signal(motion: Motion, params: Params) -> Signal:
    mask = roi_mask(params.roi)
    raw = motion.cells[:, mask].astype(np.float32).mean(axis=1) / 255.0
    s = _smooth(raw, max(1, int(round(0.4 * motion.fps))))
    base = _rolling_baseline(s, motion.fps)
    ex = s - base
    med = float(np.median(ex))
    noise = 1.4826 * float(np.median(np.abs(ex - med)))
    noise = max(noise, 0.0015)
    sens = float(np.clip(params.sensitivity, 1, 10))
    k = 2.0 * 7.0 ** ((10.0 - sens) / 9.0)  # sensitivity 10 -> 2x noise, 1 -> 14x noise
    thr = max(noise * k, 0.004)
    return Signal(np.clip(ex, 0, None), thr, motion.fps, "motion")


def compute_signal(motion: Motion, params: Params) -> Signal:
    pr = _pattern(motion, params.roi)
    if pr is None:
        return _motion_signal(motion, params)
    sens = float(np.clip(params.sensitivity, 1, 10))
    ratio = 0.30 + 0.40 * (10.0 - sens) / 9.0  # sensitivity 10 -> 30 % of a typical ball, 1 -> 70 %
    return Signal(np.clip(pr.sim, 0, None), pr.level * ratio, motion.fps, "pattern", pr.n_templates)


def _find_peaks(ex: np.ndarray, thr: float, min_dist: int) -> list[int]:
    if len(ex) < 3:
        return []
    left = np.r_[-np.inf, ex[:-1]]
    right = np.r_[ex[1:], -np.inf]
    cand = np.nonzero((ex >= thr) & (ex >= left) & (ex > right))[0]
    order = cand[np.argsort(-ex[cand], kind="stable")]
    taken = np.zeros(len(ex), bool)
    picked: list[int] = []
    for i in order:
        if taken[i]:
            continue
        picked.append(int(i))
        taken[max(0, i - min_dist + 1): i + min_dist] = True
    return sorted(picked)


def _burst_edges(ex: np.ndarray, i: int, level: float, max_gap: int, limit: int) -> tuple[int, int]:
    n = len(ex)
    lo = i
    gap = 0
    j = i
    while j > 0 and i - j < limit:
        j -= 1
        if ex[j] >= level:
            lo, gap = j, 0
        else:
            gap += 1
            if gap > max_gap:
                break
    hi = i
    gap = 0
    j = i
    while j < n - 1 and j - i < limit:
        j += 1
        if ex[j] >= level:
            hi, gap = j, 0
        else:
            gap += 1
            if gap > max_gap:
                break
    return lo, hi


def detect_balls(motion: Motion, params: Params, signal: Signal | None = None) -> list[Clip]:
    sig = signal or compute_signal(motion, params)
    fps = motion.fps
    ex = sig.excess
    peaks = _find_peaks(ex, sig.threshold, max(1, int(params.min_gap * fps)))
    peaks = _rhythm_rescue(ex, peaks, sig.threshold, fps, params.min_gap)
    extra_scores: dict[int, float] = {}
    if sig.mode == "pattern":
        # never miss a ball the plain movement detector would catch: add those as 'check' items
        ms = _motion_signal(motion, params)
        gap = max(1, int(params.min_gap * fps))
        taken = np.zeros(len(ex), bool)
        for p in peaks:
            taken[max(0, p - gap + 1): p + gap] = True
        for i in _find_peaks(ms.excess, ms.threshold, gap):
            if not taken[i]:
                peaks.append(i)
                extra_scores[i] = min(0.99, float(ex[i] / sig.threshold))
        peaks.sort()
    clips: list[Clip] = []
    for i in peaks:
        t = i / fps
        start, end = t - params.pre_roll, t + params.post_roll
        if params.auto_extend:
            lo, hi = _burst_edges(ex, i, 0.35 * sig.threshold, int(1.0 * fps), int(params.max_clip * fps))
            start = min(start, lo / fps - 0.5)
            end = max(end, hi / fps + 0.5)
            ext_f = (t - start) - params.pre_roll
            ext_b = (end - t) - params.post_roll
            room = params.max_clip - params.pre_roll - params.post_roll
            if ext_f + ext_b > room:  # too long: shrink only the extensions
                scale = max(0.0, room) / (ext_f + ext_b)
                start = t - params.pre_roll - ext_f * scale
                end = t + params.post_roll + ext_b * scale
        clips.append(Clip(start, end, t, extra_scores.get(i, float(ex[i] / sig.threshold))))
    return fix_bounds(clips, motion.duration)


def _rhythm_rescue(ex: np.ndarray, peaks: list[int], thr: float, fps: float, min_gap: float) -> list[int]:
    """Net sessions have a rhythm. Where the gap between two balls is much longer than usual,
    look again inside it with a lower bar; anything found gets a low score so it shows as 'check'."""
    if len(peaks) < 6:
        return peaks
    gaps = np.diff(peaks)
    typical = float(np.median(gaps))
    lo_gap = max(int(min_gap * fps), int(0.6 * typical))
    found = list(peaks)
    edges = [-lo_gap] + list(peaks) + [len(ex) - 1 + lo_gap]  # video start/end count as neighbours
    for a, b in zip(edges, edges[1:]):
        if b - a < 1.8 * typical:
            continue
        lo, hi = max(0, a + lo_gap), min(len(ex), b - lo_gap + 1)
        found += [lo + i for i in _find_peaks(ex[lo:hi], 0.7 * thr, lo_gap)]
    return sorted(set(found))


def fix_bounds(clips: list[Clip], duration: float) -> list[Clip]:
    """Clamp to the video and make sure neighbouring clips never overlap."""
    clips.sort(key=lambda c: c.peak)
    for c in clips:
        c.start = max(0.0, c.start)
        c.end = min(duration, c.end) if duration > 0 else c.end
    for a, b in zip(clips, clips[1:]):
        if a.end > b.start:
            # the next ball's run-up matters more than this ball's follow-through:
            # this clip keeps 1.5 s after its shot (or 35 % of the gap), the next clip gets the rest
            gap = b.peak - a.peak
            mid = a.peak + min(max(1.5, 0.35 * gap), 0.6 * gap)
            mid = min(max(mid, a.peak + 0.5), b.peak - 0.5)
            a.end = max(a.start + 0.5, mid)
            b.start = min(b.end - 0.5, mid)
    return [c for c in clips if c.end - c.start >= 0.5]


def manual_clip(t: float, params: Params, duration: float) -> Clip:
    return Clip(max(0.0, t - params.pre_roll), min(duration, t + params.post_roll), t, 0.0, True, True)
