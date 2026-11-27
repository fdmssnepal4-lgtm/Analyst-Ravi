import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("LOCALAPPDATA", tempfile.mkdtemp())

from ballcutter.detect import PRESETS, Clip, Params, analyze, detect_balls, fix_bounds, roi_mask  # noqa: E402
from ballcutter.export import ExportOptions, ball_label, export_players, export_video  # noqa: E402
from make_test_video import make  # noqa: E402
import make_hard_video  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402

BALLS = (10, 31, 50, 72, 90, 108)


class BallCutterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.video = os.path.join(cls.dir, "net.mp4")
        make(cls.video, balls=BALLS)
        cls.motion = analyze(cls.video, use_cache=False)

    def check_found(self, clips):
        self.assertEqual(len(clips), len(BALLS))
        for c, b in zip(clips, BALLS):
            self.assertLess(abs(c.peak - b), 1.5)
            self.assertLessEqual(c.start, b - 0.9)
            self.assertGreaterEqual(c.end, b + 0.5)

    def test_every_preset_finds_every_ball(self):
        for name, p in PRESETS.items():
            with self.subTest(name):
                self.check_found(detect_balls(self.motion, p))

    def test_detection_area(self):
        p = Params(roi=(0.0, 0.2, 1.0, 0.9))
        self.check_found(detect_balls(self.motion, p))
        self.assertEqual(roi_mask((0.0, 0.0, 0.5, 1.0)).sum(), 8 * 12)

    def test_clips_never_overlap(self):
        clips = fix_bounds([Clip(0, 10, 5), Clip(6, 14, 9), Clip(12, 20, 16)], 18)
        for a, b in zip(clips, clips[1:]):
            self.assertLessEqual(a.end, b.start)
        self.assertLessEqual(clips[-1].end, 18)

    def test_labels(self):
        self.assertEqual(ball_label(7, ExportOptions("x")), "Ball_007")
        self.assertEqual(ball_label(7, ExportOptions("x", over_naming=True)), "Over02_Ball1")

    def test_export(self):
        clips = detect_balls(self.motion, Params())
        clips[2].enabled = False
        out = os.path.join(self.dir, "out")
        for i, c in enumerate(clips):  # two batters in blocks, three bowlers in rotation
            c.batter = "Asha" if i < 3 else "Rubina"
            c.bowler = ["Indu", "Sita", "Kabita"][i % 3]
        folder, made = export_video(self.video, self.motion.info, clips, ExportOptions(out))
        files = os.listdir(folder)
        self.assertEqual(len([f for f in files if "_Ball_" in f]), len(BALLS) - 1)
        self.assertIn("net_Ball_001_Asha_vs_Indu.mp4", files)
        for f in ("net_ALL_BALLS.mp4", "net_balls.csv", "net_premiere.edl"):
            self.assertIn(f, files)
        root, warnings = export_players(made, out)
        self.assertEqual(warnings, [])
        players = sorted(os.listdir(root))
        self.assertEqual(players, ["Batter - Asha", "Batter - Rubina", "Bowler - Indu", "Bowler - Kabita",
                                   "Bowler - Sita", "players_summary.csv"])
        asha = os.listdir(os.path.join(root, "Batter - Asha"))
        self.assertEqual(len([f for f in asha if "_Ball_" in f]), 2)  # ball 3 was skipped
        self.assertIn("Batter - Asha - all balls.mp4", asha)

    def test_session_is_remembered(self):
        from ballcutter import session
        clips = detect_balls(self.motion, Params())
        clips[0].batter, clips[1].enabled = "Asha", False
        session.save(self.video, clips, Params(sensitivity=7), "Custom")
        got, params, preset = session.load(self.video)
        self.assertEqual((got[0].batter, got[1].enabled, params.sensitivity, preset), ("Asha", False, 7, "Custom"))

    def test_report(self):
        from ballcutter.export import write_report
        clips = detect_balls(self.motion, Params())
        path = os.path.join(self.dir, "report.zip")
        write_report(path, self.motion, clips, Params(), "test")
        with zipfile.ZipFile(path) as z:
            self.assertEqual(sorted(z.namelist()), ["motion.npz", "review.json"])
            self.assertEqual(len(json.loads(z.read("review.json"))["balls"]), len(clips))


class HardSessionTest(unittest.TestCase):
    """Fielder walking all session, batter wandering between balls, light changes, soft balls,
    balls 4-30 s apart. The tracker must not miss balls here."""

    def run_case(self, view, seed):
        d = tempfile.mkdtemp()
        video = os.path.join(d, "hard.mp4")
        truth = make_hard_video.make(video, duration=240, seed=seed, view=view)
        m = analyze(video, use_cache=False)
        preset = list(PRESETS.values())[0 if view == "batter" else 1]
        found = [c.peak for c in detect_balls(m, preset)]
        hits, missed, false = make_hard_video.score(found, truth)
        print(f"\n  {view} view: {len(truth)} balls, missed {missed}, false alarms {false}")
        self.assertLessEqual(missed, max(1, len(truth) // 15))
        self.assertLessEqual(false, len(truth) // 3)

    def test_batter_view(self):
        self.run_case("batter", 7)

    def test_bowler_view(self):
        self.run_case("bowler", 23)


if __name__ == "__main__":
    unittest.main()
