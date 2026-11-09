#!/usr/bin/env python3
"""Owner-only approved Simba voice issue runner; audios remain on private Drive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import github_secret_job as store
import simba_voice


def validate_event(event):
    issue = event.get('issue') or {}
    if ((event.get('repository') or {}).get('full_name') != 'legur/Simba'
        or event.get('action') != 'labeled'
        or (event.get('label') or {}).get('name') != 'simba-approved-voice'
        or (event.get('sender') or {}).get('login') != 'legur'
        or (issue.get('user') or {}).get('login') != 'legur'
        or issue.get('pull_request') is not None
        or type(issue.get('number')) is not int or issue['number'] < 1):
        raise ValueError('Untrusted event')
    data = json.loads(issue.get('body') or '')
    if not isinstance(data, dict) or set(data) != {'kind', 'text', 'destination_folder_id'}:
        raise ValueError('Invalid request fields')
    if data['kind'] != 'simba_approved_voice':
        raise ValueError('Invalid request kind')
    text = data['text']
    if not isinstance(text, str) or not text.strip() or len(text) > 450:
        raise ValueError('Text must be between 1 and 450 characters')
    folder = store.validate_drive_id(data['destination_folder_id'])
    return issue['number'], text, folder


def run(event, workdir):
    issue, text, folder = validate_event(event)
    simba_voice._require_github_secrets_workflow()
    store.require_secret_environment(os.environ)
    drive = store.oauth_drive_client(os.environ)
    store.validate_destination(drive, folder)
    name = f'Simba_voice_issue_{issue}.wav'
    if store._drive_matches(drive, folder, name):
        raise store.ReplayBlocked('Output exists; reuse rather than resynthesize')
    # A global private Drive marker keyed by the exact text prevents retries,
    # including via a new issue. Serialize the entire workflow globally.
    key = hashlib.sha256(text.encode('utf-8')).hexdigest()
    store.ensure_no_global_marker(drive, key)
    voice_id = simba_voice.voice_id_from_private_store()  # private; never printed
    marker = store.create_attempt_marker(drive, folder, key, os.environ)
    audio = simba_voice.synthesize_lines([{'id': 'narration', 'text': text}], workdir,
                                         voice_id=voice_id, allow_fallback=False)['narration']
    from googleapiclient.http import MediaFileUpload
    try:
        item = drive.files().create(body={'name': name, 'parents': [folder], 'mimeType': 'audio/wav',
            'description': 'Private approved Simba voice narration.',
            'appProperties': {'simba_render_marker_id': marker['id']}},
            media_body=MediaFileUpload(str(audio), mimetype='audio/wav', resumable=True),
            fields='id').execute(num_retries=0)
        observed = store._get_drive_item(drive, item['id'])
        store._assert_private(observed, expected_parent=folder)
        if observed.get('name') != name or observed.get('size') != str(audio.stat().st_size):
            raise store.JobError('Voice upload read-back failed')
    except Exception:
        raise store.JobError('Voice upload uncertain; inspect Drive and do not retry synthesis') from None
    return {'status': 'COMPLETED', 'file_id': item['id'], 'file_name': name}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--event', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        result = run(json.loads(args.event.read_text(encoding='utf-8')), args.out / 'cache')
    except (ValueError, TypeError, OSError, KeyError, simba_voice.VoiceError, store.JobError) as exc:
        result = {'status': 'STOPPED', 'reason': str(exc)}
    report = ['### Approved Simba voice', '', '**Status:** ' + result['status']]
    if result.get('file_id'):
        report += ['Private Drive file ID: ' + result['file_id'], 'Name: ' + result['file_name']]
    if result.get('reason'):
        report += ['Reason: ' + result['reason']]
    report += ['', 'No automatic retry after a paid attempt.']
    (args.out / 'report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    return 0 if result['status'] == 'COMPLETED' else 2

if __name__ == '__main__':
    sys.exit(main())
