"""Builds a synthetic 'net session' video: a batter figure that fidgets all the
time, and a fast burst of motion (delivery + shot) at known times."""
import subprocess, sys
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")
from ballcutter.ffmpeg_tools import ffmpeg_exe

def make(path, duration=120, fps=25, balls=(10, 31, 50, 72, 90, 108), w=640, h=360):
    rng = np.random.default_rng(1)
    bg = (rng.random((h, w)) * 60 + 80).astype(np.uint8)
    p = subprocess.Popen([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray",
                          "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-g", "50", path], stdin=subprocess.PIPE)
    for i in range(duration * fps):
        t = i / fps
        f = bg.copy()
        # fidgeting batter: slow sway
        x = int(300 + 15 * np.sin(t * 0.8)); f[150:300, x:x + 40] = 230
        for b in balls:
            if b - 1.0 <= t <= b + 0.6:   # run-up/ball/swing
                k = (t - (b - 1.0)) / 1.6
                bx = int(20 + k * 560); f[100:200, bx:bx + 60] = 20
                f[140:180, x - 60 + int(k * 150): x - 20 + int(k * 150)] = 250  # bat swing
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()

if __name__ == "__main__":
    make(sys.argv[1])
