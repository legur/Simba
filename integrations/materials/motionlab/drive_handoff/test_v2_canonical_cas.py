"""Synthetic v2 GitHub CAS and private evidence stages.

No actual Google Drive, GitHub REST mutation, ASR model, A2E/TTS, or render.
These tests prove the contract: only source-rechecked explicit approval can
produce an exact project SHA compare-and-swap and applied receipt.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
for folder in (str(HERE),str(HERE.parents[2]),str(HERE.parents[2]/"video"),
               str(HERE.parents[2]/"video"/"tests")):
    if folder not in sys.path:sys.path.insert(0,folder)

import v2_canonical_cas as cas
import v2_receipt_preflight as intake
import motionlab_v2_contract as v2
import motionlab_v2_stage_writeback as stage
from test_v2_receipt_preflight import V2InboxPreflightTests


class V2AtomicWritebackTests(unittest.TestCase):
    def setUp(self):
        f=V2InboxPreflightTests(
            "test_owner_ticket_selection_and_private_launch_are_crosschecked")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.fx=f
        self.bundle=f.inspect()
        self.root=tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.base={
            "id":self.bundle["project_id"],
            "stage":"VOICE_MUSIC_APPROVED",
            "stage_handoffs":{"voice_music":{"state":"approved","audio_lock":{"sha256":"c"*64}}},
            "assets":[],
            "approvals":{"source":"owner-approved"},
            "approved_asset_id":None,
            "working_asset_id":None
        }
        self.candidate=copy.deepcopy(self.base)
        self.candidate["stage"]="EDIT_CHOICE_V2_RECORDED_AWAITING_PRIVATE_MONTAGE_PLAN"
        self.candidate["stage_handoffs"]["edit_choice"]={
            "selection_sha256":self.bundle["selection_sha256"],
            "motionlab_receipt_id":self.bundle["selection_contract_receipt_id"],
            "render_authorized":False,
            "no_auto_publish":True,
        }
        self.raw=(json.dumps(self.base,ensure_ascii=False,indent=2)+"\n").encode()
        path=Path(self.root.name)/cas.project_path(self.bundle["project_id"])
        path.parent.mkdir(parents=True)
        path.write_bytes(self.raw)
        self.refs={
            "materials":{"id":"M"*26,"sha256":v2.digest(self.bundle["materials"])},
            "proposals":{"id":"P"*26,"sha256":v2.digest(self.bundle["proposals"])},
            "selection-v2":{"id":"S"*26,"sha256":self.bundle["selection_sha256"]},
            "video-spec":{"id":"V"*26,"sha256":v2.digest({"packageId":self.bundle["project_id"]})},
        }

    def test_dry_run_prevents_put_and_enforces_narrow_blob_sha(self):
        with patch.object(cas,"_github") as call:
            result=cas.github_cas_canonical(
                self.bundle["project_id"],cas.github_blob_sha(self.raw),
                self.raw,self.candidate,"",apply=False)
        call.assert_not_called()
        self.assertEqual(result["status"],"V2_CANONICAL_CAS_VALIDATED_NO_WRITE")
        self.assertFalse(result["render_authorized"])
        self.assertFalse(result["publication_authorized"])
        with self.assertRaisesRegex(cas.V2CasError,"V2_CANONICAL_BASE_SHA_MISMATCH"):
            cas.github_cas_canonical(self.bundle["project_id"],"f"*40,
                                     self.raw,self.candidate,"",apply=False)

    def test_exact_git_sha_is_submitted_to_one_main_branch_contents_path(self):
        oldsha=cas.github_blob_sha(self.raw)
        expected_sha=None
        def mocked(method,path,token,payload=None):
            nonlocal expected_sha
            self.assertEqual(method,"PUT")
            self.assertEqual(path,"/contents/"+cas.project_path(self.bundle["project_id"]))
            self.assertEqual(payload["sha"],oldsha)
            self.assertEqual(payload["branch"],"main")
            self.assertNotIn("password",str(payload))
            binary=base64.b64decode(payload["content"])
            parsed=json.loads(binary)
            self.assertEqual(parsed["stage"],self.candidate["stage"])
            self.assertFalse(parsed["stage_handoffs"]["edit_choice"]["render_authorized"])
            expected_sha=cas.github_blob_sha(binary)
            return {"content":{"sha":expected_sha},"commit":{"sha":"a"*40}}
        with patch.object(cas,"_github",side_effect=mocked) as transport:
            result=cas.github_cas_canonical(self.bundle["project_id"],oldsha,
                                   self.raw,self.candidate,"test-token"*5,apply=True)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(result["status"],"V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER")
        self.assertEqual(result["new_blob_sha"],expected_sha)

    def test_changed_canonical_source_or_voice_or_publication_blocks(self):
        changed=copy.deepcopy(self.candidate)
        changed["stage_handoffs"]["voice_music"]["audio_lock"]["sha256"]="x"*64
        with self.assertRaisesRegex(cas.V2CasError,"V2_UNSAFE_CANONICAL_CANDIDATE"):
            cas.github_cas_canonical(self.bundle["project_id"],
                cas.github_blob_sha(self.raw),self.raw,changed,"",apply=False)
        changed=copy.deepcopy(self.candidate)
        changed["stage_handoffs"]["edit_choice"]["render_authorized"]=True
        with self.assertRaisesRegex(cas.V2CasError,"V2_UNSAFE_CANONICAL_CANDIDATE"):
            cas.github_cas_canonical(self.bundle["project_id"],
                cas.github_blob_sha(self.raw),self.raw,changed,"",apply=False)
        self.base["stage_handoffs"]["edit_choice"]={"already":"committed"}
        stale=(json.dumps(self.base,sort_keys=True)+"\n").encode()
        with self.assertRaisesRegex(cas.V2CasError,"V2_UNSAFE_CANONICAL_CANDIDATE"):
            cas.github_cas_canonical(self.bundle["project_id"],
                cas.github_blob_sha(stale),stale,self.candidate,"",apply=False)

    def test_remote_main_bytes_must_match_checked_local_project(self):
        path=cas.project_path(self.bundle["project_id"])
        with patch.object(cas,"get_github_canonical",
                 return_value=(cas.github_blob_sha(b"different"),b"different")):
            with self.assertRaisesRegex(cas.V2CasError,
                                        "V2_GITHUB_MAIN_CHANGED_SINCE_SOURCE_REPLAY"):
                cas.github_cas_from_checked_workspace(
                    self.root.name,self.bundle,self.candidate,"x"*35)
        with patch.object(cas,"get_github_canonical",
                 return_value=(cas.github_blob_sha(self.raw),self.raw)):
            report=cas.github_cas_from_checked_workspace(
                self.root.name,self.bundle,self.candidate,"x"*35,apply=False)
            self.assertEqual(report["canonical_path"],path)

    def test_all_four_references_must_be_distinct_and_sha_bound(self):
        writes=[]
        def write(_svc,bundle,kind,value):
            writes.append(kind)
            return {
                "id":kind[0].upper()*25,
                "sha256":v2.digest(value)
            }
        # video-spec can intentionally share the first character with
        # others? Here keys begin M/P/S/V, all distinct.
        with patch.object(cas,"require_private_folder") as folder,\
             patch.object(cas,"store_private_json",side_effect=write):
            refs=cas.stage_all_private_references(object(),self.bundle,{"packageId":"test"})
        folder.assert_called_once_with(unittest.mock.ANY,cas.APPLIED)
        self.assertEqual(writes,["materials","proposals","selection-v2","video-spec"])
        self.assertEqual(len({x["id"] for x in refs.values()}),4)
        self.assertEqual(refs["selection-v2"]["sha256"],self.bundle["selection_sha256"])

    def test_only_true_successful_cas_can_emit_applied_ack(self):
        with self.assertRaisesRegex(cas.V2CasError,"V2_CAS_NOT_APPLIED_CANNOT_ACK"):
            cas.finish_applied_ack(object(),self.bundle,
               {"status":"V2_CANONICAL_CAS_VALIDATED_NO_WRITE"},self.refs)
        committed={
            "status":"V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER",
            "commit_sha":"a"*40,"new_blob_sha":"b"*40,
            "candidate_sha256":"c"*64
        }
        with patch.object(cas,"require_private_folder"),\
             patch.object(cas,"store_applied_ack",
                          return_value={"id":"A"*26,"sha256":"d"*64}):
            ack=cas.finish_applied_ack(object(),self.bundle,committed,self.refs)
        self.assertEqual(ack["status"],"V2_EDIT_CHOICE_CANONICALLY_APPLIED_AWAITING_MONTAGE_PLAN")
        self.assertEqual(ack["receipt_id"],self.bundle["receipt_id"])
        self.assertFalse(ack["render_authorized"])
        self.assertFalse(ack["published"])
        self.assertEqual(ack["paid_calls"],0)
        self.assertEqual(ack["private_ack_file_id"],"A"*26)

    def test_user_selection_requires_fresh_audio_video_replay_before_candidate(self):
        sample={"packageId":self.bundle["project_id"]}
        refs=copy.deepcopy(self.refs)
        refs["video-spec"]["sha256"]=v2.digest(sample)
        with patch.object(intake,"replay_private_canonical",
                return_value=({"project":self.base},sample,{
                    "status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
                    "receipt_id":self.bundle["selection_contract_receipt_id"],
                    "render_authorized":False
                })),\
             patch.object(stage,"build_candidate_v2",return_value=(
                self.candidate,{
                  "status":"MOTIONLAB_V2_EDIT_APPROVED_NOT_RENDERED",
                  "project_written":False,"render_started":False,
                  "publication_authorized":False
                })) as mock:
            candidate,outcome=cas.prepare_canonical_candidate(
                Path(self.root.name),Path("/private"),self.bundle,refs)
            self.assertEqual(candidate["stage"],self.candidate["stage"])
            mock.assert_called_once()
        refs["video-spec"]["sha256"]="f"*64
        with patch.object(intake,"replay_private_canonical",return_value=(
            {},sample,{"status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
                       "receipt_id":self.bundle["selection_contract_receipt_id"],
                       "render_authorized":False})):
            with self.assertRaisesRegex(cas.V2CasError,"V2_PREPARED_SPEC_CHANGED"):
                cas.prepare_canonical_candidate(
                    Path(self.root.name),Path("/private"),self.bundle,refs)


    def test_end_to_end_default_never_writes_even_with_authenticated_receipt(self):
        payload={
            "status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
            "receipt_id":self.bundle["selection_contract_receipt_id"],
            "render_authorized":False,
        }
        with patch.object(intake,"inspect_receipt",return_value=self.bundle),\
             patch.object(intake,"replay_private_canonical",
                          return_value=({"project":self.base},
                            {"packageId":self.bundle["project_id"]},payload)),\
             patch.object(cas,"stage_all_private_references") as saved,\
             patch.object(cas,"github_cas_from_checked_workspace") as commit:
            result=cas.process_owner_v2_receipt(
                object(),Path(self.root.name),Path("/private"),
                self.bundle["receipt_file_id"],apply=False)
        self.assertEqual(result["status"],"V2_PRIVATE_SOURCE_REPLAY_PASSED_NO_WRITE")
        self.assertFalse(result["canonical_applied"])
        saved.assert_not_called()
        commit.assert_not_called()

    def test_explicit_apply_only_after_full_source_and_private_references(self):
        payload={
            "status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
            "receipt_id":self.bundle["selection_contract_receipt_id"],
            "render_authorized":False,
        }
        committed={
            "status":"V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER",
            "commit_sha":"a"*40,
            "new_blob_sha":"b"*40,
            "candidate_sha256":"c"*64,
        }
        ack={
            "status":"V2_EDIT_CHOICE_CANONICALLY_APPLIED_AWAITING_MONTAGE_PLAN",
            "receipt_id":self.bundle["receipt_id"],
            "commit_sha":"a"*40,
            "private_ack_file_id":"K"*26,
            "render_authorized":False,
        }
        events=[]
        with patch.object(intake,"inspect_receipt",
                          side_effect=lambda *a,**kw:(events.append("private_receipt")
                             or self.bundle)),\
             patch.object(intake,"replay_private_canonical",
                          side_effect=lambda *a,**kw:(events.append("media_replay")
                             or ({}, {"packageId":self.bundle["project_id"]},payload))),\
             patch.object(cas,"stage_all_private_references",
                          side_effect=lambda *a,**kw:(events.append("stage_refs")
                             or self.refs)),\
             patch.object(cas,"prepare_canonical_candidate",
                          side_effect=lambda *a,**kw:(events.append("candidate")
                             or (self.candidate,{}))),\
             patch.object(cas,"github_cas_from_checked_workspace",
                          side_effect=lambda *a,**kw:(events.append("commit")
                             or committed)),\
             patch.object(cas,"finish_applied_ack",
                          side_effect=lambda *a,**kw:(events.append("ack") or ack)):
            result=cas.process_owner_v2_receipt(
                object(),Path(self.root.name),Path("/private"),
                self.bundle["receipt_file_id"],"t"*60,apply=True)
        self.assertEqual(events,["private_receipt","media_replay","stage_refs",
                                 "candidate","commit","ack"])
        self.assertTrue(result["canonical_applied"])
        self.assertFalse(result["render_authorized"])
        self.assertEqual(result["paid_calls"],0)

    def test_postcommit_ack_failure_reports_ambiguous_state(self):
        payload={
            "status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
            "receipt_id":self.bundle["selection_contract_receipt_id"],
            "render_authorized":False,
        }
        committed={
            "status":"V2_CANONICAL_EDIT_CHOICE_APPLIED_NO_RENDER",
            "commit_sha":"a"*40,"new_blob_sha":"b"*40,
            "candidate_sha256":"c"*64,
        }
        with patch.object(intake,"inspect_receipt",return_value=self.bundle),\
             patch.object(intake,"replay_private_canonical",
                          return_value=({},{"packageId":self.bundle["project_id"]},payload)),\
             patch.object(cas,"stage_all_private_references",return_value=self.refs),\
             patch.object(cas,"prepare_canonical_candidate",
                          return_value=(self.candidate,{})),\
             patch.object(cas,"github_cas_from_checked_workspace",
                          return_value=committed),\
             patch.object(cas,"finish_applied_ack",
                          side_effect=OSError("temporary private Drive outage")):
            with self.assertRaisesRegex(cas.V2CasError,
                        "V2_CAS_COMMITTED_ACK_PENDING_CHECK_GITHUB"):
                cas.process_owner_v2_receipt(
                    object(),Path(self.root.name),Path("/private"),
                    self.bundle["receipt_file_id"],"t"*60,apply=True)


if __name__=="__main__":unittest.main()
