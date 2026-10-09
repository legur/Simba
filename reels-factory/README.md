# SIMBA REELS FACTORY — local visual MVP

## Start interface
Requirements: Node.js 20+, FFmpeg and FFprobe installed and available on PATH.

```bash
cd reels-factory
npm test
npm start
```

Open **http://127.0.0.1:4173** on the same computer.

1. Enter offer title, destination and CTA.
2. If price/date are included, check that you verified them from current sources.
3. Upload 1–6 licensed JPEG/PNG/WebP images, maximum 8 MB each.
4. Generate five hooks and select one.
5. Render MP4; preview and download it manually.

Local HTTP server binds to 127.0.0.1 only. Images are temporarily stored in OS temp directories, video jobs remain on disk until the process exits. Do not expose the server publicly. No cloud upload, OpenAI API or auto-publishing.

CLI still available: `node src/cli.js render example.json output.mp4`.

## Status
Implemented: browser form, offer validation, five deterministic hooks, three-scene preview, image upload, FFmpeg render and video download. Browser interface and integration were committed but have **not yet been end-to-end tested**. Earlier CLI demo and eight unit tests passed locally; retest this revision before production use.

Not implemented: automatic AI hooks, multi-user access, persistent projects, music licensing, full RTL typography, Wix connection, real-time inventory validation, publishing.
