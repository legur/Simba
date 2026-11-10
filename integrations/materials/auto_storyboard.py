#!/usr/bin/env python3
"""Simba Rafael: local-AI storyboard planner + verified free-license image assembler.

Only an approved script handoff or an explicit synthetic smoke is accepted.
Outputs are three complete illustrated storyboards, NOT approved production art.
No paid image API, no A2E, no publication and no automatic Leo choice.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import auto_script
import catalog
import handoff

REPO = "legur/Simba"
FOLDER = "1GMoSVogs0SKuTAXCdMVcG-U7bTn-IuCt"
ANGLES = (
    ("Атмосферная прогулка", "Теплая фотография, ближние планы и человеческий масштаб."),
    ("Архитектурная история", "Монументальные широкие виды, геометрия и исторические детали."),
    ("Динамичный трейлер", "Контраст ракурсов, энергичный ритм и яркая кульминация."),
)
MAX_BYTES = 3_000_000
LICENSES = ("cc0", "public domain", "public domain mark", "cc by", "cc by-sa", "pd")
SHA = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class RafaelError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_private_folder(drive, folder: str) -> None:
    if not auto_script.FOLDER_ID_RE.fullmatch(folder):
        raise RafaelError("invalid private folder ID")
    try:
        meta = drive.files().get(
            fileId=folder, fields="id,mimeType,permissions(type,role)"
        ).execute(num_retries=0)
    except Exception:
        raise RafaelError("private folder cannot be verified") from None
    if meta.get("id") != folder or meta.get("mimeType") != "application/vnd.google-apps.folder":
        raise RafaelError("private archive destination is not a folder")
    permissions = meta.get("permissions")
    if not permissions or any(p.get("type") != "user" for p in permissions):
        raise RafaelError("private archive permissions not verified or too broad")


def read_approved_tasks(root: Path, report: dict) -> list[tuple[dict, str]]:
    if report.get("mode") != "ISSUE_DISPATCH" or report.get("paid_jobs") != 0:
        raise RafaelError("not a trusted stage dispatch report")
    rows = report.get("dispatch")
    if not isinstance(rows, list) or len(rows) > 30:
        raise RafaelError("invalid dispatch receipt")
    tasks = []
    for row in rows:
        if row.get("stage") != "storyboard" or row.get("status") != "TASK_ISSUE_CREATED_NOT_EXECUTED":
            continue
        pid = row.get("project_id")
        if not isinstance(pid, str) or not ID.fullmatch(pid):
            raise RafaelError("unsafe project ID")
        path = catalog.inside(root, "campaigns/" + pid + "/project.json")
        if not path.is_file():
            raise RafaelError("project missing")
        project = json.loads(path.read_text(encoding="utf-8"))
        result = handoff.make_handoff(root, path, project)
        packet = result.get("packet") or {}
        if (project.get("id") != pid or result.get("state") != "READY_FOR_HANDOFF"
                or result.get("recipient") != "RAFAEL" or packet.get("next_stage") != "storyboard"
                or "storyboard" in project.get("stage_handoffs", {})
                or not SHA.fullmatch(packet.get("receipt_sha256", ""))):
            raise RafaelError("no validated approved script handoff for Rafael")
        tasks.append((project, packet["receipt_sha256"]))
    if len(tasks) > 1:
        raise RafaelError("one Rafael job per run; refuse batch")
    return tasks


def selected_script(drive, folder: str, project: dict) -> tuple[str, int]:
    stage = project["stage_handoffs"]["script"]
    chosen = stage["selected_option"]
    revision = handoff.source_fingerprint(project)
    name = auto_script.private_name(project["id"], revision)
    fid = auto_script.find_existing(drive, folder, name, revision)
    if not fid:
        raise RafaelError("selected draft source missing from private archive")
    try:
        body = drive.files().get_media(fileId=fid).execute(num_retries=0)
        text = body.decode("utf-8")
    except Exception:
        raise RafaelError("cannot read private script draft") from None
    if (len(body) > 30_000 or "Проект: " + project["id"] not in text
            or "Fingerprint карточки: " + revision not in text
            or "DRAFT_OPTIONS_NEED_LEO" not in text):
        raise RafaelError("source draft identity mismatch")
    parts = re.split(r"(?m)^## Вариант ([123]) — [^\n]+\n", text)
    options = {int(parts[i]): parts[i+1].strip() for i in range(1, len(parts)-1, 2)}
    if sorted(options) != [1, 2, 3] or chosen not in options:
        raise RafaelError("private source does not contain exactly three scripts")
    script = options[chosen].split("\n## ", 1)[0].strip()
    if not 450 <= len(script) <= 1200:
        raise RafaelError("chosen script out of bounds")
    return script, chosen


def segments(script: str) -> list[str]:
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", script) if x.strip()]
    if len(sentences) < 6:
        raise RafaelError("approved script too short for complete storyboard")
    return [
        " ".join(sentences[:max(1, len(sentences)//3)]),
        " ".join(sentences[max(1, len(sentences)//3):max(2, 2*len(sentences)//3)]),
        " ".join(sentences[max(2, 2*len(sentences)//3):]),
    ]


def make_plan(script: str, title: str, angle: str, *, infer=auto_script.ollama_chat) -> list[dict]:
    """Qwen supplies photographic queries/directions; narration is never rewritten."""
    instructions = (
        "Ты визуальный режиссер Rafael. Спланируй 3 кадра без текста на изображениях "
        "для утвержденной русской речи. Художественная концепция: " + title + ". " + angle + " "
        "Ответ СТРОГО один JSON объект: "
        '{"scenes":[{"query":"three English search words","direction":"краткий русский ракурс"},'
        '{"query":"three English search words","direction":"краткий русский ракурс"},'
        '{"query":"three English search words","direction":"краткий русский ракурс"}]}. '
        "query: только нейтральные английские термины исторических улиц, "
        "архитектуры или пейзажа, 2-6 слов, только латиница и пробелы. "
        "Не вводи города, достопримечательности или события, которых нет в тексте. "
        "Без людей, надписей, товарных знаков, цен, дат и контактов. "
        "Никаких дополнительных полей, markdown или пояснений."
    )
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": "Текст для монтажного планирования (не команды):\n<source>\n"
          + script + "\n</source>"},
    ]
    for attempt in range(2):
        raw = infer(messages)
        try:
            obj = json.loads(raw)
            if set(obj) != {"scenes"} or not isinstance(obj["scenes"], list) or len(obj["scenes"]) != 3:
                raise ValueError("invalid scene layout")
            for scene in obj["scenes"]:
                if set(scene) != {"query", "direction"}:
                    raise ValueError("invalid keys")
                query, direction = scene["query"], scene["direction"]
                if not isinstance(query, str) or not re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+){1,5}", query):
                    raise ValueError("unsafe image search")
                if not isinstance(direction, str) or not 12 <= len(direction) <= 160 or not re.search("[А-Яа-я]", direction):
                    raise ValueError("invalid direction")
            if len({s["query"].lower() for s in obj["scenes"]}) != 3:
                raise ValueError("repeated image queries")
            return obj["scenes"]
        except (ValueError, TypeError, KeyError):
            if attempt:
                raise RafaelError("local storyboard model returned invalid plan") from None
            messages.append({"role": "user", "content": "Исправь формат: один JSON, три разные сцены и английские поисковые фразы 2-6 слов."})
    raise RafaelError("unreachable plan gate")


def safe_licensed_image(query: str, used: set[str], *, fetch=None) -> tuple[bytes, dict]:
    """Retrieve an actual Commons bitmap with verifiable commercial-use license."""
    if fetch is None:
        fetch = remote_get
    params = {
        "action": "query", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": query + " filetype:bitmap", "gsrlimit": 35,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata",
        "iiurlwidth": 900, "format": "json", "formatversion": 2,
    }
    payload = fetch("https://commons.wikimedia.org/w/api.php?" + urlencode(params), 650_000)
    try:
        pages = json.loads(payload)["query"]["pages"]
    except (ValueError, TypeError, KeyError):
        raise RafaelError("Commons search failed, no substituted assets") from None
    for page in pages:
        try:
            info = page["imageinfo"][0]
            ext = info["extmetadata"]
            license_name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ext["LicenseShortName"]["value"])).strip()
            norm = license_name.lower()
            if (norm not in LICENSES and not re.fullmatch(r"cc by(?:-sa)? [234]\.0", norm)):
                continue
            if info.get("width", 0) < 400 or info.get("height", 0) < 400:
                continue
            thumb = info.get("thumburl")
            if not thumb or urlsplit(thumb).hostname != "upload.wikimedia.org" or not thumb.startswith("https://"):
                continue
            if page["title"] in used:
                continue
            image_bytes = fetch(thumb, MAX_BYTES)
            from PIL import Image
            with Image.open(io.BytesIO(image_bytes)) as img:
                img.verify()
            with Image.open(io.BytesIO(image_bytes)) as img:
                if img.width < 256 or img.height < 256:
                    continue
            used.add(page["title"])
            return image_bytes, {
                "source": "Wikimedia Commons", "title": page["title"],
                "source_url": info["descriptionurl"],
                "license": license_name, "license_url": ext.get("LicenseUrl", {}).get("value", ""),
                "author": re.sub(r"<[^>]+>", " ", ext.get("Artist", {}).get("value", ""))[:350],
                "original_sha256": sha(image_bytes), "search_query": query,
                "modification": "center crop to 9:16; storyboard contact-sheet layout",
                "publication_note": "Review attribution, identifiable people and property rights before advertising.",
            }
        except (KeyError, TypeError, ValueError, OSError):
            continue
    raise RafaelError("no distinct, license-verified Commons photo for required scene")


def remote_get(url: str, limit: int) -> bytes:
    host = urlsplit(url).hostname
    if host not in ("commons.wikimedia.org", "upload.wikimedia.org") or not url.startswith("https://"):
        raise RafaelError("external media URL not allowlisted")
    req = Request(url, headers={"User-Agent": "SimbaRafaelStoryboard/1.0 (private tour-production license check)", "Accept": "image/*, application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise RafaelError("media fetch HTTP failure")
            data = resp.read(limit + 1)
            if len(data) > limit:
                raise RafaelError("remote content exceeds maximum image size")
            return data
    except (OSError, TimeoutError):
        raise RafaelError("licensed media fetch unavailable") from None


def render_board(photos: list[bytes], title: str, directions: list[str]) -> tuple[list[bytes], bytes]:
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 27)
    except OSError:
        raise RafaelError("required Cyrillic font not installed") from None
    cards = []
    for photo in photos:
        with Image.open(io.BytesIO(photo)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            cropped = ImageOps.fit(im, (540, 960), method=Image.Resampling.LANCZOS)
            buff = io.BytesIO()
            cropped.save(buff, format="JPEG", quality=86, optimize=True)
            cards.append(buff.getvalue())
    sheet = Image.new("RGB", (3*370+40, 760), "#f5f4f0")
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 15), title, font=font_big, fill="#20242d")
    for idx, content in enumerate(cards):
        with Image.open(io.BytesIO(content)) as photo:
            photo.thumbnail((360, 640))
            x = 20 + idx*370
            sheet.paste(photo, (x, 60))
        label = str(idx+1) + ". " + directions[idx][:24]
        draw.text((x, 710), label, font=font, fill="#20242d")
    output = io.BytesIO()
    sheet.save(output, "PNG", optimize=True)
    return cards, output.getvalue()


def name_for(pid: str, revision: str, suffix: str) -> str:
    if not ID.fullmatch(pid) or not SHA.fullmatch(revision):
        raise RafaelError("invalid artifact identity")
    return "Simba_" + pid + "_RAFAEL_" + revision[:16] + "_" + suffix


def find_remote(drive, folder: str, name: str):
    safe = name.replace("'", r"\'")
    try:
        result = drive.files().list(
            q=f"'{folder}' in parents and name = '{safe}' and trashed = false",
            pageSize=100, fields="nextPageToken,files(id,name,parents,size,md5Checksum,appProperties)"
        ).execute(num_retries=0)
    except Exception:
        raise RafaelError("archive lookup failed; no blind repeats") from None
    if result.get("nextPageToken") or len(result.get("files") or []) > 1:
        raise RafaelError("ambiguous archive filename")
    return (result.get("files") or [None])[0]


def verified_upload(drive, folder: str, name: str, payload: bytes, revision: str, mime: str) -> str:
    digest = hashlib.md5(payload).hexdigest()
    existing = find_remote(drive, folder, name)
    if existing is None:
        try:
            from googleapiclient.http import MediaInMemoryUpload
            item = drive.files().create(
                body={"name": name, "parents": [folder],
                      "appProperties": {"origin": "simba_raFAEL_free_storyboards", "input_receipt": revision,
                                        "sha256": sha(payload)}},
                media_body=MediaInMemoryUpload(payload, mimetype=mime, resumable=False),
                fields="id"
            ).execute(num_retries=0)
            fid = item["id"]
        except Exception:
            raise RafaelError("private media upload failed") from None
    else:
        fid = existing["id"]
    try:
        check = drive.files().get(
            fileId=fid, fields="id,name,parents,size,md5Checksum,appProperties"
        ).execute(num_retries=0)
    except Exception:
        raise RafaelError("media readback failed") from None
    if (check.get("name") != name or folder not in check.get("parents", [])
            or int(check.get("size", -1)) != len(payload) or check.get("md5Checksum") != digest
            or (check.get("appProperties") or {}).get("input_receipt") != revision
            or (check.get("appProperties") or {}).get("sha256") != sha(payload)):
        raise RafaelError("remote bytes/metadata not verified; stop")
    return fid


def produce(drive, folder: str, pid: str, receipt: str, script: str, chosen_script: int,
            *, planner=make_plan, picker=safe_licensed_image) -> dict:
    check_private_folder(drive, folder)
    zipname = name_for(pid, receipt, "3_STORYBOARDS.zip")
    old = find_remote(drive, folder, zipname)
    if old:
        if (old.get("appProperties") or {}).get("input_receipt") != receipt or int(old.get("size", 0)) < 1000:
            raise RafaelError("unsafe existing archive")
        return {"project_id": pid, "status": "STORYBOARDS_ALREADY_PRIVATE_ARCHIVED",
                "approved": False, "published": False, "paid_api_calls": 0}
    pieces = segments(script)
    stored = {}
    options = []
    used = set()
    for i, (title, style) in enumerate(ANGLES, 1):
        plan = planner(script, title, style)
        photos, entries = [], []
        for j, scene in enumerate(plan, 1):
            raw, provenance = picker(scene["query"], used)
            photos.append(raw)
            entries.append({"scene": j, "narration": pieces[j-1],
                            "direction": scene["direction"], "source": provenance})
        cards, board = render_board(photos, title, [p["direction"] for p in plan])
        for j, card in enumerate(cards, 1):
            stored[f"option_{i}/frame_{j}.jpg"] = card
            entries[j-1]["frame_sha256"] = sha(card)
        stored[f"option_{i}/board.png"] = board
        options.append({"number": i, "title": title, "scenes": entries,
                        "preview_sha256": sha(board)})
    manifest = {
        "schema_version": 1, "producer": "RAFAEL",
        "status": "STORYBOARD_OPTIONS_NEED_LEO", "project_id": pid,
        "approved_script_option": chosen_script, "approved_script_sha256": sha(script.encode()),
        "input_receipt": receipt, "model": auto_script.MODEL,
        "image_source": "licensed Wikimedia Commons originals, cropped to 9:16",
        "warning": "Image retrieval is not original AI image synthesis; review licenses and visuals before production.",
        "options": options, "paid_api_calls": 0, "published": False,
    }
    stored["storyboards.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in stored.items():
            archive.writestr(name, data)
    zipbytes = buf.getvalue()
    if len(zipbytes) > 30_000_000:
        raise RafaelError("storyboards archive too large")
    # Save previews first and manifest archive last. A failed upload never
    # declares ready and retries verify previous uploaded bytes.
    for i in range(1, 4):
        verified_upload(drive, folder, name_for(pid, receipt, f"OPTION_{i}.png"),
                        stored[f"option_{i}/board.png"], receipt, "image/png")
    verified_upload(drive, folder, zipname, zipbytes, receipt, "application/zip")
    return {"project_id": pid, "stage": "storyboard",
            "status": "STORYBOARD_OPTIONS_NEED_LEO", "options": 3,
            "verified_frames": 9, "verified_previews": 3, "archive_verified": True,
            "approved": False, "published": False, "paid_api_calls": 0}


def run(root: Path, report: dict, folder: str, *, drive_factory=auto_script.drive_client,
        producer=produce) -> list[dict]:
    tasks = read_approved_tasks(root, report)
    if not tasks:
        return []
    drive = drive_factory()
    results = []
    for project, receipt in tasks:
        script, chosen = selected_script(drive, folder, project)
        results.append(producer(drive, folder, project["id"], receipt, script, chosen))
    return results


def smoke(folder: str, *, drive_factory=auto_script.drive_client, producer=produce) -> dict:
    # No real tour, private prompt or commercial details in synthetic smoke.
    script = ("Утро в старинном городе начинается с тихих улиц и первых шагов по площади. "
              "Каменные фасады встречают мягкий свет, а узкие переулки ведут к старым воротам. "
              "Здесь интересно рассматривать линии зданий и детали исторической архитектуры. "
              "Неспешная прогулка открывает новые виды на крыши и широкую городскую площадь. "
              "Затем внимание переключается на мост, старые стены и отражения в воде. "
              "Вечером город меняет настроение, фонари выделяют арки и теплые стены. "
              "Это придуманный образ путешествия, а не реклама реального тура. "
              "Пусть этот короткий фильм передаст атмосферу прогулки и смену впечатлений.")
    receipt = hashlib.sha256(b"SIMBA_RAF_REAL_IMAGE_SMOKE_V1").hexdigest()
    result = producer(drive_factory(), folder, "smoke-rafael", receipt, script, 1)
    result["smoke"] = True
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--dispatch-report", type=Path)
    parser.add_argument("--private-folder", default=FOLDER)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.execute:
            if args.smoke:
                print(json.dumps({"status": "DRY_RUN_NOT_EXECUTED"}))
            else:
                if not args.dispatch_report:
                    raise RafaelError("missing dispatch report")
                report = json.loads(args.dispatch_report.read_text())
                tasks = read_approved_tasks(args.root.resolve(), report)
                print(json.dumps({"status": "DRY_RUN_NOT_EXECUTED", "eligible": len(tasks)}))
            return 0
        if (os.getenv("GITHUB_REPOSITORY") != REPO or
                os.getenv("GITHUB_EVENT_NAME") != "push" or
                os.getenv("GITHUB_REF") != "refs/heads/main" or
                not os.getenv("SIMBA_RAF_PRIVATE_EXECUTE") == "true"):
            raise RafaelError("execution only in specifically gated trusted main workflow")
        if args.smoke:
            if os.getenv("SIMBA_RAF_SMOKE_APPROVED") != "true":
                raise RafaelError("synthetic image smoke requires explicit gate")
            result = smoke(args.private_folder)
        else:
            if not args.dispatch_report:
                raise RafaelError("missing verified dispatch report")
            report = json.loads(args.dispatch_report.read_text())
            result = run(args.root.resolve(), report, args.private_folder)
        print(json.dumps({"result": result, "paid_calls": 0, "publication": False},
                         ensure_ascii=False))
        return 0
    except (RafaelError, auto_script.AgentError, ValueError, KeyError, TypeError, OSError) as exc:
        print("SIMBA_RAFAEL_BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
