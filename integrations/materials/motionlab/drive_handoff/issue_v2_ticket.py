#!/usr/bin/env python3
"""Issue source-pinned, single-use owner-private Studio v2 ticket.

The trusted canonical v2 worker (NOT the browser) must have already checked
the real approved A2E video bytes and unattended audio QA and saved this
private owner-launch/v2 (materials, proposals, verified private previews).
This issuer validates current Python contracts and private Drive metadata
without starting A2E/TTS or a renderer. No token in CLI/stdout/logs.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import secrets
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
VIDEO=HERE.parents[2]/"video"
for folder in (str(VIDEO),str(HERE)):
    if folder not in sys.path:
        sys.path.insert(0,folder)
import motionlab_v2_contract as contract
import issue_ticket as original

LAUNCH_SCHEMA="bontours.motionlab.owner-launch/v2"
TICKET_SCHEMA="bontours.motionlab.drive-ticket/v2"
SAFE=re.compile(r"^[A-Za-z0-9_-]{15,100}$")


def valid_source(source):
    if not isinstance(source,dict) or source.get("schema")!=LAUNCH_SCHEMA:
        raise original.TicketError("V2_INVALID_OWNER_LAUNCH")
    materials,proposals=source.get("materials"),source.get("proposals")
    if not isinstance(materials,dict) or not isinstance(proposals,dict):
        raise original.TicketError("V2_MATERIALS_OR_PROPOSALS_MISSING")
    if (materials.get("audio_alignment_status")!="AUDIO_ALIGNMENT_VERIFIED_AUTO"
            or source.get("project_id")!=materials.get("project_id")
            or source.get("request_id")!=materials.get("request_id")
            or source.get("expected_input_fingerprint")!=materials.get("expected_input_fingerprint")):
        raise original.TicketError("V2_AUTO_QA_OR_SOURCE_MISMATCH")
    try:
        contract.validate_proposals_v2(materials,proposals)
    except Exception:
        raise original.TicketError("V2_PROPOSALS_INVALID") from None
    if proposals.get("analysis",{}).get("status")!="REAL_VIDEO_AUTOMATICALLY_ANALYZED":
        raise original.TicketError("V2_SOURCE_NOT_AUTOMATICALLY_ANALYZED")
    previews=source.get("preview_assets")
    if not isinstance(previews,list) or len(previews)!=len(materials["scenes"]):
        raise original.TicketError("V2_PREVIEW_MANIFEST_INCOMPLETE")
    ids=set()
    total=0
    for asset,scene in zip(previews,materials["scenes"]):
        if (not isinstance(asset,dict) or asset.get("asset_id")!=scene["asset_id"]
                or asset.get("sha256")!=scene["media"]["asset_sha256"]
                or not SAFE.fullmatch(asset.get("file_id",""))
                or asset.get("mime_type")!="video/mp4"
                or type(asset.get("size_bytes")) is not int
                or not 1024<=asset["size_bytes"]<=20*1024*1024
                or asset["asset_id"] in ids):
            raise original.TicketError("V2_PREVIEW_ASSET_INVALID")
        ids.add(asset["asset_id"])
        total+=asset["size_bytes"]
    if total>120*1024*1024:
        raise original.TicketError("V2_PREVIEW_ASSETS_TOO_LARGE")
    return source


def read_source(svc,file_id):
    if not SAFE.fullmatch(file_id):
        raise original.TicketError("V2_LAUNCH_FILE_ID_INVALID")
    try:
        meta=svc.files().get(fileId=file_id,fields="id,name,mimeType,parents,trashed,size").execute()
        if (meta.get("trashed") or meta.get("parents")!=[original.LAUNCH_DIR]
                or int(meta.get("size") or 0)>300000):
            raise original.TicketError("V2_LAUNCH_NOT_PRIVATE_APPROVED")
        raw=svc.files().get_media(fileId=file_id).execute()
        if not isinstance(raw,bytes) or len(raw)>300000:
            raise original.TicketError("V2_LAUNCH_TOO_LARGE")
        source=valid_source(json.loads(raw.decode("utf-8")))
        for a in source["preview_assets"]:
            info=svc.files().get(fileId=a["file_id"],
                fields="id,mimeType,parents,trashed,size").execute()
            if (info.get("trashed")
                or info.get("parents")!=["1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"]
                or info.get("mimeType")!="video/mp4"
                or int(info.get("size") or 0)!=a["size_bytes"]):
                raise original.TicketError("V2_PREVIEW_NOT_PRIVATE_APPROVED")
        return source,raw
    except original.TicketError:
        raise
    except Exception:
        raise original.TicketError("V2_LAUNCH_READ_FAILED") from None


def issue(svc,source_file_id,now=None):
    source,raw=read_source(svc,source_file_id)
    now=now or dt.datetime.now(dt.timezone.utc)
    expires=now+dt.timedelta(hours=3)
    token=secrets.token_hex(32)
    mats=source["materials"]
    props=source["proposals"]
    ticket={
        "schema":TICKET_SCHEMA,"state":"ISSUED",
        "project_id":source["project_id"],
        "session_id":source["request_id"],
        "source_fingerprint":source["expected_input_fingerprint"],
        "materials_sha256":contract.digest(mats),
        "proposals_sha256":contract.digest(props),
        "token_sha256":hashlib.sha256(token.encode("ascii")).hexdigest(),
        "issued_utc":now.isoformat().replace("+00:00","Z"),
        "expires_utc":expires.isoformat().replace("+00:00","Z"),
        "source_launch_file_id":source_file_id,
        "source_launch_sha256":hashlib.sha256(raw).hexdigest(),
    }
    ticket_id=original.upload(svc,original.TICKET_DIR,
       "motionlab-v2-"+source["request_id"]+"-ticket.json",ticket)
    capability={
        "schema":"bontours.motionlab.drive-handoff/v2",
        "ticket_id":ticket_id,"ticket_token":token
    }
    # Secret capability stays only in the owner-private file. The HTTP link
    # can be constructed by owner tooling from its fragment, never logged.
    authorized_id=original.upload(svc,original.LAUNCH_DIR,
       "motionlab-v2-"+source["request_id"]+"-authorized-launch.json",
       {"schema":LAUNCH_SCHEMA,"project_id":source["project_id"],
        "request_id":source["request_id"],"handoff":capability})
    return {"issued":True,"ticket_file_id":ticket_id,
            "authorized_launch_file_id":authorized_id,
            "ticket_expires_utc":ticket["expires_utc"],
            "materials_sha256":ticket["materials_sha256"],
            "proposals_sha256":ticket["proposals_sha256"]}


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--owner-v2-launch-file-id",required=True)
    args=parser.parse_args()
    try:
        result=issue(original.drive(),args.owner_v2_launch_file_id)
        print(json.dumps(result,sort_keys=True))
        return 0
    except original.TicketError as exc:
        print("MOTIONLAB_V2_ISSUER_ERROR:",str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
