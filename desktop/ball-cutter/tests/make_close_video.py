"""Synthetic net session filmed the way many analysts do it: camera close to / above the batter, so
the batter fills the whole height of the picture. She fidgets all the time, walks away and back
between many balls, and plays a full stride and swing to most balls (sometimes only a small leave).
Returns the true ball times."""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ballcutter.ffmpeg_tools import ffmpeg_exe  # noqa: E402


def make(path, duration=420, fps=25, seed=3, w=640, h=360):
    rng = np.random.default_rng(seed)
    balls, t = [], 8.0
    while t < duration - 8:
        balls.append((round(t, 2), "leave" if rng.random() < 0.2 else "shot"))
        t += float(rng.uniform(10, 22))
    yy, xx = np.mgrid[0:h, 0:w]
    bg = (90 + 35 * np.sin(xx / 31.0) * np.cos(yy / 47.0) + rng.normal(0, 7, (h, w))).clip(0, 255).astype(np.float32)
    p = subprocess.Popen([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray",
                          "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "23", "-pix_fmt", "yuv420p", "-g", "50", path], stdin=subprocess.PIPE)
    walks = []  # walk away and back halfway between many balls
    for (a, _), (b, _) in zip(balls, balls[1:]):
        if rng.random() < 0.7:
            mid = (a + b) / 2
            walks.append((mid - 2.0, mid + 2.0, rng.choice([-1, 1])))
    for i in range(int(duration * fps)):
        t = i / fps
        f = bg * (1.0 + 0.05 * np.sin(t * 0.3))
        x = 260 + 10 * np.sin(t * 0.7) + 6 * np.sin(t * 1.9)  # fidgeting
        for a, b, d in walks:
            if a <= t <= b:
                x += d * 90 * np.sin(np.pi * (t - a) / (b - a))
        top = 0
        for bt, kind in balls:
            if bt - 0.6 <= t <= bt + 0.8:  # stride towards the ball, then back
                q = (t - (bt - 0.6)) / 1.4
                x += (25 if kind == "shot" else 8) * np.sin(np.pi * q)
                top = int(12 * np.sin(np.pi * q))
        xi = int(x)
        f[top:h, xi:xi + 110] = 215  # the batter, full height
        f[top:top + 60, xi + 25:xi + 85] = 60  # helmet
        for bt, kind in balls:
            if kind == "shot" and bt - 0.1 <= t <= bt + 0.7:  # bat swing across the whole body
                q = (t - (bt - 0.1)) / 0.8
                bx = int(xi - 60 + q * 260)
                by = int(120 + 140 * np.sin(np.pi * q))
                f[max(0, by - 70):by + 70, max(0, bx):max(0, bx) + 40] = 245
        f += rng.normal(0, 3, (h, w))
        p.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return [b for b, _ in balls]


if __name__ == "__main__":
    print(make(sys.argv[1]))
