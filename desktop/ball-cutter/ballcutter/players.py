"""Automatic player recognition: groups balls by who is batting (or bowling).

For each ball the app looks at the player's area a moment before the delivery (the batter in her
stance, or the bowler in her run-up) and describes what it sees: the colours of helmet, shirt,
pads, gloves and shoes, where they are (so a left-hander looks different from a right-hander),
and how tall the player is. Balls that look alike belong to the same player.

Batters bat in blocks of balls, so the sequence is first split into runs of similar balls
(a change-point search), and the runs are then grouped into players. This ignores a single odd
ball (a fielder walking past, a shadow) and copes with the batters coming back in any order.
Bowlers usually bowl in turn, so for bowlers the balls are grouped one by one instead.
"""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .detect import GRID_H, GRID_W, Cancelled, Clip, Motion
from .ffmpeg_tools import ffmpeg_exe, popen_kwargs

FRAME_W = 320
@dataclass
class PlayerGroups:
    labels: list[int]  # group per ball (same order as the clips given), -1 = no picture
    samples: dict[int, list[np.ndarray]]  # a few example crops (RGB uint8) per group
    box: tuple[float, float, float, float]


# ------------------------------------------------------------------ where to look

def _cells_box(cells: np.ndarray, frac: float = 0.35, pad_cells: float = 1.0):
    """Bounding box (0..1) of the grid cells with at least `frac` of the strongest movement."""
    if cells.max() <= 0:
        return None
    ys, xs = np.nonzero(cells >= frac * cells.max())
    x0, x1 = (xs.min() - pad_cells) / GRID_W, (xs.max() + 1 + pad_cells) / GRID_W
    y0, y1 = (ys.min() - pad_cells) / GRID_H, (ys.max() + 1 + pad_cells) / GRID_H
    return (max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1))


def auto_box(motion: Motion, clips: list[Clip]) -> tuple[float, float, float, float]:
    """The batter's area: where movement happens around the moment of each ball, widened a little."""
    fps = motion.fps
    acc = np.zeros((GRID_H, GRID_W))
    for c in clips:
        a, b = max(0, int((c.peak - 0.6) * fps)), min(motion.n, int((c.peak + 0.6) * fps))
        if b > a:
            acc += motion.cells[a:b].astype(np.float64).mean(0)
    box = _cells_box(acc, 0.35, 0.0)
    if box is None:
        return (0.25, 0.15, 0.75, 0.95)
    x0, y0, x1, y1 = box
    padx, pady = 0.25 * (x1 - x0) + 0.04, 0.25 * (y1 - y0) + 0.04
    return (max(0.0, x0 - padx), max(0.0, y0 - pady), min(1.0, x1 + padx), min(1.0, y1 + pady))


def _box_cells(box):
    x0, y0, x1, y1 = box
    gy0, gy1 = int(y0 * GRID_H), max(int(y0 * GRID_H) + 1, int(np.ceil(y1 * GRID_H)))
    gx0, gx1 = int(x0 * GRID_W), max(int(x0 * GRID_W) + 1, int(np.ceil(x1 * GRID_W)))
    return slice(gy0, gy1), slice(gx0, gx1)


def pick_views(motion: Motion, c: Clip, role: str, box, k: int = 3) -> list[tuple[float, tuple]]:
    """Moments (at least 0.3 s apart) and areas to look at for one ball.
    batter: the calmest moments of the clip inside the batter's area (standing in her stance,
            nobody in front of her);
    bowler: the moments with the most movement in the clip, framed around that movement (from
            behind the bowler, the bowler running in is the big moving figure)."""
    fps = motion.fps
    # the batter is looked at in her stance, shortly before the swing (at the end of a clip the next
    # batter may already be walking in); the bowler anywhere in the clip
    lo, hi = (max(c.start, c.peak - 2.6), c.peak - 1.0) if role == "batter" else (c.start, c.end)
    a, b = max(0, int(lo * fps)), min(motion.n, int(hi * fps))
    if b - a < 1:
        return [(max(0.0, c.peak), box)]
    if role == "batter":
        ys, xs = _box_cells(box)
        score = motion.cells[a:b, ys, xs].astype(np.float32).mean((1, 2))
    else:
        score = -motion.cells[a:b].astype(np.float32).mean((1, 2))
    chosen: list[int] = []
    for i in np.argsort(score, kind="stable"):
        if all(abs(int(i) - j) >= int(0.3 * fps) for j in chosen):
            chosen.append(int(i))
        if len(chosen) == k:
            break
    out = []
    for i in sorted(chosen):
        if role == "batter":
            out.append(((a + i) / fps, box))
        else:
            win = motion.cells[max(0, a + i - 1): a + i + 2].astype(np.float32).mean(0)
            out.append(((a + i) / fps, _cells_box(win, 0.4, 0.5) or box))
    return out


# ------------------------------------------------------------------ pictures

def _grab(path: str, times: list[float], width: int = FRAME_W) -> list[np.ndarray]:
    """Decode one frame at each of the given times."""
    frames = []
    for t in times:
        proc = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}",
             "-i", path, "-frames:v", "1", "-an", "-vf", f"scale={width}:-2", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120, **popen_kwargs())
        raw = proc.stdout
        if raw and len(raw) % (width * 3) == 0:
            frames.append(np.frombuffer(raw, np.uint8).reshape(-1, width, 3))
    return frames


def _crop(frame: np.ndarray, box) -> np.ndarray:
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    a, b = int(y0 * h), max(int(y0 * h) + 4, int(y1 * h))
    c, d = int(x0 * w), max(int(x0 * w) + 4, int(x1 * w))
    return frame[a:b, c:d]


def _rgb_to_hsv(img: np.ndarray):
    x = img.astype(np.float32) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn + 1e-6
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    sat = (mx - mn) / (mx + 1e-6)
    return hue % 1.0, sat, mx


def _grid_mean(img: np.ndarray, gh: int, gw: int) -> np.ndarray:
    h, w = img.shape[:2]
    ys = np.linspace(0, h, gh + 1).astype(int)
    xs = np.linspace(0, w, gw + 1).astype(int)
    f = img.astype(np.float32)
    return np.array([[f[ys[i]:max(ys[i] + 1, ys[i + 1]), xs[j]:max(xs[j] + 1, xs[j + 1])].reshape(-1, 3).mean(0)
                      for j in range(gw)] for i in range(gh)])


def layout(crops: list[np.ndarray], gh: int = 16, gw: int = 12) -> np.ndarray:
    """Where the colours are: helmet height, glove side, stance (left- or right-handed), pads."""
    out = []
    for img in crops:
        g = _grid_mean(img, gh, gw)
        tot = g.sum(-1, keepdims=True) + 1e-6
        chroma = g[..., :2] / tot  # colour without brightness, so light changes matter less
        bright = tot / tot.mean()
        out.append(np.concatenate([chroma.ravel() * 3.0, bright.ravel() * 0.3]))
    return np.mean(out, axis=0)


def describe(crops: list[np.ndarray]) -> np.ndarray:
    """Full description: colour make-up plus colour layout."""
    return np.concatenate([histograms(crops), layout(crops)])


def histograms(crops: list[np.ndarray]) -> np.ndarray:
    """Appearance description of a player from a few crops: colour make-up in a 3x2 grid of the
    area (head / body / legs, left / right), brightness normalised against light changes."""
    feats = []
    for img in crops:
        hue, sat, val = _rgb_to_hsv(img)
        val = val / (val.mean() + 1e-6) * 0.5  # light changes over the session
        h, w = hue.shape
        parts = []
        for r in range(3):
            for c in range(2):
                ys = slice(r * h // 3, (r + 1) * h // 3)
                xs = slice(c * w // 2, (c + 1) * w // 2)
                hh, ss, vv = hue[ys, xs].ravel(), sat[ys, xs].ravel(), val[ys, xs].ravel()
                colourful = ss > 0.25
                hs, _, _ = np.histogram2d(hh[colourful], ss[colourful], bins=(12, 3),
                                          range=((0, 1), (0.25, 1)))
                vh, _ = np.histogram(np.clip(vv, 0, 1), bins=6, range=(0, 1))
                v = np.concatenate([hs.ravel(), vh]) / max(1, len(hh))
                parts.append(np.sqrt(v))  # Hellinger: makes histogram distances behave
        feats.append(np.concatenate(parts))
    return np.mean(feats, axis=0)


def ball_descriptions(path: str, motion: Motion, clips: list[Clip], role: str, box,
                      progress=None, cancel=None, workers: int = 4):
    """Returns (descriptions (n, d) with NaN rows where no picture could be read, one crop per ball)."""
    n = len(clips)
    out: list = [None] * n
    thumbs: list = [None] * n
    done = [0]

    def one(i):
        if cancel and cancel():
            raise Cancelled()
        views = pick_views(motion, clips[i], role, box)
        frames = _grab(path, [t for t, _ in views])
        crops = [_crop(f, bx) for f, (_, bx) in zip(frames, views)]
        if crops:
            out[i] = describe(crops)
            thumbs[i] = crops[len(crops) // 2]
        done[0] += 1
        if progress:
            progress(done[0] / n)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, range(n)))
    d = len(next((o for o in out if o is not None), np.zeros(1)))
    X = np.full((n, d), np.nan)
    for i, o in enumerate(out):
        if o is not None:
            X[i] = o
    return X, thumbs


# ------------------------------------------------------------------ grouping

def _segment(X: np.ndarray, penalty: float, min_len: int = 2) -> list[tuple[int, int]]:
    """Split the sequence into runs of similar balls (optimal partition, cost = spread within each
    run + a penalty per run)."""
    n = len(X)
    c1 = np.vstack([np.zeros(X.shape[1]), np.cumsum(X, 0)])
    c2 = np.r_[0.0, np.cumsum((X * X).sum(1))]

    def cost(i, j):  # balls i..j-1
        s = c1[j] - c1[i]
        return c2[j] - c2[i] - float(s @ s) / (j - i)

    best = np.full(n + 1, np.inf)
    best[0] = 0.0
    prev = np.zeros(n + 1, int)
    for j in range(1, n + 1):
        for i in range(max(0, j - 400), j):
            if j - i < min_len and not (i == 0 or j == n):
                continue
            v = best[i] + cost(i, j) + penalty
            if v < best[j]:
                best[j], prev[j] = v, i
    segs = []
    j = n
    while j > 0:
        segs.append((prev[j], j))
        j = prev[j]
    return segs[::-1]


def _agglomerate(means: np.ndarray, sizes: np.ndarray, k: int | None, stop: float) -> list[int]:
    """Average-linkage grouping of runs into players."""
    groups = [[i] for i in range(len(means))]
    D = ((means[:, None] - means[None]) ** 2).sum(-1)

    def gdist(a, b):
        w = np.outer(sizes[a], sizes[b])
        return float((D[np.ix_(a, b)] * w).sum() / w.sum())

    while len(groups) > 1:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                d = gdist(groups[i], groups[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        if k is not None:
            if len(groups) <= k:
                break
        elif d > stop:
            break
        groups[i] = groups[i] + groups[j]
        del groups[j]
    lab = np.zeros(len(means), int)
    for g, members in enumerate(groups):
        lab[members] = g
    return list(lab)


def group_players(X: np.ndarray, role: str, k: int | None = None) -> list[int]:
    """Group balls by player. k = number of players, or None to decide automatically."""
    n = len(X)
    ok = ~np.isnan(X).any(1)
    labels = np.full(n, -1)
    Xo = X[ok]
    if len(Xo) < 2:
        labels[ok] = 0
        return list(labels)
    # typical difference between two balls of the same player. Batters: consecutive balls are mostly
    # the same batter. Bowlers change every ball, so use each ball's closest look-alike instead.
    if role == "batter":
        diffs = ((Xo[1:] - Xo[:-1]) ** 2).sum(1)
    else:
        D2 = ((Xo[:, None] - Xo[None]) ** 2).sum(-1)
        np.fill_diagonal(D2, np.inf)
        diffs = D2.min(1)
    noise = float(np.percentile(diffs, 40 if role == "batter" else 50)) + 1e-9
    if role == "batter":
        pen = 8.0 * noise
        segs = _segment(Xo, penalty=pen)
        while k is not None and len(segs) < k and pen > 1e-3 * noise:  # asked for more players: split finer
            pen /= 2
            segs = _segment(Xo, penalty=pen)
        means = np.array([Xo[a:b].mean(0) for a, b in segs])
        sizes = np.array([b - a for a, b in segs], float)
        seg_lab = _agglomerate(means, sizes, k, stop=6.0 * noise)
        lab = np.zeros(len(Xo), int)
        for (a, b), g in zip(segs, seg_lab):
            lab[a:b] = g
    else:
        lab = np.array(_agglomerate(Xo, np.ones(len(Xo)), k, stop=6.0 * noise))
    # number the groups by first appearance
    order = {}
    for g in lab:
        order.setdefault(int(g), len(order))
    labels[ok] = [order[int(g)] for g in lab]
    return list(labels)


def find_players(path: str, motion: Motion, clips: list[Clip], role: str = "batter", k: int | None = None,
                 box=None, progress: Callable[[float], None] | None = None,
                 cancel: Callable[[], bool] | None = None) -> PlayerGroups:
    """role: who to recognise, "batter" or "bowler" (bowlers only from a camera behind the bowler)."""
    use = sorted(clips, key=lambda c: c.peak)
    box = box or auto_box(motion, use)
    X, thumbs = ball_descriptions(path, motion, use, role, box, progress, cancel)
    labels = group_players(X, role, k)
    samples: dict[int, list[np.ndarray]] = {}
    for g in sorted(set(labels) - {-1}):
        idx = [i for i, l in enumerate(labels) if l == g and thumbs[i] is not None]
        pick = [idx[int(round(q * (len(idx) - 1)))] for q in np.linspace(0, 1, min(4, len(idx)))] if idx else []
        samples[g] = [thumbs[i] for i in dict.fromkeys(pick)]
    by_uid = {c.uid: l for c, l in zip(use, labels)}
    return PlayerGroups([by_uid[c.uid] for c in clips], samples, box)


def save_ppm(img: np.ndarray, path: str, height: int = 110) -> str:
    """Small picture file Tk can show without extra libraries (nearest-neighbour resize)."""
    h, w = img.shape[:2]
    s = height / max(1, h)
    ys = np.minimum((np.arange(height) / s).astype(int), h - 1)
    wn = max(1, int(w * s))
    xs = np.minimum((np.arange(wn) / s).astype(int), w - 1)
    im = img[ys][:, xs]
    with open(path, "wb") as f:
        f.write(f"P6 {wn} {height} 255\n".encode())
        f.write(np.ascontiguousarray(im, dtype=np.uint8).tobytes())
    return path



