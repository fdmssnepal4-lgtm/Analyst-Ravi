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

In the nets, 2–4 batters take turns and 4–6 bowlers bowl in rotation. Ball Cutter can recognise the players itself and sort the clips so each player gets her own folder.

**Automatically (recommended)**

1. Select the video and click **★ Recognise players automatically…** in the *Players* box.
2. Choose **Batters** and click **Find players**. The app looks at each ball's batter in her stance just before the delivery: helmet, shirt, pads, gloves, build, and whether she is left- or right-handed. It groups the balls that show the same person. Because batters bat in blocks of balls, one odd ball (a shadow, someone walking past) doesn't throw it off.
3. You see a few pictures of each group and which balls it has. Type or choose each player's name once, then click **Apply names**. If one player was split into two groups, give both the same name. If two players were put together, set **How many players** and try again.
4. For bowlers, do the same with **Bowlers**. This needs the camera behind the bowler, where the bowler running in is clearly visible. From the camera above the batter the bowler is hardly in the picture, so use **Bowling order…** (below) instead.

On test sessions, batters were grouped 100% correctly from the camera above the batter, even three batters in the same team kit who differed only in helmet, gloves, height and stance. From behind the bowler, batters were 81–93% correct and bowlers about 88%. Real footage will differ, so glance through the list after applying names and fix any wrong ball with **Selected only**.

**Export only some players**: click **Only these players…** in the *Export* box and tick, for example, just Asha. Only balls where she batted or bowled are exported. Click **All balls** to go back.

**By hand**

1. **Squad list…**: type your batters and bowlers, one per line. This is remembered.
2. **Batters**: click the first ball a batter faced, choose her name, and click **From this ball on**. Every later ball gets that name, until the next ball that already has a different batter. To fix a single ball, select it and click **Selected only**.
3. **Bowlers**: click the first ball, then **Bowling order…**, type the bowlers in the order they bowl, and click **Apply**. The names are filled in turn (1st, 2nd, 3rd, 4th, then the 1st again), skipping balls marked ✗. If the order changes partway through, select the ball where it changes and apply the new order from there.

**Exporting**: keep **Folder per player** ticked and export. You get:

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

On 18 difficult test sessions (673 balls: a fielder moving all the time, the batter wandering between balls, light changes, soft leaves and blocks, balls 4–30 seconds apart, left- and right-handers, fast bowlers mixed with spinners), the tracker missed 34 balls on its own. Most of those are recovered with the teaching tools below. Version 1.0 found none of the first 150.

### Close camera (batter fills the picture)

When the camera is close to or above the batter, she fills the whole height of the picture. In those videos the clearest sign of a delivery is her **stride and swing**: a fast movement over her whole height, unlike her fidgeting between balls. Ball Cutter checks each video for this. If the swings line up with the balls it found, it:

- adds a ball for every swing that has no clip,
- re-centres each clip on its swing, so the delivery is never cut off at the start (real sessions had clips that began exactly at the swing),
- marks clips without any swing yellow. These are often the batter walking away and back between balls. Click **Skip all yellow (unsure)** in *Teach the tracker* to clear them after a quick look. A leave, where the batter hardly moves, can also be yellow or missed.

This came from three real net-session reports: at normal sensitivity, every swing in them is now inside a clip with at least 2.5 seconds before it (one ball in one session got 1 second).

### If balls are still missed: teach the tracker

The tracker learns what a delivery looks like in each video. If your session mixes very different bowling (fast bowlers and spinners, a bowler from round the wicket, a leg-spinner's slow loop), some balls can look so different that they are missed. The tracker also takes a second look by itself for a whole group of look-alike balls it didn't cover (another bowling style) and adds them in yellow. The **Teach the tracker** box lets you fix the rest in a few clicks:

- **Next possible miss ▶**: jumps to the strongest spot where something happened but no clip exists, shows the picture, and draws a purple "possible miss?" line on the zoom graph. If it is a ball, double-click the line to add it. If not, press the button again. Spots you already looked at are skipped.
- **Adding a missed ball finds the others like it.** With *When I add a missed ball, find others like it* ticked (the default), adding one missed spinner ball also adds every other ball that looks like it, in yellow. One click often recovers all of that bowler's balls. On test sessions with spinners and fast bowlers mixed, 15–20 missed balls went down to 2–4 after adding 3–5 by hand.
- **Find more like selected**: the same, on demand, for the balls you select (for example several balls you added).
- **Skip balls like this**: select a wrong clip (no ball in it) and click this. That clip and every other clip that looks like it are marked ✗.
- **Skip all yellow (unsure)**: marks every yellow clip ✗ in one go.
- **Undo**: takes back the last add, find or skip.

If the tracker still struggles with your footage, fix the list, then click **Save report for developer…** and answer **Yes** to *Include small pictures of every ball?*: every clip gets a strip of 8 small frames from start to end, plus pictures of places where a ball may have been missed, so the developer can check your session ball by ball without the video. It saves a small zip with the movement data and your corrections, with no video and no pictures. Send that file to whoever maintains Ball Cutter (for example, upload it to the GitHub repository) so the tracker can be tuned on your real sessions.

## For developers

```
desktop/ball-cutter/
  app.py                  Tkinter desktop app
  ballcutter/detect.py    motion analysis and ball detection
  ballcutter/pattern.py   learned delivery-pattern tracker
  ballcutter/players.py   automatic player recognition
  ballcutter/session.py   remembers each video's reviewed ball list
  ballcutter/export.py    cutting, joining, CSV and EDL
  ballcutter/cli.py       command line: python -m ballcutter.cli VIDEO --out FOLDER [--view bowler]
  tests/                  python -m unittest (run inside tests/)
  packaging/              icon and Inno Setup installer script
```

Requirements: Python 3.10+, `numpy`, and `imageio-ffmpeg` (which ships the FFmpeg binary).
