"""A2E writeback: offline tests with actual archived MP4-like byte streams.

Remote A2E and Google Drive are mocked. The ffprobe decoding step is mocked
for these tests; production uses actual ffprobe and real downloaded bytes.
Never invoke paid A2E operations, issue creation, or publication.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/"video"))
import handoff
import a2e_writeback as bridge
from test_rafael_a2e_handoff import BridgeTests as SourceFixture

ISSUE=777
RUN=44000012345
TASKS=[
 "6af09197cabbb89a76fe0d5d",
 "6af0918bdac593f36d9222d5",
 "6af0918c3172c3467b549513",
]


class FakeRequest:
    def __init__(self, data):
        self.data=data
    def execute(self, num_retries=0):
        return self.data


class Drive:
    def __init__(self):
        self.records={}
        self.bytes={}
        self.forbidden=False
        self.reads=0
        self.folder=bridge.DEFAULT_ARCHIVE
    def add(self,task_id,index):
        fid=f"1a2e-private-media-{index:03d}"
        binary=b"\x00\x00\x00\x18ftypisom"+bytes([index])*2048
        sha=hashlib.sha256(binary).hexdigest()
        md5=hashlib.md5(binary).hexdigest()
        metadata={
            "id":fid,"name":f"A2E_{task_id}.mp4","mimeType":"video/mp4",
            "size":str(len(binary)),"md5Checksum":md5,
            "parents":[self.folder],
            "appProperties":{"source":"A2E","task_id":task_id,"sha256":sha},
            "permissions":[{"type":"user","role":"owner"}],
        }
        self.records[task_id]=metadata
        self.bytes[fid]=binary
    def files(self):return self
    def get(self, fileId, fields):
        if fileId==self.folder:
            return FakeRequest({
                "id":self.folder,"mimeType":"application/vnd.google-apps.folder",
                "permissions":([
                    {"type":"user","role":"owner"},
                    *([{"type":"anyone","role":"reader"}] if self.forbidden else [])
                ])
            })
        match=next((row for row in self.records.values() if row["id"]==fileId),None)
        if match is None:
            raise ValueError("test unknown file ID")
        return FakeRequest(match)
    def get_media(self, fileId):
        self.reads+=1
        return FakeRequest(self.bytes[fileId])
    def list(self,q,fields,pageSize):
        found=re.search(r"name = 'A2E_([^']+)\.mp4'",q)
        task_id=found.group(1) if found else "none"
        row=self.records.get(task_id)
        return FakeRequest({"files":([row] if row else []),"nextPageToken":None})


class WritebackTests(unittest.TestCase):
    def setUp(self):
        fixture=SourceFixture("test_selected_real_frames_and_prompts_go_to_existing_universal")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx=fixture
        hand=handoff.make_handoff(fixture.root,fixture.path,fixture.project)
        self.assertEqual(hand["recipient"],"A2E_RUNNER")
        self.state={
            "status":"COMPLETED",
            "private_source_readback_verified":True,
            "owner_issue_number":ISSUE,
            "requested_scene_count":3,
            "max_credits":100,
            "lineage":{
                "project_id":fixture.pid,
                "handoff_sha256":hand["packet"]["receipt_sha256"],
                "selected_storyboard":2,
                "selected_prompts":1,
                "verified_at_source":False,
            },
            "scenes":[
                {"number":idx,"task_id":tid,"status":"completed"}
                for idx,tid in enumerate(TASKS,1)
            ],
        }
        self.drive=Drive()
        for index,tid in enumerate(TASKS,1):
            self.drive.add(tid,index)
        self.details=lambda tid:{"_id":tid,"current_status":"completed"}
        self.ffprobe=lambda p:5.0

    def candidate(self,**options):
        return bridge.build_candidate(
            self.fx.root,self.fx.pid,self.state,
            owner_issue_number=ISSUE,source_run_id=RUN,
            drive=self.drive,task_detail=self.details,
            verify_video=self.ffprobe,**options)

    def test_three_verified_mp4s_routes_to_voice_music(self):
        path,updated,report=self.candidate()
        self.assertEqual(path,self.fx.path)
        self.assertEqual(report["status"],"A2E_WRITEBACK_CANDIDATE_VERIFIED_NOT_WRITTEN")
        self.assertFalse(report["project_written"])
        self.assertFalse(report["publication"])
        self.assertEqual(report["paid_calls"],0)
        self.assertEqual(report["next_recipient"],"VOICE_AND_MUSIC")
        self.assertEqual(self.drive.reads,3)
        self.assertEqual([a["task_id"] for a in updated["assets"][-3:]],TASKS)
        self.assertEqual(len(updated["stage_handoffs"]["a2e_clips"]["assets"]),3)
        self.assertEqual(updated["stage_handoffs"]["a2e_clips"]["input_fingerprint"],
                         self.state["lineage"]["handoff_sha256"])
        self.assertEqual(self.fx.project["approvals"],updated["approvals"])
        self.assertIsNone(updated["approved_asset_id"])
        self.assertIsNone(updated["working_asset_id"])
        self.assertNotIn("a2e_clips",self.fx.project["stage_handoffs"])
        self.assertNotIn("a2e_clips",json.loads(self.fx.path.read_text())["stage_handoffs"])
        outgoing=handoff.make_handoff(self.fx.root,path,updated)
        self.assertEqual(outgoing["recipient"],"VOICE_AND_MUSIC")
        self.assertEqual(outgoing["packet"]["next_stage"],"voice_music")

    def test_completed_status_required_no_partial_stage(self):
        for status in ("PARTIAL_OR_PROCESSING","STOPPED","SUBMITTED"):
            with self.subTest(status=status):
                self.state["status"]=status
                with self.assertRaises(bridge.WritebackError):
                    self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_less_completed_than_submitted_blocks_without_read(self):
        self.state["scenes"].pop()
        with self.assertRaisesRegex(bridge.WritebackError,"count differs"):
            self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_empty_permissions_rejected(self):
        row=self.drive.records[TASKS[0]]
        row["permissions"]=[]
        with self.assertRaises(bridge.WritebackError):
            self.candidate()

    def test_task_scene_order_duplicate_status_and_receipt_fail(self):
        self.state["scenes"][1]["number"]=3
        with self.assertRaises(bridge.WritebackError):self.candidate()
        self.state["scenes"][1]["number"]=2
        self.state["scenes"][1]["task_id"]=TASKS[0]
        with self.assertRaises(bridge.WritebackError):self.candidate()
        self.state["scenes"][1]["task_id"]=TASKS[1]
        self.state["lineage"]["handoff_sha256"]="f"*64
        with self.assertRaises(bridge.WritebackError):self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_requires_private_owner_issue_and_unchanged_user_credit_cap(self):
        for key, bad in [
            ("private_source_readback_verified",False),
            ("owner_issue_number",778),
            ("max_credits",250),
        ]:
            with self.subTest(case=key):
                previous=self.state[key]
                self.state[key]=bad
                with self.assertRaises(bridge.WritebackError):self.candidate()
                self.state[key]=previous
        self.assertEqual(self.drive.reads,0)

    def test_upstream_approval_change_blocks_no_remote_reads(self):
        self.fx.project["stage_handoffs"]["storyboard"]["selected_option"]=3
        self.fx.save()
        with self.assertRaises(bridge.WritebackError):self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_missing_archive_is_not_success(self):
        self.drive.records.pop(TASKS[1])
        with self.assertRaisesRegex(bridge.WritebackError,"not yet archived"):
            self.candidate()
        self.assertEqual(self.drive.reads,1)

    def test_drive_modified_mp4_sha_is_blocked(self):
        fid=self.drive.records[TASKS[0]]["id"]
        self.drive.bytes[fid]+=b"modified"
        with self.assertRaisesRegex(bridge.WritebackError,"mismatch"):
            self.candidate()

    def test_broad_archive_folder_permissions_block_all(self):
        self.drive.forbidden=True
        with self.assertRaises(bridge.WritebackError):self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_unconfirmed_a2e_remote_task_blocks(self):
        self.details=lambda tid:{"_id":tid,"current_status":"processing"}
        with self.assertRaisesRegex(bridge.WritebackError,"did not confirm"):
            self.candidate()
        self.assertEqual(self.drive.reads,0)

    def test_duplicate_task_cannot_be_appended_again(self):
        _,updated,_=self.candidate()
        self.fx.project=updated
        self.fx.save()
        with self.assertRaises(bridge.WritebackError):
            self.candidate()

    def test_apply_rejects_non_owner_and_non_main(self):
        path,updated,_=self.candidate()
        current=path.read_bytes()
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(bridge.WritebackError):
                bridge.apply_candidate(self.fx.root,path,updated,
                    original_sha256=hashlib.sha256(current).hexdigest())
        self.assertEqual(path.read_bytes(),current)

    def test_owner_local_atomic_apply_when_explicitly_authorized(self):
        path,updated,_=self.candidate()
        current=path.read_bytes()
        trusted={
            "GITHUB_REPOSITORY":"legur/Simba",
            "GITHUB_EVENT_NAME":"workflow_dispatch",
            "GITHUB_REF":"refs/heads/main",
            "GITHUB_ACTOR":"legur",
            "GITHUB_RUN_ID":"100201",
        }
        with patch.dict(os.environ,trusted,clear=True):
            bridge.apply_candidate(self.fx.root,path,updated,
                original_sha256=hashlib.sha256(current).hexdigest())
        saved=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["stage_handoffs"]["a2e_clips"]["state"],"completed")
        self.assertEqual(saved["approvals"]["publication"],"pending")
        with patch.dict(os.environ,trusted,clear=True):
            with self.assertRaises(bridge.WritebackError):
                bridge.apply_candidate(self.fx.root,path,updated,
                    original_sha256=hashlib.sha256(current).hexdigest())


if __name__=="__main__":
    unittest.main()
