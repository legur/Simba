"""Offline resolver tests: private Drive Issue -> EXISTING universal A2E schema.

Uses actual synthetic JPEG/PNG/ZIP bytes from the Rafael handoff tests.
All Drive, Wix, GitHub, A2E API calls are mocked; no spending/publication.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/"materials"))

import github_a2e_private as private
import github_a2e_universal as universal
from test_rafael_a2e_handoff import BridgeTests as Fixture

PLAN_ID="1planasset23456789012345"


class Resp:
    def __init__(self, value):
        self.value=value
    def execute(self, num_retries=0):
        return self.value


class FakeDrive:
    def __init__(self, files:dict):
        self.blobs=files
        self.reads=0
    def files(self): return self
    def get(self, fileId, fields):
        if fileId==private.FOLDER:
            return Resp({"id":private.FOLDER,
                         "mimeType":"application/vnd.google-apps.folder",
                         "capabilities":{"canAddChildren":True},
                         "permissions":[{"type":"user","role":"owner"}]})
        if fileId not in self.blobs:
            raise AssertionError("unexpected Google file ID")
        data=self.blobs[fileId]
        return Resp({"id":fileId,"parents":[private.FOLDER],
                     "size":str(len(data)),
                     "md5Checksum":hashlib.md5(data).hexdigest(),
                     "permissions":[{"type":"user","role":"owner"}]})
    def get_media(self, fileId):
        self.reads+=1
        return Resp(self.blobs[fileId])


class PrivateResolverTests(unittest.TestCase):
    def setUp(self):
        self.case=Fixture("test_selected_real_frames_and_prompts_go_to_existing_universal")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.project["assets"][2]["drive_file_id"]=PLAN_ID
        self.case.save()
        self.fake=FakeDrive({
            self.case.project["assets"][1]["drive_file_id"]:self.case.zip.read_bytes(),
            PLAN_ID:self.case.plan_file.read_bytes()
        })
        self.request={
            "kind":private.KIND,
            "project_id":self.case.pid,
            "plan_file_id":PLAN_ID,
            "storyboard_file_id":self.case.project["assets"][1]["drive_file_id"],
        }
        self.event={
            "action":"labeled","repository":{"full_name":"legur/Simba"},
            "sender":{"login":"legur"},"label":{"name":"a2e-generate-approved"},
            "issue":{"number":777,"user":{"login":"legur"},
                     "body":json.dumps(self.request)}
        }

    def _resolve(self, event=None, **kw):
        return private.resolve_private_issue(
            event or self.event,root=self.case.root,drive=self.fake,
            fetch_wix=lambda url:self.case.mock_media[url],**kw)

    def test_minimal_public_issue_reads_actual_private_bytes_and_binds_universal(self):
        self.assertEqual(set(self.request),{"kind","project_id","plan_file_id","storyboard_file_id"})
        final=self._resolve()
        body=json.loads(final["issue"]["body"])
        self.assertEqual(body["kind"],"simba_a2e_generate")
        self.assertEqual(body["max_credits"],100)
        self.assertEqual(body["project_id"],self.case.pid)
        self.assertEqual(body["selected_storyboard"],2)
        self.assertEqual(len(body["scenes"]),3)
        self.assertGreaterEqual(self.fake.reads,2)
        number,ceiling,scenes=universal.validate(final)
        self.assertEqual((number,ceiling),(777,100))
        self.assertEqual(scenes[0]["negative_prompt"],"blurry, distorted, static")
        self.assertEqual(scenes[0]["model_version"],"a2e")

    def test_untrusted_author_and_label_block_before_any_drive_read(self):
        cases=[
            dict(self.event,sender={"login":"attacker"}),
            dict(self.event,label={"name":"wrong"}),
            dict(self.event,repository={"full_name":"somewhere/else"}),
        ]
        for event in cases:
            with self.assertRaises(private.PrivateBridgeError):
                self._resolve(event)
        self.assertEqual(self.fake.reads,0)

    def test_bad_file_id_blocks_before_drive_read(self):
        self.request["plan_file_id"]="different-file-id-123"
        self.event["issue"]["body"]=json.dumps(self.request)
        with self.assertRaises(private.PrivateBridgeError):
            self._resolve()
        self.assertEqual(self.fake.reads,0)

    def test_modified_private_plan_bytes_rejected(self):
        self.fake.blobs[PLAN_ID]+=b"tamper"
        with self.assertRaises(private.PrivateBridgeError):
            self._resolve()

    def test_modified_frame_archive_rejected(self):
        self.fake.blobs[self.request["storyboard_file_id"]]+=b"tamper"
        with self.assertRaises(private.PrivateBridgeError):
            self._resolve()

    def test_private_mode_router_leaves_existing_issue_mode_unmodified(self):
        legacy=dict(self.event)
        legacy["issue"]=dict(legacy["issue"],body=json.dumps({
            "kind":"simba_a2e_generate","max_credits":100,
            "scenes":[{"name":"scene 1","image_url":self.case.plan["scenes"][0]["image_url"],
                       "prompt":self.case.plan["scenes"][0]["prompt_en"]}]}))
        retained,changed=private.perhaps_resolve(legacy)
        self.assertFalse(changed)
        self.assertEqual(retained,legacy)

    def test_universal_run_consumes_resolved_payload_without_paid_call(self):
        # Verify the existing one-time runner remains the only paid codepath.
        resolved=self._resolve()
        import tempfile
        with tempfile.TemporaryDirectory() as out, \
             patch.object(private,"perhaps_resolve",return_value=(resolved,True)), \
             patch.dict(universal.os.environ, {"A2E_API_KEY":"sk_"+"x"*20}), \
             patch.object(universal,"price",return_value=[101]), \
             patch.object(universal.core,"a2e_start") as paid:
            result=universal.run(self.event,Path(out))
            self.assertEqual(result["status"],"STOPPED")
            self.assertTrue(result["private_source_readback_verified"])
            self.assertEqual(result["lineage"]["project_id"],self.case.pid)
            paid.assert_not_called()


if __name__ == "__main__": unittest.main()
