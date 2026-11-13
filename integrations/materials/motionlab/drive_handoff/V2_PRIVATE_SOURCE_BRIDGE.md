# Studio v2: owner-private source bridge (pre-production)

This adds a trusted, read-only bridge from the owner's Google Drive canonical project to the existing Studio v2 source preparer.

## Trust boundaries

1. The owner worker supplies an independently pinned SHA for an actual project.json inside an owner-only Drive folder. The v2_private_canonical_source module checks exact filename, folder/file ACL, size, bytes, SHA and evidence. The archived Alaska *candidate* remains rejected: historical script approval is not new v2 voice_music and a2e_clips approval.
2. The worker retrieves each separately approved script/reference source from protected storage, keyed to the SHA recorded in that canonical project. v2_private_workspace.private_stage requires exact source-set equality, rejects changed/unpinned source bytes and outside-project paths, and writes to a disposable mode-0700 directory outside the public repository. Private files are mode 0600 and removed afterward.
3. prepare_real_private_studio invokes the EXISTING motionlab_v2_stage_writeback.prepare_automatic_v2_proposals, never a parallel renderer. The original v2 checks for stage handoff, private A2E media, original WAV/music, offline independent audio QA and real video frame analysis all remain active. A failure stops before any v2 ticket or owner selection.
4. A prepared private proposal is not owner approval, canonical CAS, render authorization or MP4. Three real options need separate authenticated owner review.

## Next required stages

The legacy v2_canonical_cas.py expects a public campaigns/PROJECT/project.json. **Never run it with owner-private Alaska data.** A dedicated Drive-only concurrent-safe writeback with an immutable Applied receipt is necessary before production use.

Status: no live GAS, Wix editor, v1 route or paid service changed here. The current historical Alaska candidate is not admitted. Independent small/medium ASR does not agree with every approved word. No false voice/music approval, owner selection, render or publication was created.

Synthetic CI uses only synthetic data and validates failure closures; it is not a live Alaska end-to-end pass. Keep private tokens, Drive IDs, full scripts and original media outside GitHub and browser logs.
