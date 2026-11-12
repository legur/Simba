#!/usr/bin/env python3
"""Simba Step 5F: existing approved narration and licensed music -> montage.

Read-only by default. Validates explicit Leo choices among three text/music
options, a private manifest pinned to current a2e_clips handoff, real voice
WAV and music bytes on private Google Drive, and a recorded Music Editor
license review. Updates ONLY the existing project.json's voice_music stage
when explicitly --apply on a trusted owner workflow_dispatch on main.

Does not synthesize speech, scrape music, infer commercial permissions,
spend API credits, render/publish, or select an option on Leo's behalf.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MATERIALS = Path(__file__).resolve().parent
VIDEO = MATERIALS.parent / "video"
if str(MATERIALS) not in sys.path:
    sys.path.insert(0, str(MATERIALS))
if str(VIDEO) not in sys.path:
    sys.path.insert(0, str(VIDEO))
import catalog
import handoff
import auto_script
import rafael_archive
import a2e_writeback
import studio_v2_audio_stage
import simba_voice
import simba_voice_issue

SHA = re.compile(r"^[0-9a-f]{64}$")
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ALLOWED_CHANNELS = {"facebook", "instagram", "youtube", "tiktok", "website"}
TRACK_HOST = {"mixkit": "mixkit.co", "pixabay": "pixabay.com"}
LICENSE_PATH = {
    "mixkit": "/license/modal/musicFree/",
    "pixabay": "/service/license-summary/",
}
MIMES = {"audio/mpeg": "mp3", "audio/wav": "wav",
         "audio/x-wav": "wav", "audio/flac": "flac",
         "audio/mp4": "m4a", "audio/ogg": "ogg"}
MAX_MANIFEST = 18000
MAX_MUSIC = 100 * 1024 * 1024


class AudioHandoffError(RuntimeError):
    """Errors must be safe for public Actions logs; no private source content."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _private_file(drive, file_id: str, folder_id: str, sha: str,
                  *, content_type: str, limit: int) -> tuple[bytes, dict]:
    if (not isinstance(file_id, str) or DRIVE_ID.fullmatch(file_id) is None
            or not isinstance(folder_id, str) or DRIVE_ID.fullmatch(folder_id) is None
            or not isinstance(sha, str) or SHA.fullmatch(sha) is None):
        raise AudioHandoffError("invalid private Drive file identity or SHA-256")
    try:
        folder = rafael_archive.drive_call(drive.files().get(
            fileId=folder_id, fields="id,mimeType,permissions(type,role)"))
        if (folder.get("id") != folder_id
                or folder.get("mimeType") != "application/vnd.google-apps.folder"
                or not isinstance(folder.get("permissions"), list)
                or not folder["permissions"]
                or any(row.get("type") != "user" for row in folder["permissions"])):
            raise AudioHandoffError("private media folder is missing or broadly shared")
        meta = rafael_archive.drive_call(drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType,parents,size,md5Checksum,permissions(type,role),appProperties"))
        if (meta.get("id") != file_id
                or folder_id not in (meta.get("parents") or [])
                or (meta.get("mimeType") not in
                    (MIMES if content_type == "audio" else {"application/json"}))
                or not isinstance(meta.get("permissions"), list)
                or not meta["permissions"]
                or any(row.get("type") != "user" for row in meta["permissions"])):
            raise AudioHandoffError("private media file metadata or permissions invalid")
        size = int(meta.get("size", -1))
        if not 100 <= size <= limit:
            raise AudioHandoffError("private media file missing or too large")
        raw = rafael_archive.drive_call(drive.files().get_media(fileId=file_id))
        if (not isinstance(raw, bytes) or len(raw) != size
                or digest(raw) != sha
                or hashlib.md5(raw).hexdigest() != meta.get("md5Checksum")):
            raise AudioHandoffError("private media full-byte SHA-256/MD5 mismatch")
        return raw, meta
    except AudioHandoffError:
        raise
    except Exception:
        raise AudioHandoffError("private Drive read-only verification unavailable") from None


def _url(url: object, *, exact_host: str, path_prefix: str) -> bool:
    if not isinstance(url, str) or not 10 <= len(url) <= 600:
        return False
    parsed = urlsplit(url)
    return (parsed.scheme == "https"
            and parsed.hostname in {exact_host, "www." + exact_host}
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.query and not parsed.fragment
            and parsed.path.startswith(path_prefix))


def _approved_license(value: dict, *, channels: list[str]) -> str:
    if not isinstance(value, dict):
        raise AudioHandoffError("Music Editor selected track must be an object")
    provider = value.get("source")
    if provider not in TRACK_HOST:
        raise AudioHandoffError("selected music source not in Music Editor shortlist")
    if (not _url(value.get("track_url"), exact_host=TRACK_HOST[provider],
                 path_prefix="/free-stock-music/" if provider == "mixkit" else "/music/")
            or not _url(value.get("license_url"), exact_host=TRACK_HOST[provider],
                        path_prefix=LICENSE_PATH[provider])
            or not isinstance(value.get("title"), str) or not value["title"].strip()
            or not isinstance(value.get("author"), str) or not value["author"].strip()
            or value.get("commercial_use_verified") is not True
            or value.get("online_ads_verified") is not True
            or not isinstance(value.get("license_evidence"), str)
            or not 15 <= len(value["license_evidence"].strip()) <= 600
            or type(value.get("attribution_required")) is not bool):
        raise AudioHandoffError("selected track lacks actual commercial license review")
    try:
        checked = date.fromisoformat(value["verified_at"])
    except (KeyError, TypeError, ValueError):
        raise AudioHandoffError("Music Editor license verification date required") from None
    days = (datetime.now(timezone.utc).date() - checked).days
    if not 0 <= days <= 90:
        raise AudioHandoffError("Music Editor license evidence outdated or future dated")
    allowed = value.get("licensed_channels")
    if (not isinstance(allowed, list) or not allowed
            or any(not isinstance(c, str) or c not in ALLOWED_CHANNELS for c in allowed)
            or not set(channels).issubset(set(allowed))):
        raise AudioHandoffError("music rights do not explicitly cover all planned channels")
    # This is a human Music Editor attestation, NOT an automated legal opinion.
    return ("Music Editor reviewed " + provider +
            " track licensing for agreed channels on " + str(checked) +
            "; private evidence SHA256 " + digest(value["license_evidence"].encode()))


def _options(data: dict, stage_receipt: str, project_id: str) -> tuple[dict, dict, dict]:
    if (not isinstance(data, dict)
            or set(data) != {"schema_version", "project_id", "input_fingerprint",
                             "selection", "voice", "music", "channels"}
            or data.get("schema_version") != 1
            or data.get("project_id") != project_id
            or data.get("input_fingerprint") != stage_receipt):
        raise AudioHandoffError("private music/narration plan is stale or invalid")
    sel, voice, music = data["selection"], data["voice"], data["music"]
    if (not isinstance(sel, dict) or not isinstance(voice, dict)
            or not isinstance(music, dict)):
        raise AudioHandoffError("private choices must be objects")
    texts = sel.get("texts")
    tracks = sel.get("music")
    txt = sel.get("text_option")
    mus = sel.get("music_option")
    if (not isinstance(texts, list) or len(texts) != 3
            or not all(isinstance(x, dict) and set(x) == {"option", "sha256"}
                       and type(x["option"]) is int and x["option"] == i
                       and isinstance(x["sha256"], str) and SHA.fullmatch(x["sha256"])
                       for i, x in enumerate(texts, 1))
            or len({x["sha256"] for x in texts}) != 3
            or not isinstance(tracks, list) or len(tracks) != 3
            or not all(isinstance(x, dict) and set(x) == {"option", "source", "track_url"}
                       and type(x["option"]) is int and x["option"] == i
                       and x["source"] in TRACK_HOST
                       and _url(x["track_url"], exact_host=TRACK_HOST[x["source"]],
                                path_prefix=("/free-stock-music/" if x["source"] == "mixkit"
                                             else "/music/"))
                       for i, x in enumerate(tracks, 1))
            or len({x["track_url"] for x in tracks}) != 3
            or type(txt) is not int or txt not in (1, 2, 3)
            or type(mus) is not int or mus not in (1, 2, 3)
            or not isinstance(sel.get("leo_approval_evidence"), str)
            or not 20 <= len(sel["leo_approval_evidence"].strip()) <= 600):
        raise AudioHandoffError("three real options and explicit Leo selections required")
    if (voice.get("profile") not in ("simba_warmbaritone", "none")
            or voice.get("text_sha256") != texts[txt-1]["sha256"]):
        raise AudioHandoffError("selected spoken text SHA-256/profile mismatch")
    if (music.get("source") != tracks[mus-1]["source"]
            or music.get("track_url") != tracks[mus-1]["track_url"]):
        raise AudioHandoffError("selected music differs from presented option")
    channels = data.get("channels")
    if (not isinstance(channels, list) or not channels
            or len(channels) != len(set(channels))
            or any(not isinstance(x, str) or x not in ALLOWED_CHANNELS for x in channels)):
        raise AudioHandoffError("target publication channels missing or malformed")
    _approved_license(music, channels=channels)
    return sel, voice, music


def _fetch_existing_voice_issue(number: int) -> dict:
    """GET-only owner voice Issue; never synthesize or create a new Issue."""
    if type(number) is not int or number <= 0 or number > 1_000_000:
        raise AudioHandoffError("existing approved Simba voice issue number required")
    token = __import__("os").environ.get("GH_TOKEN", "")
    if not token:
        raise AudioHandoffError("GitHub read-only voice provenance token missing")
    req = Request(
        f"https://api.github.com/repos/legur/Simba/issues/{number}",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "simba-voice-music-verified-handoff/1"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=20) as response:
            if response.status != 200:
                raise AudioHandoffError("existing approved voice issue not readable")
            raw = response.read(262_145)
        if len(raw) > 262_144:
            raise AudioHandoffError("voice issue response exceeded safe limit")
        return json.loads(raw)
    except AudioHandoffError:
        raise
    except Exception:
        raise AudioHandoffError("read-only trusted GitHub voice issue lookup failed") from None


def _verify_voice_issue(issue: dict, voice: dict) -> None:
    """Pin recorded selection to the input of the EXISTING owner-only TTS runner."""
    issue_no = voice.get("issue_number")
    if (not isinstance(issue, dict)
            or issue.get("number") != issue_no
            or (issue.get("user") or {}).get("login") != "legur"
            or issue.get("pull_request") is not None
            or not any(row.get("name") == "simba-approved-voice"
                       for row in (issue.get("labels") or [])
                       if isinstance(row, dict))):
        raise AudioHandoffError("approved owner voice Issue identity/label does not match")
    try:
        exact_number, speech_text, destination = simba_voice_issue.validate_event({
            "repository": {"full_name": "legur/Simba"},
            "action": "labeled", "sender": {"login": "legur"},
            "label": {"name": "simba-approved-voice"},
            "issue": issue,
        })
    except (ValueError, KeyError, TypeError):
        raise AudioHandoffError("existing voice issue cannot be validated") from None
    if (exact_number != issue_no
            or destination != voice.get("folder_id")
            or digest(speech_text.encode("utf-8")) != voice.get("text_sha256")):
        raise AudioHandoffError("approved WAV does not match selected speech text/Drive folder")


def _probe_music(raw: bytes, mime: str) -> float:
    """Production audio decode check, never a paid TTS or media download."""
    if mime not in MIMES:
        raise AudioHandoffError("unknown music audio format")
    import shutil
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioHandoffError("ffprobe required to verify selected audio")
    with tempfile.TemporaryDirectory(prefix="simba-music-check-") as d:
        audio = Path(d) / ("music." + MIMES[mime])
        audio.write_bytes(raw)
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "format=duration:stream=codec_type", "-of", "json", str(audio)],
                capture_output=True, text=True, timeout=30, check=True)
            document = json.loads(result.stdout)
            duration = float(document["format"]["duration"])
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            raise AudioHandoffError("selected audio cannot be decoded") from None
        if (not 10 <= duration <= 1800
                or not any(x.get("codec_type") == "audio"
                           for x in document.get("streams", []))):
            raise AudioHandoffError("selected music has no valid audio stream/duration")
        return duration


def build_candidate(root: Path, project_id: str, manifest_id: str,
                    manifest_sha256: str, *, drive=None,
                    probe_music=None, voice_issue_fetch=None,
                    v2_approved_text_source: str | None = None) -> tuple[Path, dict, dict]:
    """Reconcile private selected voice/music and produce canonical project update."""
    if not isinstance(project_id, str) or not ID.fullmatch(project_id):
        raise AudioHandoffError("invalid project ID")
    root = root.resolve()
    path = catalog.inside(root, f"campaigns/{project_id}/project.json")
    try:
        original = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise AudioHandoffError("project record cannot be read") from None
    if original.get("id") != project_id:
        raise AudioHandoffError("project ID does not match canonical path")
    state = handoff.make_handoff(root, path, original)
    packet = state.get("packet") or {}
    if (state.get("state") != "READY_FOR_HANDOFF"
            or state.get("recipient") != "VOICE_AND_MUSIC"
            or packet.get("next_stage") != "voice_music"
            or not isinstance(packet.get("receipt_sha256"), str)
            or not SHA.fullmatch(packet["receipt_sha256"])):
        raise AudioHandoffError("A2E clips stage is not fully verified/ready")
    drive = drive if drive is not None else auto_script.drive_client()
    manifest_raw, _ = _private_file(
        drive, manifest_id, rafael_archive.ARCHIVE_FOLDER, manifest_sha256,
        content_type="json", limit=MAX_MANIFEST)
    try:
        data = json.loads(manifest_raw)
    except (ValueError, UnicodeDecodeError):
        raise AudioHandoffError("private audio selection plan is not JSON") from None
    selection, voice, music = _options(data, packet["receipt_sha256"], project_id)
    music_id, music_folder, music_sha = (
        music.get("file_id"), music.get("folder_id"), music.get("sha256"))
    music_bytes, music_meta = _private_file(
        drive, music_id, music_folder, music_sha, content_type="audio", limit=MAX_MUSIC)
    probe_music = probe_music or _probe_music
    music_duration = probe_music(music_bytes, music_meta["mimeType"])
    if type(music_duration) not in (int, float) or not 10 <= music_duration <= 1800:
        raise AudioHandoffError("selected music duration unverified")
    # The Voice Design profile was previously approved by Leo. This step
    # verifies already-produced audio, never requests speech synthesis.
    if voice["profile"] == "simba_warmbaritone":
        issue_number = voice.get("issue_number")
        if type(issue_number) is not int or issue_number <= 0:
            raise AudioHandoffError("existing approved voice Issue number required")
        # Lookup never calls Gemini and is after private selection verification.
        trusted_voice_issue = (voice_issue_fetch or _fetch_existing_voice_issue)(issue_number)
        _verify_voice_issue(trusted_voice_issue, voice)
        wav_id, wav_folder, wav_sha = (
            voice.get("file_id"), voice.get("folder_id"), voice.get("sha256"))
        wav, wav_meta = _private_file(
            drive, wav_id, wav_folder, wav_sha,
            content_type="audio", limit=simba_voice.MAX_AUDIO_BYTES)
        if (wav_meta.get("mimeType") not in ("audio/wav", "audio/x-wav")
                or wav_meta.get("name") != f"Simba_voice_issue_{issue_number}.wav"):
            raise AudioHandoffError("selected Simba narration not from approved TTS issue")
        if (not isinstance((wav_meta.get("appProperties") or {}).get("simba_render_marker_id"), str)
                or not (wav_meta.get("appProperties") or {})["simba_render_marker_id"]):
            raise AudioHandoffError("existing approved Simba voice run marker missing")
        try:
            wav_duration = simba_voice._validated_wav(wav)
        except simba_voice.VoiceError:
            raise AudioHandoffError("existing Simba narration WAV invalid") from None
    else:
        if any(key in voice for key in ("file_id", "folder_id", "sha256", "issue_number")):
            raise AudioHandoffError("voice=none cannot silently add a new narrator")
        wav_duration, wav_id, wav_sha = None, None, None
    result = json.loads(json.dumps(original, ensure_ascii=False))
    music_asset_id = "music-" + music_sha[:24]
    if any(a.get("id") == music_asset_id or
           a.get("drive_file_id") == music_id for a in result["assets"]):
        raise AudioHandoffError("music is already registered; no duplicate stage")
    rights = _approved_license(music, channels=data["channels"])
    result["assets"].append({
        "id": music_asset_id, "kind": "music", "title": "Music Editor selected track",
        "state": "available",
        "url": "https://drive.google.com/file/d/" + music_id + "/view",
        "drive_file_id": music_id,
        "recorded_sha256": music_sha, "recorded_duration_seconds": round(music_duration, 3),
        "recorded_size_bytes": len(music_bytes),
        "evidence": rights + "; selected by Leo, rights are recorded assertions not legal certification",
    })
    new_ids = [music_asset_id]
    if wav_id:
        wav_asset_id = "narration-" + wav_sha[:24]
        if any(a.get("id") == wav_asset_id or
               a.get("drive_file_id") == wav_id for a in result["assets"]):
            raise AudioHandoffError("narration is already registered; no duplicate stage")
        result["assets"].append({
            "id": wav_asset_id, "kind": "narration", "title": "Simba approved WarmBaritone",
            "state": "available",
            "url": "https://drive.google.com/file/d/" + wav_id + "/view",
            "drive_file_id": wav_id, "recorded_sha256": wav_sha,
            "recorded_duration_seconds": round(wav_duration, 3),
            "recorded_size_bytes": len(wav),
            "evidence": "Previously generated Simba WarmBaritone WAV with private Drive marker; "
                        "actual voice words require final Whisper/QA",
        })
        new_ids.append(wav_asset_id)
    result.setdefault("stage_handoffs", {})["voice_music"] = {
        "state": "completed", "input_fingerprint": packet["receipt_sha256"],
        "assets": new_ids, "approval_evidence": (
            "Leo selected text option " + str(selection["text_option"]) +
            " and music option " + str(selection["music_option"]) +
            "; private selection evidence SHA-256 " +
            digest(selection["leo_approval_evidence"].encode())),
        "texts_presented": 3, "music_presented": 3,
        "text_option": selection["text_option"],
        "music_option": selection["music_option"],
        "voice_profile": voice["profile"],
        "music_license_evidence": rights,
    }
    if v2_approved_text_source is not None:
        # The existing private manifest and owner Voice Issue already verified
        # the EXACT selected narration text. A v2 lock is allowed only when
        # that exact text SHA is also pinned in the canonical source list.
        # This is opt-in; existing voice/music v1 records are unchanged.
        result = studio_v2_audio_stage.bind_verified_voice_music(
            result,
            approved_text_source_path=v2_approved_text_source,
            approved_voice_text_sha256=voice["text_sha256"])

    result["stage"] = "VOICE_AND_MUSIC_MEDIA_VERIFIED"
    result["next_action"] = (
        "MONTAGE: show three edit/transition/caption approaches; "
        "do not render until an explicit selection.")
    result["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    if (original.get("approvals") != result.get("approvals")
            or original.get("approved_asset_id") != result.get("approved_asset_id")
            or original.get("working_asset_id") != result.get("working_asset_id")):
        raise AudioHandoffError("voice/music step attempted to change final approvals")
    downstream = handoff.make_handoff(root, path, result)
    next_packet = downstream.get("packet") or {}
    if (downstream.get("state") != "READY_FOR_HANDOFF"
            or downstream.get("recipient") != "MONTAGE"
            or next_packet.get("next_stage") != "edit_choice"):
        raise AudioHandoffError("voice/music candidate failed existing montage stage gate")
    report = {
        "status": "VOICE_MUSIC_CANDIDATE_VERIFIED_NOT_WRITTEN",
        "project_id": project_id,
        "selected_text_option": selection["text_option"],
        "selected_music_option": selection["music_option"],
        "voice_profile": voice["profile"],
        "voice_seconds_recorded": round(wav_duration, 3) if wav_duration else None,
        "music_seconds_recorded": round(music_duration, 3),
        "music_license_human_review_recorded": True,
        "music_license_legally_certified_by_code": False,
        "asset_ids": new_ids, "next_recipient": "MONTAGE",
        "next_stage": "edit_choice", "paid_calls": 0,
        "v2_audio_lock_metadata": (
            "VALID_METADATA_NOT_ALIGNED" if v2_approved_text_source is not None
            else "LEGACY_V1_NO_CANONICAL_AUDIO_LOCK"),
        "rendered": False, "published": False, "project_written": False,
    }
    return path, result, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest-file-id", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--v2-approved-text-source",
                        help="Opt-in canonical approved narration source file; SHA must exactly match owner-approved voice Issue text")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        path = catalog.inside(root, f"campaigns/{args.project}/project.json")
        before = digest(path.read_bytes())
        target, updated, report = build_candidate(
            root, args.project, args.manifest_file_id, args.manifest_sha256,
            v2_approved_text_source=args.v2_approved_text_source)
        if args.apply:
            a2e_writeback.apply_candidate(
                root, target, updated, original_sha256=before)
            report["status"] = "VOICE_MUSIC_APPLIED_LOCALLY_GIT_PUSH_PENDING"
            report["project_written"] = True
        exit_code = 0
    except Exception:
        # Do not reveal private prompt/music selection metadata in public logs.
        report = {
            "status": "BLOCKED_VOICE_MUSIC",
            "reason": "Stage, human selection, existing WAV, private track or license evidence missing/invalid",
            "paid_calls": 0, "project_written": False,
        }
        exit_code = 2
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
