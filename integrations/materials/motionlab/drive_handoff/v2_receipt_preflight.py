"""Trust boundary: owner-private v2 Drive inbox -> canonical source replay.

No operations are inferred from a browser ACK: this module authenticates the
actual durable receipt, consumed ticket, exact original private launch bytes,
and source-pinned 3-option owner selection BEFORE any GitHub CAS or media work.

It does not run A2E, TTS, a renderer, publish, create GitHub issues or edit
the canonical project. Public/domain Drive ACL, arbitrary caller file paths,
synthetic unapproved choices and stale owner selection fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
for folder in (str(HERE),str(HERE.parents[2]),str(HERE.parents[2]/"video")):
    if folder not in sys.path:
        sys.path.insert(0,folder)

import motionlab_v2_contract as v2
import issue_v2_ticket as issuer
import issue_ticket

INBOX="1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD"
TICKETS=issue_ticket.TICKET_DIR
LAUNCHES=issue_ticket.LAUNCH_DIR
APPLIED="1Ya87Y6FUUmstpSs8jG0mKvEVLRqTvwxH"
IDENTIFIER=re.compile(r"^[A-Za-z0-9_-]{15,100}$")
UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA=re.compile(r"^[a-f0-9]{64}$")
MAX_RECEIPT=140_000
MAX_TICKET=16_000
MAX_LAUNCH=300_000


class V2InboxError(ValueError):
    pass


def guard(ok,reason):
    if not ok: raise V2InboxError(reason)


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def _datetime(value,code):
    try:
        time=datetime.fromisoformat(value.replace("Z","+00:00"))
        if time.tzinfo is None: raise ValueError
        return time.astimezone(timezone.utc)
    except (AttributeError,TypeError,ValueError):
        raise V2InboxError(code) from None


def secure_private_bytes(svc,file_id,folder,limit,*,mime=None,filename=None):
    """Read exact ID in exact owner folder with explicit owner-only ACL."""
    guard(isinstance(file_id,str) and IDENTIFIER.fullmatch(file_id),
          "V2_PRIVATE_FILE_ID_INVALID")
    try:
        meta=svc.files().get(fileId=file_id,
               fields="id,name,parents,trashed,mimeType,size,md5Checksum").execute()
        guard(meta.get("id",file_id)==file_id and not meta.get("trashed")
              and meta.get("parents")==[folder]
              and isinstance(meta.get("size"),(str,int))
              and 2<=int(meta["size"])<=limit,
              "V2_PRIVATE_FILE_OUTSIDE_FOLDER_OR_LIMIT")
        if mime:guard(meta.get("mimeType") in mime,"V2_PRIVATE_FILE_TYPE_MISMATCH")
        if filename:guard(meta.get("name")==filename,"V2_PRIVATE_FILE_NAME_MISMATCH")
        perms=svc.permissions().list(fileId=file_id,
             fields="nextPageToken,permissions(type,role)",pageSize=100).execute()
        guard(not perms.get("nextPageToken")
              and isinstance(perms.get("permissions"),list)
              and bool(perms["permissions"])
              and all(p.get("type")=="user" for p in perms["permissions"]),
              "V2_PRIVATE_FILE_ACL_UNTRUSTED")
        raw=svc.files().get_media(fileId=file_id).execute()
        guard(isinstance(raw,bytes) and len(raw)==int(meta["size"]),
              "V2_PRIVATE_FILE_BYTES_CHANGED")
        if meta.get("md5Checksum"):
            guard(hashlib.md5(raw).hexdigest()==meta["md5Checksum"],
                  "V2_PRIVATE_FILE_BYTES_CHANGED")
        return raw
    except V2InboxError:
        raise
    except Exception:
        raise V2InboxError("V2_PRIVATE_FILE_UNAVAILABLE") from None


def parse_json(raw,reason):
    try:
        obj=json.loads(raw.decode("utf-8"))
        guard(isinstance(obj,dict),reason)
        return obj
    except (UnicodeError,ValueError):
        raise V2InboxError(reason) from None


def inspect_receipt(svc,receipt_file_id,*,now=None):
    """Verify actual owner selection without requiring bearer token in worker.

    At ingestion GAS already authenticated the short-lived capability;
    trusted worker uses its consumed ticket+immutable private inbox evidence,
    and does NOT retrieve/store the user's secret fragment.
    """
    now=now or datetime.now(timezone.utc)
    raw=secure_private_bytes(svc,receipt_file_id,INBOX,MAX_RECEIPT,
                             mime={"text/plain","application/json"})
    row=parse_json(raw,"V2_PRIVATE_RECEIPT_INVALID")
    receipt=row.get("receipt_id")
    ticket_id=row.get("ticket_id")
    guard(row.get("schema")=="bontours.motionlab.drive-inbox/v2"
          and row.get("status")=="V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS"
          and row.get("canonical_applied") is False
          and row.get("render_authorized") is False
          and row.get("paid_operations_authorized") is False
          and row.get("published") is False
          and isinstance(receipt,str) and UUID.fullmatch(receipt)
          and isinstance(ticket_id,str) and IDENTIFIER.fullmatch(ticket_id),
          "V2_RECEIPT_NOT_PENDING_CANONICAL_CAS")
    # Inspect name separately after we know the claimed ticket.
    secure_private_bytes(svc,receipt_file_id,INBOX,MAX_RECEIPT,
         filename="motionlab-v2-"+ticket_id+".json",
         mime={"text/plain","application/json"})
    ticket_raw=secure_private_bytes(svc,ticket_id,TICKETS,MAX_TICKET,
            mime={"application/json","text/plain"})
    ticket=parse_json(ticket_raw,"V2_CONSUMED_TICKET_INVALID")
    guard(ticket.get("schema")==issuer.TICKET_SCHEMA
          and ticket.get("state")=="ISSUED"
          and ticket.get("consumed_receipt_id")==receipt
          and ticket.get("consumed_sha256")==row.get("selection_sha256")
          and isinstance(ticket.get("token_sha256"),str)
          and SHA.fullmatch(ticket["token_sha256"])
          and isinstance(ticket.get("source_launch_sha256"),str)
          and SHA.fullmatch(ticket["source_launch_sha256"])
          and ticket.get("project_id")==row.get("project_id")
          and ticket.get("session_id")==row.get("session_id")
          and ticket.get("source_fingerprint")==row.get("source_fingerprint")
          and ticket.get("materials_sha256")==row.get("materials_sha256")
          and ticket.get("proposals_sha256")==row.get("proposals_sha256")
          and row.get("source_launch_sha256")==ticket.get("source_launch_sha256"),
          "V2_CONSUMED_TICKET_MISMATCH")
    issued=_datetime(ticket.get("issued_utc"),"V2_TICKET_TIME_INVALID")
    expires=_datetime(ticket.get("expires_utc"),"V2_TICKET_TIME_INVALID")
    consumed=_datetime(ticket.get("consumed_utc"),"V2_TICKET_TIME_INVALID")
    saved=_datetime(row.get("saved_utc"),"V2_RECEIPT_TIME_INVALID")
    guard(issued<=expires<=issued+timedelta(hours=4)
          and issued-timedelta(minutes=1)<=consumed<=expires+timedelta(minutes=1)
          and saved==consumed and saved<=now+timedelta(minutes=5)
          and now-saved<=timedelta(days=7),
          "V2_TICKET_USE_TIME_INVALID")
    launch_raw=secure_private_bytes(svc,ticket.get("source_launch_file_id"),
                       LAUNCHES,MAX_LAUNCH,mime={"application/json","text/plain"})
    guard(digest(launch_raw)==ticket["source_launch_sha256"],
          "V2_OWNER_LAUNCH_SHA_CHANGED")
    launch=parse_json(launch_raw,"V2_OWNER_LAUNCH_INVALID")
    try:
        issuer.valid_source(launch)
    except (issuer.original.TicketError,TypeError,KeyError,ValueError):
        raise V2InboxError("V2_OWNER_LAUNCH_CONTRACT_INVALID") from None
    mats=launch["materials"]
    props=launch["proposals"]
    guard(launch["project_id"]==row["project_id"]
          and launch["request_id"]==row["session_id"]
          and launch["expected_input_fingerprint"]==row["source_fingerprint"]
          and v2.digest(mats)==ticket["materials_sha256"]
          and v2.digest(props)==ticket["proposals_sha256"],
          "V2_OWNER_SOURCE_FINGERPRINT_MISMATCH")
    selection=row.get("selection")
    guard(isinstance(selection,dict)
          and isinstance(row.get("selection_sha256"),str)
          and SHA.fullmatch(row["selection_sha256"])
          and digest(canonical(selection))==row["selection_sha256"]
          and selection.get("project_id")==row["project_id"]
          and selection.get("request_id")==row["session_id"],
          "V2_SELECTION_SHA_OR_ID_MISMATCH")
    try:
        report=v2.validate_selection_v2(mats,props,selection)
    except (ValueError,TypeError,KeyError):
        raise V2InboxError("V2_OWNER_SELECTION_CONTRACT_INVALID") from None
    guard(report.get("status")=="V2_SELECTION_VALIDATED_NOT_WRITTEN"
          and report.get("receipt_id")=="motionlab:v2:"+row["selection_sha256"]
          and report.get("render_authorized") is False,
          "V2_OWNER_SELECTION_CONTRACT_INVALID")
    decision_time=_datetime(selection["decision"].get("user_selected_at"),
                            "V2_OWNER_DECISION_TIME_INVALID")
    guard(issued-timedelta(minutes=1)<=decision_time<=saved+timedelta(minutes=5),
          "V2_OWNER_DECISION_TIME_INVALID")
    return {
        "receipt_file_id":receipt_file_id,
        "receipt_id":receipt,
        "ticket_file_id":ticket_id,
        "source_launch_file_id":ticket["source_launch_file_id"],
        "source_launch_sha256":ticket["source_launch_sha256"],
        "project_id":ticket["project_id"],
        "request_id":ticket["session_id"],
        "materials":mats,
        "proposals":props,
        "selection":selection,
        "selection_sha256":row["selection_sha256"],
        "selection_contract_receipt_id":report["receipt_id"],
        "status":"V2_RECEIPT_AUTHENTICATED_PENDING_SOURCE_REPLAY",
        "render_authorized":False,
        "publication_authorized":False,
    }


def replay_private_canonical(workspace_root,private_root,bundle):
    """Re-run actual private WAV/MP4 verification before canonical CAS.

    No fallback to a raw Drive receipt or to a self-attested pixel report.
    """
    import motionlab_v2_stage_writeback as stage
    try:
        context,spec,report=stage.check_current_v2(
            Path(workspace_root),Path(private_root),bundle["project_id"],
            bundle["materials"],bundle["proposals"],bundle["selection"])
    except (ValueError,KeyError,TypeError,OSError):
        raise V2InboxError("V2_CANONICAL_SOURCE_OR_AUDIO_REPLAY_FAILED") from None
    guard(report is not None
          and report.get("status")=="V2_VIDEO_SPEC_MAPPED_NOT_RENDERED"
          and report.get("receipt_id")==bundle["selection_contract_receipt_id"]
          and report.get("render_authorized") is False
          and spec.get("packageId")==bundle["project_id"],
          "V2_CANONICAL_SPEC_REPLAY_FAILED")
    return context,spec,report
