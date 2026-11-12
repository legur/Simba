#!/usr/bin/env python3
"""Review Drive inbox and create idempotent Montage notifications. NO rendering."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from issue_ticket import drive, TICKET_DIR

INBOX_ID = '1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD'
REPO = 'legur/Simba'
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
SAFE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')
class InboxError(RuntimeError): pass

def canonical(value):
    def norm(x):
        if isinstance(x, float) and x.is_integer(): return int(x)
        if isinstance(x, dict): return {k:norm(v) for k,v in x.items()}
        if isinstance(x, list): return [norm(v) for v in x]
        return x
    return json.dumps(norm(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def read_private(svc, file_id, folder, limit=320000):
    meta = svc.files().get(fileId=file_id, fields='id,name,size,parents,trashed').execute()
    if meta.get('trashed') or meta.get('parents') != [folder] or int(meta.get('size') or 0) > limit:
        raise InboxError('PRIVATE_DRIVE_PARENT_OR_SIZE_MISMATCH')
    raw = svc.files().get_media(fileId=file_id).execute()
    if not isinstance(raw, bytes) or len(raw) > limit: raise InboxError('INVALID_DRIVE_CONTENT')
    try: return json.loads(raw.decode('utf-8'))
    except Exception: raise InboxError('INVALID_DRIVE_JSON') from None

def validate(svc, file_id):
    data = read_private(svc, file_id, INBOX_ID)
    if data.get('schema') != 'bontours.motionlab.drive-inbox/v1' or data.get('status') != 'SAVED_IN_DRIVE_PENDING_MONTAGE' or data.get('render_authorized') is not False or data.get('paid_operations_authorized') is not False:
        raise InboxError('INVALID_RECEIPT_STATUS')
    receipt, ticket_id = data.get('receipt_id'), data.get('ticket_id')
    if not isinstance(receipt, str) or not UUID.fullmatch(receipt) or not isinstance(ticket_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{15,100}', ticket_id):
        raise InboxError('INVALID_RECEIPT_OR_TICKET_ID')
    if not SAFE.fullmatch(data.get('project_id') or '') or not SAFE.fullmatch(data.get('session_id') or '') or not SHA.fullmatch(data.get('source_fingerprint') or '') or not SHA.fullmatch(data.get('selection_sha256') or ''):
        raise InboxError('INVALID_SOURCE_METADATA')
    selection = data.get('selection')
    if not isinstance(selection, dict) or selection.get('schema') not in ('bontours.motionlab.storyboard.selection/v1', 'bontours.motionlab.selection/v2'):
        raise InboxError('INVALID_SELECTION_SCHEMA')
    if hashlib.sha256(canonical(selection).encode('utf-8')).hexdigest() != data['selection_sha256']:
        raise InboxError('SELECTION_HASH_MISMATCH')
    if selection.get('project_id') != data['project_id'] or selection.get('request_id') != data['session_id'] or selection.get('expected_input_fingerprint') != data['source_fingerprint']:
        raise InboxError('SELECTION_SOURCE_MISMATCH')
    if not isinstance(selection.get('scenes'), list) or not 1 <= len(selection['scenes']) <= 24:
        raise InboxError('INVALID_SCENES')
    decision, guards = selection.get('decision') or {}, selection.get('guards') or {}
    if decision.get('selected_option') not in (1, 2, 3) or decision.get('options_presented') != 3 or decision.get('confirmation_scope') != 'EDIT_CHOICES_ONLY':
        raise InboxError('UNCONFIRMED_SELECTION')
    if any(guards.get(k) is not False for k in ('run_render', 'run_tts', 'run_a2e', 'run_paid_operations', 'auto_publish')) or any(guards.get(k) is not True for k in ('preserve_approved_voice','preserve_approved_music','preserve_approved_narration')):
        raise InboxError('PAID_OR_SOURCE_GUARD_VIOLATION')
    ticket = read_private(svc, ticket_id, TICKET_DIR, limit=16000)
    if ticket.get('schema') != 'bontours.motionlab.drive-ticket/v1' or ticket.get('consumed_receipt_id') != receipt or ticket.get('consumed_sha256') != data['selection_sha256'] or ticket.get('project_id') != data['project_id'] or ticket.get('session_id') != data['session_id']:
        raise InboxError('UNTRUSTED_TICKET')
    return data

def github(method, endpoint, data=None):
    token=os.environ.get('GITHUB_TOKEN')
    if not token: raise InboxError('GITHUB_TOKEN_NOT_CONFIGURED')
    payload=json.dumps(data).encode() if data is not None else None
    req=Request('https://api.github.com/repos/'+REPO+endpoint, data=payload, method=method, headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=35) as resp: return json.loads(resp.read())
    except HTTPError as err: raise InboxError('GITHUB_HTTP_'+str(err.code)) from None

def notified_before(receipt_id):
    marker='<!-- motionlab-drive-receipt:'+receipt_id+' -->'
    for page in range(1,8):
        items=github('GET',f'/issues?state=all&per_page=100&page={page}')
        if not isinstance(items,list): raise InboxError('INVALID_ISSUE_SEARCH')
        for issue in items:
            if not issue.get('pull_request') and marker in (issue.get('body') or ''): return issue['number']
        if len(items)<100:return None
    raise InboxError('ISSUE_SEARCH_INCOMPLETE')

def notify(data,file_id):
    rid=data['receipt_id']
    existing=notified_before(rid)
    if existing:return existing
    body=('\n'.join([
        '## MotionLab selection awaiting Montage verification',
        'Project: '+data['project_id'],
        'Session: '+data['session_id'],
        'Receipt: '+rid,
        'Source fingerprint: '+data['source_fingerprint'],
        'Selection SHA-256: '+data['selection_sha256'],
        'Owner-only Drive selection: https://drive.google.com/file/d/'+file_id+'/view',
        '',
        'Status: SAVED_IN_DRIVE_PENDING_MONTAGE. No MP4 render, TTS, A2E or publication authorized.',
        'Montage must verify source files, approved audio lock, word timings, visual layout and QA.',
        '<!-- motionlab-drive-receipt:'+rid+' -->'
    ]))
    result=github('POST','/issues',{'title':'MotionLab to Montage | '+data['project_id']+' | '+data['session_id'], 'body':body})
    return int(result['number'])

def list_pending(svc):
    page=None
    while True:
        kwargs={'q':"'" + INBOX_ID + "' in parents and trashed = false",'pageSize':100,'fields':'nextPageToken,files(id,appProperties)'}
        if page: kwargs['pageToken']=page
        result=svc.files().list(**kwargs).execute()
        for f in result.get('files',[]):
            if not (f.get('appProperties') or {}).get('montage_issue_number'): yield f['id']
        page=result.get('nextPageToken')
        if not page:break

def run(svc,dry_run=True):
    status={'found':0,'notified':0,'blocked':0,'dry_run':dry_run,'render_started':False}
    for fid in list_pending(svc):
        status['found']+=1
        try:
            item=validate(svc,fid)
            if not dry_run:
                issue=notify(item,fid)
                svc.files().update(fileId=fid,body={'appProperties':{'montage_issue_number':str(issue),'motionlab_status':'NOTIFIED_PENDING_VERIFICATION'}},fields='id,appProperties').execute()
                status['notified']+=1
        except (InboxError,ValueError,TypeError,KeyError) as e:
            print('Blocked private Drive receipt:',str(e),file=sys.stderr)
            status['blocked']+=1
    return status

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--send-notifications',action='store_true')
    args=parser.parse_args()
    try:
        report=run(drive(),dry_run=not args.send_notifications)
        print(json.dumps(report,sort_keys=True))
        return 2 if report['blocked'] else 0
    except InboxError as e:
        print('Private Drive ingestion failed:',str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
