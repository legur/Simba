"""Isolated owner-private canonical v2 workspace → real Studio preparation.

Trusted owner worker ONLY. Never copy owner project into the public GitHub
checkout; never substitute a historical candidate for actual stage approvals.
The exact privately SHA-pinned project and source bytes are replayed through
the existing Studio v2 source/audio/video gates, from a disposable workspace.
No recipient receives a raw source by the public API.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile

import v2_private_canonical_source as owner

MAX_SINGLE_SOURCE=256_000
MAX_TOTAL_SOURCES=1_000_000
MAX_FILES=30


class PrivateWorkspaceError(ValueError):
    pass


def guard(value,code):
    if not value:
        raise PrivateWorkspaceError(code)


def _secure_parent(parent: Path, public_repo: Path) -> Path:
    root=Path(parent).expanduser()
    checkout=Path(public_repo).resolve()
    guard(root.is_absolute() and root.exists() and root.is_dir()
          and not root.is_symlink(), "V2_PRIVATE_WORKSPACE_PARENT_INVALID")
    resolved=root.resolve()
    guard(resolved != checkout and not resolved.is_relative_to(checkout)
          and not checkout.is_relative_to(resolved),
          "V2_PRIVATE_WORKSPACE_OVERLAPS_PUBLIC_GIT")
    # Restrict untrusted guest/group access to generated workspace even when
    # the parent has broader permissions.
    return resolved


def _paths(document: dict, project_id: str) -> dict[str,str]:
    specs={}
    for group in ("sources","references"):
        entries=document.get(group, [])
        guard(isinstance(entries,list),"V2_PRIVATE_SOURCE_LIST_INVALID")
        for item in entries:
            guard(isinstance(item,dict),"V2_PRIVATE_SOURCE_ENTRY_INVALID")
            name=item.get("path")
            sha=item.get("sha256")
            guard(isinstance(name,str)
                  and isinstance(sha,str) and owner.private.SHA.fullmatch(sha),
                  "V2_PRIVATE_SOURCE_REQUIRES_CANONICAL_SHA")
            path=PurePosixPath(name)
            guard(not path.is_absolute() and len(path.parts)>=3
                  and path.parts[:2]==("campaigns",project_id)
                  and not any(p in (".","..","") for p in path.parts)
                  and "\\" not in name and name==str(path)
                  and name not in specs,
                  "V2_PRIVATE_SOURCE_PATH_UNSAFE")
            specs[name]=sha
    guard(0<len(specs)<=MAX_FILES, "V2_PRIVATE_SOURCE_COUNT_INVALID")
    return specs


def _put_locked(workspace: Path, path: str, raw: bytes):
    destination=workspace.joinpath(*PurePosixPath(path).parts)
    guard(destination.parent.resolve().is_relative_to(workspace.resolve()),
          "V2_PRIVATE_SOURCE_PATH_UNSAFE")
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with destination.open("xb") as fd:
        os.chmod(destination,0o600)
        fd.write(raw)
        fd.flush()
        os.fsync(fd.fileno())


@contextmanager
def private_stage(workspace_parent:Path,public_repo:Path,project_id:str,
                  canonical_raw:bytes,canonical:dict,
                  owner_source_bytes:dict[str,bytes]):
    """Yield ephemeral source-only workspace; remove it on exit/failure."""
    parent=_secure_parent(workspace_parent,public_repo)
    owner.check_canonical_shape(canonical,project_id)
    guard(isinstance(canonical_raw,bytes)
          and len(canonical_raw)<=owner.MAX_PROJECT_BYTES,
          "V2_PRIVATE_CANONICAL_BYTES_INVALID")
    import json
    try:
        guard(json.loads(canonical_raw.decode("utf-8"))==canonical,
              "V2_PRIVATE_CANONICAL_BYTES_MISMATCH")
    except (ValueError,UnicodeError):
        raise PrivateWorkspaceError("V2_PRIVATE_CANONICAL_BYTES_MISMATCH") from None
    sources=_paths(canonical,project_id)
    guard(isinstance(owner_source_bytes,dict)
          and set(owner_source_bytes)==set(sources),
          "V2_PRIVATE_APPROVED_SOURCE_FILES_MISSING")
    total=0
    for path,expected in sources.items():
        raw=owner_source_bytes[path]
        guard(type(raw) is bytes and 0<len(raw)<=MAX_SINGLE_SOURCE,
              "V2_PRIVATE_APPROVED_SOURCE_BYTES_INVALID")
        total+=len(raw)
        guard(hashlib.sha256(raw).hexdigest()==expected,
              "V2_PRIVATE_APPROVED_SOURCE_SHA_CHANGED")
    guard(total<=MAX_TOTAL_SOURCES,
          "V2_PRIVATE_APPROVED_SOURCE_TOO_LARGE")
    # TemporaryDirectory creates the protected 0700 directory, never inside
    # a public Git working tree. The caller never chooses a destination file.
    with tempfile.TemporaryDirectory(prefix="simba-v2-source-",dir=parent) as name:
        workspace=Path(name)
        for path in sorted(sources):
            _put_locked(workspace,path,owner_source_bytes[path])
        _put_locked(workspace,f"campaigns/{project_id}/project.json",canonical_raw)
        yield workspace


def prepare_real_private_studio(svc, *, folder_id:str,file_id:str,
                                expected_sha256:str,project_id:str,
                                request_id:str,owner_source_bytes:dict[str,bytes],
                                workspace_parent:Path,public_repo:Path,
                                private_media_root:Path):
    """Wire the existing actual Studio v2 preparer to private canonical data.

    This is NOT a new approval route. A missing/incorrect v2 stage or
    independent ASR evidence stops before a ticket, selection, CAS or render.
    Returns the original fully verified *private* proposals only to trusted
    owner tooling. Never print or publish the returned materials.
    """
    raw,document,_=owner._read_private_canonical(
        svc,folder_id=folder_id,file_id=file_id,project_id=project_id,
        expected_sha256=expected_sha256)
    with private_stage(workspace_parent,public_repo,project_id,
                       raw,document,owner_source_bytes) as workspace:
        import motionlab_v2_stage_writeback as stage
        result=stage.prepare_automatic_v2_proposals(
            workspace,Path(private_media_root),project_id,request_id)
        guard(isinstance(result,dict)
              and result.get("owner_selection_required") is True
              and result.get("run_render") is False
              and result.get("run_paid_operations") is False
              and result.get("auto_publish") is False
              and result.get("materials",{}).get("audio_alignment_status")
                   == "AUDIO_ALIGNMENT_VERIFIED_AUTO",
              "V2_PRIVATE_STUDIO_PREPARATION_NOT_AUTHORIZED")
        return result
