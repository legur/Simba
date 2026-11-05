#!/usr/bin/env python3
"""Upload ONE pinned Rafael Prague image directly to A2E storage, maximum 1 credit.

A2E charges API-token calls to /v1/r2/upload-presigned-url. This script
intentionally makes at most ONE such POST, after confirming live 1-credit
pricing and writing an irreversible GitHub journal marker. It NEVER submits
image-to-video generation. The result is a free new quote on the A2E CDN URL.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from github_a2e_issue_bridge import (
    request_quote, DEFAULT_NEGATIVE_PROMPT, validate_generation_body,
)

GITHUB_COMMENTS = "https://api.github.com/repos/legur/Simba/issues/8/comments"
SOURCE_IMAGE = (
    "https://static.wixstatic.com/media/"
    "7fd7b8_377e66bfa46b4a87a0223b02bec5d6f0~mv2.jpg"
)
JOURNAL_MARKER = "A2E_PRAGUE_UPLOAD_ONE_PRESIGN_INTENT_20261103"
TRIGGER_LABEL = "a2e-upload-one-max1"
MAX_FEE = 1.0
MAX_IMAGE_BYTES = 10 * 1024 * 1024

class UploadStopped(RuntimeError):
    pass


def api_get_pricing(key: str) -> float:
    req = Request("https://api.a2e.ai/v1/feature-pricing", method="GET",
                  headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            value = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise UploadStopped("Cannot verify current A2E R2 upload price") from None
    if not isinstance(value, dict) or value.get("code") != 0:
        raise UploadStopped("A2E pricing response invalid")
    data = value.get("data")
    price = (data.get("prices") or {}).get("r2") if isinstance(data, dict) else None
    fee = price.get("credits") if isinstance(price, dict) else None
    if type(fee) not in (int, float) or not (0 <= fee <= MAX_FEE):
        raise UploadStopped("Current R2 presign price exceeds 1-credit authorization")
    return float(fee)


def read_source_image() -> bytes:
    req = Request(SOURCE_IMAGE, headers={"Accept": "image/jpeg"}, method="GET")
    try:
        with urlopen(req, timeout=35) as res:
            if res.status != 200 or not res.headers.get("Content-Type", "").startswith("image/"):
                raise UploadStopped("Source image is not available as a JPEG")
            data = res.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise UploadStopped("Wix source image download failed") from None
    if not (1000 <= len(data) <= MAX_IMAGE_BYTES and data.startswith(bytes.fromhex("ffd8"))):
        raise UploadStopped("Source is not a valid-sized JPEG")
    return data


def gh_request(method: str, body: dict | None = None) -> object:
    token = os.environ.get("GH_TOKEN", "")
    if len(token) < 20:
        raise UploadStopped("GitHub journal token missing")
    req = Request(GITHUB_COMMENTS + ("?per_page=100" if method == "GET" else ""),
                  method=method,
                  data=json.dumps(body).encode("utf-8") if body else None,
                  headers={"Authorization": "Bearer " + token,
                           "Accept": "application/vnd.github+json",
                           "Content-Type": "application/json",
                           "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urlopen(req, timeout=25) as res:
            return json.load(res)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise UploadStopped("GitHub journal unavailable; no new upload permitted") from None


def claim_once(fee: float) -> None:
    comments = gh_request("GET")
    if not isinstance(comments, list) or len(comments) >= 100:
        raise UploadStopped("GitHub journal incomplete; stop before charge")
    if any(JOURNAL_MARKER in str(x.get("body", "")) for x in comments if isinstance(x, dict)):
        raise UploadStopped("This A2E staging upload was already attempted; no duplicate")
    receipt = gh_request("POST", {"body":
        JOURNAL_MARKER +
        "\n\nOwner requested a direct upload test for Prague scene 1. "
        "One presigned URL maximum; live R2 fee " + str(fee) +
        " credit(s), maximum 1. No paid video creation. "
        "No retry after an ambiguous POST, because presigning may charge."})
    if not isinstance(receipt, dict) or not receipt.get("id"):
        raise UploadStopped("Durable journal not acknowledged; upload blocked")


def valid_storage_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 4000:
        raise UploadStopped("A2E storage URL invalid")
    url = urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.hostname in {"localhost", "127.0.0.1", "::1"}
            or url.hostname.endswith(".local")):
        raise UploadStopped("A2E returned a non-public or insecure storage URL")
    return value


def charged_presign(key: str, count: int) -> tuple[str, str]:
    # This action costs A2E credits once a signed URL is issued.
    payload = {
        "key": "simba-prague-scene1-" + uuid.uuid4().hex + ".jpg",
        # Official A2E image-to-video documentation uses the 3days-apac
        # image bucket. Do not rely on a deployment-specific default.
        "bucket": "3days-apac",
        "contentType": "image/jpeg",
        "fileSize": count,
        "expiresIn": 300
    }
    req = Request(
        "https://api.a2e.ai/v1/r2/upload-presigned-url",
        method="POST", data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urlopen(req, timeout=35) as res:
            response = json.load(res)
    except HTTPError as ex:
        raise UploadStopped("A2E_PRESIGN_HTTP_" + str(ex.code) + "; no retry") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise UploadStopped("A2E presign outcome uncertain; do not retry") from None
    if not isinstance(response, dict) or response.get("code") != 0:
        raise UploadStopped("A2E presign not accepted; reconcile billing before retry")
    data = response.get("data")
    if not isinstance(data, dict):
        raise UploadStopped("A2E presign returned invalid data")
    return valid_storage_url(data.get("uploadUrl")), valid_storage_url(data.get("cdnUrl"))


def upload_bytes(upload_url: str, raw: bytes) -> None:
    # Signed URL authenticates PUT; NEVER attach A2E bearer token.
    req = Request(upload_url, method="PUT", data=raw,
                  headers={"Content-Type": "image/jpeg",
                           "Content-Length": str(len(raw))})
    try:
        with urlopen(req, timeout=90) as res:
            if res.status not in (200, 201, 204):
                raise UploadStopped("A2E storage upload returned non-success status")
            if res.geturl() != upload_url:
                raise UploadStopped("Signed storage PUT unexpectedly redirected")
    except HTTPError as ex:
        raise UploadStopped("A2E_STORAGE_PUT_HTTP_" + str(ex.code) + "; no presign retry") from None
    except (URLError, TimeoutError, OSError):
        raise UploadStopped("A2E storage PUT outcome uncertain; no presign retry") from None


def verify_staged_image(cdn_url: str) -> bool:
    for _ in range(3):
        req = Request(cdn_url, method="GET", headers={
            "Range": "bytes=0-1023",
            "User-Agent": "Genjutsu",  # Required by A2E/CDN support for outbound reads.
            "Accept": "image/jpeg",
        })
        try:
            with urlopen(req, timeout=20) as res:
                sample = res.read(1024)
                if res.status in (200, 206) and sample.startswith(bytes.fromhex("ffd8")):
                    return True
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    return False


def quote_uploaded(cdn_url: str, key: str) -> float | None:
    body = {
        "name": "Prague Charles Bridge",
        "image_url": cdn_url,
        "prompt": ("Slow cinematic dolly toward Charles Bridge, realistic winter snowfall, "
                   "gold reflections in the Vltava; preserve buildings; no text."),
        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        "model_version": "a2e", "video_time": 5,
        "auto_add_audio": False, "number_of_images": 1
    }
    try:
        validate_generation_body(body)
        response = request_quote(body, key)
        data = response.get("data") if isinstance(response, dict) else None
        price = data.get("coins") if isinstance(data, dict) else None
        if (response.get("code") == 0 and isinstance(data, dict)
                and data.get("available") is True and data.get("exact") is True
                and type(price) in (float, int) and 0 <= price <= 30):
            return float(price)
    except Exception:
        pass
    return None


def run(event: dict, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    state = {"status": "NOT_STARTED", "presign_max_credits": 1,
             "generation_started": False, "cdn_url": None,
             "quoted_video_credits": None, "note": ""}
    def persist() -> None:
        (folder / "upload_status.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        issue = event.get("issue") or {}
        if (event.get("action") != "labeled"
                or (event.get("label") or {}).get("name") != TRIGGER_LABEL
                or issue.get("number") != 8
                or (issue.get("user") or {}).get("login") != "legur"
                or (event.get("repository") or {}).get("full_name") not in (None, "legur/Simba")):
            raise UploadStopped("Unapproved event; no upload")
        key = os.environ.get("A2E_API_KEY", "")
        if not key.startswith("sk_") or len(key) < 15:
            raise UploadStopped("GitHub A2E_API_KEY missing")
        fee = api_get_pricing(key)
        raw = read_source_image()
        state["source_bytes"] = len(raw)
        state["presign_fee_credits"] = fee
        state["status"] = "PRECHECK_PASSED"
        persist()
        claim_once(fee)  # Durable journal BEFORE any chargeable presign.
        state["status"] = "PRESIGN_SUBMISSION_ATTEMPTED"
        persist()
        signed_url, cdn_url = charged_presign(key, len(raw))
        state["cdn_url"] = cdn_url
        state["status"] = "PRESIGN_ISSUED_POSSIBLE_ONE_CREDIT_CHARGE"
        persist()
        upload_bytes(signed_url, raw)
        state["status"] = "BYTES_UPLOADED"
        persist()
        if not verify_staged_image(cdn_url):
            raise UploadStopped("Image PUT succeeded but staged CDN GET not verified")
        state["status"] = "A2E_CDN_VERIFIED"
        persist()
        quoted = quote_uploaded(cdn_url, key)
        state["quoted_video_credits"] = quoted
        state["status"] = "IMAGE_UPLOADED_AND_VIDEO_QUOTED" if quoted is not None else "IMAGE_UPLOADED_QUOTE_UNAVAILABLE"
        persist()
    except UploadStopped as ex:
        state["note"] = str(ex)
        state["status"] = "STOPPED"
        persist()
    report = [
        "### Simba / A2E — прямой тест загрузки кадра Праги",
        "",
        "**Статус:** " + state["status"],
        "**Стоимость presign:** " + str(state.get("presign_fee_credits", "неизвестно")) + " кредита",
        "**Байт исходного JPEG:** " + str(state.get("source_bytes", "не загружен")),
        "**Ссылка на A2E CDN:** " + (state["cdn_url"] or "отсутствует"),
        "**Цена одного 5-секундного ролика:** " +
            (str(state["quoted_video_credits"]) + " кредитов" if state["quoted_video_credits"] is not None else "не подтверждена"),
        "**Видео запущено:** нет",
        "**Примечание:** " + state["note"],
        "",
        "Presign запрос может списать 1 кредит даже при неудачном PUT.",
        "Не запускать платную генерацию до нового согласованного общего бюджета.",
    ]
    (folder / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(state["status"])
    return state


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args=parser.parse_args()
    event=json.loads(args.event.read_text(encoding="utf-8"))
    result=run(event, args.out)
    return 0 if result["status"] == "IMAGE_UPLOADED_AND_VIDEO_QUOTED" else 2

if __name__ == "__main__":
    raise SystemExit(main())
