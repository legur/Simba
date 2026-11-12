"""Authenticate synthetic v2 Drive selection against real Python contracts.

No Google OAuth, no GitHub writes, no customer MP4, no model, no paid calls.
Original source/proposal fixture originates from existing v2 issuer tests.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
for p in (str(HERE),str(HERE.parents[2]/"video"),
          str(HERE.parents[1]),str(HERE.parents[2]),str(HERE.parents[2]/"video"/"tests")):
    if p not in sys.path:sys.path.insert(0,p)

import v2_receipt_preflight as pre
import issue_ticket as issuer
import motionlab_v2_contract as v2
import motionlab_v2_stage_writeback as stage
from test_issue_v2_ticket import IssueV2TicketTests


class PrivateDrive:
    def __init__(self):
        self.items={}
        self.calls=[]
        self._op=None
    def add(self,id,folder,name,body,mime="application/json",perms=None):
        if isinstance(body,dict):body=json.dumps(body,ensure_ascii=False).encode("utf-8")
        self.items[id]={
            "id":id,"name":name,"body":body,"parents":[folder],
            "mimeType":mime,"size":len(body),
            "md5Checksum":hashlib.md5(body).hexdigest(),
            "permissions":perms if perms is not None else [{"type":"user","role":"owner"}]
        }
    def files(self):return self
    def permissions(self):return self
    def get(self,fileId,fields=None):
        self._op=("get",fileId)
        return self
    def get_media(self,fileId):
        self._op=("media",fileId)
        return self
    def list(self,fileId,fields=None,pageSize=None):
        self._op=("perms",fileId)
        return self
    def execute(self):
        op,id=self._op
        self.calls.append((op,id))
        row=self.items[id]
        if op=="media":return row["body"]
        if op=="perms":return {"permissions":row["permissions"]}
        return {k:v for k,v in row.items() if k not in ("body","permissions")}


class V2InboxPreflightTests(unittest.TestCase):
    def setUp(self):
        owner=IssueV2TicketTests("test_three_source_pinned_proposals_and_auto_qa_required")
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        self.source=owner.source
        self.now=datetime.now(timezone.utc)
        self.ticket_id="T"*26
        self.receipt_id="e38c479b-f131-4b19-a11d-011d9ce06838"
        self.receipt_file_id="R"*26
        self.launch_file_id="L"*26
        self.private=PrivateDrive()
        self.chosen={
            "schema":v2.SELECTION,
            "project_id":self.source["project_id"],
            "request_id":self.source["request_id"],
            "expected_input_fingerprint":self.source["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.source["materials"]),
            "proposals_sha256":v2.digest(self.source["proposals"]),
            "format":"9:16",
            "next_stage":"MONTAGE_PLANNING_REVIEW",
            "decision":{
                "selected_option":1,"options_presented":3,
                "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                "explicit_approval":True,"visual_layout_edited":False,
                "user_selected_at":(self.now-timedelta(seconds=40)).isoformat()
            },
            "guards":{
                "run_render":False,"run_tts":False,"run_a2e":False,
                "run_paid_operations":False,"auto_publish":False,
                "preserve_approved_voice":True,"preserve_approved_music":True,
                "preserve_approved_narration":True
            },
            "scenes":copy.deepcopy(self.source["proposals"]["proposals"][0]["scenes"])
        }
        self.ticket={
            "schema":"bontours.motionlab.drive-ticket/v2",
            "state":"ISSUED","project_id":self.source["project_id"],
            "session_id":self.source["request_id"],
            "source_fingerprint":self.source["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.source["materials"]),
            "proposals_sha256":v2.digest(self.source["proposals"]),
            "token_sha256":"d"*64,
            "source_launch_file_id":self.launch_file_id,
            "source_launch_sha256":"",
            "issued_utc":(self.now-timedelta(minutes=20)).isoformat(),
            "expires_utc":(self.now+timedelta(hours=2)).isoformat(),
            "consumed_utc":self.now.isoformat(),
            "consumed_receipt_id":self.receipt_id,
            "consumed_sha256":v2.digest(self.chosen),
        }
        self.row={
            "schema":"bontours.motionlab.drive-inbox/v2",
            "receipt_id":self.receipt_id,"ticket_id":self.ticket_id,
            "project_id":self.source["project_id"],
            "session_id":self.source["request_id"],
            "source_fingerprint":self.source["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.source["materials"]),
            "proposals_sha256":v2.digest(self.source["proposals"]),
            "source_launch_sha256":"",
            "selection_sha256":v2.digest(self.chosen),
            "selection":self.chosen,
            "saved_utc":self.now.isoformat(),
            "status":"V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS",
            "canonical_applied":False,"render_authorized":False,
            "paid_operations_authorized":False,"published":False
        }
        self.reset_files()

    def reset_files(self):
        self.private=PrivateDrive()
        source_raw=json.dumps(self.source,ensure_ascii=False).encode("utf-8")
        self.ticket["source_launch_sha256"]=pre.digest(source_raw)
        self.row["source_launch_sha256"]=pre.digest(source_raw)
        self.private.add(self.launch_file_id,pre.LAUNCHES,
                          "approved-owner-v2.json",source_raw)
        self.private.add(self.ticket_id,pre.TICKETS,
                         "motionlab-v2-ticket.json",self.ticket)
        self.private.add(self.receipt_file_id,pre.INBOX,
                         "motionlab-v2-"+self.ticket_id+".json",self.row,
                         mime="text/plain")

    def inspect(self):
        return pre.inspect_receipt(self.private,self.receipt_file_id,now=self.now)

    def test_owner_ticket_selection_and_private_launch_are_crosschecked(self):
        bundle=self.inspect()
        self.assertEqual(bundle["status"],"V2_RECEIPT_AUTHENTICATED_PENDING_SOURCE_REPLAY")
        self.assertEqual(bundle["selection_contract_receipt_id"],
                         "motionlab:v2:"+v2.digest(self.chosen))
        self.assertEqual(bundle["source_launch_sha256"],self.ticket["source_launch_sha256"])
        self.assertFalse(bundle["render_authorized"])
        self.assertFalse(bundle["publication_authorized"])
        self.assertNotIn("ticket_token",str(bundle))
        self.assertIn(("perms",self.receipt_file_id),self.private.calls)

    def test_fail_closed_on_unconsumed_ticket_or_modified_source(self):
        self.ticket["consumed_receipt_id"]="f"*36
        self.reset_files()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_CONSUMED_TICKET_MISMATCH"):
            self.inspect()
        self.ticket["consumed_receipt_id"]=self.receipt_id
        self.reset_files()
        data=self.private.items[self.launch_file_id]
        data["body"]+=b" "
        data["size"]+=1
        data["md5Checksum"]=hashlib.md5(data["body"]).hexdigest()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_OWNER_LAUNCH_SHA_CHANGED"):
            self.inspect()

    def test_invalid_private_acl_or_folder_fails(self):
        self.private.items[self.receipt_file_id]["permissions"]=[
            {"type":"anyone","role":"reader"}]
        with self.assertRaisesRegex(pre.V2InboxError,"V2_PRIVATE_FILE_ACL_UNTRUSTED"):
            self.inspect()
        self.reset_files()
        self.private.items[self.receipt_file_id]["parents"]=["public"]
        with self.assertRaisesRegex(pre.V2InboxError,"V2_PRIVATE_FILE_OUTSIDE_FOLDER"):
            self.inspect()

    def test_different_option_replay_and_paid_guard_fail(self):
        self.chosen["decision"]["selected_option"]=2
        self.reset_files()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_SELECTION_SHA_OR_ID_MISMATCH"):
            self.inspect()
        self.ticket["consumed_sha256"]=v2.digest(self.chosen)
        self.row["selection_sha256"]=v2.digest(self.chosen)
        self.reset_files()
        # Selecting option 2 with 1st option's scenes is allowed by current
        # contract only if user deliberately edited settings, but no fake
        # source/data approval should ever be invented here.
        self.chosen["guards"]["run_tts"]=True
        self.ticket["consumed_sha256"]=v2.digest(self.chosen)
        self.row["selection_sha256"]=v2.digest(self.chosen)
        self.reset_files()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_OWNER_SELECTION_CONTRACT_INVALID"):
            self.inspect()

    def test_sha_identity_and_owner_time_window(self):
        self.row["selection_sha256"]="f"*64
        self.reset_files()
        # A mismatched consumed ticket must be rejected before inspecting
        # the selection payload. The earliest broken trust boundary wins.
        with self.assertRaisesRegex(pre.V2InboxError,"V2_CONSUMED_TICKET_MISMATCH"):
            self.inspect()
        self.row["selection_sha256"]=v2.digest(self.chosen)
        self.ticket["consumed_utc"]=(self.now+timedelta(hours=4)).isoformat()
        self.row["saved_utc"]=self.ticket["consumed_utc"]
        self.reset_files()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_TICKET_USE_TIME_INVALID"):
            self.inspect()

    def test_bad_source_proposals_are_rejected(self):
        self.source["materials"]["audio_alignment_status"]="TIMINGS_NOT_VERIFIED"
        self.reset_files()
        with self.assertRaisesRegex(pre.V2InboxError,"V2_OWNER_LAUNCH_CONTRACT_INVALID"):
            self.inspect()

    def test_canonical_replay_never_promotes_unverified_timing(self):
        bundle=self.inspect()
        with patch.object(stage,"check_current_v2",side_effect=stage.V2SourceError("AUDIO_NOT_VERIFIED")):
            with self.assertRaisesRegex(pre.V2InboxError,"V2_CANONICAL_SOURCE_OR_AUDIO_REPLAY_FAILED"):
                pre.replay_private_canonical(Path("/repo"),Path("/private"),bundle)
        with patch.object(stage,"check_current_v2",return_value=(
            {"job":Path("/private"),"project":{}} ,
            {"packageId":bundle["project_id"]},
            {"status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
             "receipt_id":bundle["selection_contract_receipt_id"],
             "render_authorized":False}
        )):
            ctx,spec,report=pre.replay_private_canonical(Path("/repo"),Path("/private"),bundle)
            self.assertEqual(spec["packageId"],bundle["project_id"])
            self.assertFalse(report["render_authorized"])


if __name__=="__main__":
    unittest.main()
