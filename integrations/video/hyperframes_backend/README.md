# HyperFrames renderer

Set `"renderer": "hyperframes"` in a `video-spec.json` job to select the
HyperFrames renderer. Omit `renderer` or set it to `"simba"` for the existing
renderer. The separate `motion` field selects `"anime"` or `"classic"`.

Both renderers use the same timeline, narration, audio mixing, subtitles,
approval checks and final quality checks. HyperFrames renders video only; the
existing pipeline supplies the final soundtrack. Requires Node.js 22 or newer,
the pinned npm dependencies, Chromium and FFmpeg. The backend does not pass
Gemini or Drive secrets to the HyperFrames subprocess.

Run the backend checks with:

```sh
python -m unittest discover -s integrations/video/hyperframes_backend -t integrations/video -p test_adapter.py
```
