<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/f2019433-ab9e-4280-83e4-0116584965f9

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Crease Video Analyst (installable tablet app)

`public/crease/` is a self-contained ball-by-ball video tagging app (frame stepping, drawing, side-by-side/overlay compare, ball-speed estimate, pitch map, wagon wheel, batter/bowler stats, CSV/JSON export). It is a Progressive Web App: it installs to the home screen, opens full screen and works offline. Videos never leave the device; tags are kept in the browser's storage on that device.

**Hosting.** Browsers only install apps served over HTTPS. `.github/workflows/crease-pages.yml` publishes `public/crease/` to GitHub Pages on every push to `main` that touches it. Turn it on once under *Settings → Pages → Source: GitHub Actions*. The app is then at `https://<owner>.github.io/<repo>/`. Any other static HTTPS host works too: upload the folder's contents.

**Install on the tablet**
- Android (Chrome): open the address, then menu ⋮ → *Install app* (or *Add to Home screen*).
- iPad (Safari): open the address, then Share → *Add to Home Screen*.

Open it once while online; after that it works with no internet. Save a backup (Charts tab) regularly: uninstalling the app or clearing browser data deletes the tags.

**Updating.** After changing any file in `public/crease/`, bump `VERSION` in `public/crease/sw.js` so tablets pick up the new version.

**Locally:** `npm run dev`, then open `/crease/`.
