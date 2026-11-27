import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("LOCALAPPDATA", tempfile.mkdtemp())

from ballcutter.detect import PRESETS, Clip, Params, analyze, detect_balls, fix_bounds, roi_mask  # noqa: E402
from ballcutter.export import ExportOptions, ball_label, export_video  # noqa: E402
from make_test_video import make  # noqa: E402

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
        folder = export_video(self.video, self.motion.info, clips, ExportOptions(out))
        files = os.listdir(folder)
        self.assertEqual(len([f for f in files if "_Ball_" in f]), len(BALLS) - 1)
        for f in ("net_ALL_BALLS.mp4", "net_balls.csv", "net_premiere.edl"):
            self.assertIn(f, files)


if __name__ == "__main__":
    unittest.main()
