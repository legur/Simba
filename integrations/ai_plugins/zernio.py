"""Approved Simba packages to Zernio drafts through existing CLI authentication."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PAGES = ("Leo's Travel Tips", "Simba World Travel")
STATE = Path(__file__).resolve().parents[2] / '.zernio-state'

class Blocked(RuntimeError):
    pass

class RejectedNoWrite(Blocked):
    """Structured validation/auth rejection, known not to create a post."""

def digest(value):
    return hashlib.sha256(value).hexdigest()

def cli_command():
    candidates = []
    if os.environ.get('SIMBA_ZERNIO_CLI_JS'):
        candidates.append(Path(os.environ['SIMBA_ZERNIO_CLI_JS']))
    executable = shutil.which('zernio')
    if executable:
        base = Path(executable).parent
        candidates += [base / 'node_modules/@zernio/cli/dist/index.js',
                       base.parent / '@zernio/cli/dist/index.js']
    caches = [Path.home() / 'AppData/Local/npm-cache/_npx']
    if os.environ.get('LOCALAPPDATA'):
        caches.append(Path(os.environ['LOCALAPPDATA']) / 'npm-cache/_npx')
    for cache in caches:
        candidates += sorted(cache.glob('*/node_modules/@zernio/cli/dist/index.js'))
    node = shutil.which('node')
    if node:
        for path in candidates:
            if path.is_file():
                return [node, str(path.resolve())]
    if executable and os.name != 'nt':
        return [executable]
    raise Blocked('ZERNIO_CLI_UNAVAILABLE')

def cli(*args):
    if not args or args[0] not in {'accounts:list', 'posts:list', 'posts:get', 'media:upload', 'posts:create'}:
        raise Blocked('UNSUPPORTED_COMMAND')
    if args[0] == 'posts:create' and '--draft' not in args:
        raise Blocked('DRAFT_FLAG_REQUIRED')
    try:
        result = subprocess.run(cli_command() + list(args), capture_output=True,
                                text=True, encoding='utf-8', timeout=120, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked('CLI_FAILED_OUTCOME_UNKNOWN; no automatic write retry') from None
    if result.returncode:
        # Never forward arbitrary CLI output, headers or credentials.
        try:
            error = json.loads(result.stderr)
            status = error.get('status') if isinstance(error, dict) else None
        except ValueError:
            status = None
        if type(status) is int and status in {400, 401, 403, 404, 413, 415, 422, 429}:
            raise RejectedNoWrite(f'ZERNIO_REJECTED_HTTP_{status}; no post created; fix cause before rerun')
        raise Blocked('CLI_FAILED_OUTCOME_UNKNOWN; check connectivity/account; no automatic write retry')
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or data.get('error'):
            raise ValueError()
        return data
    except ValueError:
        raise Blocked('CLI_INVALID_JSON_OUTCOME_UNKNOWN') from None

def select_page(page, run):
    if page not in PAGES:
        raise Blocked("PAGE_REQUIRED: Leo's Travel Tips или Simba World Travel?")
    accounts = run('accounts:list').get('accounts')
    if not isinstance(accounts, list):
        raise Blocked('INVALID_ACCOUNTS_RESPONSE')
    matches = [a for a in accounts if a.get('displayName') == page
               and a.get('platform') == 'facebook' and a.get('isActive') is True]
    if len(matches) != 1 or not matches[0].get('_id', matches[0].get('id')):
        raise Blocked('PAGE_NOT_UNIQUE_OR_INACTIVE')
    return matches[0].get('_id', matches[0].get('id'))

def validate(package, page):
    if page not in PAGES:
        raise Blocked("PAGE_REQUIRED: Leo's Travel Tips или Simba World Travel?")
    fields = {'packageId', 'content', 'image', 'status', 'textStatus', 'visualStatus'}
    if not isinstance(package, dict) or set(package) != fields:
        raise Blocked('INVALID_PACKAGE_FIELDS')
    for field in ('packageId', 'content', 'image'):
        if not isinstance(package[field], str) or not package[field].strip():
            raise Blocked('INVALID_PACKAGE')
    if (package['status'], package['textStatus'], package['visualStatus']) != (
            'PUBLICATION_PACKAGE_READY', 'APPROVED_TEXT', 'FINAL_VISUAL_READY'):
        raise Blocked('PACKAGE_NOT_APPROVED_OR_READY')
    image = Path(package['image']).resolve(strict=True)
    if not image.is_file() or image.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise Blocked('FINAL_IMAGE_REQUIRED')
    fingerprint = digest(json.dumps([package['content'], digest(image.read_bytes())],
                                    ensure_ascii=False).encode('utf-8'))
    key = digest(json.dumps([package['packageId'], page]).encode('utf-8'))
    return image, key, fingerprint

@contextmanager
def lock(path):
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Blocked('LOCKED: inspect interrupted/concurrent run before removing lock') from None
    os.close(descriptor)
    try:
        yield
    finally:
        path.unlink()

def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)

def remote_matches(run, key, fingerprint, page_name):
    matches = []
    for page in range(1, 10001):
        result = run('posts:list', '--page', str(page), '--limit', '100')
        posts, pagination = result.get('posts'), result.get('pagination')
        if not isinstance(posts, list) or not isinstance(pagination, dict):
            raise Blocked('INVALID_POST_LIST')
        pages = pagination.get('pages')
        if type(pages) is not int or pages < 0:
            raise Blocked('INVALID_PAGINATION')
        for post in posts:
            meta = post.get('metadata') or {}
            if (meta.get('simbaDraftKey') == key or (
                    meta.get('simbaFingerprint') == fingerprint and meta.get('simbaPage') == page_name)):
                matches.append(post)
        if page >= pages:
            return matches
    raise Blocked('POST_SCAN_INCOMPLETE')

def post_id(post):
    value = post.get('_id', post.get('id'))
    if not isinstance(value, str) or not value or value.startswith('-'):
        raise Blocked('INVALID_POST_ID')
    return value

def readback(run, ident, page, account, package, fingerprint, media_url):
    post = run('posts:get', ident).get('post')
    if not isinstance(post, dict) or post_id(post) != ident:
        raise Blocked('INVALID_POST_READBACK')
    if post.get('status') != 'draft' or post.get('scheduledFor') or post.get('publishNow'):
        raise Blocked('NOT_DRAFT: existing post retained')
    targets = post.get('platforms', [])
    ids = [p.get('accountId') for p in targets]
    ids = [a.get('_id', a.get('id')) if isinstance(a, dict) else a for a in ids]
    media = post.get('mediaItems', [])
    meta = post.get('metadata') or {}
    if any(target.get('status') not in (None, 'draft', 'pending')
           or any(target.get(field) for field in (
               'customContent', 'customMedia', 'scheduledFor', 'platformSpecificData'))
           for target in targets):
        raise Blocked('READBACK_MISMATCH: platform override or released target')
    if (post.get('content') != package['content'] or ids != [account]
            or len(targets) != 1 or targets[0].get('platform') != 'facebook'
            or not meta.get('simbaDraftKey') or meta.get('simbaFingerprint') != fingerprint
            or len(media) != 1 or media[0].get('type') != 'image' or media[0].get('url') != media_url):
        raise Blocked('READBACK_MISMATCH; inspect existing post')
    return {'status': 'DRAFT_VERIFIED', 'id': ident, 'page': page, 'accountId': account,
            'content': post['content'], 'mediaItems': [
                {'type': m.get('type'), 'url': m.get('url')} for m in media],
            'remoteStatus': post['status']}

def draft(package, page=None, send=False, state_dir=STATE, run=cli):
    image, key, fingerprint = validate(package, page)
    if not send:
        return {'status': 'DRY_RUN', 'page': page, 'content': package['content'],
                'image': str(image), 'draftKey': key, 'fingerprint': fingerprint, 'remote_writes': False}
    account = select_page(page, run)
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    record_path = state_dir / (key + '.json')
    payload_key = digest(json.dumps([fingerprint, page]).encode('utf-8'))
    with lock(state_dir / (payload_key + '.payload.lock')), lock(state_dir / (key + '.lock')):
        record = json.loads(record_path.read_text(encoding='utf-8')) if record_path.exists() else {}
        if record and record.get('fingerprint') != fingerprint:
            raise Blocked('PACKAGE_CHANGED: new approval and new packageId required')
        if record.get('id'):
            return readback(run, record['id'], page, account, package, fingerprint, record['mediaUrl'])
        matches = remote_matches(run, key, fingerprint, page)
        if len(matches) > 1:
            raise Blocked('REMOTE_DUPLICATES; no write')
        if matches:
            post = matches[0]
            if (post.get('metadata') or {}).get('simbaFingerprint') != fingerprint:
                raise Blocked('PACKAGE_CHANGED: remote package differs')
            media = post.get('mediaItems') or []
            if len(media) != 1 or not media[0].get('url'):
                raise Blocked('READBACK_MISMATCH')
            record = {'id': post_id(post), 'fingerprint': fingerprint, 'mediaUrl': media[0]['url']}
            save(record_path, record)
        elif record:
            raise Blocked('OUTCOME_UNKNOWN: reconcile before retry')
        else:
            # Upload an immutable snapshot whose bytes match the approved fingerprint.
            with tempfile.TemporaryDirectory(dir=state_dir) as temporary:
                snapshot = Path(temporary) / ('final' + image.suffix.lower())
                snapshot.write_bytes(image.read_bytes())
                if validate(dict(package, image=str(snapshot)), page)[2] != fingerprint:
                    raise Blocked('IMAGE_CHANGED: approval invalid; no post created')
                record = {'fingerprint': fingerprint, 'phase': 'OUTCOME_UNKNOWN'}
                save(record_path, record)
                try:
                    upload = run('media:upload', str(snapshot))
                except RejectedNoWrite:
                    record_path.unlink()
                    raise
            url = upload.get('url')
            if not isinstance(url, str) or not url.startswith('https://'):
                raise Blocked('INVALID_MEDIA_UPLOAD')
            record['mediaUrl'] = url
            save(record_path, record)
            try:
                result = run('posts:create', '--text=' + package['content'], '--accounts', account,
                             '--media', url, '--metadata', json.dumps(
                                 {'simbaDraftKey': key, 'simbaFingerprint': fingerprint, 'simbaPage': page}), '--draft')
            except RejectedNoWrite:
                record_path.unlink()
                raise
            record['id'] = post_id(result.get('post', {}))
            save(record_path, record)
        return readback(run, record['id'], page, account, package, fingerprint, record['mediaUrl'])

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    draft_parser = commands.add_parser('draft')
    draft_parser.add_argument('package', type=Path)
    draft_parser.add_argument('--page', choices=PAGES)
    draft_parser.add_argument('--send', action='store_true', help='Create/reuse remote draft only')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            accounts = cli('accounts:list').get('accounts', [])
            result = {'status': 'CONNECTED', 'pages': [
                {'id': a.get('_id', a.get('id')), 'page': a.get('displayName'),
                 'platform': a.get('platform'), 'active': a.get('isActive')}
                for a in accounts if a.get('displayName') in PAGES], 'publish_supported_by_adapter': False}
        else:
            package = json.loads(args.package.read_text(encoding='utf-8-sig'))
            if not isinstance(package, dict):
                raise Blocked('INVALID_PACKAGE_FIELDS')
            if not Path(package.get('image', '')).is_absolute():
                package['image'] = str(args.package.resolve().parent / package.get('image', ''))
            result = draft(package, args.page, args.send)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Blocked, OSError, ValueError) as error:
        reason = str(error) if isinstance(error, Blocked) else 'LOCAL_INPUT_OR_STATE_ERROR'
        print(json.dumps({'status': 'BLOCKED', 'reason': reason}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
