"""Delivery-pattern tracker.

With a fixed camera every delivery looks alike: the bowler comes in on the
same line, the ball travels the same path and the batter moves at the same
spot, in the same order. Things that cause false alarms or hide balls (the
batter walking around between balls, a fielder or coach moving, light
changes) look different each time.

So instead of only asking "is there a lot of movement now?", the tracker
1. turns the motion grid into per-area activity, each area scaled by how
   often it normally moves (an area that is always busy, such as a fielder's
   patch, counts for little; an area that only moves during deliveries,
   such as the bowler's arm or the ball's path, counts for a lot);
2. collects short bursts of movement and finds the ones that resemble many
   other bursts: those are the deliveries;
3. averages them into a spatio-temporal template ("what a delivery looks
   like in this video"), refines it a few times, and allows a second
   template when deliveries come in two kinds (e.g. right- and left-handed
   batters);
4. scores every moment of the video by how closely it matches a template.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PRE_S, POST_S = 1.5, 1.0  # template window around the moment of the burst
SEED_GAP_S = 2.5
MIN_MATCHES = 6


@dataclass
class PatternResult:
    sim: np.ndarray  # similarity to the delivery pattern, per sample (a typical delivery ~ 1)
    level: float  # typical similarity of a real delivery in this video
    n_templates: int
    quality: float  # how well deliveries stand out (higher is better)


def smooth(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x
    return np.convolve(x, np.ones(win) / win, mode="same")


def find_peaks(x: np.ndarray, thr: float, min_dist: int) -> list[int]:
    """Local maxima >= thr, strongest first, at least min_dist samples apart."""
    if len(x) < 3:
        return []
    left = np.r_[-np.inf, x[:-1]]
    right = np.r_[x[1:], -np.inf]
    cand = np.nonzero((x >= thr) & (x >= left) & (x > right))[0]
    order = cand[np.argsort(-x[cand], kind="stable")]
    taken = np.zeros(len(x), bool)
    picked: list[int] = []
    for i in order:
        if taken[i]:
            continue
        picked.append(int(i))
        taken[max(0, i - min_dist + 1): i + min_dist] = True
    return sorted(picked)


def _rolling_percentile(a: np.ndarray, fps: float, win_s: float, q: float, block_s: float = 1.0) -> np.ndarray:
    """Per-column rolling percentile, computed on 1-second blocks for speed."""
    n = a.shape[0]
    b = max(1, int(block_s * fps))
    nb = (n + b - 1) // b
    pad = nb * b - n
    ap = np.concatenate([a, np.repeat(a[-1:], pad, axis=0)]) if pad else a
    blocks = np.median(ap.reshape(nb, b, -1), axis=1)
    span = max(1, int(win_s / 2 / block_s))
    out = np.empty_like(blocks)
    for j in range(nb):
        out[j] = np.percentile(blocks[max(0, j - span): j + span + 1], q, axis=0)
    centers = np.minimum(n - 1, np.arange(nb) * b + b / 2)
    idx = np.arange(n)
    res = np.empty((n, a.shape[1]), np.float32)
    for k in range(a.shape[1]):
        res[:, k] = np.interp(idx, centers, out[:, k])
    return res


def features(cells: np.ndarray, mask: np.ndarray, fps: float) -> np.ndarray:
    """(n, GRID_H, GRID_W) uint8 -> (n, GRID_H*GRID_W) activity scaled per area; 0 outside the area."""
    n, gh, gw = cells.shape
    a = cells.reshape(n, -1).astype(np.float32) / 255.0
    a[:, ~mask.ravel()] = 0
    base = _rolling_percentile(a, fps, 40.0, 30.0)
    d = np.clip(a - base, 0, None)
    scale = np.maximum(np.percentile(d, 80, axis=0), 0.02)
    return np.clip(d / scale, 0, 8).astype(np.float32)


def _mirror(T: np.ndarray, gw: int, shift: int) -> np.ndarray:
    """Flip a template left-right (a left-hander vs a right-hander), then move it by `shift` columns."""
    W = T.shape[0]
    g = T.reshape(W, -1, gw)[:, :, ::-1]
    out = np.zeros_like(g)
    if shift >= 0:
        out[:, :, shift:] = g[:, :, : gw - shift]
    else:
        out[:, :, :shift] = g[:, :, -shift:]
    return out.reshape(W, -1)


def _energy(F: np.ndarray, W: int, pre: int) -> np.ndarray:
    """Amount of movement in the template-sized window centred on each sample."""
    sq = np.einsum("nc,nc->n", F, F, dtype=np.float64)
    cs = np.r_[0.0, np.cumsum(sq)]
    out = np.zeros(F.shape[0], np.float32)
    if F.shape[0] >= W:
        out[pre: pre + F.shape[0] - W + 1] = np.sqrt(np.maximum(cs[W:] - cs[:-W], 0))
    return out


def _ncc(F: np.ndarray, T: np.ndarray, pre: int) -> np.ndarray:
    """Normalised correlation of template T (W, C) with F (n, C) at every centre."""
    W = T.shape[0]
    n = F.shape[0]
    out = np.zeros(n, np.float32)
    if n < W:
        return out
    tn = float(np.linalg.norm(T))
    if tn <= 0:
        return out
    dot = np.zeros(n - W + 1, np.float64)
    for w in range(W):  # sum of shifted row dot-products; memory-light for long videos
        dot += F[w: n - W + 1 + w] @ T[w]
    sq = np.einsum("nc,nc->n", F, F, dtype=np.float64)
    cs = np.r_[0.0, np.cumsum(sq)]
    nrm = np.sqrt(np.maximum(cs[W:] - cs[:-W], 0)) + 1e-6
    out[pre: pre + len(dot)] = (dot / (nrm * tn)).astype(np.float32)
    return out


def _windows(F: np.ndarray, idx, pre: int, post: int) -> np.ndarray:
    return np.stack([F[p - pre: p + post + 1] for p in idx])


def _time_spread(T: np.ndarray) -> float:
    """How spread out in time the movement of a template is (in samples)."""
    prof = T.sum(axis=1)
    prof = prof / (prof.sum() + 1e-9)
    t = np.arange(len(prof))
    mu = float((prof * t).sum())
    return float(np.sqrt((prof * (t - mu) ** 2).sum()))


def _quality(s: np.ndarray, cand: list[int], sel: list[int]) -> tuple[float, float]:
    """Typical similarity of a delivery, and how far it stands above the other bursts."""
    level = float(np.median(s[sel]))
    rest = s[[p for p in cand if s[p] < 0.5 * level]]
    background = float(np.median(rest)) if len(rest) else 0.0
    return level / (background + 1e-3), level


def _learn_one(F, burst, pk, fps, pre, post, gap):
    """Find the most repeated kind of burst among candidate peaks pk and build its template."""
    n = F.shape[0]
    if len(pk) < MIN_MATCHES:
        return None
    pk = np.array(sorted(pk, key=lambda i: -burst[i])[:300])
    # which bursts resemble many other bursts? (allow +-0.2 s misalignment)
    V = np.stack([_windows(F, pk + s, pre, post).reshape(len(pk), -1) for s in (-2, 0, 2)], axis=1)
    V /= np.linalg.norm(V, axis=2, keepdims=True) + 1e-6
    sim = np.einsum("id,jsd->ijs", V[:, 1], V, optimize=True).max(2)
    np.fill_diagonal(sim, -1)
    k = min(8, len(pk) - 1)
    density = -np.sort(-sim, axis=1)[:, :k].mean(1)
    height = burst[pk] / (np.median(burst[pk]) + 1e-9)
    sel = list(pk[np.argsort(-(density * np.sqrt(height)))[:12]])
    # refine the template from its own best matches
    for _ in range(4):
        T = _windows(F, sel, pre, post).mean(0)
        s = _ncc(F, T, pre)
        cand = find_peaks(s, 1e-9, gap)
        if len(cand) < MIN_MATCHES:
            return None
        thr = np.percentile(s[cand], 70)
        sel = [p for p in cand if s[p] >= thr and pre <= p < n - post]
    q, level = _quality(s, cand, sel)
    return T, s, q, level


def learn(F: np.ndarray, fps: float, gw: int) -> PatternResult | None:
    n = F.shape[0]
    pre, post = int(PRE_S * fps), int(POST_S * fps)
    if n < (pre + post + 1) * 4:
        return None
    act = F.mean(1)
    burst = np.clip(smooth(act, 3) - smooth(act, int(3 * fps)), 0, None)
    gap = int(SEED_GAP_S * fps)
    pk = [p for p in find_peaks(burst, 1e-9, gap) if p - pre - 2 >= 0 and p + post + 2 < n]

    # Learn up to three different repeated patterns: the deliveries, but perhaps also the batter
    # walking back to the crease or a fielder/coach moving about. Among the patterns that come with a
    # real burst of movement, keep the one whose matches are most alike and most compact in time.
    options = []
    rest = pk
    for _ in range(3):
        r = _learn_one(F, burst, rest, fps, pre, post, gap)
        if r is None:
            break
        T_, s_, q_, level_ = r
        hits = find_peaks(s_, 0.6 * level_, gap)
        if level_ >= 0.35 and q_ >= 1.6 and len(hits) >= MIN_MATCHES:
            # deliveries match each other closely and are compact in time
            options.append((level_ / _time_spread(T_), float(np.median(burst[hits])), r))
        covered = np.zeros(n, bool)
        for h in hits:
            covered[max(0, h - gap): h + gap] = True
        rest = [p for p in rest if not covered[p]]
    if not options:
        return None
    top_burst = max(o[1] for o in options)
    T, s, q, level = max((o for o in options if o[1] >= 0.5 * top_burst), key=lambda o: o[0])[2]

    n_t = 1
    s = s / level  # scaled so that a typical delivery scores 1.0

    # left- and right-handers: try the mirrored template at a few positions (the camera may not be
    # centred on the stumps). Keep it only if it explains a good number of strong, unexplained bursts.
    best = None
    explained = s >= 0.6
    first_hits = find_peaks(s, 0.6, gap)
    n_first = len(first_hits)
    first_burst = float(np.median(burst[first_hits])) if first_hits else 0.0
    for shift in range(-gw // 4, gw // 4 + 1):
        sm = _ncc(F, _mirror(T, gw, shift), pre) / level
        own = [p for p in find_peaks(sm, 0.7, gap) if not explained[max(0, p - gap): p + gap].any()]
        # the extra matches must be sharp bursts like the deliveries already found
        own = [p for p in own if burst[p] >= 0.4 * first_burst]
        if len(own) >= max(MIN_MATCHES, 0.2 * n_first):
            score = float(np.median(sm[own])) * len(own)
            if best is None or score > best[0]:
                best = (score, sm, len(own))
    if best is not None:
        s = np.maximum(s, best[1])
        n_t = 2
    # the shape of the movement is not enough: a slow shuffle in the batter's spot has the right
    # shape but far less movement than a delivery. Scale down anything weaker than a typical ball.
    energy = _energy(F, pre + post + 1, pre)
    strong = find_peaks(s, 0.8, gap)
    if strong:
        ref = float(np.median(energy[strong]))
        s = s * np.sqrt(np.clip(energy / (ref + 1e-6), 0, 1))
        s = s / max(1e-6, float(np.median(s[strong])))
    cand = find_peaks(s, 1e-9, gap)
    sel = [p for p in cand if s[p] >= np.percentile(s[cand], 70)]
    q, level = _quality(s, cand, sel)
    return PatternResult(s, level, n_t, q)


def find_similar(F: np.ndarray, fps: float, examples: list[float], taken: list[tuple[float, float]],
                 min_gap: float, strictness: float = 0.6) -> list[tuple[float, float]]:
    """Teach by example: the analyst points at balls the tracker missed (times in seconds, roughly at
    the shot). Each example is lined up on its burst of movement, the examples are averaged into a
    template, and every other moment that matches it closely (and is not inside an existing clip in
    `taken`) is returned as (time, similarity relative to the examples)."""
    n = F.shape[0]
    pre, post = int(PRE_S * fps), int(POST_S * fps)
    act = F.mean(1)
    burst = np.clip(smooth(act, 3) - smooth(act, int(3 * fps)), 0, None)
    centres = []
    for t in examples:
        i = int(t * fps)
        lo, hi = max(pre, i - int(1.5 * fps)), min(n - post - 1, i + int(1.5 * fps))
        if hi <= lo:
            continue
        centres.append(lo + int(np.argmax(burst[lo:hi + 1])))  # line up on the burst
    if not centres:
        return []
    T = _windows(F, centres, pre, post).mean(0)
    s = _ncc(F, T, pre)
    energy = _energy(F, pre + post + 1, pre)
    ref = float(np.median(energy[centres])) + 1e-6
    s = s * np.sqrt(np.clip(energy / ref, 0, 1))
    level = float(np.median(s[centres])) + 1e-6
    s = s / level
    gap = max(1, int(min_gap * fps))
    blocked = np.zeros(n, bool)
    for a, b in taken:
        blocked[max(0, int(a * fps)): int(b * fps) + 1] = True
    for c in centres:
        blocked[max(0, c - gap): c + gap] = True
    return [(p / fps, float(s[p])) for p in find_peaks(s, strictness, gap) if not blocked[p]]


def similarity_to(F: np.ndarray, fps: float, example: float, times: list[float]) -> list[float]:
    """How much each moment in `times` looks like the example moment (1.0 = as much as the example
    itself), allowing +-1 s of misalignment."""
    n = F.shape[0]
    pre, post = int(PRE_S * fps), int(POST_S * fps)
    act = F.mean(1)
    burst = np.clip(smooth(act, 3) - smooth(act, int(3 * fps)), 0, None)
    i = int(example * fps)
    lo, hi = max(pre, i - int(1.5 * fps)), min(n - post - 1, i + int(1.5 * fps))
    if hi <= lo:
        return [0.0] * len(times)
    c = lo + int(np.argmax(burst[lo:hi + 1]))
    T = _windows(F, [c], pre, post)[0]
    s = _ncc(F, T, pre)
    energy = _energy(F, pre + post + 1, pre)
    s = s * np.sqrt(np.clip(energy / (energy[c] + 1e-6), 0, 1))
    s = s / (s[c] + 1e-6)
    w = int(1.0 * fps)
    return [float(s[max(0, int(t * fps) - w): int(t * fps) + w + 1].max()) if 0 <= int(t * fps) < n else 0.0
            for t in times]
