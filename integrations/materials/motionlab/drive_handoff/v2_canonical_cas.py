"""Atomic canonical Simba project writeback after authenticated Studio v2.

This is a library for a TRUSTED, owner-run private worker, NOT an anonymous
web endpoint or v1 render route. The caller must first authenticate the
owner-private Drive receipt with v2_receipt_preflight.inspect_receipt(),
then independently replay approved WAV and each MP4 from private files.

The only GitHub mutation is a narrow Contents API CAS for ONE canonical
campaigns/<project>/project.json at an exact pre-verified blob SHA, on main.
Private Drive stage references are written/read-back BEFORE the CAS; private
ack AFTER. A receipt alone never means APPLIED. No TTS/A2E/render/publish.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError,URLError

HERE=Path(__file__).resolve().parent
for folder in (str(HERE),str(HERE.parents[1]),str(HERE.parents[2]),str(HERE.parents[2]/"video")):
    if folder not in sys.path: sys.path.insert(0,folder)

import motionlab_v2_contract as v2
import motionlab_v2_stage_writeback as stage
import v2_receipt_preflight as intake

REPO="legur/Simba"
BRANCH="main"
SHA=intake.SHA
UUID=intake.UUID
DRIVE=intake.IDENTIFIER
MAX_JSON=300_000
APPLIED=intake.APPLIED


class V2CasError(ValueError):
    pass


def ensure(ok,code):
    if not ok: raise V2CasError(code)


def _bytes(value):
    try:return intake.canonical(value)
    except (ValueError,TypeError,OverflowError):
        raise V2CasError("V2_PRIVATE_EVIDENCE_JSON_INVALID") from None


def _private_name(bundle,kind):
    ensure(kind in {"materials","proposals","selection-v2","video-spec"},
           "V2_UNKNOWN_EVIDENCE_KIND")
    ensure(UUID.fullmatch(bundle["receipt_id"]),"V2_RECEIPT_ID_INVALID")
    return "motionlab-v2-"+bundle["receipt_id"]+"-"+kind+".json"


def require_private_folder(svc,folder):
    try:
        info=svc.files().get(fileId=folder,
            fields="id,mimeType,trashed").execute()
        perms=svc.permissions().list(fileId=folder,
            fields="nextPageToken,permissions(type,role)",pageSize=100).execute()
    except Exception:
        raise V2CasError("V2_PRIVATE_EVIDENCE_FOLDER_UNAVAILABLE") from None
    ensure(info.get("id",folder)==folder
           and info.get("mimeType")=="application/vnd.google-apps.folder"
           and not info.get("trashed")
           and not perms.get("nextPageToken")
           and isinstance(perms.get("permissions"),list)
           and bool(perms["permissions"])
           and all(p.get("type")=="user" for p in perms["permissions"]),
           "V2_PRIVATE_EVIDENCE_FOLDER_NOT_PRIVATE")


def store_private_json(svc,bundle,kind,obj):
    """Idempotent stage: name+exact bytes, no overwrite on collision."""
    raw=_bytes(obj)
    ensure(2<=len(raw)<=MAX_JSON,"V2_EVIDENCE_TOO_LARGE")
    name=_private_name(bundle,kind)
    escaped=name.replace("\\","\\\\").replace("'","\\'")
    try:
        found=svc.files().list(q=f"'{APPLIED}' in parents and name = '{escaped}' and trashed = false",
          pageSize=100,fields="nextPageToken,files(id,name,mimeType,size,parents)").execute()
    except Exception:
        raise V2CasError("V2_PRIVATE_EVIDENCE_LIST_FAILED") from None
    items=found.get("files") or []
    ensure(not found.get("nextPageToken") and len(items)<=1,
           "V2_PRIVATE_EVIDENCE_DUPLICATE_NAME")
    if items:
        file_id=items[0].get("id")
    else:
        try:
            from googleapiclient.http import MediaIoBaseUpload
            body={"name":name,"mimeType":"application/json","parents":[APPLIED]}
            uploaded=svc.files().create(
                body=body,
                media_body=MediaIoBaseUpload(io.BytesIO(raw),
                    mimetype="application/json",resumable=False),
                fields="id,name,mimeType,size,parents").execute()
            file_id=uploaded["id"]
        except Exception:
            raise V2CasError("V2_PRIVATE_EVIDENCE_WRITE_FAILED") from None
    actual=intake.secure_private_bytes(svc,file_id,APPLIED,MAX_JSON,
                mime={"application/json"},filename=name)
    ensure(actual==raw,"V2_PRIVATE_EVIDENCE_COLLISION")
    return {"id":file_id,"sha256":hashlib.sha256(raw).hexdigest()}


def stage_all_private_references(svc,bundle,spec):
    """Copies only private approved data after full source/audio/video replay."""
    ensure(bundle.get("status")=="V2_RECEIPT_AUTHENTICATED_PENDING_SOURCE_REPLAY",
           "V2_UNAUTHENTICATED_SELECTION_FORBIDDEN")
    ensure(bundle["selection_sha256"]==v2.digest(bundle["selection"]),
           "V2_SELECTION_CHANGED")
    require_private_folder(svc,APPLIED)
    record={
        "materials":bundle["materials"],
        "proposals":bundle["proposals"],
        "selection-v2":bundle["selection"],
        "video-spec":spec,
    }
    refs={}
    for key,value in record.items():
        refs[key]=store_private_json(svc,bundle,key,value)
    ensure(len({r["id"] for r in refs.values()})==4,
           "V2_EVIDENCE_FILE_IDS_NOT_DISTINCT")
    ensure(refs["materials"]["sha256"]==v2.digest(bundle["materials"])
           and refs["proposals"]["sha256"]==v2.digest(bundle["proposals"])
           and refs["selection-v2"]["sha256"]==bundle["selection_sha256"],
           "V2_EVIDENCE_SHA_CHANGED")
    return refs


def prepare_canonical_candidate(workspace_root,private_root,bundle,refs):
    """Does NOT write GitHub. Replays source twice through canonical gate."""
    _,spec,report=intake.replay_private_canonical(workspace_root,private_root,bundle)
    ensure(refs["video-spec"]["sha256"]==v2.digest(spec),
           "V2_PREPARED_SPEC_CHANGED")
    try:
        candidate,outcome=stage.build_candidate_v2(
            Path(workspace_root),Path(private_root),bundle["project_id"],
            bundle["materials"],bundle["proposals"],bundle["selection"],
            spec,refs,bundle["selection_contract_receipt_id"])
    except (ValueError,KeyError,TypeError,OSError):
        raise V2CasError("V2_CANONICAL_CANDIDATE_REJECTED") from None
    ensure(outcome.get("status")=="MOTIONLAB_V2_EDIT_APPROVED_NOT_RENDERED"
           and outcome.get("project_written") is False
           and outcome.get("render_started") is False
           and outcome.get("publication_authorized") is False,
           "V2_CANONICAL_CANDIDATE_NOT_SAFE")
    return candidate,outcome


def project_path(project_id):
    ensure(isinstance(project_id,str)
           and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}",project_id),
           "V2_CANONICAL_PROJECT_ID_INVALID")
    return "campaigns/"+project_id+"/project.json"


def github_blob_sha(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def _github(method,path,token,payload=None):
    ensure(isinstance(token,str) and len(token)>25,"V2_GITHUB_TOKEN_MISSING")
    url="https://api.github.com/repos/"+REPO+path
    data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    request=Request(url,data=data,method=method,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json",
        "User-Agent":"simba-studio-v2-cas/1",
    })
    try:
        with urlopen(request,timeout=35) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        if exc.code in (409,412,422):
            raise V2CasError("V2_CANONICAL_CAS_CONFLICT") from None
        raise V2CasError("V2_GITHUB_API_UNAVAILABLE") from None
    except (URLError,TimeoutError,OSError,ValueError):
        raise V2CasError("V2_GITHUB_API_UNAVAILABLE") from None


def get_github_canonical(project_id,token):
    path=project_path(project_id)
    item=_github("GET","/contents/"+path+"?ref=main",token)
    ensure(item.get("type")=="file" and item.get("path")==path
           and item.get("encoding")=="base64"
           and isinstance(item.get("sha"),str)
           and re.fullmatch(r"[0-9a-f]{40}",item["sha"]),
           "V2_GITHUB_CANONICAL_UNREADABLE")
    try: raw=base64.b64decode(item["content"],validate=False)
    except (ValueError,KeyError,TypeError):
        raise V2CasError("V2_GITHUB_CANONICAL_UNREADABLE") from None
    ensure(github_blob_sha(raw)==item["sha"],
           "V2_GITHUB_SOURCE_SHA_INCONSISTENT")
    return item["sha"],raw


def github_cas_canonical(project_id,old_sha,original,candidate,token,*,apply=False):
    """GitHub Contents API updates one file only if the base blob is exact.

    When apply=False, this has NO writes and never calls PUT.
    """
    path=project_path(project_id)
    ensure(isinstance(old_sha,str) and re.fullmatch(r"[0-9a-f]{40}",old_sha)
           and isinstance(original,bytes) and github_blob_sha(original)==old_sha,
           "V2_CANONICAL_BASE_SHA_MISMATCH")
    try:
        old=json.loads(original.decode("utf-8"))
        ensure(isinstance(old,dict) and old.get("id")==project_id
               and "edit_choice" not in old.get("stage_handoffs",{}),
               "V2_CANONICAL_NOT_READY_FOR_EDIT")
        ensure(candidate.get("id")==project_id
               and candidate.get("stage")=="EDIT_CHOICE_V2_RECORDED_AWAITING_PRIVATE_MONTAGE_PLAN"
               and candidate.get("stage_handoffs",{}).get("edit_choice",{}).get("render_authorized") is False
               and candidate["stage_handoffs"]["edit_choice"].get("no_auto_publish") is True
               and candidate.get("approvals")==old.get("approvals")
               and candidate.get("approved_asset_id")==old.get("approved_asset_id"),
               "V2_UNSAFE_CANONICAL_CANDIDATE")
        ensure(candidate.get("stage_handoffs",{}).get("voice_music")==
               old.get("stage_handoffs",{}).get("voice_music"),
               "V2_APPROVED_AUDIO_LOCK_CHANGED")
    except (KeyError,TypeError,UnicodeError,ValueError):
        raise V2CasError("V2_UNSAFE_CANONICAL_CANDIDATE") from None
    raw=(json.dumps(candidate,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    ensure(100<=len(raw)<=1_000_000,"V2_CANONICAL_SIZE_INVALID")
    result={
        "status":"V2_CANONICAL_CAS_VALIDATED_NO_WRITE",
        "project_id":project_id,
        "base_blob_sha":old_sha,
        "candidate_sha256":hashlib.sha256(raw).hexdigest(),
        "canonical_path":path,
        "render_authorized":False,"publication_authorized":False,
    }
    if not apply:return result
    # Standard REST /contents update enforces atomic expected SHA.
    response=_github("PUT","/contents/"+path,token,{
        "message":"feat(studio): record owner-approved MotionLab v2 edit plan (NO RENDER)",
        "content":base64.b64encode(raw).decode("ascii"),
        "sha":old_sha,"branch":BRANCH,
    })
    new=response.get("content") or {}
    commit=response.get("commit") or {}
    ensure(new.get("sha")==github_blob_sha(raw)
           and isinstance(commit.get("sha"),str)
           and re.fullmatch(r"[0-9a-f]{40}",commit["sha"]),
           "V2_CANONICAL_CAS_OUTCOME_AMBIGUOUS_CHECK_GITHUB")
    return {**result,
        "status":"V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER",
        "commit_sha":commit["sha"],"new_blob_sha":new["sha"]}


def github_cas_from_checked_workspace(root,bundle,candidate,token,*,apply=False):
    """Compare exact local repo bytes with fresh GitHub main before any PUT."""
    path=project_path(bundle["project_id"])
    local=Path(root).resolve()/path
    ensure(not local.is_symlink() and local.is_file(),
           "V2_LOCAL_CANONICAL_UNAVAILABLE")
    try: local_raw=local.read_bytes()
    except OSError:
        raise V2CasError("V2_LOCAL_CANONICAL_UNAVAILABLE") from None
    remote_sha,remote_raw=get_github_canonical(bundle["project_id"],token)
    ensure(local_raw==remote_raw,"V2_GITHUB_MAIN_CHANGED_SINCE_SOURCE_REPLAY")
    return github_cas_canonical(bundle["project_id"],remote_sha,remote_raw,
                                candidate,token,apply=apply)


def finish_applied_ack(svc,bundle,commit_result,refs):
    """Post-CAS only. On failure, recovery MUST inspect GitHub before retry."""
    ensure(commit_result.get("status")=="V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER"
          and isinstance(commit_result.get("commit_sha"),str),
          "V2_CAS_NOT_APPLIED_CANNOT_ACK")
    receipt={
        "schema":"bontours.motionlab.v2-canonical-applied/v1",
        "status":"V2_EDIT_CHOICE_CANONICALLY_APPLIED_AWAITING_MONTAGE_PLAN",
        "project_id":bundle["project_id"],
        "receipt_id":bundle["receipt_id"],
        "selection_sha256":bundle["selection_sha256"],
        "owner_selection_contract_receipt":bundle["selection_contract_receipt_id"],
        "commit_sha":commit_result["commit_sha"],
        "new_blob_sha":commit_result["new_blob_sha"],
        "candidate_sha256":commit_result["candidate_sha256"],
        "private_references":refs,
        "render_authorized":False,
        "published":False,
        "paid_calls":0,
    }
    require_private_folder(svc,APPLIED)
    ref=store_applied_ack(svc,bundle,receipt)
    return {**receipt,"private_ack_file_id":ref["id"]}


def store_applied_ack(svc,bundle,receipt):
    """Same idempotent write/readback as spec evidence, distinct ack filename."""
    # The helper writes an allowlisted kind, and its name includes the UUID.
    mirror={**bundle}
    mirror["receipt_id"]=bundle["receipt_id"]
    # use a separate kind through a dedicated guarded small upload path
    name="motionlab-v2-"+mirror["receipt_id"]+"-canonical-applied.json"
    raw=_bytes(receipt)
    ensure(100<=len(raw)<=MAX_JSON,"V2_APPLIED_ACK_TOO_LARGE")
    escaped=name.replace("\\","\\\\").replace("'","\\'")
    try:
        result=svc.files().list(q=f"'{APPLIED}' in parents and name = '{escaped}' and trashed = false",
               fields="nextPageToken,files(id,name,parents,size,mimeType)",pageSize=100).execute()
        found=result.get("files") or []
        ensure(len(found)<=1 and not result.get("nextPageToken"),"V2_APPLIED_ACK_DUPLICATE")
        if found:
            file_id=found[0]["id"]
        else:
            from googleapiclient.http import MediaIoBaseUpload
            file=svc.files().create(body={"name":name,"parents":[APPLIED],
                     "mimeType":"application/json"},
                     media_body=MediaIoBaseUpload(io.BytesIO(raw),
                         mimetype="application/json",resumable=False),
                     fields="id").execute()
            file_id=file["id"]
    except V2CasError:
        raise
    except Exception:
        raise V2CasError("V2_CAS_COMMITTED_ACK_PENDING") from None
    actual=intake.secure_private_bytes(svc,file_id,APPLIED,MAX_JSON,
                          mime={"application/json"},filename=name)
    ensure(actual==raw,"V2_APPLIED_ACK_COLLISION_AFTER_COMMIT")
    return {"id":file_id,"sha256":hashlib.sha256(raw).hexdigest()}


def process_owner_v2_receipt(svc,workspace_root,private_root,
                             receipt_file_id,github_token="",*,apply=False):
    """Trust-gated handoff: Drive receipt -> real media replay -> optional CAS.

    Default NO WRITE. The apply path is callable ONLY by a trusted private
    owner worker with pre-provisioned private original MP4/WAV, offline ASR
    models and a narrowly scoped GitHub contents-write token.
    """
    bundle=intake.inspect_receipt(svc,receipt_file_id)
    context,spec,report=intake.replay_private_canonical(
        workspace_root,private_root,bundle)
    ensure(report.get("render_authorized") is False,
           "V2_SOURCE_REPLAY_NOT_RENDER_SAFE")
    if not apply:
        return {
            "status":"V2_PRIVATE_SOURCE_REPLAY_PASSED_NO_WRITE",
            "project_id":bundle["project_id"],
            "receipt_id":bundle["receipt_id"],
            "selection_sha256":bundle["selection_sha256"],
            "spec_sha256":v2.digest(spec),
            "owner_approval_authenticated":True,
            "automatic_audio_qa_required":True,
            "original_video_replayed":True,
            "canonical_applied":False,"render_authorized":False,
            "published":False,"paid_calls":0,
        }
    ensure(isinstance(github_token,str) and len(github_token)>25,
           "V2_GITHUB_TOKEN_MISSING")
    refs=stage_all_private_references(svc,bundle,spec)
    candidate,outcome=prepare_canonical_candidate(
        workspace_root,private_root,bundle,refs)
    committed=github_cas_from_checked_workspace(
        workspace_root,bundle,candidate,github_token,apply=True)
    # If this final Drive ACK fails AFTER the CAS, report an ambiguous
    # post-commit state rather than saying no canonical mutation occurred.
    try:
        ack=finish_applied_ack(svc,bundle,committed,refs)
    except Exception:
        raise V2CasError("V2_CAS_COMMITTED_ACK_PENDING_CHECK_GITHUB") from None
    return {
        "status":ack["status"],
        "project_id":bundle["project_id"],
        "receipt_id":bundle["receipt_id"],
        "selection_sha256":bundle["selection_sha256"],
        "canonical_applied":True,
        "commit_sha":ack["commit_sha"],
        "private_ack_file_id":ack["private_ack_file_id"],
        "render_authorized":False,"published":False,
        "paid_calls":0,
    }


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt-file-id",required=True)
    parser.add_argument("--private-root",required=True,
                        help="OWNER-PRIVATE staged verified WAV/MP4 workspace, OUTSIDE GitHub")
    parser.add_argument("--apply",action="store_true",
                        help="Explicitly commit one canonical edit-choice via GitHub SHA CAS")
    args=parser.parse_args()
    try:
        import issue_ticket
        root=HERE.parents[3]
        result=process_owner_v2_receipt(
            issue_ticket.drive(),root,Path(args.private_root),
            args.receipt_file_id,os.environ.get("GITHUB_TOKEN",""),
            apply=args.apply)
        # Never print selection, audio source, bearer capability or private URLs.
        print(json.dumps(result,sort_keys=True))
        return 0
    except (V2CasError,intake.V2InboxError,ValueError,KeyError,OSError) as err:
        reason=str(err)
        if not re.fullmatch(r"[A-Z0-9_]{4,90}",reason):
            reason="V2_CANONICAL_IMPORT_BLOCKED"
        print("SIMBA_V2_OWNER_IMPORT_BLOCKED:"+reason,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
