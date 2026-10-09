# SIMBA REELS FACTORY — tested silent-reels MVP

Standalone Node.js 20+ CLI. No npm dependencies. Requires FFmpeg with drawtext and ffprobe on PATH. No automatic publication or external AI calls.

## Run

```bash
cd reels-factory
npm test
node src/cli.js hooks example.json
node src/cli.js storyboard example.json
node src/cli.js render example.json output.mp4
```

Replace photo1.jpg, photo2.jpg, photo3.jpg with your own licensed photos. Image paths resolve relative to the input JSON file. An output.mp4.json QC manifest is written beside the MP4.

Optional hooks: exactly five approved custom strings. A supplied price requires priceVerified:true, and a supplied date requires dateVerified:true. conflict:true blocks rendering. Verification flags are operator attestations, not automated verification.

Scope: five deterministic hooks, three silent scenes (4+6+4 seconds), 1080×1920 H.264 MP4, FFprobe QC. No OpenAI/Gemini API, no publishing, no music, no Wix, no tested RTL yet. Production integration must respect AGENTS.md, META, Router, KB, Scenario Writer, Rafael and human approval.

Local verification on 2026-10-09: 8/8 Node tests passed; demo MP4 rendered and ffprobe validated 1080×1920 H.264 duration 14s.
