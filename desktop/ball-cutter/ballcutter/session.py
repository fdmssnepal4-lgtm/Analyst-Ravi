"""Remembers the reviewed ball list (keep/skip, added balls, batter and bowler names) for each video,
so the work is not lost when the app is closed."""
from __future__ import annotations

import hashlib
import json
import os

from .detect import Clip, Params, cache_dir


def _path(video: str) -> str:
    st = os.stat(video)
    key = f"{os.path.abspath(video)}|{st.st_size}|{int(st.st_mtime)}"
    return os.path.join(cache_dir(), "review_" + hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")


def save(video: str, clips: list[Clip], params: Params, preset: str) -> None:
    data = {
        "version": 1,
        "params": params.to_dict(),
        "preset": preset,
        "clips": [{"start": c.start, "end": c.end, "peak": c.peak, "score": c.score, "enabled": c.enabled,
                   "manual": c.manual, "batter": c.batter, "bowler": c.bowler} for c in clips],
    }
    tmp = _path(video) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, _path(video))


def load(video: str):
    """Returns (clips, params, preset) or None."""
    try:
        with open(_path(video), encoding="utf-8") as f:
            data = json.load(f)
        clips = [Clip(d["start"], d["end"], d["peak"], d.get("score", 0.0), d.get("enabled", True),
                      d.get("manual", False), batter=d.get("batter", ""), bowler=d.get("bowler", ""))
                 for d in data["clips"]]
        return clips, Params.from_dict(data.get("params", {})), data.get("preset", "")
    except Exception:
        return None
