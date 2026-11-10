#!/usr/bin/env python3
"""Authenticated persistent Motion Lab host receiver and verified Simba stage relay.

Deploy behind an HTTPS same-origin reverse proxy. This is a companion service,
NOT Wix static hosting. Start sessions only for authenticated owner actions;
the browser receives a single-use short-lived capability, never a GitHub/Drive
credential. POST /selection validates the PR #112 contract, persists a receipt
with SQLite FULL durability, and returns it for SIMBA_MOTIONLAB_ACK. A durable
worker writes both JSON sources to private Drive, then CAS-updates exactly one
canonical project.json via GitHub. The existing push dispatcher routes Montage.

No A2E/TTS/renderer/publishing calls. Never issue an ACK before durable local
storage. An ACK means "selection safely received", not "video rendered".
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
import motionlab_stage_writeback as stage
import rafael_archive
import auto_script

ID=re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SID=re.compile(r"^[a-f0-9]{32}$")
REPO="legur/Simba"
MAX_BODY=140_000
SESSION_TTL_SECONDS=20*60


class ReceiverError(Exception):
    pass


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")


def _now() -> int:
    return int(time.time())


def _safe_repository_content(root: Path, project: str) -> Path:
    if not ID.fullmatch(project):
        raise ReceiverError("Invalid project")
    return root / "campaigns" / project / "project.json"


class SessionStore:
    """Single-owner SQLite queue; never store raw credentials in the DB."""
    def __init__(self, filename: Path):
        self.filename=filename.resolve()
        self.filename.parent.mkdir(parents=True,exist_ok=True)
        if self.filename.exists() and self.filename.is_symlink():
            raise ReceiverError("SQLite path must not be a symlink")
        self.filename.touch(mode=0o600,exist_ok=True)
        os.chmod(self.filename,0o600)
        with self.open() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS sessions(
                sid TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
                project_id TEXT NOT NULL, launch_json TEXT NOT NULL,
                created INTEGER NOT NULL, expires INTEGER NOT NULL,
                selection_json TEXT, receipt_id TEXT,
                status TEXT NOT NULL, drive_launch_id TEXT, drive_selection_id TEXT,
                applied_commit TEXT, error_code TEXT
              );
              CREATE INDEX IF NOT EXISTS sessions_status ON sessions(status);
            """)

    def open(self):
        conn=sqlite3.connect(str(self.filename),timeout=10,isolation_level=None)
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def create(self, root: Path, project_id: str, options: list[dict]) -> dict:
        sid=secrets.token_hex(16)
        token=secrets.token_urlsafe(32)
        launch=stage.build_launch(root,project_id,options,"studio-"+sid)
        created=_now()
        with self.open() as db:
            db.execute("""INSERT INTO sessions(sid,token_hash,project_id,launch_json,
                       created,expires,status) VALUES(?,?,?,?,?,?,?)""",
                       (sid,hashlib.sha256(token.encode()).hexdigest(),project_id,
                        _json_bytes(launch).decode(),created,created+SESSION_TTL_SECONDS,"OPEN"))
        return {"session_id":sid,"capability":token,"launch":launch,
                "expires_at_epoch":created+SESSION_TTL_SECONDS,
                "status":"READY_FOR_BROWSER"}

    @staticmethod
    def _auth(row, token: str) -> bool:
        return (isinstance(token,str) and 20<=len(token)<=128 and
                hmac.compare_digest(row["token_hash"],hashlib.sha256(token.encode()).hexdigest()))

    def accept(self, root: Path, sid: str, token: str, selection: dict) -> dict:
        if not SID.fullmatch(sid) or not isinstance(selection,dict):
            raise ReceiverError("Invalid selection request")
        raw=_json_bytes(selection)
        if len(raw)>MAX_BODY:
            raise ReceiverError("Selection too large")
        with self.open() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM sessions WHERE sid=?",(sid,)).fetchone()
            if row is None or not self._auth(row,token):
                raise ReceiverError("Unknown or unauthorized session")
            if row["status"] in ("QUEUED","PROCESSING","APPLIED"):
                if row["selection_json"]==raw.decode() and row["receipt_id"]:
                    db.execute("COMMIT")
                    return {"receipt_id":row["receipt_id"],"persisted":True,
                            "stage_status":row["status"],"render_started":False}
                raise ReceiverError("A session cannot accept a different decision")
            if row["status"]!="OPEN" or row["expires"]<_now():
                raise ReceiverError("Session expired or closed")
            launch=json.loads(row["launch_json"])
            # Recheck canonical stage at the moment of accepting; no stale
            # source fingerprint can become a valid user decision.
            _,project,packet=stage._open_stage(root,row["project_id"])
            stage._verify_launch(root,row["project_id"],launch,packet,project)
            receipt=stage._check_choice(launch,selection,project)
            receipt_id=receipt["receipt_id"]
            db.execute("""UPDATE sessions SET selection_json=?,receipt_id=?,
                       status='QUEUED' WHERE sid=? AND status='OPEN'""",
                       (raw.decode(),receipt_id,sid))
            db.execute("COMMIT")
        return {"receipt_id":receipt_id,"persisted":True,
                "stage_status":"QUEUED","render_started":False}

    def status(self,sid:str,token:str)->dict:
        if not SID.fullmatch(sid):
            raise ReceiverError("Invalid session ID")
        with self.open() as db:
            row=db.execute("SELECT * FROM sessions WHERE sid=?",(sid,)).fetchone()
        if row is None or not self._auth(row,token):
            raise ReceiverError("Unknown or unauthorized session")
        return {"session_id":sid,"status":row["status"],"receipt_id":row["receipt_id"],
                "project_applied":row["status"]=="APPLIED",
                "error_code":row["error_code"] if row["status"]=="BLOCKED" else None,
                "render_started":False}

    def next_pending(self):
        with self.open() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM sessions WHERE status='QUEUED' ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE sessions SET status='PROCESSING' WHERE sid=?",(row["sid"],))
            db.execute("COMMIT")
        return dict(row) if row else None

    def finish(self,sid:str,*,status:str,commit:str|None=None,error:str|None=None):
        if status not in ("APPLIED","BLOCKED"):
            raise ReceiverError("Invalid terminal status")
        with self.open() as db:
            db.execute("UPDATE sessions SET status=?,applied_commit=?,error_code=? WHERE sid=? AND status='PROCESSING'",
                       (status,commit,error,sid))


def _drive_json(drive, sid: str, kind: str, payload: bytes) -> tuple[str,str]:
    """Create-once or resume by deterministic name; no blind repeat upload."""
    if kind not in ("launch","selection") or not SID.fullmatch(sid):
        raise ReceiverError("Invalid private source name")
    folder=rafael_archive.ARCHIVE_FOLDER
    name=f"Simba_MotionLab_{sid}_{kind}.json"
    expected=stage.digest(payload)
    q=f"'{folder}' in parents and name = '{name}' and trashed = false"
    listing=rafael_archive.drive_call(drive.files().list(
        q=q,fields="nextPageToken,files(id,name,parents,size,md5Checksum)",pageSize=10))
    if listing.get("nextPageToken") or len(listing.get("files") or [])>1:
        raise ReceiverError("Ambiguous private Drive source")
    if listing.get("files"):
        file_id=listing["files"][0]["id"]
    else:
        from googleapiclient.http import MediaInMemoryUpload
        created=rafael_archive.drive_call(drive.files().create(
            body={"name":name,"parents":[folder],"mimeType":"application/json",
                  "appProperties":{"origin":"simba_motionlab_host","sha256":expected}},
            media_body=MediaInMemoryUpload(payload,mimetype="application/json",resumable=False),
            fields="id"))
        file_id=created.get("id")
        if not file_id:
            raise ReceiverError("Private Drive did not confirm file ID")
    actual,meta=stage._verified_json(drive,file_id,expected,MAX_BODY)
    if actual!=payload or meta.get("name")!=name:
        raise ReceiverError("Private Drive readback did not match exact source")
    return file_id,expected


def github_put_project(repo_root:Path, project_id:str, candidate:dict) -> str:
    """GitHub contents PUT CAS; existing branch push dispatcher gets the next stage."""
    token=os.environ.get("SIMBA_GITHUB_WRITE_TOKEN","")
    if len(token)<25:
        raise ReceiverError("GitHub write authorization missing")
    path=f"campaigns/{project_id}/project.json"
    local=_safe_repository_content(repo_root,project_id).read_bytes()
    url="https://api.github.com/repos/"+REPO+"/contents/"+quote(path,safe="/")
    def request(method,payload=None,readurl=url):
        headers={"Authorization":"Bearer "+token,"User-Agent":"simba-motionlab-live-host/1",
                 "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        raw=None
        if payload is not None:
            raw=json.dumps(payload).encode()
            headers["Content-Type"]="application/json"
        try:
            with urlopen(Request(readurl,data=raw,headers=headers,method=method),timeout=25) as response:
                return json.loads(response.read(250_000))
        except HTTPError as e:
            if e.code in (409,422):
                raise ReceiverError("GitHub project CAS conflict; reconcile before retry") from None
            raise ReceiverError("Authenticated GitHub project API failed") from None
        except Exception:
            raise ReceiverError("GitHub project API unreachable") from None
    doc=request("GET",readurl=url+"?ref=main")
    existing=base64.b64decode(doc.get("content",""))
    new=_json_bytes(candidate)
    if existing==new:
        return "ALREADY_APPLIED"
    # Do not let stale or uncommitted local source redefine the current project.
    if existing!=local or doc.get("path")!=path or not re.fullmatch(r"[a-f0-9]{40}",doc.get("sha","")):
        raise ReceiverError("Canonical main project changed; reconcile before retry")
    result=request("PUT",{
        "message":f"chore(studio): accepted Motion Lab choice for {project_id}",
        "branch":"main","sha":doc["sha"],"content":base64.b64encode(new).decode()
    })
    sha=(result.get("commit") or {}).get("sha")
    if not isinstance(sha,str) or not re.fullmatch(r"[a-f0-9]{40}",sha):
        raise ReceiverError("GitHub did not confirm project write-back")
    return sha


class Relay:
    def __init__(self,root:Path,store:SessionStore,drive_factory=None,commit_project=None):
        self.root=root.resolve()
        self.store=store
        self.drive_factory=drive_factory or auto_script.drive_client
        self.commit_project=commit_project or github_put_project

    def process_once(self)->bool:
        row=self.store.next_pending()
        if not row:
            return False
        sid=row["sid"]
        try:
            # Revalidate source and connected selection before any Drive/REST write.
            launch=json.loads(row["launch_json"])
            choice=json.loads(row["selection_json"])
            _,project,packet=stage._open_stage(self.root,row["project_id"])
            stage._verify_launch(self.root,row["project_id"],launch,packet,project)
            result=stage._check_choice(launch,choice,project)
            if result["receipt_id"]!=row["receipt_id"]:
                raise ReceiverError("Selection receipt changed after acceptance")
            drive=self.drive_factory()
            rafael_archive.check_private_folder(drive,rafael_archive.ARCHIVE_FOLDER)
            lid,lsha=_drive_json(drive,sid,"launch",row["launch_json"].encode())
            cid,csha=_drive_json(drive,sid,"selection",row["selection_json"].encode())
            _,candidate,report=stage.build_candidate(
                self.root,row["project_id"],launch_file_id=lid,launch_sha256=lsha,
                selection_file_id=cid,selection_sha256=csha,drive=drive)
            if report.get("selection_receipt_id")!=row["receipt_id"]:
                raise ReceiverError("Canonical write-back receipt differs")
            commit=self.commit_project(self.root,row["project_id"],candidate)
            self.store.finish(sid,status="APPLIED",commit=commit)
        except Exception:
            # Failed or ambiguous external write: NEVER blind-retry an
            # unknown commit/upload. An operator must reconcile the source.
            self.store.finish(sid,status="BLOCKED",error="WRITEBACK_REQUIRES_RECONCILIATION")
        return True


class API:
    """Framework-free handler logic, also tested without network sockets."""
    def __init__(self,relay:Relay,owner_secret:str,host_origin:str):
        if len(owner_secret)<32:
            raise ReceiverError("Owner secret must be 32+ characters")
        origin=urlparse(host_origin)
        if origin.scheme!="https" or not origin.netloc or origin.path not in ("","/"):
            raise ReceiverError("HTTPS host origin required")
        self.relay=relay
        self.owner_secret=owner_secret
        self.host_origin=origin.scheme+"://"+origin.netloc

    def post(self,route:str,body:dict,headers:dict)->tuple[int,dict]:
        if headers.get("Origin") not in (None,self.host_origin):
            raise ReceiverError("Cross-origin selection rejected")
        if route=="/api/motionlab/session":
            token=headers.get("Authorization","")
            if not hmac.compare_digest(token,"Bearer "+self.owner_secret):
                raise ReceiverError("Owner authorization required")
            return 201,self.relay.store.create(self.relay.root,body.get("project_id"),body.get("options"))
        if route=="/api/motionlab/selection":
            sid=body.get("session_id")
            token=headers.get("X-Simba-Capability")
            return 200,self.relay.store.accept(self.relay.root,sid,token,body.get("selection"))
        raise ReceiverError("Unsupported route")

    def get(self,route:str,headers:dict)->tuple[int,dict]:
        if headers.get("Origin") not in (None,self.host_origin):
            raise ReceiverError("Cross-origin request rejected")
        if route=="/api/motionlab/health":
            return 200,{"status":"ready","paid_calls":0}
        m=re.fullmatch(r"/api/motionlab/status/([a-f0-9]{32})",route)
        if m:
            return 200,self.relay.store.status(m.group(1),headers.get("X-Simba-Capability"))
        raise ReceiverError("Unsupported route")


def run_server(api:API,port:int):
    """Use only on localhost, with a proper authenticated HTTPS reverse proxy."""
    class Handler(BaseHTTPRequestHandler):
        def _send(self,code,body):
            raw=_json_bytes(body)
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def _headers(self):
            return {k:self.headers.get(k) for k in ("Origin","Authorization","X-Simba-Capability")}
        def do_POST(self):
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 1<=length<=MAX_BODY:
                    raise ReceiverError("Invalid request size")
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ReceiverError("Object required")
                status,result=api.post(self.path,data,self._headers())
                self._send(status,result)
            except (ReceiverError,ValueError,TypeError):
                self._send(403,{"error":"REJECTED","saved":False})
        def do_GET(self):
            try:
                status,result=api.get(self.path,self._headers())
                self._send(status,result)
            except ReceiverError:
                self._send(403,{"error":"REJECTED"})
        def log_message(self,*args):
            # Do not log capability URLs, incoming input or tokens.
            return
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    def worker():
        while True:
            try:
                api.relay.process_once()
            except Exception:
                pass
            time.sleep(1)
    threading.Thread(target=worker,daemon=True).start()
    server.serve_forever()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--sqlite",type=Path,required=True)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--drain-once",action="store_true")
    args=parser.parse_args(argv)
    relay=Relay(args.repo_root,SessionStore(args.sqlite))
    if args.drain_once:
        print(json.dumps({"processed":relay.process_once(),"paid_calls":0}))
        return 0
    api=API(relay,os.environ.get("SIMBA_MOTIONLAB_OWNER_TOKEN",""),
            os.environ.get("SIMBA_MOTIONLAB_HOST_ORIGIN",""))
    run_server(api,args.port)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
