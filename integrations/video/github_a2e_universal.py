#!/usr/bin/env python3
"""Issue-driven reusable image-to-video runner. One paid attempt per issue."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request
from github_a2e_issue_bridge import build_bodies
import github_a2e_prague_generate as core

LABEL = 'a2e-generate-approved'
MARKER = 'SIMBA_A2E_UNIVERSAL_START_V1'


def validate(event):
    issue = event.get('issue') or {}
    if ((event.get('repository') or {}).get('full_name') != 'legur/Simba'
        or (event.get('sender') or {}).get('login', '').lower() != 'legur'
        or (issue.get('user') or {}).get('login', '').lower() != 'legur'
        or issue.get('pull_request') is not None
        or event.get('action') != 'labeled'
        or (event.get('label') or {}).get('name') != LABEL
        or type(issue.get('number')) is not int or issue['number'] <= 0):
        raise ValueError('Untrusted event')
    raw = issue.get('body')
    if not isinstance(raw, str) or len(raw) > 20000:
        raise ValueError('Invalid issue body')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('kind') != 'simba_a2e_generate':
        raise ValueError('Invalid request kind')
    # Optional non-private provenance from the approved Rafael/A2E stage
    # contract. Older owner-created issues remain valid unchanged.
    lineage_keys = ('project_id', 'handoff_sha256', 'selected_storyboard', 'selected_prompts')
    if any(k in data for k in lineage_keys):
        if (not isinstance(data.get('project_id'), str)
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', data['project_id'])
            or not isinstance(data.get('handoff_sha256'), str)
            or not re.fullmatch(r'[a-f0-9]{64}', data['handoff_sha256'])
            or any(type(data.get(k)) is not int or data[k] not in (1, 2, 3)
                   for k in ('selected_storyboard', 'selected_prompts'))):
            raise ValueError('Malformed or incomplete approved provenance')
    cap = data.get('max_credits')
    if type(cap) not in (int, float) or not math.isfinite(cap) or not 0 < cap <= 1000:
        raise ValueError('Invalid credit ceiling')
    # Reuse the existing strict Wix URL and scene validation.
    fake = dict(event)
    fake['label'] = {'name': 'a2e-quote'}
    fake['issue'] = dict(issue, body=json.dumps(dict(data, kind='simba_a2e_quote')))
    bodies = build_bodies(fake)
    for body in bodies:
        core.validate_generation_body(body)
    return issue['number'], float(cap), bodies


def price(bodies, key):
    prices = []
    for body in bodies:
        data = core.checked_api(core.request_quote(body, key))
        value = data.get('coins')
        if (data.get('available') is not True or data.get('exact') is not True
            or type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise core.StopGeneration('Exact price unavailable')
        prices.append(float(value))
    return prices


def no_existing_tasks(bodies, key):
    urls = [b['image_url'] for b in bodies]
    for page in range(1, 21):
        req = Request(core.API_BASE + '/v1/userImage2Video/allRecords?pageNum=' + str(page) + '&pageSize=100',
                      headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})
        data = core.checked_api(core.read_json(req))
        rows = data.get('rows')
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise core.StopGeneration('Task history unavailable')
        if any(any(url in json.dumps(row) for url in urls) for row in rows):
            raise core.StopGeneration('Existing task uses a source image; inspect and reuse first')
        if len(rows) < 100:
            return
    raise core.StopGeneration('Task history incomplete')


def run(event, out):
    out.mkdir(parents=True, exist_ok=True)
    state = {'status': 'NOT_STARTED', 'scenes': []}
    def save():
        (out / 'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        issue, cap, bodies = validate(event)
        approved_source = json.loads(event['issue']['body'])
        if 'project_id' in approved_source:
            state['lineage'] = {
                'project_id': approved_source['project_id'],
                'handoff_sha256': approved_source['handoff_sha256'],
                'selected_storyboard': approved_source['selected_storyboard'],
                'selected_prompts': approved_source['selected_prompts'],
                'verified_at_source': False,
                'note': 'Owner-authored record; previously validated by Rafael bridge, not re-read from Drive here',
            }
        key = os.environ.get('A2E_API_KEY', '')
        if not key.startswith('sk_') or len(key) < 15:
            raise core.StopGeneration('A2E key unavailable')
        prices = price(bodies, key)
        if sum(prices) > cap:
            raise core.StopGeneration('Quote exceeds selected credit ceiling')
        no_existing_tasks(bodies, key)
        core.GITHUB_COMMENTS = f'https://api.github.com/repos/legur/Simba/issues/{issue}/comments'
        comments = core.github_request('GET')
        if not isinstance(comments, list) or len(comments) >= 100 or any(MARKER in str(c.get('body', '')) for c in comments if isinstance(c, dict)):
            raise core.StopGeneration('Start journal exists or cannot be verified')
        receipt = core.github_request('POST', json_body={'body': MARKER + '\nPaid start attempted. Do not retry; inspect task history and billing.'})
        if not isinstance(receipt, dict) or not receipt.get('id'):
            raise core.StopGeneration('Journal not acknowledged')
        state.update(status='JOURNALED', max_credits=cap, quoted_credits=prices)
        save()
        spent = 0.0
        for idx, body in enumerate(bodies, 1):
            current = price([body], key)[0]
            if spent + current > cap:
                raise core.StopGeneration('Updated price exceeds remaining ceiling')
            state.update(status='START_ATTEMPT_IN_PROGRESS', current_scene=idx)
            save()
            data = core.checked_api(core.a2e_start(body, key))
            task = data.get('_id')
            if not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,96}', task):
                raise core.StopGeneration('Unknown start result; reconcile before retry')
            billed = data.get('coins')
            spent += float(billed) if type(billed) in (int, float) and math.isfinite(billed) and billed >= 0 else current
            state['scenes'].append({'number': idx, 'task_id': task, 'status': 'submitted'})
            save()
            if spent > cap:
                raise core.StopGeneration('Reported charge exceeds ceiling')
        state['status'] = 'SUBMITTED'
        save()
        deadline = time.monotonic() + 18 * 60
        while time.monotonic() < deadline:
            pending = 0
            for row in state['scenes']:
                if row['status'] in ('completed', 'failed', 'blocked'):
                    continue
                detail = core.checked_api(core.a2e_status(row['task_id'], key))
                status = detail.get('current_status')
                if status == 'completed':
                    url = detail.get('result_url')
                    if not isinstance(url, str):
                        raise core.StopGeneration('Completed task has no result URL')
                    core.download_video(url, out / ('scene_%02d.mp4' % row['number']))
                    row['status'] = 'completed'
                elif status in ('failed', 'blocked'):
                    row['status'] = status
                else:
                    pending += 1
            save()
            if not pending:
                break
            time.sleep(13)
        state['status'] = 'COMPLETED' if all(x['status'] == 'completed' for x in state['scenes']) else 'PARTIAL_OR_PROCESSING'
    except (ValueError, TypeError, KeyError, core.StopGeneration, OSError) as exc:
        state.update(status='STOPPED', note=str(exc))
    save()
    (out / 'report.md').write_text('### A2E universal\n\nStatus: ' + state['status'] + '\nTasks: ' + ', '.join(x['task_id'] for x in state['scenes']) + '\n' + state.get('note', '') + '\nDo not retry paid starts without reconciliation.\n', encoding='utf-8')
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run(json.loads(args.event.read_text(encoding='utf-8')), args.out)
    return 1 if result['status'] == 'STOPPED' else 0

if __name__ == '__main__':
    raise SystemExit(main())
