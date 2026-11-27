# Ball Cutter

A Windows desktop app that turns long net/training session recordings into **one clip per ball**, with no manual cutting in Premiere Pro.

Add your videos, wait for the analysis, check the list of balls it found, then press **Export**. You get:

- **One file per ball:** `Session1_Ball_001.mp4`, `Session1_Ball_002.mp4` … (or `Over01_Ball1` … if you prefer overs)
- **All balls joined into one video** with the waiting time between balls removed
- **A ball list (CSV)** that opens in Excel: start/end time and length of each ball
- **A Premiere Pro EDL** so you can rebuild the cuts on a Premiere timeline

Everything runs offline on your PC. Videos are never uploaded anywhere.

## Install

**Installer (recommended).** Download [BallCutter-Setup.exe](https://github.com/fdmssnepal4-lgtm/Analyst-Ravi/releases/latest/download/BallCutter-Setup.exe) (log in to GitHub first if the link says Not Found), double-click it, and follow the steps. Windows SmartScreen may warn that the app is from an unknown publisher, because it is not code-signed: click **More info → Run anyway**. FFmpeg comes bundled; nothing else needs installing.

**Portable.** Unzip the `BallCutter-Windows-Portable` download anywhere and run `BallCutter.exe`.

### Getting the installer

The installer is built automatically by GitHub Actions on a Windows machine every time this folder changes, and published on the repository's **Releases** page: <https://github.com/fdmssnepal4-lgtm/Analyst-Ravi/releases>. Click **BallCutter-Setup.exe** under *Assets*.

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

### Clips for each player (batters and bowlers)

In the nets, 2–4 batters take turns and 4–6 bowlers bowl in rotation. Ball Cutter can sort the clips so each player gets their own folder:

1. **Squad list…** (in the *Players* box): type your batters and bowlers, one per line. This is remembered.
2. **Batters**: click the first ball a batter faced, choose her name, and click **From this ball on**. Every later ball gets that name, until the next ball that already has a different batter. Do this once each time the batter changes. To fix a single ball, select it and click **Selected only**.
3. **Bowlers**: click the first ball, then **Bowling order…**, type the bowlers in the order they bowl, and click **Apply**. The names are filled in turn (1st, 2nd, 3rd, 4th, then the 1st again), skipping balls marked ✗. Fix any single ball with **Selected only**. If the order changes partway through, select the ball where it changes and apply the new order from there.
4. Keep **Folder per player** ticked and export. You get:

```
Ball Cutter/
  Session1/                        every ball, the joined video, the CSV and the EDL
  Players/
    Batter - Asha/                 Asha's balls + "Batter - Asha - all balls.mp4"
    Batter - Rubina/
    Bowler - Indu/
    ...
    players_summary.csv            how many balls each player has
```

Each file name also says who batted and who bowled, for example `Session1_Ball_014_Asha_vs_Indu.mp4`, and the CSV has *batter* and *bowler* columns. Send each player her folder, or just her "all balls" video (WhatsApp, Google Drive, a pen drive). When you export several videos together, each player's folder collects her balls from all of them. Player folders use hard links where Windows allows it, so they take no extra disk space.

Your ball list and names are saved automatically for each video. Opening the same video again brings them back.

The app does not yet recognise players by itself. Similar kit makes that unreliable, so for now the names come from the quick steps above.

### Opening the EDL in Premiere Pro

**File → Import**, choose the `*_premiere.edl` file, and accept the sequence settings. When Premiere asks for the media, point it at the original session video. The EDL assumes the video's timecode starts at 00:00:00:00, which is normal for phone and most camera files. If your camera writes time-of-day timecode, use the exported clips or the CSV instead.

## Tips for best detection

- Use a tripod. A shaking camera looks like movement everywhere.
- Keep the camera still for the whole session. If you move it, split the recording or set the detection area again.
- For the batter view, a detection-area box around the batter and stumps works best.
- For the behind-the-bowler view, a box from the bowling crease to the batter cuts out fielders walking around.

## How it works

FFmpeg decodes the video at 10 frames a second at low resolution, and the app records how much each part of the picture changes over time. Brightness changes from clouds or auto-exposure are ignored.

Ball Cutter then **learns what a delivery looks like in each video**. With a fixed camera every ball looks alike: the bowler comes in on the same line, the ball takes the same path, and the batter moves at the same spot, in the same order. The batter walking around between balls, a fielder or coach moving, or the batter walking back to the crease look different each time. So the tracker:

1. scales each part of the picture by how busy it normally is. An area that is always moving (a fielder's patch) counts for little; an area that only moves during deliveries (the bowler's arm, the ball's path) counts for a lot.
2. finds the bursts of movement that resemble many other bursts, and builds a delivery pattern from them. It compares a few candidate patterns and keeps the one whose matches are most alike and shortest in time, which is what a delivery is.
3. also tries the pattern mirrored, so a left-hander and a right-hander in the same session can both be found.
4. scores every moment of the video against the pattern. Each strong match is a ball.
5. takes a second look in unusually long gaps between balls. Anything the plain movement tracker of version 1.0 would have caught is added too. These extra finds are shown in yellow so you can check them quickly.

If a video has too few clear balls to learn from (under about 6), the app uses the plain movement tracker instead. The line above the graph shows which tracker was used.

On difficult test sessions (a fielder moving all the time, the batter wandering between balls, light changes, soft leaves and blocks, balls 4–30 seconds apart) version 1.1 found 343 of 368 balls. Version 1.0 found none of the first 150. The weakest cases left are very soft balls filmed from behind the bowler, and sessions where right- and left-handers alternate.

### If balls are still missed

Fix the list in the app (double-click the zoom graph to add each missed ball, and press Del on false ones), then click **Save report for developer…**. This saves a small zip with the movement data and your corrections. It contains no video and no pictures. Send that file to whoever maintains Ball Cutter (for example, upload it to the GitHub repository) so the tracker can be tuned on your real footage.

## For developers

```
desktop/ball-cutter/
  app.py                  Tkinter desktop app
  ballcutter/detect.py    motion analysis and ball detection
  ballcutter/pattern.py   learned delivery-pattern tracker
  ballcutter/export.py    cutting, joining, CSV and EDL
  ballcutter/cli.py       command line: python -m ballcutter.cli VIDEO --out FOLDER [--view bowler]
  tests/                  python -m unittest (run inside tests/)
  packaging/              icon and Inno Setup installer script
```

Requirements: Python 3.10+, `numpy`, and `imageio-ffmpeg` (which ships the FFmpeg binary).
