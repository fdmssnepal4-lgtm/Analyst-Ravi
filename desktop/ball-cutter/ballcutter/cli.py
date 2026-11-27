"""Command line use, for batch jobs:  python -m ballcutter.cli VIDEO [VIDEO...] --out FOLDER"""
from __future__ import annotations

import argparse
import sys

from .detect import PRESETS, Params, analyze, detect_balls
from .export import ExportOptions, export_video, fmt_time


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cut cricket training video into ball-by-ball clips.")
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--view", choices=["batter", "bowler"], default="batter",
                    help="batter = camera above/side of batter, bowler = camera behind the bowler")
    ap.add_argument("--sensitivity", type=float)
    ap.add_argument("--min-gap", type=float)
    ap.add_argument("--pre", type=float)
    ap.add_argument("--post", type=float)
    ap.add_argument("--accurate", action="store_true", help="re-encode for frame-exact cuts (slower)")
    ap.add_argument("--no-reel", action="store_true")
    ap.add_argument("--list-only", action="store_true", help="only print detected balls")
    a = ap.parse_args(argv)
    preset = list(PRESETS.values())[0 if a.view == "batter" else 1]
    p = Params.from_dict(preset.to_dict())
    for k, v in (("sensitivity", a.sensitivity), ("min_gap", a.min_gap), ("pre_roll", a.pre), ("post_roll", a.post)):
        if v is not None:
            setattr(p, k, v)
    for path in a.videos:
        print(f"Analysing {path} ...", flush=True)
        m = analyze(path, progress=lambda f: print(f"\r  {f * 100:5.1f}%", end="", flush=True))
        print()
        clips = detect_balls(m, p)
        print(f"  {len(clips)} balls found")
        for i, c in enumerate(clips, 1):
            print(f"  {i:3d}  {fmt_time(c.start)} - {fmt_time(c.end)}  shot {fmt_time(c.peak)}  conf {c.score:.1f}")
        if not a.list_only:
            folder, _ = export_video(path, m.info, clips,
                                  ExportOptions(a.out, accurate=a.accurate, reel=not a.no_reel),
                                  progress=lambda f, s: print(f"\r  {s:<60}", end="", flush=True))
            print(f"\n  saved to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
