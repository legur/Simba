#!/usr/bin/env python3
"""Issue a single-project MotionLab Drive ticket via GitHub Actions OAuth.

Input: private, independently approved storyboard launch/v1 file in Launches.
Output: private ticket file in Tickets (hash only) and private launch copy with
secret capability in Launches. No credentials, tokens or launch JSON in Git/logs.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, io, json, os, re, secrets, sys
from pathlib import Path

TICKET_DIR = "1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs"
LAUNCH_DIR = "10IdAl9pS-YSqLEYFbfTIKNEoho7bWGWA"
MAX_SCENES = 24

class TicketError(Exception): pass

def validate_launch(p):
    if not isinstance(p,dict) or p.get("schema")!="bontours.motionlab.storyboard.launch/v1" or p.get("stage")!="edit_choice":
        raise TicketError("INVALID_LAUNCH_SCHEMA")
    for k,regex in [("request_id",r"[A-Za-z0-9_.:-]{4,90}"),
                    ("project_id",r"[A-Za-z0-9_-]{3,120}"),
                    ("expected_input_fingerprint",r"[0-9a-f]{64}")]:
        if not isinstance(p.get(k),str) or re.fullmatch(regex,p[k]) is None:
            raise TicketError("INVALID_"+k.upper())
    scenes,options=p.get("scenes"),p.get("options")
    if not isinstance(scenes,list) or not 1<=len(scenes)<=MAX_SCENES:
        raise TicketError("INVALID_SCENE_COUNT")
    if not isinstance(options,list) or len(options)!=3:
        raise TicketError("THREE_OPTIONS_REQUIRED")
    if p.get("handoff"):
        raise TicketError("LAUNCH_ALREADY_HAS_HANDOFF")
    previews=p.get('preview_assets',[])
    if not isinstance(previews,list) or len(previews)>24:
        raise TicketError('INVALID_PREVIEW_ASSETS')
    seen=set(); total=0
    for a in previews:
        if (not isinstance(a,dict) or not isinstance(a.get('asset_id'),str)
            or a['asset_id'] in seen
            or not re.fullmatch(r'[A-Za-z0-9_-]{15,100}',a.get('file_id',''))
            or not re.fullmatch(r'[a-f0-9]{64}',a.get('sha256',''))
            or type(a.get('size_bytes')) is not int or not 1024<=a['size_bytes']<=20*1024*1024
            or a.get('mime_type')!='video/mp4'):
            raise TicketError('INVALID_PREVIEW_ASSET')
        seen.add(a['asset_id']);total+=a['size_bytes']
    if total>120*1024*1024:raise TicketError('PROJECT_PREVIEW_TOO_LARGE')
    if previews:
        by_id={a['asset_id']:a for a in previews}
        for scene in scenes:
            a=by_id.get(scene.get('asset_id'))
            if not a or (scene.get('media') or {}).get('asset_sha256')!=a['sha256']:
                raise TicketError('PREVIEW_SCENE_SOURCE_MISMATCH')
    return p

def drive():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    keys=("GDRIVE_OAUTH_CLIENT_ID","GDRIVE_OAUTH_CLIENT_SECRET","GDRIVE_OAUTH_REFRESH_TOKEN")
    if not all(os.environ.get(k) for k in keys):
        raise TicketError("GOOGLE_DRIVE_ACTIONS_SECRETS_MISSING")
    c=Credentials(token=None,refresh_token=os.environ[keys[2]],
                  client_id=os.environ[keys[0]],client_secret=os.environ[keys[1]],
                  token_uri="https://oauth2.googleapis.com/token",
                  scopes=["https://www.googleapis.com/auth/drive"])
    try:
        c.refresh(Request())
        return build("drive","v3",credentials=c,cache_discovery=False)
    except Exception:
        raise TicketError("GOOGLE_DRIVE_AUTH_FAILED") from None

def read_approved_launch(svc,file_id,include_raw=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]{15,100}",file_id):
        raise TicketError("INVALID_PRIVATE_DRIVE_FILE_ID")
    try:
        meta=svc.files().get(fileId=file_id,fields="id,name,mimeType,parents,trashed,size").execute()
        if meta.get("trashed") or meta.get("parents")!=[LAUNCH_DIR] or int(meta.get("size") or 0)>300000:
            raise TicketError("LAUNCH_NOT_IN_PRIVATE_APPROVED_FOLDER")
        raw=svc.files().get_media(fileId=file_id).execute()
        if not isinstance(raw,bytes) or len(raw)>300000:
            raise TicketError("LAUNCH_TOO_LARGE")
        source=validate_launch(json.loads(raw.decode("utf-8")))
        return (source,raw) if include_raw else source
    except TicketError:
        raise
    except Exception:
        raise TicketError("LAUNCH_READ_OR_PARSE_FAILED") from None

def upload(svc,folder,filename,data):
    from googleapiclient.http import MediaIoBaseUpload
    blob=json.dumps(data,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
    if len(blob)>320000:
        raise TicketError("PRIVATE_DRIVE_WRITE_TOO_LARGE")
    media=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/json",resumable=False)
    return svc.files().create(body={"name":filename,"mimeType":"application/json","parents":[folder]},
                               media_body=media,fields="id,name,parents").execute()["id"]

def issue(svc,launch_id,now=None):
    source,raw=read_approved_launch(svc,launch_id,include_raw=True)
    now=now or dt.datetime.now(dt.timezone.utc)
    expires=now+dt.timedelta(hours=3)
    token=secrets.token_hex(32)
    ticket={
      "schema":"bontours.motionlab.drive-ticket/v1","state":"ISSUED",
      "project_id":source["project_id"],"session_id":source["request_id"],
      "source_fingerprint":source["expected_input_fingerprint"],
      "token_sha256":hashlib.sha256(token.encode("ascii")).hexdigest(),
      "issued_utc":now.isoformat().replace("+00:00","Z"),
      "expires_utc":expires.isoformat().replace("+00:00","Z"),
      "source_launch_file_id":launch_id,
      "source_launch_sha256":hashlib.sha256(raw).hexdigest(),
      "project_read_enabled":bool(source.get('preview_assets'))
    }
    id=upload(svc,TICKET_DIR,"motionlab-"+source["request_id"]+"-ticket.json",ticket)
    output={**source,"handoff":{"schema":"bontours.motionlab.drive-handoff/v1",
                                  "ticket_id":id,"ticket_token":token}}
    # Only the owner-accessible Drive launch has the bearer token. No stdout.
    launch_copy_id=upload(svc,LAUNCH_DIR,"motionlab-"+source["request_id"]+"-authorized-launch.json",output)
    return {"ticket_file_id":id,"authorized_launch_file_id":launch_copy_id,
            "ticket_expires_utc":ticket["expires_utc"],"issued":True}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--launch-file-id",required=True)
    args=a.parse_args()
    try:
        receipt=issue(drive(),args.launch_file_id)
        # Print only Drive IDs and expiry, NEVER bearer token / selection.
        print(json.dumps(receipt,sort_keys=True))
    except TicketError as e:
        print("MOTIONLAB_TICKET_ERROR:",str(e),file=sys.stderr);return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
