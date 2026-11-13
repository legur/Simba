"""Owner-private Drive project snapshots with an atomic, public *blind* head.

The private project and edit-plan IDs NEVER enter GitHub. A GitHub Contents API
CAS stores just a revision and HMAC commitment (not the raw source SHA).
Immutable snapshots and durable receipts remain in owner-only Drive. Both
bootstrap and apply require the trusted owner's private worker and exact
previous GitHub blob SHA. This is not a browser/GAS endpoint.

No A2E, TTS, render, publish, or invented v2 owner approvals.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
from pathlib import Path
import re

import v2_private_canonical_source as source
import v2_private_workspace as workspace
import v2_canonical_cas as cas
import v2_receipt_preflight as intake

SCHEMA="bontours.studio.owner-private-blind-head/v1"
PRIVATE_HEAD_DIR="integrations/materials/motionlab/drive_handoff/private_heads"
SHA=intake.SHA
MAX_SNAPSHOT=300_000


class PrivateHeadError(ValueError):
    pass


def need(value,code):
    if not value:
        raise PrivateHeadError(code)


def _json_bytes(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def head_path(project_id):
    need(isinstance(project_id,str) and source.PROJECT_ID.fullmatch(project_id),
         "V2_PRIVATE_HEAD_PROJECT_ID_INVALID")
    return f"{PRIVATE_HEAD_DIR}/{project_id}.json"


def commitment(project_id,sha256,secret):
    """Keyed commitment: no Drive SHA, filename, URL or content in GitHub."""
    head_path(project_id)
    need(isinstance(sha256,str) and SHA.fullmatch(sha256),
         "V2_PRIVATE_HEAD_SOURCE_SHA_INVALID")
    need(type(secret) is bytes and len(secret)>=32,
         "V2_PRIVATE_HEAD_HMAC_KEY_REQUIRED")
    return hmac.new(secret, (project_id+"\n"+sha256).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _valid_head(project_id,head):
    need(isinstance(head,dict)
         and set(head)=={"schema","project_id","revision","state",
                         "blind_commitment","render_authorized",
                         "publication_authorized"}
         and head["schema"]==SCHEMA
         and head["project_id"]==project_id
         and type(head["revision"]) is int
         and head["revision"]>=0
         and head["state"] in {"UNINITIALIZED","READY_FOR_EDIT_CHOICE",
                               "EDIT_CHOICE_RECORDED"}
         and head["render_authorized"] is False
         and head["publication_authorized"] is False,
         "V2_PRIVATE_HEAD_METADATA_INVALID")
    if head["state"]=="UNINITIALIZED":
        need(head["revision"]==0 and head["blind_commitment"] is None,
             "V2_PRIVATE_HEAD_GENESIS_INVALID")
    else:
        need(head["revision"]>=1
             and isinstance(head["blind_commitment"],str)
             and SHA.fullmatch(head["blind_commitment"]),
             "V2_PRIVATE_HEAD_COMMITMENT_INVALID")
    return head


def get_head(project_id,github_token):
    """Read and SHA-check the GitHub *metadata* file; never a private JSON."""
    path=head_path(project_id)
    try:
        info=cas._github("GET","/contents/"+path+"?ref=main",github_token)
        need(isinstance(info,dict) and info.get("path")==path
             and info.get("type")=="file" and info.get("encoding")=="base64"
             and isinstance(info.get("sha"),str)
             and re.fullmatch(r"[a-f0-9]{40}",info["sha"]),
             "V2_PRIVATE_HEAD_REMOTE_INVALID")
        raw=base64.b64decode(info["content"],validate=False)
        need(cas.github_blob_sha(raw)==info["sha"],
             "V2_PRIVATE_HEAD_BLOB_CHANGED")
        head=json.loads(raw.decode("utf-8"))
    except (ValueError,TypeError,KeyError,UnicodeError):
        raise PrivateHeadError("V2_PRIVATE_HEAD_REMOTE_UNREADABLE") from None
    return info["sha"],_valid_head(project_id,head)


def require_ready_head(project_id,head,old_project_sha,secret):
    _valid_head(project_id,head)
    need(head["state"]=="READY_FOR_EDIT_CHOICE",
         "V2_PRIVATE_HEAD_NOT_READY_FOR_EDIT")
    need(hmac.compare_digest(head["blind_commitment"],
                             commitment(project_id,old_project_sha,secret)),
         "V2_PRIVATE_HEAD_SOURCE_CHANGED")


def proposed_head(project_id,old_head,new_raw_sha,secret,*,bootstrap=False):
    _valid_head(project_id,old_head)
    need(old_head["state"]==("UNINITIALIZED" if bootstrap
                            else "READY_FOR_EDIT_CHOICE"),
         "V2_PRIVATE_HEAD_WRONG_STAGE")
    return _valid_head(project_id,{
        "schema":SCHEMA,
        "project_id":project_id,
        "revision":old_head["revision"]+1,
        "state":("READY_FOR_EDIT_CHOICE" if bootstrap
                 else "EDIT_CHOICE_RECORDED"),
        "blind_commitment":commitment(project_id,new_raw_sha,secret),
        "render_authorized":False,"publication_authorized":False,
    })


def _check_exact_owner_acl(svc,file_id):
    try:
        response=svc.permissions().list(
            fileId=file_id,fields="nextPageToken,permissions(type,role)",
            pageSize=100).execute()
    except Exception:
        raise PrivateHeadError("V2_PRIVATE_SNAPSHOT_ACL_UNAVAILABLE") from None
    rows=response.get("permissions")
    need(not response.get("nextPageToken")
         and isinstance(rows,list) and len(rows)==1
         and rows[0].get("type")=="user" and rows[0].get("role")=="owner",
         "V2_PRIVATE_SNAPSHOT_OWNER_ONLY_REQUIRED")


def store_immutable_snapshot(svc,folder_id,raw):
    """Owner-only Drive immutable named-by-SHA revision, with byte readback.

    Any stale/racing duplicate name must have EXACT matching content, otherwise
    stop. Orphan snapshots after CAS conflict are safe; they are not active.
    """
    need(type(raw) is bytes and 100<=len(raw)<=MAX_SNAPSHOT,
         "V2_PRIVATE_SNAPSHOT_SIZE_INVALID")
    source.verify_private_folder(svc,folder_id)
    sha=hashlib.sha256(raw).hexdigest()
    name=f"project.v2.{sha}.json"
    q=f"'{folder_id}' in parents and name = '{name}' and trashed = false"
    try:
        found=svc.files().list(q=q,pageSize=100,
                 fields="nextPageToken,files(id,name,parents,mimeType,size)").execute()
    except Exception:
        raise PrivateHeadError("V2_PRIVATE_SNAPSHOT_LIST_FAILED") from None
    rows=found.get("files") or []
    need(not found.get("nextPageToken") and len(rows)<=1,
         "V2_PRIVATE_SNAPSHOT_AMBIGUOUS")
    if rows:
        fid=rows[0].get("id")
    else:
        try:
            from googleapiclient.http import MediaIoBaseUpload
            result=svc.files().create(
                body={"name":name,"parents":[folder_id],
                      "mimeType":"application/json"},
                media_body=MediaIoBaseUpload(
                    io.BytesIO(raw),mimetype="application/json",resumable=False),
                fields="id,name,parents,mimeType,size").execute()
            fid=result.get("id")
        except Exception:
            raise PrivateHeadError("V2_PRIVATE_SNAPSHOT_UPLOAD_FAILED") from None
    _check_exact_owner_acl(svc,fid)
    try:
        checked=intake.secure_private_bytes(
            svc,fid,folder_id,MAX_SNAPSHOT,
            mime={"application/json"},filename=name)
    except intake.V2InboxError:
        raise PrivateHeadError("V2_PRIVATE_SNAPSHOT_READBACK_FAILED") from None
    need(checked==raw, "V2_PRIVATE_SNAPSHOT_CHANGED_OR_COLLIDED")
    return {"id":fid,"sha256":sha}


def update_blind_head(project_id,old_blob_sha,next_head,github_token,*,apply=False):
    """Only the public HMAC metadata changes atomically, never project.json."""
    path=head_path(project_id)
    _valid_head(project_id,next_head)
    need(isinstance(old_blob_sha,str)
         and re.fullmatch(r"[a-f0-9]{40}",old_blob_sha),
         "V2_PRIVATE_HEAD_BASE_BLOB_INVALID")
    raw=_json_bytes(next_head)
    need(b"drive.google.com" not in raw and b"drive_file_id" not in raw
         and b"selection_sha256" not in raw,
         "V2_PRIVATE_HEAD_LEAKAGE")
    report={
        "status":"V2_PRIVATE_HEAD_CAS_VALIDATED_NO_WRITE",
        "project_id":project_id,"new_revision":next_head["revision"],
        "render_authorized":False,"published":False,"paid_calls":0
    }
    if not apply:
        return report
    try:
        answer=cas._github("PUT","/contents/"+path,github_token,{
            "message":"chore(studio): advance blind owner-private v2 revision (NO RENDER)",
            "sha":old_blob_sha,"branch":cas.BRANCH,
            "content":base64.b64encode(raw).decode("ascii")
        })
    except cas.V2CasError:
        raise PrivateHeadError("V2_PRIVATE_HEAD_COMMIT_UNCERTAIN_OR_CONFLICT") from None
    content=answer.get("content") or {}
    commit=answer.get("commit") or {}
    need(content.get("sha")==cas.github_blob_sha(raw)
         and isinstance(commit.get("sha"),str)
         and re.fullmatch(r"[a-f0-9]{40}",commit["sha"]),
         "V2_PRIVATE_HEAD_COMMIT_UNCERTAIN_CHECK_GITHUB")
    return {**report,"status":"V2_PRIVATE_BLIND_HEAD_CAS_APPLIED_NO_RENDER",
            "commit_sha":commit["sha"]}


def _pinned_source_workspace(project_id,raw,document,owner_source_bytes,
                             workspace_parent,public_repo):
    return workspace.private_stage(workspace_parent,public_repo,
        project_id,raw,document,owner_source_bytes)


def bootstrap_private_head(svc,*,folder_id,file_id,project_id,
                           expected_sha256,owner_source_bytes,
                           workspace_parent,public_repo,
                           github_token,secret,apply=False):
    """One-time bootstrap. Cannot initialize from the historical candidate."""
    raw,document,sha=source._read_private_canonical(
        svc,folder_id=folder_id,file_id=file_id,project_id=project_id,
        expected_sha256=expected_sha256)
    with _pinned_source_workspace(project_id,raw,document,owner_source_bytes,
                                  workspace_parent,public_repo) as root:
        import handoff
        path=root/"campaigns"/project_id/"project.json"
        packet=handoff.make_handoff(root,path,document)
        need(packet.get("state")=="READY_FOR_HANDOFF"
             and (packet.get("packet") or {}).get("next_stage")=="edit_choice",
             "V2_PRIVATE_SOURCE_HANDOFF_NOT_AT_EDIT_CHOICE")
    old_blob,head=get_head(project_id,github_token)
    next_head=proposed_head(project_id,head,sha,secret,bootstrap=True)
    report=update_blind_head(project_id,old_blob,next_head,
                             github_token,apply=False)
    if not apply:
        return {**report,"status":"V2_PRIVATE_HEAD_BOOTSTRAP_VALIDATED_NO_WRITE"}
    store_immutable_snapshot(svc,folder_id,raw)
    return update_blind_head(project_id,old_blob,next_head,
                             github_token,apply=True)


def apply_private_edit_choice(svc,*,folder_id,file_id,project_id,
                              expected_sha256,owner_source_bytes,
                              workspace_parent,public_repo,private_media_root,
                              receipt_file_id,github_token,secret,apply=False):
    """Authenticated owner selection -> private revision -> blind CAS.

    IMPORTANT: the owner worker must provision the original media in its
    protected private_media_root. No fallback to the public GitHub source.
    Existing authentic consumed ticket, source replay, spec, original WAV/MP4
    and independent audio gates remain mandatory. A dry-run writes NOTHING.
    """
    raw,document,old_sha=source._read_private_canonical(
        svc,folder_id=folder_id,file_id=file_id,project_id=project_id,
        expected_sha256=expected_sha256)
    old_blob,head=get_head(project_id,github_token)
    require_ready_head(project_id,head,old_sha,secret)
    bundle=intake.inspect_receipt(svc,receipt_file_id)
    need(bundle["project_id"]==project_id,
         "V2_PRIVATE_OWNER_SELECTION_PROJECT_MISMATCH")
    with _pinned_source_workspace(project_id,raw,document,owner_source_bytes,
                                  workspace_parent,public_repo) as root:
        _,spec,report=intake.replay_private_canonical(
            root,private_media_root,bundle)
        need(report.get("render_authorized") is False,
             "V2_PRIVATE_SPEC_NOT_RENDER_SAFE")
        if not apply:
            return {
                "status":"V2_OWNER_SELECTION_AND_SOURCE_REPLAY_PASSED_NO_WRITE",
                "project_id":project_id,
                "owner_receipt_authenticated":True,
                "canonical_applied":False,
                "render_authorized":False,
                "published":False,"paid_calls":0
            }
        refs=cas.stage_all_private_references(svc,bundle,spec)
        candidate,outcome=cas.prepare_canonical_candidate(
            root,private_media_root,bundle,refs)
        need(outcome.get("project_written") is False
             and outcome.get("render_started") is False,
             "V2_PRIVATE_EDIT_CHOICE_WAS_ALREADY_RENDERED")
        # Reuse the *same* strict no-unrelated-fields candidate delta validator
        # as the original GitHub CAS, but NEVER GitHub-PUT the private document.
        cas.github_cas_canonical(project_id,cas.github_blob_sha(raw),
                                 raw,candidate,"",apply=False)
        candidate_raw=(json.dumps(candidate,ensure_ascii=False,sort_keys=True,
                                  indent=2)+"\n").encode("utf-8")
    new_sha=hashlib.sha256(candidate_raw).hexdigest()
    next_head=proposed_head(project_id,head,new_sha,secret,bootstrap=False)
    stored=store_immutable_snapshot(svc,folder_id,candidate_raw)
    need(stored["sha256"]==new_sha,"V2_PRIVATE_CANDIDATE_SHA_CHANGED")
    committed=update_blind_head(project_id,old_blob,next_head,
                                github_token,apply=True)
    # The pointer commit, not mere Drive snapshot creation, changes the head.
    # ACK failure is explicitly ambiguous: never pretend the CAS did not run.
    try:
        from googleapiclient.http import MediaIoBaseUpload
        name="motionlab-v2-"+bundle["receipt_id"]+"-private-head-applied.json"
        ack={"schema":"bontours.studio.private-head-applied/v1",
             "status":"PRIVATE_DRIVE_EDIT_CHOICE_CANONICALLY_APPLIED",
             "project_id":project_id,"receipt_id":bundle["receipt_id"],
             "selection_sha256":bundle["selection_sha256"],
             "private_snapshot_sha256":new_sha,
             "private_snapshot_file_id":stored["id"],
             "head_commit_sha":committed["commit_sha"],
             "render_authorized":False,"published":False,"paid_calls":0}
        ack_raw=_json_bytes(ack)
        # Reuse immutable snapshot write semantics inside an owner-only folder
        # and keep the resulting file ID private.
        ack_stored=cas.store_applied_ack(
            svc,bundle,ack)  # Existing method is immutable and SHA verified.
    except Exception:
        raise PrivateHeadError(
            "V2_PRIVATE_HEAD_COMMITTED_ACK_PENDING_CHECK_PRIVATE_HEAD") from None
    return {**committed,
            "status":"V2_PRIVATE_DRIVE_EDIT_CHOICE_APPLIED_NO_RENDER",
            "private_ack_file_id":ack_stored["id"],
            "render_authorized":False,"published":False,"paid_calls":0}
