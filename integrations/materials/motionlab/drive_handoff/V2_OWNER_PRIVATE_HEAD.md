# Owner-private canonical Studio v2: blind head and immutable Drive snapshots

## Why

The original public-GitHub Contents CAS requires the FULL canonical
campaigns/PROJECT/project.json in the public repository. This is inappropriate
for the owner-private Alaska campaign. It must never be used to publish
Alaska's client/private working data.

The replacement separates two concerns:

- **Private truth:** the full, exact-byte-pinned owner project, approved
  WAV/music and MP4 references, edit proposals, and immutable revision
  snapshots are in an owner-only Google Drive folder.
- **Concurrency control:** a minimal public GitHub Contents file contains
  only the project slug, increasing revision, boolean NOT-render and
  NOT-publish flags, and an **HMAC commitment** to the private project's
  SHA-256. No raw project bytes, full scripts, Drive IDs, client records,
  source SHA, URL or chosen edit proposal are copied into GitHub.

The HMAC key exists only inside the trusted private owner worker, never
inside public repository or GitHub Actions. It must be 32+ unguessable bytes.

## Pipeline

1. The installed public head begins UNINITIALIZED at revision 0. It is
   deliberately **NOT** a claim that Alaska already has a canonical approved
   project or new Studio v2 owner selection.
2. A real owner-only project.json and its exact source files pass SHA,
   Google Drive ACL, all stage approvals and canonical handoff integrity.
   Only then can the worker bootstrap an immutable owner-private Drive
   snapshot and atomically CAS the public blind head to
   READY_FOR_EDIT_CHOICE.
3. The owner uses the existing Studio v2 launcher to review three real
   plans. A consumed, authentic v2 ticket and signed SHA-pinned selection
   enter the owner-private inbox.
4. The existing source replay verifies unchanged original WAV/music/MP4,
   independent local audio QA, scene-to-media source bindings, and the
   current owner selection. All old approval and publication guards remain.
5. The worker stores the original selection/spec evidence privately,
   prepares a candidate edit_choice using the existing contract, and
   invokes the **same strict candidate delta validator** as the public
   GitHub CAS in NO-WRITE mode.
6. It writes an owner-private immutable project.v2.SHA256.json and rereads
   exact bytes, then CAS-updates **only the blind public head** from the
   exact previously read GitHub blob SHA. A stale head is rejected without
   deleting or using the private orphaned revision.
7. Only after successful CAS does the worker write a distinct immutable
   private-head-applied ACK. If the ACK fails, the outcome is AMBIGUOUS,
   and the worker must inspect the GitHub blind head before retrying.

All Python functions default to apply=False. None starts TTS, A2E, render,
publishing or paid generation. A committed edit_choice merely makes a
private version ready for the next Montage planning stage. Full release
and renderer require new independent explicit authorization.

## Current Alaska status

The project on Drive is still a historical candidate. It lacks a
genuine v2 voice_music audio lock and independent verified per-word QA.
Third unprompted ASR still has two discrepant geographic-name tokens.
The two source-WAV listening clips are owner-only and UNREVIEWED.

The blind GitHub head remains deliberately **UNINITIALIZED**. Do not
call bootstrap/apply until authentic v2 approvals and automatic QA pass.

## Tests

Synthetic PR tests verify: exact HMAC-only head serialization, dry-run
zero writes, wrong key/source blocked, stale concurrent CAS rejected,
no ability to skip UNINITIALIZED → READY → EDIT_CHOICE_RECORDED, and
render/publish flags always false. Live private Drive writes are NOT
performed in CI. No customer bytes or secrets enter CI.
