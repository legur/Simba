"""Offline end-to-end contract test: selected Rafael -> existing universal A2E.

No GitHub issues, credits, remote writes or A2E API calls are made.
Synthetic photos are actual decodable image bytes, not live production art.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import handoff
import rafael_a2e_handoff as bridge
from test_rafael_archive import make_zip

WIX = "https://static.wixstatic.com/media/7fd7b8_377e66bfa46b4a87a0223b02bec5d6f0~mv2.jpg"


class BridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.private = Path(temp.name).parent / (self.root.name + "-private")
        self.private.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.private, ignore_errors=True))
        self.pid = "synthetic-bridge"
        source = self.root/"SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/approved.md"
        source.parent.mkdir(parents=True)
        source.write_text("STATUS: APPROVED\n## APPROVED_TEXT\n" + "Старинный город приветствует гостей. "*20)
        self.project = {
            "schema_version": 1, "id": self.pid, "title": "Synthetic bridge",
            "aliases": [], "updated_at": "2026-11-10", "stage": "A2E_PROMPTS_APPROVED",
            "next_action": "Create owner-ready issue request; do not start payment",
            "references": [],
            "sources": [{"path": source.relative_to(self.root).as_posix(),
                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
            "assets": [
                {"id":"script-source","kind":"script","state":"available",
                 "url":"https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9i0j/view",
                 "evidence":"Leo selected script option 2"},
                {"id":"board-asset","kind":"storyboard","state":"available",
                 "url":"https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9i0j/view",
                 "drive_file_id":"1a2b3c4d5e6f7g8h9i0j",
                 "recorded_sha256":"f"*64,
                 "drive_readback_verified": True,
                 "drive_readback_evidence":"2026-11-10 verified full remote SHA-256 readback",
                 "evidence":"Leo chose actual storyboard 2 after full preview"},
                {"id":"prompt-asset","kind":"animation_prompt","state":"available",
                 "url":"https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9i0j/view",
                 "recorded_sha256":"0"*64,
                 "evidence":"Private approved English prompts"},
            ],
            "working_asset_id":None,"approved_asset_id":None,
            "approvals":{"editorial":"pending","publication":"pending"},
        }
        self.project["stage_handoffs"] = {}
        script_rec = {
            "state":"approved","input_fingerprint":handoff.source_fingerprint(self.project),
            "selected_option":2, "options_presented":3,
            "approval_evidence":"Leo approved script option 2", "options_evidence":"private scripts",
            "assets":["script-source"]
        }
        self.project["stage_handoffs"]["script"] = script_rec
        script_receipt=handoff._validate_stage(self.project,"script",script_rec,script_rec["input_fingerprint"])[0]["receipt"]
        self.zip = make_zip(self.private)
        self.zip = self.zip.rename(self.private/"real-storyboard.zip")
        with zipfile.ZipFile(self.zip) as z:
            files={k:z.read(k) for k in z.namelist()}
        man=json.loads(files["manifest.json"])
        man["project_id"]=self.pid
        man["input_receipt"]=script_receipt
        files["manifest.json"]=json.dumps(man,ensure_ascii=False).encode()
        with zipfile.ZipFile(self.zip,"w",zipfile.ZIP_DEFLATED) as z:
            for name,data in files.items():
                z.writestr(name,data)
        self.man=man
        archive_sha=bridge.digest(self.zip.read_bytes())
        self.project["assets"][1]["recorded_sha256"]=archive_sha
        board_rec = {
            "state":"approved", "input_fingerprint":script_receipt,
            "selected_option":2,"options_presented":3,
            "approval_evidence":"Leo selected storyboard 2",
            "options_evidence":"3 private full contact sheets + Drive checksum",
            "assets":["board-asset"]
        }
        self.project["stage_handoffs"]["storyboard"]=board_rec
        board_receipt=handoff._validate_stage(self.project,"storyboard",board_rec,script_receipt)[0]["receipt"]
        prompt_rec = {
            "state":"approved","input_fingerprint":board_receipt,
            "selected_option":1,"options_presented":3,
            "approval_evidence":"Leo selected motion prompt set 1 including total credits",
            "options_evidence":"3 English prompt packages with alternatives",
            "max_credits":100,"quoted_credits":90,
            "quote_evidence":"Checked price quote for 3 scenes",
            "assets":["prompt-asset"]
        }
        self.project["stage_handoffs"]["a2e_prompts"]=prompt_rec
        prompt_receipt=handoff._validate_stage(self.project,"a2e_prompts",prompt_rec,board_receipt)[0]["receipt"]
        scenes=[]
        self.mock_media={}
        with zipfile.ZipFile(self.zip) as z:
            for i,row in enumerate(man["options"][1]["scenes"],1):
                url=WIX.replace("377e66bfa46b4a87a0223b02bec5d6f0",f"377e66bfa46b4a87a0223b02bec5d6f{i}")
                self.mock_media[url]=z.read(row["image"])
                scenes.append({
                    "scene":i,
                    "frame_sha256":row["image_sha256"],
                    "image_url":url,
                    "prompt_en":f"Slow cinematic camera push with stable focus scene {i}",
                    "wix_upload_evidence":"Wix Media Manager upload, selected source frame matched",
                })
        self.plan={
            "schema_version":1,"project_id":self.pid,"stage_receipt":prompt_receipt,
            "storyboard_option":2,"prompt_option":1,
            "storyboard_archive":{"drive_file_id":self.project["assets"][1]["drive_file_id"],
                                  "sha256":archive_sha},
            "scenes":scenes
        }
        self.plan_file=self.private/"approved-a2e-plan.json"
        self.save_plan()
        self.path=self.root/f"campaigns/{self.pid}/project.json"
        self.path.parent.mkdir(parents=True)
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.project,ensure_ascii=False),encoding="utf-8")

    def save_plan(self):
        raw=json.dumps(self.plan,ensure_ascii=False,indent=2).encode()
        self.plan_file.write_bytes(raw)
        self.project["assets"][2]["recorded_sha256"]=bridge.digest(raw)

    def invoke(self, **params):
        return bridge.create_owner_issue(self.root,self.pid,self.plan_file,self.zip,
                                         fetch=lambda url:self.mock_media[url],
                                         drive_check=lambda file_id, data: True,
                                         **params)

    def test_selected_real_frames_and_prompts_go_to_existing_universal(self):
        issue,receipt=self.invoke()
        self.assertEqual(issue["kind"],"simba_a2e_generate")
        self.assertEqual(issue["max_credits"],100)
        self.assertEqual(len(issue["scenes"]),3)
        self.assertEqual(issue["scenes"][0]["prompt"],self.plan["scenes"][0]["prompt_en"])
        self.assertEqual(receipt["selected_storyboard"],2)
        self.assertEqual(receipt["selected_prompts"],1)
        self.assertEqual(len(receipt["wix_media_sha256"]),3)
        self.assertFalse(receipt["a2e_started"])
        self.assertFalse(receipt["issued"])
        self.assertEqual(receipt["paid_calls"],0)
        self.assertNotIn("drive_file_id",json.dumps(issue))
        self.assertNotIn("private",json.dumps(issue))
        self.assertNotIn("A2E_API_KEY",json.dumps(issue))

    def test_wrong_selection_or_stale_script_blocks(self):
        self.plan["storyboard_option"]=3
        self.save_plan();self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()
        self.plan["storyboard_option"]=2
        self.save_plan();self.save()
        self.project["stage_handoffs"]["storyboard"]["selected_option"]=3
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()

    def test_changed_source_or_archive_blocks(self):
        self.project["sources"][0]["sha256"]="0"*64
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()
        self.project["sources"][0]["sha256"]=hashlib.sha256((self.root/self.project["sources"][0]["path"]).read_bytes()).hexdigest()
        self.save()
        self.project["assets"][1]["recorded_sha256"]="1"*64
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()

    def test_url_allowlist_and_bad_content_blocks(self):
        bad=WIX.replace("static.wixstatic.com","hostile.example")
        self.plan["scenes"][0]["image_url"]=bad
        self.save_plan();self.save()
        with self.assertRaises(ValueError):
            self.invoke()
        self.plan["scenes"][0]["image_url"]=next(iter(self.mock_media))
        self.save_plan();self.save()
        # Another approved frame must NOT be substituted.
        mismatched=self.mock_media[self.plan["scenes"][1]["image_url"]]
        with self.assertRaises(bridge.BridgeError):
            bridge.create_owner_issue(self.root,self.pid,self.plan_file,self.zip,
                                      fetch=lambda _:mismatched,
                                      drive_check=lambda file_id, data: True)

    def test_missing_drive_readback_or_prompt_approval_blocks(self):
        self.project["assets"][1]["drive_readback_verified"]=False
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()
        self.project["assets"][1]["drive_readback_verified"]=True
        self.project["stage_handoffs"]["a2e_prompts"]["state"]="pending"
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()

    def test_budget_limit_and_quote_guard(self):
        self.project["stage_handoffs"]["a2e_prompts"]["max_credits"]=50
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()
        self.project["stage_handoffs"]["a2e_prompts"]["quoted_credits"]=0
        self.project["stage_handoffs"]["a2e_prompts"]["max_credits"]=1200
        self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()

    def test_live_drive_verification_required_before_export(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.create_owner_issue(self.root,self.pid,self.plan_file,self.zip,
                                      fetch=lambda url:self.mock_media[url],
                                      drive_check=lambda file_id, data: False)

    def test_no_unverified_wix_to_paid_issue(self):
        with self.assertRaises(bridge.BridgeError):
            self.invoke(verify_remote=False)

    def test_private_issue_write_only_outside_public_git(self):
        issue,_=self.invoke()
        with self.assertRaises(bridge.BridgeError):
            bridge.private_write(self.root/"public-issue.json",self.root,issue)
        output=self.private/"owner-issue.json"
        bridge.private_write(output,self.root,issue)
        self.assertEqual(json.loads(output.read_text()),issue)
        if os.name=="posix":
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
        with self.assertRaises(bridge.BridgeError):
            bridge.private_write(output,self.root,issue)

    def test_no_incorrect_scenes_or_changed_artifact(self):
        self.plan["scenes"]=self.plan["scenes"][:2]
        self.save_plan();self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()
        self.plan["scenes"]=self.plan["scenes"]+[dict(self.plan["scenes"][0],scene=3)]
        self.save_plan();self.save()
        with self.assertRaises(bridge.BridgeError):
            self.invoke()


if __name__=="__main__":
    unittest.main()
