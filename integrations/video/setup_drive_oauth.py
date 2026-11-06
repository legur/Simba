#!/usr/bin/env python3
"""One-time LOCAL OAuth setup for Simba A2E Drive archive.

Never commit the downloaded Google OAuth client JSON. Never print auth tokens.
Requires google-auth-oauthlib, google-api-python-client and authenticated gh CLI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_ID = "1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"


def gh_set(name: str, value: str, repo: str, kind: str = "secret") -> None:
    if not value:
        raise RuntimeError("Refusing to upload an empty GitHub " + kind)
    command = ["gh", kind, "set", name, "--repo", repo]
    # stdin instead of --body prevents secret appearing in shell process arguments.
    completed = subprocess.run(command, input=value, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=45)
    if completed.returncode != 0:
        raise RuntimeError("gh " + kind + " set failed for " + name +
                           "; check gh auth login and repository write permissions")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client-json", required=True, type=Path)
    p.add_argument("--repo", default="legur/Simba")
    p.add_argument("--expected-account", required=True)
    p.add_argument("--enable", action="store_true",
                   help="Enable scheduled workflow after all secrets are set")
    args = p.parse_args()
    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI (gh) is required; run gh auth login first")
    data = json.loads(args.client_json.read_text(encoding="utf-8"))
    installed = data.get("installed")
    if not isinstance(installed, dict) or not all(
            installed.get(key) for key in ("client_id", "client_secret")):
        raise RuntimeError("Use Google OAuth client credentials of type Desktop app")

    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    flow = InstalledAppFlow.from_client_config(data, scopes=[DRIVE_SCOPE])
    print("Authorize the intended Google Drive account in the local browser.")
    print("This requests full Drive permission; the scheduled code writes only to the designated private folder.")
    creds = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=True,
        access_type="offline", prompt="consent")
    if not creds.refresh_token:
        raise RuntimeError("Google did not return a refresh token; nothing has been saved")
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = drive.about().get(fields="user(emailAddress)").execute()
    account = (about.get("user") or {}).get("emailAddress", "").lower()
    if account != args.expected_account.strip().lower():
        raise RuntimeError("Authorized a different Google account; no secrets were saved")
    folder = drive.files().get(fileId=FOLDER_ID, fields="id,name,mimeType").execute()
    if folder.get("id") != FOLDER_ID or folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise RuntimeError("The target private archive folder is not accessible")

    gh_set("GDRIVE_OAUTH_CLIENT_ID", installed["client_id"], args.repo)
    gh_set("GDRIVE_OAUTH_CLIENT_SECRET", installed["client_secret"], args.repo)
    gh_set("GDRIVE_OAUTH_REFRESH_TOKEN", creds.refresh_token, args.repo)
    print("GitHub Actions OAuth secrets saved without printing credentials.")
    if args.enable:
        gh_set("SIMBA_A2E_DRIVE_ENABLED", "true", args.repo, kind="variable")
        print("Auto-archive enabled (scheduled every 20 minutes).")
    else:
        print("Auto-archive remains DISABLED. After checking settings, enable the GitHub Actions variable SIMBA_A2E_DRIVE_ENABLED=true.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
