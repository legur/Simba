# OpenCut handoff

After a Simba job has been rendered, prepare a separate folder for manual
timeline editing:

```sh
python integrations/video/opencut_handoff.py --job <job-dir> --output-dir <new-handoff-dir>
```

Open https://opencut.app, create a project and import the files needed for the
edit. The MP4 is a flattened video: existing text, animation and transitions
cannot be edited as separate layers. The handoff also includes referenced media
and available voice tracks for a manual timeline rebuild. It does not create or
import an OpenCut project, nor does it transfer media automatically.

Export the edited result to a new file and repeat the necessary visual,
factual, subtitle and audio checks before treating it as ready. Do not overwrite
the Simba output. Keep credentials out of job specifications and media folders.

OpenCut projects are stored in the browser; clearing browser storage can remove
them. Keep the Simba files and exported video separately. OpenCut Classic is
archived upstream; the replacement's editor API is not yet available.
