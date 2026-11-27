"""Synthetic colour net session with several batters taking turns (and bowlers in rotation), for
testing automatic player recognition. Players can be made deliberately similar (same team kit,
differing only in helmet, pads or gloves) to test the hard case.

Returns (ball_times, batter_per_ball, bowler_per_ball)."""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ballcutter.ffmpeg_tools import ffmpeg_exe  # noqa: E402

# (helmet, shirt, pads/trousers, gloves, height px, left-handed)
DISTINCT = [
    ((30, 30, 140), (200, 40, 40), (240, 240, 240), (20, 120, 20), 150, False),
    ((20, 20, 20), (40, 90, 200), (230, 230, 230), (230, 200, 0), 140, False),
    ((160, 20, 20), (240, 240, 240), (60, 60, 60), (240, 240, 240), 160, True),
    ((10, 80, 10), (240, 140, 20), (240, 240, 240), (200, 0, 120), 145, False),
]
# same team shirt and white pads; only helmet / gloves / height / stance differ
SAME_KIT = [
    ((30, 30, 140), (200, 40, 40), (235, 235, 235), (20, 120, 20), 150, False),
    ((20, 20, 20), (200, 40, 40), (235, 235, 235), (240, 240, 240), 138, False),
    ((30, 30, 140), (200, 40, 40), (235, 235, 235), (230, 200, 0), 160, True),
]
BOWLERS = [(220, 220, 30), (30, 200, 220), (220, 30, 200), (90, 40, 10), (250, 250, 250)]


def make(path, duration=480, fps=25, seed=1, kit="distinct", n_batters=3, n_bowlers=4, view="batter",
         w=640, h=360):
    rng = np.random.default_rng(seed)
    players = (DISTINCT if kit == "distinct" else SAME_KIT)[:n_batters]
    # balls every 6-12 s; batters change every 3-8 balls, in a repeating-ish order
    times, bats, bowls = [], [], []
    t, cur, left = 5.0, 0, int(rng.integers(3, 9))
    k = 0
    while t < duration - 5:
        times.append(round(t, 2))
        bats.append(cur)
        bowls.append(k % n_bowlers)
        k += 1
        left -= 1
        if left == 0:
            cur = int((cur + rng.integers(1, n_batters)) % n_batters)
            left = int(rng.integers(3, 9))
        t += float(rng.uniform(6, 12))
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.stack([70 + 30 * np.sin(xx / 41.0), 120 + 25 * np.cos(yy / 29.0), 60 + 0 * xx], -1)
    bg = (bg + rng.normal(0, 6, (h, w, 3))).clip(0, 255).astype(np.float32)
    p = subprocess.Popen([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "23", "-pix_fmt", "yuv420p", "-g", "50", path], stdin=subprocess.PIPE)
    for i in range(int(duration * fps)):
        tt = i / fps
        light = 1.0 + 0.10 * np.sin(tt / 60.0)  # slow light change over the session
        f = bg * light
        # which batter is in: the one for the next ball (they walk in a few seconds before)
        j = int(np.searchsorted(times, tt - 2.0))
        j = min(j, len(times) - 1)
        helmet, shirt, pads, gloves, ht, lefty = players[bats[j]]
        b = times[j]
        sc = 0.5 if view == "bowler" else 1.0  # from behind the bowler the batter is at the far end
        base_y = 200 if view == "bowler" else 300
        ht = int(ht * sc)
        bw = int(40 * sc)
        bx = (330 if lefty else 290) if view == "batter" else (322 if lefty else 302)
        bx += int(6 * sc * np.sin(tt * 0.9 + 0.3 * np.sin(tt * 0.23)))
        top = base_y - ht
        hh = int(22 * sc)
        f[top:top + hh, bx + bw // 8:bx + bw - bw // 8] = helmet
        f[top + hh:top + hh + ht // 3, bx:bx + bw] = shirt
        f[top + hh + ht // 3:base_y, bx + bw // 12:bx + bw - bw // 12] = pads
        gx = bx - int(12 * sc) if not lefty else bx + bw
        f[top + hh + ht // 4:top + hh + int(12 * sc) + ht // 4, gx:gx + int(12 * sc)] = gloves
        bowler = BOWLERS[bowls[j] % len(BOWLERS)]
        if view == "bowler" and b - 4.0 <= tt <= b - 0.3:
            # run-up: starts big near the camera, gets smaller towards the batter
            q = (tt - (b - 4.0)) / 3.7
            size = int(150 - 110 * q)
            y1 = int(360 - 150 * q)
            x0 = 280 + int(20 * np.sin(q * 3))
            f[max(0, y1 - size):y1, x0:x0 + size // 3] = bowler
            f[max(0, y1 - size):max(0, y1 - size) + size // 6, x0:x0 + size // 3] = (40, 30, 20)  # hair/cap
        if b - 1.2 <= tt <= b + 0.8:  # delivery
            q = (tt - (b - 1.2)) / 2.0
            if view == "batter":
                f[int(10 + q * 120):int(10 + q * 120) + 30, 335:350] = bowler
            if tt >= b - 0.2:
                s_ = (tt - (b - 0.2)) / 1.0
                x0 = gx + (-int(s_ * 120 * sc) if lefty else int(s_ * 120 * sc))
                f[top + int(40 * sc):top + int(90 * sc), max(0, x0):max(0, x0) + int(40 * sc)] = (180, 140, 90)
        f += rng.normal(0, 3, (h, w, 3))
        p.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return times, bats, bowls


if __name__ == "__main__":
    print(make(sys.argv[1]))
