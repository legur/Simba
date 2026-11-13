"""Verified private Drive archive of individual files produced by Studio.

Call from a producer once its real source bytes have been validated. No polling,
generation, external publication, or credential handling occurs here.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re

ROOT_FOLDER = '18Nv8mJ-pAafpGIkxNaDBnlVdBZ51cJ_2'
SAFE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')


class ArchiveError(RuntimeError):
    pass


def call(request):
    try:
        return request.execute(num_retries=0)
    except Exception:
        raise ArchiveError('DRIVE_OPERATION_FAILED_RECONCILE_BEFORE_RETRY') from None


def assert_private(drive, folder):
    meta = call(drive.files().get(fileId=folder, fields='id,mimeType,trashed,permissions(type,role),capabilities(canAddChildren)'))
    permissions = meta.get('permissions')
    if (meta.get('id') != folder or meta.get('trashed') or
        meta.get('mimeType') != 'application/vnd.google-apps.folder' or
        not meta.get('capabilities', {}).get('canAddChildren') or
        not isinstance(permissions, list) or not permissions or
        any(p.get('type') != 'user' for p in permissions)):
        raise ArchiveError('ARCHIVE_FOLDER_NOT_PRIVATE_OR_WRITABLE')


def find_one(drive, parent, name):
    if not SAFE.fullmatch(name):
        raise ArchiveError('INVALID_ARCHIVE_NAME')
    q = f"'{parent}' in parents and name = '{name}' and trashed = false"
    result = call(drive.files().list(q=q, fields='nextPageToken,files(id,name,mimeType,parents,size,md5Checksum)', pageSize=100))
    files = result.get('files') or []
    if result.get('nextPageToken') or len(files) > 1:
        raise ArchiveError('AMBIGUOUS_ARCHIVE_NAME')
    return files[0] if files else None


def folder(drive, parent, name):
    assert_private(drive, parent)
    item = find_one(drive, parent, name)
    if item is None:
        item = call(drive.files().create(body={'name':name, 'mimeType':'application/vnd.google-apps.folder', 'parents':[parent]}, fields='id,name,mimeType,parents'))
    if item.get('name') != name or item.get('mimeType') != 'application/vnd.google-apps.folder' or item.get('parents') != [parent]:
        raise ArchiveError('ARCHIVE_FOLDER_MISMATCH')
    assert_private(drive, item['id'])
    return item['id']


def save_files(drive, project_id, category, files, *, root=ROOT_FOLDER):
    """Store {safe filename: bytes}, rejecting collisions and verifying bytes."""
    if not SAFE.fullmatch(project_id) or not SAFE.fullmatch(category) or not files:
        raise ArchiveError('INVALID_ARCHIVE_REQUEST')
    if len(files) > 100 or any(not SAFE.fullmatch(n) or not isinstance(b, bytes) or not b or len(b) > 40_000_000 for n,b in files.items()):
        raise ArchiveError('INVALID_ARCHIVE_FILES')
    from googleapiclient.http import MediaInMemoryUpload
    project = folder(drive, root, project_id)
    target = folder(drive, project, category)
    results = []
    for name, data in sorted(files.items()):
        expected_sha = hashlib.sha256(data).hexdigest()
        expected_md5 = hashlib.md5(data).hexdigest()
        item = find_one(drive, target, name)
        reused = item is not None
        if item is None:
            mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            item = call(drive.files().create(body={'name':name, 'parents':[target]}, media_body=MediaInMemoryUpload(data, mimetype=mime, resumable=False), fields='id,name,parents,size,md5Checksum'))
        if (item.get('name') != name or item.get('parents') != [target] or
            int(item.get('size') or -1) != len(data) or item.get('md5Checksum') != expected_md5):
            raise ArchiveError('ARCHIVE_FILE_COLLISION_OR_METADATA_MISMATCH')
        remote = call(drive.files().get_media(fileId=item['id']))
        if not isinstance(remote, bytes) or hashlib.sha256(remote).hexdigest() != expected_sha:
            raise ArchiveError('ARCHIVE_FILE_READBACK_MISMATCH')
        results.append({'name':name, 'drive_file_id':item['id'], 'sha256':expected_sha, 'reused':reused})
    return {'status':'INDIVIDUAL_FILES_VERIFIED', 'project_folder_id':project, 'folder_id':target, 'files':results}
