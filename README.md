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

## Crease Video Analyst (standalone page)

`public/crease-analyst.html` is a self-contained ball-by-ball video tagging tool (frame stepping, drawing, side-by-side/overlay compare, ball-speed estimate, pitch map, wagon wheel, batter/bowler stats, CSV/JSON export). It needs no build step or API key; data stays in the browser's localStorage.

- Dev: `npm run dev`, then open `/crease-analyst.html`
- Or open the file directly in a browser.
