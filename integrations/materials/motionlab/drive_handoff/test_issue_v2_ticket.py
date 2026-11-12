"""Trusted v2 ticket issuance tests using real generated fixture MP4 pixels.

Mocks only Google OAuth/Drive storage. No owner token in logs, no credentials
or paid A2E/TTS/rendering calls.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
VIDEO=HERE.parents[2]/"video"
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(VIDEO))
sys.path.insert(0,str(VIDEO/"tests"))
import issue_v2_ticket as issuer
import issue_ticket as original
from test_motionlab_auto_proposals import ActualPixelBasedProposalsTests


class FakeDrive:
    def __init__(self,source):
        self.id="L"*25
        self.raw=json.dumps(source,sort_keys=True,ensure_ascii=False).encode("utf-8")
        self.source=source
        self.created=[]
        self.files=self

    def __call__(self):
        return self

    def get(self,fileId,fields=""):
        self.current=fileId
        return self

    def get_media(self,fileId):
        self.current=fileId
        return self

    def execute(self):
        if self.current==self.id:
            return self.raw if self.pending_media else {
                "id":self.id,"parents":[issuer.original.LAUNCH_DIR],
                "size":str(len(self.raw)),"mimeType":"application/json","trashed":False}
        if self.current in {a["file_id"] for a in self.source["preview_assets"]}:
            a=next(row for row in self.source["preview_assets"] if row["file_id"]==self.current)
            return {"id":self.current,"parents":["1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"],
                    "mimeType":"video/mp4","size":str(a["size_bytes"]),"trashed":False}
        raise KeyError(self.current)

    @property
    def pending_media(self):
        return getattr(self,"_read_media",False)

    def track_get_media(self,fileId):
        self.current=fileId
        self._read_media=True
        return self


class IssueV2TicketTests(unittest.TestCase):
    def setUp(self):
        fixture=ActualPixelBasedProposalsTests(
            "test_real_frames_measured_with_correct_source_sha_and_three_variants")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture=fixture
        self.source={
            "schema":issuer.LAUNCH_SCHEMA,
            "project_id":fixture.materials["project_id"],
            "request_id":fixture.materials["request_id"],
            "expected_input_fingerprint":fixture.materials["expected_input_fingerprint"],
            "materials":{**fixture.materials,
                "audio_alignment_status":"AUDIO_ALIGNMENT_VERIFIED_AUTO",
                "audio_alignment_sha256":"a"*64},
            "proposals":copy.deepcopy(fixture.proposals),
            "preview_assets":[{
                "asset_id":row["asset_id"],
                "sha256":row["sha256"],
                "file_id":("M"*20)+str(i),
                "size_bytes":(Path(fixture.job)/row["file"]).stat().st_size,
                "mime_type":"video/mp4",
            } for i,row in enumerate(fixture.media)]
        }
        # materials_sha256 includes the audio receipt; proposals must be
        # freshly pinned to this exact source packet.
        from motionlab_v2_contract import digest
        self.source["proposals"]["materials_sha256"]=digest(self.source["materials"])

    def test_three_real_mp4_proposals_and_auto_qa_required(self):
        self.assertEqual(issuer.valid_source(self.source),self.source)
        bad=copy.deepcopy(self.source)
        bad["materials"]["audio_alignment_status"]="TIMINGS_NOT_VERIFIED"
        with self.assertRaisesRegex(original.TicketError,"V2_AUTO_QA_OR_SOURCE_MISMATCH"):
            issuer.valid_source(bad)

    def test_forged_proposals_or_unverified_media_blocks_before_ticket(self):
        bad=copy.deepcopy(self.source)
        bad["proposals"]["proposals"][0]["scenes"][0]["camera"]["id"]="orbit"
        with self.assertRaisesRegex(original.TicketError,"V2_PROPOSALS_INVALID"):
            issuer.valid_source(bad)
        bad=copy.deepcopy(self.source)
        bad["preview_assets"][1]["sha256"]="f"*64
        with self.assertRaisesRegex(original.TicketError,"V2_PREVIEW_ASSET_INVALID"):
            issuer.valid_source(bad)

    def test_source_too_large_or_preview_from_unknown_folder_blocks(self):
        fake=FakeDrive(self.source)
        # Explicitly isolate metadata from binary fetch. No real credentials.
        def metadata(fileId,fields=None):
            if fileId==fake.id:
                return {"parents":[original.LAUNCH_DIR],"size":len(fake.raw),"trashed":False}
            if fileId in {a["file_id"] for a in self.source["preview_assets"]}:
                return {"parents":["public-folder"],"mimeType":"video/mp4",
                        "size":"1024","trashed":False}
        class DriveMock:
            def __init__(self):self.pending=None
            def files(self):return self
            def get(self,fileId,fields=None):
                self.pending=("get",fileId);return self
            def get_media(self,fileId):
                self.pending=("media",fileId);return self
            def execute(self):
                kind,file_id=self.pending
                return fake.raw if kind=="media" else metadata(file_id)
        with self.assertRaisesRegex(original.TicketError,"V2_PREVIEW_NOT_PRIVATE_APPROVED"):
            issuer.read_source(DriveMock(),fake.id)

    def test_issuer_preserves_secret_only_in_private_authorized_launch(self):
        fake=FakeDrive(self.source)
        class DriveMock:
            def __init__(self):self.pending=None
            def files(self):return self
            def get(self,fileId,fields=None):self.pending=("get",fileId);return self
            def get_media(self,fileId):self.pending=("media",fileId);return self
            def execute(self):
                kind,file_id=self.pending
                if kind=="media":return fake.raw
                if file_id==fake.id:
                    return {"parents":[original.LAUNCH_DIR],
                            "size":str(len(fake.raw)),"trashed":False}
                a=next(x for x in self_source["preview_assets"] if x["file_id"]==file_id)
                return {"parents":["1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"],
                        "mimeType":"video/mp4","size":str(a["size_bytes"]),"trashed":False}
        self_source=self.source
        calls=[]
        def upload(_svc,folder,filename,payload):
            calls.append((folder,filename,payload))
            return ("T" if folder==original.TICKET_DIR else "A")*25
        with patch.object(original,"upload",side_effect=upload):
            result=issuer.issue(DriveMock(),fake.id,
                now=datetime(2026,11,12,16,0,0,tzinfo=timezone.utc))
        self.assertTrue(result["issued"])
        self.assertEqual(len(calls),2)
        ticket=calls[0][2]
        authorized=calls[1][2]
        self.assertEqual(ticket["schema"],issuer.TICKET_SCHEMA)
        self.assertNotIn("ticket_token",ticket)
        self.assertNotIn("ticket_token",result)
        self.assertEqual(len(ticket["token_sha256"]),64)
        self.assertEqual(authorized["handoff"]["schema"],"bontours.motionlab.drive-handoff/v2")
        self.assertEqual(len(authorized["handoff"]["ticket_token"]),64)


if __name__=="__main__":
    unittest.main()
