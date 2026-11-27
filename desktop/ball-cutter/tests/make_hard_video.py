"""A deliberately difficult synthetic net session, to measure missed balls.

It imitates the things that make real footage hard:
- balls bowled close together (4-6 s) and far apart (up to 30 s)
- weak deliveries (a leave or a soft block) with very little movement
- a fielder / coach walking around all the time in one part of the frame
- the batter walking around between balls (sustained medium movement)
- light flicker (clouds / auto exposure) and sensor noise
Returns the true ball times so a test can count hits and misses.
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ballcutter.ffmpeg_tools import ffmpeg_exe  # noqa: E402


def schedule(duration, seed):
    rng = np.random.default_rng(seed)
    t, balls = 6.0, []
    while t < duration - 6:
        # strength: 1 = full shot, 0.5 = block, 0.3 = leave
        balls.append((round(t, 2), float(rng.choice([1.0, 1.0, 0.7, 0.5, 0.3]))))
        t += float(rng.choice([rng.uniform(4.0, 6.0), rng.uniform(7, 14), rng.uniform(14, 30)], p=[0.3, 0.5, 0.2]))
    return balls


def make(path, duration=420, fps=25, seed=7, w=640, h=360, view="batter", switch=False):
    """switch=True: a left-hander bats in the second half (mirrored stance and shots)."""
    rng = np.random.default_rng(seed + 100)
    balls = schedule(duration, seed)
    yy, xx = np.mgrid[0:h, 0:w]
    bg = (90 + 40 * np.sin(xx / 37.0) * np.cos(yy / 23.0) + rng.normal(0, 8, (h, w))).clip(0, 255).astype(np.float32)
    walk_until = -1.0
    walk_dir = 1
    bx_home = 300
    bxo = 0.0
    p = subprocess.Popen([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray",
                          "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "23", "-pix_fmt", "yuv420p", "-g", "50", path], stdin=subprocess.PIPE)
    for i in range(int(duration * fps)):
        t = i / fps
        f = bg * (1.0 + 0.06 * np.sin(t * 0.35) + 0.03 * np.sin(t * 2.1))  # light changes
        # fielder walking back and forth in the top-left corner all session
        fx = int(40 + 120 * (0.5 + 0.5 * np.sin(t * 0.6)))
        f[30:110, fx:fx + 25] = 200
        # batter: sways, and sometimes walks away and back between balls
        near = any(b - 2.5 <= t <= b + 2.0 for b, _ in balls)
        if not near and t > walk_until and rng.random() < 0.004:
            walk_until = t + rng.uniform(3, 7)
            walk_dir = rng.choice([-1, 1])
        if t < walk_until and not near:
            bxo += walk_dir * 2.0
        else:
            bxo *= 0.96
        lefty = switch and t > duration / 2
        bx_home = 380 if lefty else 300
        bx = int(np.clip(bx_home + bxo + 8 * np.sin(t * 0.9), 120, 520))
        f[150:300, bx:bx + 40] = 230
        for b, s in balls:
            if b - 1.2 <= t <= b + 0.8:
                k = (t - (b - 1.2)) / 2.0
                if view == "bowler":  # bowler running away from camera, getting smaller
                    size = int(90 - 50 * k)
                    by = int(200 - 60 * k)
                    f[by:by + size, 300:300 + size // 2] = 25
                else:  # bowler's arm / ball entering the top of the frame
                    ay = int(10 + k * 120)
                    ax = 400 if lefty else 330
                    f[ay:ay + int(30 * s + 8), ax:ax + 15] = 30
                    # tiny ball travelling to the batter
                    f[int(20 + k * 260):int(20 + k * 260) + 6, ax + 10:ax + 16] = 255
                if t >= b - 0.2:  # bat swing, size depends on the shot
                    sw = int(150 * s)
                    q = (t - (b - 0.2)) / 1.0
                    x0 = bx + 40 - int(q * sw) - int(50 * s + 10) if lefty else bx - 40 + int(q * sw)
                    f[160:160 + int(60 * s + 10), x0:x0 + int(50 * s + 10)] = 250
        f += rng.normal(0, 3, (h, w))
        p.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return [b for b, _ in balls]


def score(found_peaks, truth, tol=1.5):
    """Returns (hits, misses, false_alarms)."""
    used = set()
    hits = 0
    for b in truth:
        m = [i for i, t in enumerate(found_peaks) if abs(t - b) <= tol and i not in used]
        if m:
            used.add(min(m, key=lambda i: abs(found_peaks[i] - b)))
            hits += 1
    return hits, len(truth) - hits, len(found_peaks) - len(used)


if __name__ == "__main__":
    print(make(sys.argv[1], view=sys.argv[2] if len(sys.argv) > 2 else "batter", switch="switch" in sys.argv))
