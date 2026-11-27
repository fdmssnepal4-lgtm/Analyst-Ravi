"""Ball Cutter: desktop app that cuts cricket training video into ball-by-ball clips."""
from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

import numpy as np

from ballcutter import __version__
from ballcutter.detect import (PRESETS, Cancelled, Clip, Motion, Params, analyze, compute_signal,
                               detect_balls, fix_bounds, manual_clip)
from ballcutter import session
from ballcutter.export import (ExportOptions, cut, export_players, export_video, fmt_time, remove_clip_files,
                               write_report)
from ballcutter.ffmpeg_tools import extract_frame, open_with_system_player, probe

APP_NAME = "Ball Cutter"
VIDEO_TYPES = [("Video files", "*.mp4 *.mov *.m4v *.mkv *.avi *.mts *.m2ts *.mxf *.wmv *.MP4 *.MOV *.MTS"),
               ("All files", "*.*")]
SETTINGS_VERSION = 2
DETAIL_SPAN = 60.0  # seconds shown in the zoomed graph
CUSTOM = "Custom"

COL_BG = "#ffffff"
COL_LINE = "#1f4e9c"
COL_THR = "#d9480f"
COL_CLIP = "#c9e7cf"
COL_CLIP_OFF = "#e4e4e4"
COL_SEL = "#ffd76e"
COL_CURSOR = "#7a1fa2"


def resource(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def settings_path() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "BallCutter")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")


class VideoItem:
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.motion: Motion | None = None
        self.signal = None
        self.clips: list[Clip] = []
        self.params = Params()
        self.preset = list(PRESETS)[0]
        self.status = "waiting"
        self.edited = False
        self.analysed = False  # set by the worker thread as soon as its analysis is finished


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__} – ball-by-ball clips for cricket training")
        self.geometry("1480x940")
        self.minsize(1100, 700)
        try:
            self.iconbitmap(resource(os.path.join("packaging", "icon.ico")))
        except tk.TclError:
            pass
        self.videos: list[VideoItem] = []
        self.cur: VideoItem | None = None
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()
        self.detail_center = 0.0
        self.cursor_t: float | None = None
        self.loading_widgets = False
        self.redetect_job = None
        self.thumb_img = None
        self.tmp = tempfile.mkdtemp(prefix="ballcutter_")
        self.settings = self._load_settings()
        self.batters: list[str] = list(self.settings.get("batters", []))
        self.bowlers: list[str] = list(self.settings.get("bowlers", []))
        self.bowling_order: list[str] = list(self.settings.get("bowling_order", []))
        self.autosave_job = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_job = self.after(100, self._poll)

    # ------------------------------------------------------------------ settings
    def _load_settings(self) -> dict:
        try:
            with open(settings_path(), encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            return {}
        if s.get("version", 1) < SETTINGS_VERSION:  # detection defaults changed: start from the new ones
            s.pop("params", None)
            s.pop("preset", None)
        return s

    def _save_settings(self):
        s = {
            "out_dir": self.out_dir.get(),
            "accurate": self.accurate.get(),
            "do_clips": self.do_clips.get(), "do_reel": self.do_reel.get(),
            "do_csv": self.do_csv.get(), "do_edl": self.do_edl.get(),
            "over_naming": self.over_naming.get(), "bpo": self.bpo.get(),
            "preset": self.preset_var.get(), "params": self._params_from_widgets().to_dict(),
            "last_dir": self.settings.get("last_dir", ""),
            "version": SETTINGS_VERSION,
            "batters": self.batters, "bowlers": self.bowlers, "bowling_order": self.bowling_order,
            "do_players": self.do_players.get(),
        }
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(s, f, indent=1)
        except Exception:
            pass

    # ------------------------------------------------------------------ layout
    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Treeview", rowheight=24)

        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        # ---- left: videos
        left = ttk.LabelFrame(outer, text=" 1. Videos ", padding=6)
        left.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        bar = ttk.Frame(left)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Button(bar, text="+ Add videos…", command=self.add_videos).pack(side="left")
        ttk.Button(bar, text="Remove", command=self.remove_video).pack(side="left", padx=4)
        self.vlist = ttk.Treeview(left, columns=("status",), show="tree headings", height=12, selectmode="browse")
        self.vlist.heading("#0", text="File")
        self.vlist.heading("status", text="Status")
        self.vlist.column("#0", width=200)
        self.vlist.column("status", width=95, anchor="center")
        self.vlist.grid(row=1, column=0, sticky="nsew", pady=6)
        self.vlist.bind("<<TreeviewSelect>>", lambda e: self._on_video_select())
        ttk.Button(left, text="Find balls in all videos", style="Big.TButton",
                   command=self.analyze_all).grid(row=2, column=0, sticky="ew")
        ttk.Label(left, text="Analysis reads each file once (about\n2–10 min per hour of HD video). After\n"
                             "that, changing settings is instant.",
                  foreground="#555").grid(row=3, column=0, sticky="w", pady=(6, 0))

        # ---- top: detection settings
        top = ttk.LabelFrame(outer, text=" 2. Detection settings (for the selected video) ", padding=6)
        top.grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Label(top, text="Camera position:").grid(row=0, column=0, sticky="w")
        self.preset_var = tk.StringVar(value=self.settings.get("preset", list(PRESETS)[0]))
        cb = ttk.Combobox(top, textvariable=self.preset_var, values=list(PRESETS) + [CUSTOM],
                          state="readonly", width=40)
        cb.grid(row=0, column=1, columnspan=3, sticky="w", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._apply_preset())

        sp = self.settings.get("params") or list(PRESETS.values())[0].to_dict()
        p0 = Params.from_dict(sp)
        self.sens = tk.DoubleVar(value=p0.sensitivity)
        self.min_gap = tk.DoubleVar(value=p0.min_gap)
        self.pre = tk.DoubleVar(value=p0.pre_roll)
        self.post = tk.DoubleVar(value=p0.post_roll)
        self.auto_ext = tk.BooleanVar(value=p0.auto_extend)
        self.roi = p0.roi

        ttk.Label(top, text="Sensitivity:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        sf = ttk.Frame(top)
        sf.grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(sf, text="fewer").pack(side="left")
        ttk.Scale(sf, from_=1, to=10, variable=self.sens, length=180,
                  command=lambda v: self._settings_changed()).pack(side="left", padx=4)
        ttk.Label(sf, text="more balls").pack(side="left")

        def spin(row, col, label, var, lo, hi, step, tip):
            ttk.Label(top, text=label).grid(row=row, column=col, sticky="e", padx=(14, 2), pady=(6, 0))
            s = ttk.Spinbox(top, from_=lo, to=hi, increment=step, textvariable=var, width=5,
                            command=self._settings_changed)
            s.grid(row=row, column=col + 1, sticky="w", pady=(6, 0))
            s.bind("<KeyRelease>", lambda e: self._settings_changed())
            ttk.Label(top, text=tip, foreground="#666").grid(row=row, column=col + 2, sticky="w", pady=(6, 0))

        spin(1, 2, "Seconds before shot:", self.pre, 0, 30, 0.5, "")
        spin(1, 5, "Seconds after shot:", self.post, 0, 30, 0.5, "")
        spin(2, 2, "Min. seconds between balls:", self.min_gap, 2, 120, 1, "")
        ttk.Checkbutton(top, text="Stretch to cover whole movement", variable=self.auto_ext,
                        command=self._settings_changed).grid(row=2, column=5, columnspan=3, sticky="w",
                                                             padx=(14, 0), pady=(6, 0))
        rf = ttk.Frame(top)
        rf.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(rf, text="Detection area…", command=self.choose_roi).pack(side="left")
        self.roi_label = ttk.Label(rf, text="whole frame", foreground="#666")
        self.roi_label.pack(side="left", padx=6)
        ttk.Button(top, text="Apply to all videos", command=self.apply_all).grid(
            row=0, column=5, columnspan=3, sticky="e")

        # ---- centre: graphs + clip list
        mid = ttk.Frame(outer)
        mid.grid(row=1, column=1, sticky="nsew", pady=8)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(3, weight=1)

        self.info_label = ttk.Label(mid, text="Add your training videos on the left to begin.",
                                    font=("Segoe UI", 10, "bold"))
        self.info_label.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(mid, text="Whole session – click to zoom there. Green = a ball clip, orange line = detection level.",
                  foreground="#555").grid(row=1, column=0, sticky="w")
        self.ov = tk.Canvas(mid, height=90, bg=COL_BG, highlightthickness=1, highlightbackground="#bbb")
        self.ov.grid(row=2, column=0, sticky="ew")
        self.ov.bind("<Configure>", lambda e: self.redraw())
        self.ov.bind("<Button-1>", self._click_overview)

        lower = ttk.Frame(mid)
        lower.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        lower.columnconfigure(0, weight=1)
        lower.rowconfigure(1, weight=1)
        ttk.Label(lower, text="Zoom (60 s, mouse wheel or ← → to scroll) – click a clip to select it; "
                              "double-click empty space to add a missed ball.", foreground="#555").grid(row=0, column=0, sticky="w")
        self.dt = tk.Canvas(lower, height=150, bg=COL_BG, highlightthickness=1, highlightbackground="#bbb")
        self.dt.grid(row=1, column=0, sticky="new")
        self.dt.bind("<Configure>", lambda e: self.redraw())
        self.dt.bind("<Button-1>", self._click_detail)
        self.dt.bind("<Double-Button-1>", self._dbl_detail)
        self.dt.bind("<MouseWheel>", self._wheel_detail)
        self.dt.bind("<Button-4>", lambda e: self._pan(-10))
        self.dt.bind("<Button-5>", lambda e: self._pan(10))

        thumbf = ttk.Frame(lower)
        thumbf.grid(row=2, column=0, sticky="nw", pady=8)
        self.thumb = ttk.Label(thumbf, text="(frame at the shot appears here)", width=34, anchor="center",
                               relief="groove")
        self.thumb.pack(side="left")
        ctl = ttk.Frame(thumbf, padding=(10, 0))
        ctl.pack(side="left", anchor="n")
        ttk.Button(ctl, text="▶  Watch this ball", style="Big.TButton", command=self.preview).grid(
            row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(ctl, text="Start:").grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Button(ctl, text="− 0.5 s", width=7, command=lambda: self.nudge("start", -0.5)).grid(row=1, column=1, pady=(8, 0))
        ttk.Button(ctl, text="+ 0.5 s", width=7, command=lambda: self.nudge("start", 0.5)).grid(row=1, column=2, pady=(8, 0))
        ttk.Label(ctl, text="End:").grid(row=2, column=0, sticky="e")
        ttk.Button(ctl, text="− 0.5 s", width=7, command=lambda: self.nudge("end", -0.5)).grid(row=2, column=1)
        ttk.Button(ctl, text="+ 0.5 s", width=7, command=lambda: self.nudge("end", 0.5)).grid(row=2, column=2)
        ttk.Button(ctl, text="Keep / skip  (Space)", command=self.toggle).grid(row=3, column=0, columnspan=3,
                                                                              sticky="ew", pady=(8, 0))
        ttk.Button(ctl, text="Delete  (Del)", command=self.delete_clip).grid(row=4, column=0, columnspan=3,
                                                                           sticky="ew", pady=(4, 0))
        ttk.Button(ctl, text="Re-detect (drop my edits)", command=self.force_redetect).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        right = ttk.LabelFrame(outer, text=" 3. Balls found ", padding=6)
        right.grid(row=1, column=2, sticky="nsew", pady=8, padx=(8, 0))
        right.rowconfigure(0, weight=1)
        cols = ("n", "keep", "start", "len", "batter", "bowler", "conf")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", selectmode="extended", height=16)
        for c, t, w in zip(cols, ("Ball", "Keep", "Start", "Sec", "Batter", "Bowler", "Str."),
                           (36, 42, 64, 34, 80, 80, 38)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("off", foreground="#999")
        self.tree.tag_configure("weak", background="#fff4d6")
        self.tree.tag_configure("manual", background="#e6f0ff")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_clip_select())
        self.tree.bind("<space>", lambda e: (self.toggle(), "break")[1])
        self.tree.bind("<Delete>", lambda e: self.delete_clip())
        self.tree.bind("<Return>", lambda e: self.preview())
        self.tree.bind("<Double-Button-1>", lambda e: self.preview())
        self.count_label = ttk.Label(right, text="", foreground="#333")
        self.count_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(right, text="Yellow = weak detection, worth a look.  Blue = added by you.\n"
                              "Shift/Ctrl-click to select several balls.",
                  foreground="#666").grid(row=2, column=0, columnspan=2, sticky="w")

        pl = ttk.LabelFrame(right, text=" Players ", padding=6)
        pl.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        pl.columnconfigure(1, weight=1)
        self.batter_var = tk.StringVar()
        self.bowler_var = tk.StringVar()
        ttk.Label(pl, text="Batter:").grid(row=0, column=0, sticky="w")
        self.batter_cb = ttk.Combobox(pl, textvariable=self.batter_var, values=self.batters, width=14)
        self.batter_cb.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(pl, text="From this ball on", command=lambda: self.set_player("batter", True)).grid(row=0, column=2)
        ttk.Button(pl, text="Selected only", command=lambda: self.set_player("batter", False)).grid(
            row=0, column=3, padx=(4, 0))
        ttk.Label(pl, text="Bowler:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.bowler_cb = ttk.Combobox(pl, textvariable=self.bowler_var, values=self.bowlers, width=14)
        self.bowler_cb.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 0))
        ttk.Button(pl, text="Bowling order…", command=self.bowling_rotation).grid(row=1, column=2, pady=(4, 0))
        ttk.Button(pl, text="Selected only", command=lambda: self.set_player("bowler", False)).grid(
            row=1, column=3, padx=(4, 0), pady=(4, 0))
        pb = ttk.Frame(pl)
        pb.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Button(pb, text="Squad list…", command=self.edit_squad).pack(side="left")
        ttk.Button(pb, text="Clear names (selected)", command=self.clear_players).pack(side="left", padx=4)
        ttk.Button(right, text="Save report for developer…", command=self.save_report).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # ---- bottom: export
        bot = ttk.LabelFrame(outer, text=" 4. Export ", padding=6)
        bot.grid(row=2, column=1, columnspan=2, sticky="ew")
        bot.columnconfigure(1, weight=1)
        ttk.Label(bot, text="Save to:").grid(row=0, column=0, sticky="w")
        self.out_dir = tk.StringVar(value=self.settings.get("out_dir") or
                                    os.path.join(os.path.expanduser("~"), "Videos", "Ball Cutter"))
        ttk.Entry(bot, textvariable=self.out_dir).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(bot, text="Browse…", command=self.choose_out).grid(row=0, column=2)
        ttk.Button(bot, text="Open folder", command=self.open_out).grid(row=0, column=3, padx=(4, 0))

        opt = ttk.Frame(bot)
        opt.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.accurate = tk.BooleanVar(value=self.settings.get("accurate", False))
        ttk.Radiobutton(opt, text="Fast – no quality loss (clip may start ~1 s early)",
                        variable=self.accurate, value=False).pack(side="left")
        ttk.Radiobutton(opt, text="Exact frame (re-encodes, slower)", variable=self.accurate,
                        value=True).pack(side="left", padx=(10, 0))
        opt2 = ttk.Frame(bot)
        opt2.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.do_clips = tk.BooleanVar(value=self.settings.get("do_clips", True))
        self.do_reel = tk.BooleanVar(value=self.settings.get("do_reel", True))
        self.do_csv = tk.BooleanVar(value=self.settings.get("do_csv", True))
        self.do_edl = tk.BooleanVar(value=self.settings.get("do_edl", True))
        self.over_naming = tk.BooleanVar(value=self.settings.get("over_naming", False))
        self.bpo = tk.IntVar(value=self.settings.get("bpo", 6))
        ttk.Checkbutton(opt2, text="One file per ball", variable=self.do_clips).pack(side="left")
        ttk.Checkbutton(opt2, text="All balls joined in one video", variable=self.do_reel).pack(side="left", padx=8)
        ttk.Checkbutton(opt2, text="Ball list (CSV/Excel)", variable=self.do_csv).pack(side="left", padx=8)
        ttk.Checkbutton(opt2, text="Premiere Pro EDL", variable=self.do_edl).pack(side="left", padx=8)
        self.do_players = tk.BooleanVar(value=self.settings.get("do_players", True))
        ttk.Checkbutton(opt2, text="Folder per player", variable=self.do_players).pack(side="left", padx=8)
        ttk.Checkbutton(opt2, text="Name by over, balls/over:",
                        variable=self.over_naming).pack(side="left", padx=(16, 2))
        ttk.Spinbox(opt2, from_=1, to=12, textvariable=self.bpo, width=3).pack(side="left")

        act = ttk.Frame(bot)
        act.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        act.columnconfigure(2, weight=1)
        ttk.Button(act, text="Export this video", style="Big.TButton", command=lambda: self.export(False)).grid(
            row=0, column=0)
        ttk.Button(act, text="Export all videos", style="Big.TButton", command=lambda: self.export(True)).grid(
            row=0, column=1, padx=6)
        self.prog = ttk.Progressbar(act, mode="determinate", maximum=1000)
        self.prog.grid(row=0, column=2, sticky="ew", padx=6)
        self.cancel_btn = ttk.Button(act, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=3)
        self.status = ttk.Label(bot, text="Ready.", foreground="#333")
        self.status.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self.bind_all("<Left>", lambda e: self._key_pan(e, -5))
        self.bind_all("<Right>", lambda e: self._key_pan(e, 5))
        self._update_roi_label()

    # ------------------------------------------------------------------ videos
    def add_videos(self):
        paths = filedialog.askopenfilenames(title="Choose training videos", filetypes=VIDEO_TYPES,
                                            initialdir=self.settings.get("last_dir") or None)
        if not paths:
            return
        self.settings["last_dir"] = os.path.dirname(paths[0])
        self.add_paths(paths)

    def add_paths(self, paths):
        known = {v.path for v in self.videos}
        first = None
        for p in paths:
            if p in known:
                continue
            v = VideoItem(p)
            v.params = self._params_from_widgets()
            v.preset = self.preset_var.get()
            self.videos.append(v)
            self.vlist.insert("", "end", iid=str(id(v)), text=v.name, values=(v.status,))
            first = first or v
        if first:
            self.vlist.selection_set(str(id(first)))
            self.analyze_all()

    def remove_video(self):
        v = self.cur
        if not v or self._busy():
            return
        self.vlist.delete(str(id(v)))
        self.videos.remove(v)
        self.cur = None
        if self.videos:
            self.vlist.selection_set(str(id(self.videos[0])))
        else:
            self._show_video(None)

    def _set_vstatus(self, v: VideoItem, s: str):
        v.status = s
        if self.vlist.exists(str(id(v))):
            self.vlist.item(str(id(v)), values=(s,))

    def _on_video_select(self):
        sel = self.vlist.selection()
        v = next((x for x in self.videos if str(id(x)) == (sel[0] if sel else "")), None)
        if self.cur is not None and v is not self.cur:
            self.cur.params = self._params_from_widgets()
            self.cur.preset = self.preset_var.get()
        self._show_video(v)

    def _show_video(self, v: VideoItem | None):
        self.cur = v
        self.cursor_t = None
        if v is None:
            self.info_label.config(text="Add your training videos on the left to begin.")
            self._fill_tree()
            self.redraw()
            return
        self.loading_widgets = True
        self.preset_var.set(v.preset)
        self._params_to_widgets(v.params)
        self.loading_widgets = False
        self._update_info()
        self.detail_center = v.clips[0].peak if v.clips else DETAIL_SPAN / 2
        self._fill_tree()
        self.redraw()

    def _update_info(self):
        v = self.cur
        if not v:
            return
        if v.motion:
            i = v.motion.info
            kept = sum(c.enabled for c in v.clips)
            if v.signal is not None and v.signal.mode == "pattern":
                how = "tracker: learned delivery pattern" + (" (+ mirrored, left & right-handers)"
                                                              if v.signal.templates > 1 else "")
            else:
                how = "tracker: movement bursts (too few clear balls to learn a pattern)"
            self.info_label.config(text=f"{v.name}   ·   {fmt_time(v.motion.duration)}   ·   "
                                        f"{i.width}x{i.height} @ {i.fps:.0f} fps   ·   {kept} balls   ·   {how}")
        else:
            self.info_label.config(text=f"{v.name}   ·   {v.status}")

    # ------------------------------------------------------------------ settings widgets
    def _params_from_widgets(self) -> Params:
        def f(var, default):
            try:
                return float(var.get())
            except (tk.TclError, ValueError):
                return default
        return Params(sensitivity=f(self.sens, 6), min_gap=max(1.0, f(self.min_gap, 6)),
                      pre_roll=max(0.0, f(self.pre, 3)), post_roll=max(0.0, f(self.post, 3)),
                      auto_extend=bool(self.auto_ext.get()), roi=self.roi)

    def _params_to_widgets(self, p: Params):
        self.sens.set(round(p.sensitivity, 1))
        self.min_gap.set(p.min_gap)
        self.pre.set(p.pre_roll)
        self.post.set(p.post_roll)
        self.auto_ext.set(p.auto_extend)
        self.roi = p.roi
        self._update_roi_label()

    def _apply_preset(self):
        name = self.preset_var.get()
        if name in PRESETS:
            p = Params.from_dict(PRESETS[name].to_dict())
            p.roi = self.roi
            self.loading_widgets = True
            self._params_to_widgets(p)
            self.loading_widgets = False
        self._settings_changed(keep_preset=True)

    def _settings_changed(self, keep_preset=False):
        if self.loading_widgets:
            return
        if not keep_preset and self.preset_var.get() != CUSTOM:
            self.preset_var.set(CUSTOM)
        if self.redetect_job:
            self.after_cancel(self.redetect_job)
        self.redetect_job = self.after(300, self._redetect_current)

    def _redetect_current(self, force=False):
        self.redetect_job = None
        v = self.cur
        if not v:
            return
        v.params = self._params_from_widgets()
        v.preset = self.preset_var.get()
        if v.motion:
            self._detect(v, keep_edits=not force)
            self._fill_tree()
            self._update_info()
            self.redraw()

    def force_redetect(self):
        if self.cur and self.cur.motion:
            self.cur.edited = False
            self._redetect_current(force=True)

    def _detect(self, v: VideoItem, keep_edits=True):
        v.signal = compute_signal(v.motion, v.params)
        new = detect_balls(v.motion, v.params, v.signal)
        if keep_edits and v.edited:
            manual = [c for c in v.clips if c.manual]
            skipped = [c.peak for c in v.clips if not c.enabled and not c.manual]
            for c in new:
                if any(abs(c.peak - s) < 1.0 for s in skipped):
                    c.enabled = False
            new = fix_bounds(new + [m for m in manual if all(abs(m.peak - c.peak) > 1.0 for c in new)],
                             v.motion.duration)
        old = [c for c in v.clips if c.batter or c.bowler]
        if old:  # carry player names over to the re-detected balls
            for c in new:
                near = min(old, key=lambda o: abs(o.peak - c.peak))
                if abs(near.peak - c.peak) < 1.0:
                    c.batter, c.bowler = near.batter, near.bowler
                elif not c.batter:
                    before = [o for o in old if o.peak < c.peak and o.batter]
                    if before:  # batters bat in blocks: a new ball belongs to the batter in at the time
                        c.batter = before[-1].batter
        v.clips = new

    def apply_all(self):
        p = self._params_from_widgets()
        for v in self.videos:
            v.params = Params.from_dict(p.to_dict())
            v.preset = self.preset_var.get()
            if v.motion:
                self._detect(v, keep_edits=False)
                v.edited = False
                self._set_vstatus(v, f"{sum(c.enabled for c in v.clips)} balls")
        self._fill_tree()
        self._update_info()
        self.redraw()
        self.status.config(text=f"Settings applied to {len(self.videos)} videos.")

    def _update_roi_label(self):
        if self.roi:
            x0, y0, x1, y1 = self.roi
            self.roi_label.config(text=f"box {int((x1 - x0) * 100)}% × {int((y1 - y0) * 100)}% of frame")
        else:
            self.roi_label.config(text="whole frame")

    def choose_roi(self):
        v = self.cur
        if not v:
            messagebox.showinfo(APP_NAME, "Add and select a video first.")
            return
        RoiDialog(self, v)

    def set_roi(self, roi):
        self.roi = roi
        self._update_roi_label()
        self._settings_changed()

    # ------------------------------------------------------------------ background work
    def _busy(self) -> bool:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Please wait for the current job to finish (or press Cancel).")
            return True
        return False

    def _start(self, target, *args):
        self.cancel_flag.clear()
        self.cancel_btn.config(state="normal")
        self.worker = threading.Thread(target=self._run_safe, args=(target, *args), daemon=True)
        self.worker.start()

    def _run_safe(self, target, *args):
        try:
            target(*args)
        except Cancelled:
            self.q.put(("status", "Cancelled."))
        except Exception as e:
            traceback.print_exc()
            self.q.put(("error", str(e)))
        finally:
            self.q.put(("idle",))

    def cancel(self):
        self.cancel_flag.set()
        self.status.config(text="Cancelling…")

    def analyze_all(self):
        todo = [v for v in self.videos if not v.analysed]
        if not todo:
            return
        if self.worker and self.worker.is_alive():
            return  # the running job picks up new files when it loops again
        self._start(self._analyze_job)

    def _analyze_job(self):
        while True:
            todo = [v for v in self.videos if not v.analysed and v.status != "error"]
            if not todo:
                return
            v = todo[0]
            self.q.put(("vstatus", v, "analysing"))

            def prog(f, v=v):
                self.q.put(("progress", f, f"Analysing {v.name}: {f * 100:.0f}%"))

            try:
                m = analyze(v.path, progress=prog, cancel=self.cancel_flag.is_set)
            except Cancelled:
                self.q.put(("vstatus", v, "waiting"))
                raise
            except Exception as e:
                self.q.put(("vstatus", v, "error"))
                self.q.put(("error", f"{v.name}: {e}"))
                continue
            self.q.put(("progress", 1.0, f"{v.name}: learning what a delivery looks like…"))
            compute_signal(m, v.params)  # learns the delivery pattern here, off the UI thread (cached)
            v.analysed = True
            self.q.put(("analysed", v, m))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    self.prog["value"] = msg[1] * 1000
                    self.status.config(text=msg[2])
                elif kind == "status":
                    self.status.config(text=msg[1])
                elif kind == "vstatus":
                    self._set_vstatus(msg[1], msg[2])
                    if msg[1] is self.cur:
                        self._update_info()
                elif kind == "analysed":
                    v, m = msg[1], msg[2]
                    v.motion = m
                    if v is self.cur:
                        v.params = self._params_from_widgets()
                    saved = session.load(v.path)
                    if saved:
                        v.clips, v.params, preset = saved
                        v.preset = preset or v.preset
                        v.signal = compute_signal(v.motion, v.params)
                        v.edited = True
                        msg_text = f"{v.name}: restored your earlier ball list and player names."
                    else:
                        self._detect(v, keep_edits=False)
                        msg_text = f"{v.name}: found {len(v.clips)} balls."
                    self._set_vstatus(v, f"{sum(c.enabled for c in v.clips)} balls")
                    if v is self.cur:
                        self._show_video(v)
                    self.status.config(text=msg_text)
                elif kind == "thumb":
                    self._show_thumb(msg[1], msg[2])
                elif kind == "open":
                    try:
                        open_with_system_player(msg[1])
                    except Exception as e:
                        messagebox.showerror(APP_NAME, f"Could not open the video player:\n{e}")
                elif kind == "error":
                    messagebox.showerror(APP_NAME, msg[1])
                elif kind == "exported":
                    self.status.config(text=f"Export finished: {msg[1]}")
                    extra = ("\n\nNote:\n" + "\n".join(msg[2])) if len(msg) > 2 and msg[2] else ""
                    if messagebox.askyesno(APP_NAME, f"Export finished.\n\n{msg[1]}{extra}\n\nOpen the folder?"):
                        self.open_out()
                elif kind == "idle":
                    self.cancel_btn.config(state="disabled")
                    self.prog["value"] = 0
        except queue.Empty:
            pass
        self._poll_job = self.after(100, self._poll)

    # ------------------------------------------------------------------ clip list
    def _fill_tree(self, select_uid=None, select_uids=None):
        self.tree.delete(*self.tree.get_children())
        v = self.cur
        if not v:
            self.count_label.config(text="")
            return
        n = 0
        for c in v.clips:
            if c.enabled:
                n += 1
            tags = ("off",) if not c.enabled else ("manual",) if c.manual else ("weak",) if c.score < 1.4 else ()
            self.tree.insert("", "end", iid=str(c.uid), tags=tags, values=(
                n if c.enabled else "–", "✓" if c.enabled else "✗", fmt_time(c.start),
                f"{c.length:.1f}", c.batter, c.bowler, "hand" if c.manual else f"{c.score:.1f}"))
        kept = sum(c.enabled for c in v.clips)
        self.count_label.config(text=f"{kept} balls kept, {len(v.clips) - kept} skipped")
        if select_uids:
            keep = [str(u) for u in select_uids if self.tree.exists(str(u))]
            if keep:
                self.tree.selection_set(keep)
                self.tree.see(keep[0])
        elif select_uid is not None and self.tree.exists(str(select_uid)):
            self.tree.selection_set(str(select_uid))
            self.tree.see(str(select_uid))

    def _sel_clip(self) -> Clip | None:
        if not self.cur:
            return None
        sel = self.tree.selection()
        if not sel:
            return None
        return next((c for c in self.cur.clips if str(c.uid) == sel[0]), None)

    def _on_clip_select(self):
        c = self._sel_clip()
        if not c:
            return
        self.detail_center = c.peak
        self.redraw()
        self._load_thumb(c)

    def _load_thumb(self, c: Clip):
        v = self.cur
        out = os.path.join(self.tmp, f"thumb_{c.uid}_{int(c.peak * 10)}.png")

        def job():
            if os.path.exists(out) or extract_frame(v.path, c.peak, out, 300):
                self.q.put(("thumb", c.uid, out))
        threading.Thread(target=job, daemon=True).start()

    def _show_thumb(self, uid, path):
        c = self._sel_clip()
        if not c or c.uid != uid:
            return
        try:
            self.thumb_img = tk.PhotoImage(file=path)
            self.thumb.config(image=self.thumb_img, text="", width=0)
        except tk.TclError:
            pass

    def _edited(self, c: Clip | None = None, select_uids=None):
        v = self.cur
        v.edited = True
        v.clips = fix_bounds(v.clips, v.motion.duration)
        self._fill_tree(select_uid=c.uid if c else None, select_uids=select_uids)
        self._set_vstatus(v, f"{sum(x.enabled for x in v.clips)} balls")
        self._update_info()
        self.redraw()
        self._autosave(v)

    # ------------------------------------------------------------------ players
    def _sel_clips(self) -> list[Clip]:
        if not self.cur:
            return []
        sel = set(self.tree.selection())
        return [c for c in self.cur.clips if str(c.uid) in sel]

    def _remember_name(self, role: str, name: str):
        lst = self.batters if role == "batter" else self.bowlers
        if name and name not in lst:
            lst.append(name)
            (self.batter_cb if role == "batter" else self.bowler_cb).config(values=lst)

    def set_player(self, role: str, onwards: bool):
        """Batters bat in blocks: 'from this ball on' names every later ball until the next change."""
        v = self.cur
        sel = self._sel_clips()
        name = (self.batter_var if role == "batter" else self.bowler_var).get().strip()
        if not v or not sel:
            messagebox.showinfo(APP_NAME, "Select a ball in the list first.")
            return
        if not name:
            messagebox.showinfo(APP_NAME, f"Type or choose the {role}'s name first.")
            return
        self._remember_name(role, name)
        if onwards:
            first = min(sel, key=lambda c: c.peak)
            old = getattr(first, role)
            targets = []
            for c in v.clips:
                if c.peak < first.peak:
                    continue
                cur = getattr(c, role)
                if c is not first and cur and cur != old:  # stop at the next player already named
                    break
                targets.append(c)
        else:
            targets = sel
        for c in targets:
            setattr(c, role, name)
        self.status.config(text=f"{name}: {role} for {len(targets)} ball(s).")
        self._edited(select_uids=[c.uid for c in sel])

    def clear_players(self):
        sel = self._sel_clips()
        for c in sel:
            c.batter = c.bowler = ""
        if sel:
            self._edited(select_uids=[c.uid for c in sel])

    def bowling_rotation(self):
        if not self.cur or not self._sel_clips():
            messagebox.showinfo(APP_NAME, "Select the first ball of the rotation in the list first.")
            return
        RotationDialog(self)

    def apply_rotation(self, order: list[str], fill_to_end: bool, end_uid=None):
        v = self.cur
        sel = self._sel_clips()
        if not v or not sel or not order:
            return
        self.bowling_order = order
        for n in order:
            self._remember_name("bowler", n)
        first = min(sel, key=lambda c: c.peak)
        last = max(sel, key=lambda c: c.peak) if (len(sel) > 1 and not fill_to_end) else None
        k = 0
        for c in v.clips:
            if c.peak < first.peak or not c.enabled:
                continue
            if last is not None and c.peak > last.peak:
                break
            c.bowler = order[k % len(order)]
            k += 1
        self.status.config(text=f"Bowling order applied to {k} balls.")
        self._edited(select_uids=[c.uid for c in sel])

    def edit_squad(self):
        SquadDialog(self)

    def set_squad(self, batters: list[str], bowlers: list[str]):
        self.batters, self.bowlers = batters, bowlers
        self.batter_cb.config(values=batters)
        self.bowler_cb.config(values=bowlers)
        self._save_settings()

    def _autosave(self, v: VideoItem):
        if self.autosave_job:
            self.after_cancel(self.autosave_job)

        def do():
            self.autosave_job = None
            try:
                session.save(v.path, v.clips, v.params, v.preset)
            except Exception:
                pass
        self.autosave_job = self.after(800, do)

    def toggle(self):
        sel = self._sel_clips()
        if sel:
            new = not sel[0].enabled
            for c in sel:
                c.enabled = new
            self._edited(select_uids=[c.uid for c in sel])

    def delete_clip(self):
        c = self._sel_clip()
        if not c:
            return
        i = self.cur.clips.index(c)
        if c.manual:
            self.cur.clips.remove(c)
        else:
            c.enabled = False  # kept as "skipped" so changing settings doesn't bring it back
            i += 1
        self._edited()
        if self.cur.clips:
            nxt = self.cur.clips[min(i, len(self.cur.clips) - 1)]
            self.tree.selection_set(str(nxt.uid))
            self.tree.see(str(nxt.uid))

    def nudge(self, edge, d):
        c = self._sel_clip()
        if not c:
            return
        if edge == "start":
            c.start = min(max(0.0, c.start + d), c.end - 0.5)
        else:
            c.end = max(min(self.cur.motion.duration, c.end + d), c.start + 0.5)
        self._edited(c)

    def add_ball_at(self, t: float):
        v = self.cur
        if not v or not v.motion:
            return
        c = manual_clip(t, v.params, v.motion.duration)
        v.clips.append(c)
        self._edited(c)
        self.status.config(text=f"Added a ball at {fmt_time(t)}.")

    def preview(self):
        c = self._sel_clip()
        v = self.cur
        if not c or not v:
            return
        out = os.path.join(self.tmp, f"preview_{c.uid}_{int(c.start * 10)}_{int(c.end * 10)}"
                                     f"{os.path.splitext(v.path)[1] or '.mp4'}")
        self.status.config(text="Opening clip in your video player…")

        def job():
            try:
                if not os.path.exists(out):
                    cut(v.path, c.start, c.end, out, v.motion.info, accurate=False)
                self.q.put(("open", out))
            except Exception as e:
                self.q.put(("error", str(e)))
        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------------ graphs
    def redraw(self):
        self._draw_overview()
        self._draw_detail()

    def _graph_data(self):
        v = self.cur
        if not v or not v.motion or v.signal is None:
            return None
        return v, v.signal.excess, v.signal.threshold, v.motion.fps, v.motion.duration

    def _ymax(self, ex, thr):
        return max(thr * 2.5, float(np.percentile(ex, 99.7)) if len(ex) else thr) * 1.05

    def _draw_overview(self):
        cv = self.ov
        cv.delete("all")
        W, H = cv.winfo_width(), cv.winfo_height()
        d = self._graph_data()
        if not d or W < 10:
            if self.cur and self.cur.status == "analysing":
                cv.create_text(W / 2, H / 2, text="Analysing…", fill="#888")
            return
        v, ex, thr, fps, dur = d
        sx = W / max(dur, 1e-6)
        ymax = self._ymax(ex, thr)
        sel = self._sel_clip()
        for c in v.clips:
            col = COL_SEL if c is sel else COL_CLIP if c.enabled else COL_CLIP_OFF
            cv.create_rectangle(c.start * sx, 0, max(c.start * sx + 1, c.end * sx), H, fill=col, outline="")
        n = len(ex)
        idx = np.linspace(0, n, W + 1).astype(int)[:-1]
        idx = np.minimum(idx, n - 1)
        peaks = np.maximum.reduceat(ex, idx) if n else np.zeros(W)
        pts = []
        for x, y in enumerate(peaks):
            pts += [x, H - 2 - min(1.0, y / ymax) * (H - 6)]
        if len(pts) >= 4:
            cv.create_line(*pts, fill=COL_LINE)
        ty = H - 2 - thr / ymax * (H - 6)
        cv.create_line(0, ty, W, ty, fill=COL_THR, dash=(4, 3))
        x0 = (self.detail_center - DETAIL_SPAN / 2) * sx
        cv.create_rectangle(x0, 1, x0 + DETAIL_SPAN * sx, H - 1, outline=COL_CURSOR, width=2)

    def _detail_range(self, dur):
        span = min(DETAIL_SPAN, dur)
        t0 = min(max(0.0, self.detail_center - span / 2), max(0.0, dur - span))
        return t0, t0 + span

    def _draw_detail(self):
        cv = self.dt
        cv.delete("all")
        W, H = cv.winfo_width(), cv.winfo_height()
        d = self._graph_data()
        if not d or W < 10:
            return
        v, ex, thr, fps, dur = d
        t0, t1 = self._detail_range(dur)
        sx = W / max(t1 - t0, 1e-6)
        gh = H - 18
        ymax = self._ymax(ex, thr)
        sel = self._sel_clip()
        num = 0
        for c in v.clips:
            if c.enabled:
                num += 1
            if c.end < t0 or c.start > t1:
                continue
            col = COL_SEL if c is sel else COL_CLIP if c.enabled else COL_CLIP_OFF
            cv.create_rectangle((c.start - t0) * sx, 0, (c.end - t0) * sx, gh, fill=col, outline="#7fb98a")
            cv.create_line((c.peak - t0) * sx, 0, (c.peak - t0) * sx, gh, fill="#5c9a6a", dash=(2, 2))
            cv.create_text((c.start - t0) * sx + 4, 4, anchor="nw", font=("Segoe UI", 9, "bold"),
                           text=(f"Ball {num}" if c.enabled else "skipped") + (" (added)" if c.manual else "")
                           + (f" · {c.batter}" if c.batter else ""))
        i0, i1 = int(t0 * fps), min(len(ex), int(t1 * fps) + 1)
        seg = ex[i0:i1]
        pts = []
        for k, y in enumerate(seg):
            pts += [((i0 + k) / fps - t0) * sx, gh - min(1.0, y / ymax) * (gh - 18)]
        if len(pts) >= 4:
            cv.create_line(*pts, fill=COL_LINE, width=1.5)
        ty = gh - thr / ymax * (gh - 18)
        cv.create_line(0, ty, W, ty, fill=COL_THR, dash=(4, 3))
        cv.create_line(0, gh, W, gh, fill="#999")
        step = 5
        t = (int(t0) // step) * step
        while t <= t1:
            if t >= t0:
                x = (t - t0) * sx
                cv.create_line(x, gh, x, gh + 4, fill="#999")
                cv.create_text(x, gh + 5, anchor="n", text=fmt_time(t)[:-2], fill="#555", font=("Segoe UI", 8))
            t += step

    def _x_to_t_detail(self, x):
        d = self._graph_data()
        if not d:
            return None
        t0, t1 = self._detail_range(d[4])
        return t0 + x / max(1, self.dt.winfo_width()) * (t1 - t0)

    def _click_overview(self, e):
        d = self._graph_data()
        if not d:
            return
        self.detail_center = e.x / max(1, self.ov.winfo_width()) * d[4]
        hit = next((c for c in d[0].clips if c.start <= self.detail_center <= c.end), None)
        if hit:
            self.tree.selection_set(str(hit.uid))
            self.tree.see(str(hit.uid))
        self.redraw()

    def _click_detail(self, e):
        t = self._x_to_t_detail(e.x)
        if t is None:
            return
        hit = next((c for c in self.cur.clips if c.start <= t <= c.end), None)
        if hit:
            self.tree.selection_set(str(hit.uid))
            self.tree.see(str(hit.uid))

    def _dbl_detail(self, e):
        t = self._x_to_t_detail(e.x)
        if t is None:
            return
        if any(c.start <= t <= c.end for c in self.cur.clips):
            self.preview()
        else:
            self.add_ball_at(t)

    def _pan(self, secs):
        d = self._graph_data()
        if d:
            self.detail_center = min(max(0.0, self.detail_center + secs), d[4])
            self.redraw()

    def _wheel_detail(self, e):
        self._pan(-10 if e.delta > 0 else 10)

    def _key_pan(self, e, secs):
        if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)):
            return
        self._pan(secs)

    def save_report(self):
        """Motion data + the analyst's corrections (no video), to tune the tracker on real sessions."""
        v = self.cur
        if not v or not v.motion:
            messagebox.showinfo(APP_NAME, "Select an analysed video first.")
            return
        if not messagebox.askokcancel(APP_NAME, (
                "This saves a small file (no video, no pictures) with the movement data of this video and "
                "your corrections to the ball list.\n\nBefore saving, please fix the list as well as you "
                "can: add the balls that were missed (double-click the zoom graph) and delete false ones. "
                "Your corrections show exactly where the tracker went wrong.")):
            return
        stem = os.path.splitext(v.name)[0]
        path = filedialog.asksaveasfilename(title="Save report", defaultextension=".zip",
                                            initialfile=f"{stem}_ballcutter_report.zip",
                                            filetypes=[("Zip file", "*.zip")])
        if not path:
            return
        try:
            write_report(path, v.motion, v.clips, v.params, __version__)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save the report:\n{e}")
            return
        messagebox.showinfo(APP_NAME, f"Report saved:\n{path}\n\nSend this file to whoever maintains "
                                      "Ball Cutter (for example, upload it to the GitHub repository).")

    # ------------------------------------------------------------------ export
    def choose_out(self):
        d = filedialog.askdirectory(title="Where should the clips be saved?", initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(d)

    def open_out(self):
        d = self.out_dir.get()
        os.makedirs(d, exist_ok=True)
        try:
            open_with_system_player(d)
        except Exception:
            pass

    def export(self, all_videos: bool):
        if self._busy():
            return
        vids = [v for v in (self.videos if all_videos else [self.cur] if self.cur else []) if v.motion]
        if not vids:
            messagebox.showinfo(APP_NAME, "There is nothing to export yet – add a video and wait for the analysis.")
            return
        if not any(c.enabled for v in vids for c in v.clips):
            messagebox.showinfo(APP_NAME, "No balls are marked to keep.")
            return
        if not (self.do_clips.get() or self.do_reel.get() or self.do_csv.get() or self.do_edl.get()
                or self.do_players.get()):
            messagebox.showinfo(APP_NAME, "Tick at least one thing to export.")
            return
        if self.cur:
            self.cur.params = self._params_from_widgets()
        try:
            bpo = int(self.bpo.get())
        except (tk.TclError, ValueError):
            bpo = 6
        opts = ExportOptions(out_dir=self.out_dir.get(), accurate=self.accurate.get(), clips=self.do_clips.get(),
                             reel=self.do_reel.get(), csv=self.do_csv.get(), edl=self.do_edl.get(),
                             over_naming=self.over_naming.get(), balls_per_over=bpo,
                             by_player=self.do_players.get())
        try:
            os.makedirs(opts.out_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror(APP_NAME, f"Cannot use that folder:\n{e}")
            return
        free = shutil.disk_usage(opts.out_dir).free
        if free < 2 * 1024 ** 3:
            if not messagebox.askyesno(APP_NAME, f"Only {free / 1024 ** 3:.1f} GB free in the output folder. Continue?"):
                return
        self._save_settings()
        jobs = [(v.path, v.motion.info, [Clip(c.start, c.end, c.peak, c.score, c.enabled, c.manual,
                                              batter=c.batter, bowler=c.bowler)
                                         for c in v.clips], v.name) for v in vids]
        self._start(self._export_job, jobs, opts)

    def _export_job(self, jobs, opts):
        n = len(jobs) + (1 if opts.by_player else 0)
        made_all = []
        for k, (path, info, clips, name) in enumerate(jobs):
            def prog(f, s, k=k):
                self.q.put(("progress", (k + f) / n, s))
            _, made = export_video(path, info, clips, opts, prog, self.cancel_flag.is_set)
            made_all += made
        warnings = []
        if opts.by_player:
            def prog(f, s):
                self.q.put(("progress", (len(jobs) + f) / n, s))
            _, warnings = export_players(made_all, opts.out_dir, True, prog, self.cancel_flag.is_set)
        if not opts.clips:  # per-ball files were only needed for the reel / player folders
            remove_clip_files(made_all)
        self.q.put(("exported", opts.out_dir, warnings))

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, "A job is still running. Quit anyway?"):
                return
            self.cancel_flag.set()
        self._save_settings()
        for v in self.videos:
            if v.motion and v.edited:
                try:
                    session.save(v.path, v.clips, v.params, v.preset)
                except Exception:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        for job in (self._poll_job, self.redetect_job, self.autosave_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self.destroy()


def _lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        name = line.strip()
        if name and name not in out:
            out.append(name)
    return out


class SquadDialog(tk.Toplevel):
    """Names of the batters and bowlers, one per line. Remembered for next time."""

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title("Squad list")
        self.transient(app)
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Type one name per line.").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="Batters").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(f, text="Bowlers").grid(row=1, column=1, sticky="w", pady=(6, 0), padx=(10, 0))
        self.bat = tk.Text(f, width=24, height=14)
        self.bowl = tk.Text(f, width=24, height=14)
        self.bat.grid(row=2, column=0)
        self.bowl.grid(row=2, column=1, padx=(10, 0))
        self.bat.insert("1.0", "\n".join(app.batters))
        self.bowl.insert("1.0", "\n".join(app.bowlers))
        b = ttk.Frame(f)
        b.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Save", command=self.ok).pack(side="right", padx=6)
        self.grab_set()

    def ok(self):
        self.app.set_squad(_lines(self.bat.get("1.0", "end")), _lines(self.bowl.get("1.0", "end")))
        self.destroy()


class RotationDialog(tk.Toplevel):
    """Bowlers in the nets usually bowl in turn: A, B, C, D, A, B, ..."""

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title("Bowling order")
        self.transient(app)
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        n_sel = len(app._sel_clips())
        ttk.Label(f, wraplength=320, justify="left", text=(
            "Type the bowlers in the order they bowl, one per line. The names are filled in turn "
            "(1st, 2nd, 3rd, …, then the 1st again), starting at the selected ball and skipping balls "
            "marked ✗. Fix any single ball afterwards with 'Selected only'.")).grid(row=0, column=0, sticky="w")
        self.txt = tk.Text(f, width=28, height=8)
        self.txt.grid(row=1, column=0, sticky="w", pady=6)
        self.txt.insert("1.0", "\n".join(app.bowling_order or app.bowlers))
        self.to_end = tk.BooleanVar(value=n_sel <= 1)
        ttk.Radiobutton(f, text="From the selected ball to the end of the video", variable=self.to_end,
                        value=True).grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(f, text=f"Only the {n_sel} selected balls" if n_sel > 1 else "Only the selected balls",
                        variable=self.to_end, value=False,
                        state="normal" if n_sel > 1 else "disabled").grid(row=3, column=0, sticky="w")
        b = ttk.Frame(f)
        b.grid(row=4, column=0, sticky="e", pady=(8, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Apply", command=self.ok).pack(side="right", padx=6)
        self.grab_set()

    def ok(self):
        order = _lines(self.txt.get("1.0", "end"))
        if not order:
            messagebox.showinfo(APP_NAME, "Type at least one bowler.", parent=self)
            return
        self.app.apply_rotation(order, self.to_end.get())
        self.destroy()


class RoiDialog(tk.Toplevel):
    """Drag a box over the part of the picture where the delivery happens."""

    W = 720

    def __init__(self, app: App, v: VideoItem):
        super().__init__(app)
        self.app = app
        self.title("Detection area")
        self.transient(app)
        self.resizable(False, False)
        ttk.Label(self, padding=8, wraplength=self.W, text=(
            "Drag a box over the area where each delivery happens: for the batter view, the batter and the "
            "crease; for the behind-the-bowler view, the pitch from the bowler's crease to the batter. "
            "Movement outside the box (people walking past, other nets, trees) is ignored.")).pack()
        self.cv = tk.Canvas(self, width=self.W, height=405, bg="#222", highlightthickness=0, cursor="crosshair")
        self.cv.pack(padx=8)
        b = ttk.Frame(self, padding=8)
        b.pack(fill="x")
        ttk.Button(b, text="Use whole frame", command=self.clear).pack(side="left")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="OK", command=self.ok).pack(side="right", padx=6)
        self.roi = app.roi
        self.rect = None
        self.start = None
        self.img = None
        self.ih = 405
        self.cv.bind("<ButtonPress-1>", self._down)
        self.cv.bind("<B1-Motion>", self._drag)
        dur = v.motion.duration if v.motion else 0
        out = os.path.join(app.tmp, f"roi_{id(v)}.png")
        try:
            dur = dur or probe(v.path).duration
            if os.path.exists(out) or extract_frame(v.path, dur * 0.3, out, self.W):
                self.img = tk.PhotoImage(file=out)
                self.ih = self.img.height()
                self.cv.config(height=self.ih)
                self.cv.create_image(0, 0, anchor="nw", image=self.img)
        except Exception:
            pass
        if self.roi:
            x0, y0, x1, y1 = self.roi
            self.rect = self.cv.create_rectangle(x0 * self.W, y0 * self.ih, x1 * self.W, y1 * self.ih,
                                                 outline="#ffd400", width=3)
        self.grab_set()

    def _down(self, e):
        self.start = (e.x, e.y)
        if self.rect:
            self.cv.delete(self.rect)
        self.rect = self.cv.create_rectangle(e.x, e.y, e.x, e.y, outline="#ffd400", width=3)

    def _drag(self, e):
        if self.start:
            x = min(max(0, e.x), self.W)
            y = min(max(0, e.y), self.ih)
            self.cv.coords(self.rect, self.start[0], self.start[1], x, y)
            x0, x1 = sorted((self.start[0], x))
            y0, y1 = sorted((self.start[1], y))
            if x1 - x0 > 8 and y1 - y0 > 8:
                self.roi = (x0 / self.W, y0 / self.ih, x1 / self.W, y1 / self.ih)

    def clear(self):
        self.app.set_roi(None)
        self.destroy()

    def ok(self):
        self.app.set_roi(self.roi)
        self.destroy()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    if len(sys.argv) > 1:
        app.after(200, lambda: app.add_paths([p for p in sys.argv[1:] if os.path.isfile(p)]))
    app.mainloop()


if __name__ == "__main__":
    main()
