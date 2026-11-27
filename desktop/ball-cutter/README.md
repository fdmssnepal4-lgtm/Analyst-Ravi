# Ball Cutter

A Windows desktop app that turns long net/training session recordings into **one clip per ball**, with no manual cutting in Premiere Pro.

Add your videos, wait for the analysis, check the list of balls it found, then press **Export**. You get:

- **One file per ball:** `Session1_Ball_001.mp4`, `Session1_Ball_002.mp4` … (or `Over01_Ball1` … if you prefer overs)
- **All balls joined into one video** with the waiting time between balls removed
- **A ball list (CSV)** that opens in Excel: start/end time and length of each ball
- **A Premiere Pro EDL** so you can rebuild the cuts on a Premiere timeline

Everything runs offline on your PC. Videos are never uploaded anywhere.

## Install

**Installer (recommended).** Download `BallCutter-Setup-x.y.z.exe` (see *Getting the installer* below), double-click it, and follow the steps. Windows SmartScreen may warn that the app is from an unknown publisher, because it is not code-signed: click **More info → Run anyway**. FFmpeg comes bundled; nothing else needs installing.

**Portable.** Unzip the `BallCutter-Windows-Portable` download anywhere and run `BallCutter.exe`.

### Getting the installer

The installer is built automatically by GitHub Actions on a Windows machine every time this folder changes:

1. On GitHub, open the repository's **Actions** tab, then **Build Ball Cutter for Windows**.
2. Click the latest green run.
3. Under **Artifacts**, download **BallCutter-Windows-Installer** (a zip holding the setup .exe).

To build on your own PC instead: install Python 3.12 from python.org (tick *Add to PATH*), optionally Inno Setup 6, then double-click `build_windows.bat`. To just run it without building: `run_from_source.bat`.

## How to use

1. **Add videos.** Click **+ Add videos…** and pick one or more session files (MP4, MOV, MTS, MKV, AVI…). Analysis starts on its own and runs one file after another. It reads each file once, which takes roughly 2–10 minutes per hour of HD footage (longer for 4K). The result is cached, so opening the same file again is instant.
2. **Choose the camera position** for each video:
   - **Batter view**: camera above or beside the batter, where mostly the batter is in frame.
   - **Behind the bowler**: end-on camera, run-up visible. Clips start earlier to include the run-up.
3. **Check the balls found.** The top graph shows the whole session: each spike is movement, each green band is a ball clip, and the orange dashed line is the detection level. Click anywhere to zoom the lower graph to that spot.
   - **▶ Watch this ball** (or double-click a row) plays the clip in your normal video player.
   - **Space** keeps or skips a ball. **Del** skips a detected ball, or removes one you added.
   - **Double-click empty space** in the zoom graph to add a ball the app missed.
   - **Start/End ±0.5 s** fine-tunes a clip.
   - Rows in **yellow** are weak detections, worth a quick look.
4. **Tune if needed.** Every change applies instantly, without reading the video again:
   - *Too many clips* (false alarms between balls): move **Sensitivity** towards *fewer*, or raise **Min. seconds between balls**.
   - *Balls missed*: move **Sensitivity** towards *more balls*.
   - *Clip starts too late or ends too early*: change **Seconds before/after shot**, or tick **Stretch to cover whole movement**.
   - *People walking past, other nets, trees moving*: click **Detection area…** and drag a box over where the delivery happens (the batter and crease, or the pitch). Movement outside the box is ignored.
   - **Apply to all videos** copies the current settings to every loaded video.
5. **Export.** Pick the output folder and what to export, then click **Export this video** or **Export all videos**. Each video gets its own sub-folder.
   - **Fast** copies the video data as-is: no quality loss, and very quick. Because a cut can only start on a keyframe, a clip may begin up to about a second early.
   - **Exact frame** re-encodes (H.264, high quality) so cuts land on the exact frame. It is slower.

### Opening the EDL in Premiere Pro

**File → Import**, choose the `*_premiere.edl` file, and accept the sequence settings. When Premiere asks for the media, point it at the original session video. The EDL assumes the video's timecode starts at 00:00:00:00, which is normal for phone and most camera files. If your camera writes time-of-day timecode, use the exported clips or the CSV instead.

## Tips for best detection

- Use a tripod. A shaking camera looks like movement everywhere.
- Keep the camera still for the whole session. If you move it, split the recording or set the detection area again.
- For the batter view, a detection-area box around the batter and stumps works best.
- For the behind-the-bowler view, a box from the bowling crease to the batter cuts out fielders walking around.

## How it works

FFmpeg decodes the video at 10 frames a second at low resolution. For each frame, the app measures how much of the picture changed (ignoring whole-frame brightness changes from clouds or auto-exposure). A delivery shows up as a sharp burst of movement (run-up, release, shot) that stands out from the slower background movement between balls. The app takes the strongest bursts that are at least *min. seconds between balls* apart and cuts *seconds before* to *seconds after* around each one.

## For developers

```
desktop/ball-cutter/
  app.py                  Tkinter desktop app
  ballcutter/detect.py    motion analysis and ball detection
  ballcutter/export.py    cutting, joining, CSV and EDL
  ballcutter/cli.py       command line: python -m ballcutter.cli VIDEO --out FOLDER [--view bowler]
  tests/                  python -m unittest (run inside tests/)
  packaging/              icon and Inno Setup installer script
```

Requirements: Python 3.10+, `numpy`, and `imageio-ffmpeg` (which ships the FFmpeg binary).
