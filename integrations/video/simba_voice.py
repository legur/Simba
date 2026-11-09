"""Approved Simba voice for the photo-story renderer (Google Gemini Voice Design).

The recurring WarmBaritone voice is stored PRIVATELY on Google Drive. Never commit
the voice id or Google/API credentials, publish audio, or silently fall back to Edge.
Each line has at most one attempt per model. Primary outages allow one Flash-Lite
attempt with the same voice; both attempts are journaled before billing.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.request
import wave

VOICE_NAME = "WarmBaritone"
FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
GITHUB_TTS_WORKFLOW = "Simba video — private GitHub Secrets render"
GITHUB_TTS_WORKFLOW_REF = (
    "legur/Simba/.github/workflows/"
    "simba-video-secrets-render.yml@refs/heads/main"
)
META_NAME = "SimbaDesign_WarmBaritone.json"
FOLDER_NAME = "Simba Private TTS Prague 2026-11-07"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "tts" / "prague_male_voices.json"
MAX_RESPONSE_BYTES = 18 * 1024 * 1024
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_NEW_LINES = 16
MAX_NEW_CHARACTERS = 1200
STYLE = (
    "Speak the supplied Russian text exactly, as Simba, a warm and confident "
    "mature male travel companion: comfortable natural baritone, gentle grain, "
    "conversational phrasing and restrained emotion. Not a booming announcer; "
    "do not sing, rush, change figures or add words."
)


class VoiceError(RuntimeError):
    pass


class ProviderUnavailable(VoiceError):
    def __init__(self, reason, *, may_have_been_billed):
        self.reason = reason
        self.may_have_been_billed = may_have_been_billed
        super().__init__("Gemini unavailable (" + reason + "); attempt recorded")


def _require_github_secrets_workflow():
    """Enforce runtime policy from GitHub environment evidence.

    These variables identify the dedicated owner-dispatched workflow but are
    not cryptographic attestation of where an environment value originated.
    """
    checkout_sha = os.environ.get("GITHUB_SHA", "")
    workflow_sha = os.environ.get("GITHUB_WORKFLOW_SHA", "")
    event_kind = os.environ.get("GITHUB_EVENT_NAME")
    trusted_issue = False
    if event_kind == "issues":
        try:
            event = json.loads(Path(os.environ.get("GITHUB_EVENT_PATH", "")).read_text(encoding="utf-8"))
            issue = event.get("issue") or {}
            trusted_issue = (
                event.get("action") == "labeled"
                and (event.get("label") or {}).get("name") == "simba-approved-voice"
                and (event.get("sender") or {}).get("login") == "legur"
                and (issue.get("user") or {}).get("login") == "legur"
                and issue.get("pull_request") is None
                and os.environ.get("GITHUB_WORKFLOW") == "Simba approved voice issue runner"
                and os.environ.get("GITHUB_WORKFLOW_REF") == "legur/Simba/.github/workflows/simba-approved-voice-issue.yml@refs/heads/main"
            )
        except (OSError, ValueError, TypeError):
            trusted_issue = False
    trusted_dispatch = (event_kind == "workflow_dispatch"
        and os.environ.get("GITHUB_WORKFLOW") == GITHUB_TTS_WORKFLOW
        and os.environ.get("GITHUB_WORKFLOW_REF") == GITHUB_TTS_WORKFLOW_REF)
    trusted = (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and (trusted_dispatch or trusted_issue)
        and os.environ.get("GITHUB_ACTOR") == os.environ.get("GITHUB_REPOSITORY_OWNER")
        and os.environ.get("GITHUB_TRIGGERING_ACTOR") == os.environ.get("GITHUB_REPOSITORY_OWNER")
        and os.environ.get("GITHUB_ACTOR") == "legur"
        and os.environ.get("GITHUB_REPOSITORY") == "legur/Simba"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and re.fullmatch(r"[0-9a-fA-F]{40}", checkout_sha) is not None
        and workflow_sha == checkout_sha
    )
    if not trusted:
        raise VoiceError(
            "New Simba TTS is allowed only in the owner-dispatched dedicated "
            "GitHub Actions workflow on main; no request submitted"
        )


def approved_profile():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        selected = config["production_voice"]
        if (selected["selection_status"] != "approved_by_user"
                or selected["profile"] != VOICE_NAME
                or selected["provider"] != "Google Gemini Voice Design"
                or selected["model"] != "gemini-3.8-flash-tts"
                or config.get("voice_gender") != "male_only"):
            raise VoiceError("Simba voice approval and model configuration disagree")
        return selected
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise VoiceError("Approved Simba voice config unavailable or invalid") from None


def _check_voice_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"voice_[A-Za-z0-9_-]{6,150}", value):
        raise VoiceError("Approved private voice id missing or invalid")
    return value


def _from_metadata(raw):
    try:
        d = json.loads(raw)
        if (d.get("label") != "Simba — Теплый баритон"
                or d.get("provider") != "Google Gemini"
                or d.get("model") != "gemini-3.8-flash-tts"
                or d.get("gender") != "male"
                or d.get("language_code") != "ru-RU"
                or d.get("type") != "prompted"):
            raise VoiceError("Private voice metadata does not match the approved Simba profile")
        return _check_voice_id(d.get("voice_id"))
    except (ValueError, TypeError, AttributeError):
        raise VoiceError("Private voice metadata is unreadable") from None


def voice_id_from_private_store():
    """Resolve selected voice ID: local private file / secret / existing Drive OAuth."""
    approved_profile()
    direct = os.environ.get("SIMBA_GEMINI_VOICE_ID", "").strip()
    if direct:
        return _check_voice_id(direct)

    path = os.environ.get("SIMBA_GEMINI_VOICE_METADATA_FILE", "").strip()
    if path:
        try:
            meta = Path(path)
            if not meta.is_file() or meta.stat().st_size > 12000:
                raise VoiceError("Private voice metadata file missing or too large")
            return _from_metadata(meta.read_text(encoding="utf-8"))
        except OSError:
            raise VoiceError("Could not read private Simba voice metadata") from None

    required = ("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET",
                "GDRIVE_OAUTH_REFRESH_TOKEN")
    if any(not os.environ.get(name) for name in required):
        raise VoiceError(
            "Simba voice ID not accessible: set SIMBA_GEMINI_VOICE_METADATA_FILE "
            "to the private Drive JSON, or configure Google Drive OAuth secrets; "
            "no fallback voice will be used."
        )
    _require_github_secrets_workflow()
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        creds = Credentials(
            token=None, refresh_token=os.environ["GDRIVE_OAUTH_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GDRIVE_OAUTH_CLIENT_ID"],
            client_secret=os.environ["GDRIVE_OAUTH_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        creds.refresh(GoogleRequest())
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        folders = drive.files().list(
            q="name = '" + FOLDER_NAME + "' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="nextPageToken,files(id,shared,parents)", pageSize=20,
        ).execute(num_retries=0)
        if folders.get("nextPageToken") or len(folders.get("files", [])) != 1:
            raise VoiceError("Private Simba voice folder is missing or ambiguous")
        folder = folders["files"][0]
        if folder.get("shared"):
            raise VoiceError("Simba voice metadata folder must remain private")
        file_query = "name = '" + META_NAME + "' and '" + folder["id"] + "' in parents and trashed = false"
        matching = drive.files().list(
            q=file_query, fields="nextPageToken,files(id,shared,mimeType,size,parents)",
            pageSize=20
        ).execute(num_retries=0)
        if matching.get("nextPageToken") or len(matching.get("files", [])) != 1:
            raise VoiceError("Approved private Simba voice metadata file is missing or ambiguous")
        file = matching["files"][0]
        if (file.get("shared") or file.get("mimeType") != "application/json"
                or int(file.get("size", 0)) > 12000 or not int(file.get("size", 0))):
            raise VoiceError("Simba voice metadata file is not small, JSON, and private")
        raw = drive.files().get_media(fileId=file["id"]).execute(num_retries=0)
        if not isinstance(raw, bytes) or len(raw) > 12000:
            raise VoiceError("Private voice metadata contents invalid")
        return _from_metadata(raw.decode("utf-8"))
    except VoiceError:
        raise
    except Exception:
        # Never include network exception strings, which may contain credentials or URLs.
        raise VoiceError("Google Drive voice lookup failed; credentials and data remain private") from None


def _validated_wav(blob):
    """A real little-endian PCM WAV, 24 kHz 16-bit mono or stereo, 2–120 s."""
    if not isinstance(blob, bytes) or not 4096 <= len(blob) <= MAX_AUDIO_BYTES:
        raise VoiceError("Generated WAV size invalid")
    if not blob.startswith(b"RIFF") or blob[8:12] != b"WAVE":
        raise VoiceError("Gemini returned non-WAV audio")
    try:
        with wave.open(io.BytesIO(blob), "rb") as r:
            if r.getnchannels() not in (1, 2) or r.getsampwidth() != 2 or r.getframerate() != 24000:
                raise VoiceError("Unexpected Gemini WAV format (expected 24 kHz, 16-bit PCM)")
            seconds = r.getnframes() / r.getframerate()
            if not 0.3 <= seconds <= 120:
                raise VoiceError("Gemini WAV duration out of bounds")
            return seconds
    except (wave.Error, EOFError):
        raise VoiceError("Gemini returned corrupt WAV") from None


def _audio_from_response(obj):
    choices = []
    if isinstance(obj, dict):
        a = obj.get("output_audio")
        if isinstance(a, dict) and isinstance(a.get("data"), str):
            choices.append(a)
        for step in obj.get("steps", []):
            if isinstance(step, dict) and step.get("type") == "model_output":
                for part in step.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "audio" and isinstance(part.get("data"), str):
                        choices.append(part)
    if len(choices) != 1:
        raise VoiceError("Gemini audio response missing or ambiguous; never automatically retry")
    try:
        blob = base64.b64decode(choices[0]["data"], validate=True)
    except (ValueError, base64.binascii.Error):
        raise VoiceError("Gemini audio payload is malformed") from None
    _validated_wav(blob)
    return blob


def _generate_once(text, voice_id, model, *, response_path=None):
    # Keep this check at the actual network boundary too: callers can inject a
    # wrapper around this private generator and bypass synthesize_lines' early
    # preflight identity check.
    _require_github_secrets_workflow()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise VoiceError("GEMINI_API_KEY missing; Simba voice cannot be rendered")
    payload = {
        "model": model,
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": text,
            "annotations": [{"type": "speech_metadata", "style": STYLE}]
        }]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice_id}]}
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        INTERACTIONS_URL, data=data, method="POST",
        headers={"x-goog-api-key": key, "Content-Type": "application/json",
                 "Accept": "application/json"}
    )
    # Strictly one attempt. Even timeout/HTTP 500 may represent a billed synthesis.
    try:
        with urllib.request.urlopen(req, timeout=150) as result:
            body = result.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 429 or 500 <= code <= 599:
            raise ProviderUnavailable("http_" + str(code), may_have_been_billed=code != 429) from None
        raise VoiceError("Gemini request rejected (HTTP " + str(code) + "); no automatic retry") from None
    except OSError:
        raise ProviderUnavailable("network_or_timeout", may_have_been_billed=True) from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise VoiceError("Gemini response exceeds safe limit; do not retry automatically")
    try:
        parsed = json.loads(body)
        if response_path is not None and isinstance(parsed, dict):
            # Private recovery only: no headers, key, request URL or raw errors.
            saved = {k: parsed[k] for k in ("id", "steps", "output_audio", "status", "usage", "model") if k in parsed}
            with Path(response_path).open("x", encoding="utf-8") as out:
                json.dump(saved, out)
        return _audio_from_response(parsed)
    except (UnicodeDecodeError, ValueError):
        raise VoiceError("Malformed Gemini JSON response; attempt recorded, no automatic retry") from None


def _cache_paths(cache_dir, model, voice_id, text):
    digest = hashlib.sha256(
        json.dumps([model, voice_id, STYLE, text], ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return cache_dir / (digest + ".wav"), cache_dir / (digest + ".attempt.json")


def _primary_unavailable(attempt):
    try:
        return json.loads(attempt.read_text(encoding="utf-8")).get("state") == "provider_unavailable"
    except (OSError, ValueError, AttributeError):
        return False


def _synthesize_once(text, voice_id, model, dst, attempt, generate):
    audit = {"state": "attempt_started", "provider": "Gemini", "model": model,
             "profile": VOICE_NAME, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
             "cache_name": dst.name}
    try:
        with attempt.open("x", encoding="utf-8") as f:
            json.dump(audit, f)
    except FileExistsError:
        raise VoiceError("Concurrent or previous TTS attempt detected; no request submitted") from None
    try:
        if generate is _generate_once:
            blob = generate(text, voice_id, model, response_path=attempt.with_suffix('.response.json'))
        else:
            blob = generate(text, voice_id, model)
    except ProviderUnavailable as exc:
        audit.update(state="provider_unavailable", reason=exc.reason,
                     may_have_been_billed=exc.may_have_been_billed)
        attempt.write_text(json.dumps(audit), encoding="utf-8")
        raise
    _validated_wav(blob)
    tmp = dst.with_suffix(".pending")
    with tmp.open("xb") as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(dst)


def synthesize_lines(lines, cache_dir: Path, *, voice_id=None, generate=None, allow_fallback=True, selected_model=None):
    """Prepare all non-clip narration lines and return their cached WAV paths.

    Fail before ANY paid request if the maximum new lines/chars would be exceeded.
    Primary outages allow one Flash-Lite attempt. A .attempt.json is written
    BEFORE each model's request. Existing uncertain attempts are never repeated.
    """
    if type(allow_fallback) is not bool:
        raise VoiceError("allow_fallback must be a boolean; no request submitted")
    selected = approved_profile()
    if selected_model not in (None, selected["model"], FALLBACK_MODEL):
        raise VoiceError("Selected Google TTS model is not approved; no request submitted")
    if selected_model == FALLBACK_MODEL:
        allow_fallback = False
    if voice_id is None:
        voice_id = voice_id_from_private_store()
    else:
        voice_id = _check_voice_id(voice_id)
    model = selected_model or selected["model"]
    generate = generate or _generate_once
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tasks, result, new_count, new_chars = [], {}, 0, 0
    for L in lines:
        if L.get("fromClip"):
            continue
        text = L.get("say", L["text"])
        if not isinstance(text, str) or not text.strip() or len(text) > 450:
            raise VoiceError("Invalid single-line Simba voice text")
        primary = _cache_paths(cache_dir, model, voice_id, text)
        fallback = _cache_paths(cache_dir, FALLBACK_MODEL, voice_id, text)
        cached = next((p for p, _ in (primary, fallback) if p.exists()), None)
        if cached is not None:
            _validated_wav(cached.read_bytes())
            result[L["id"]] = cached
            continue
        use_fallback = allow_fallback and primary[1].exists() and _primary_unavailable(primary[1])
        if fallback[1].exists() or (primary[1].exists() and not use_fallback):
            raise VoiceError("Earlier Gemini attempt has no verified WAV: no automatic retry")
        new_count += 1
        new_chars += len(text)
        tasks.append((L, text, primary, fallback, use_fallback))
    if new_count > MAX_NEW_LINES or new_chars > MAX_NEW_CHARACTERS:
        raise VoiceError(
            f"Simba TTS request cap exceeded ({new_count} new lines, {new_chars} chars); "
            "split the video or obtain explicit budget approval"
        )
    if new_count:
        # This must precede _synthesize_once, which creates the attempt journal
        # immediately before the potentially billable provider call.
        _require_github_secrets_workflow()
    if new_count and not os.environ.get("GEMINI_API_KEY"):
        raise VoiceError("GEMINI_API_KEY missing; no paid requests attempted")

    switched = False
    for L, text, primary, fallback, use_fallback in tasks:
        cached = next((p for p, _ in (primary, fallback) if p.exists()), None)
        if cached is not None:
            _validated_wav(cached.read_bytes())
            result[L["id"]] = cached
            continue
        switched = switched or use_fallback
        if not switched:
            try:
                _synthesize_once(text, voice_id, model, *primary, generate)
                result[L["id"]] = primary[0]
                continue
            except ProviderUnavailable:
                if not allow_fallback:
                    raise
                switched = True
        _synthesize_once(text, voice_id, FALLBACK_MODEL, *fallback, generate)
        result[L["id"]] = fallback[0]
    return result

