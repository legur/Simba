"""Synthetic orchestration tests: never fetch, edit or expose owner media."""
from contextlib import nullcontext
import hashlib
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import v2_private_drive_head as private
from test_v2_private_drive_head import InMemoryHeadGitHub


class FakeWorkspaceSource:
    def __init__(self):
        self.document={"id":"synthetic-tour"}
        self.raw=json.dumps(self.document).encode()
        self.sha=hashlib.sha256(self.raw).hexdigest()


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.project="synthetic-tour"
        self.secret=b"synthetic private HMAC 32 bytes never for real use"
        self.state=InMemoryHeadGitHub(self.project)
        self.fakeapi=patch.object(private.cas,"_github",side_effect=self.state.api)
        self.fakeapi.start()
        self.addCleanup(self.fakeapi.stop)
        self.source=FakeWorkspaceSource()
        old,genesis=private.get_head(self.project,"dummy-token")
        prepared=private.proposed_head(self.project,genesis,
             self.source.sha,self.secret,bootstrap=True)
        private.update_blind_head(self.project,old,prepared,"dummy-token",apply=True)
        self.state.calls.clear()

    def args(self):
        return dict(svc=None,folder_id="F"*26,file_id="X"*26,
            project_id=self.project,expected_sha256=self.source.sha,
            owner_source_bytes={},
            workspace_parent=Path("/tmp/owner"),public_repo=Path("/tmp/repo"),
            private_media_root=Path("/tmp/media"),
            receipt_file_id="R"*26,github_token="dummy-token",
            secret=self.secret)

    def test_authenticated_dry_run_never_writes_private_or_github(self):
        with patch.object(private.source,"_read_private_canonical",
                          return_value=(self.source.raw,self.source.document,self.source.sha)), \
             patch.object(private.workspace,"private_stage",return_value=nullcontext(Path("/tmp/isolated"))), \
             patch.object(private.intake,"inspect_receipt",return_value={"project_id":self.project}), \
             patch.object(private.intake,"replay_private_canonical",
                          return_value=({},{"packageId":self.project},{"render_authorized":False})), \
             patch.object(private.cas,"stage_all_private_references") as stage, \
             patch.object(private,"store_immutable_snapshot") as snapshot, \
             patch.object(private,"store_owner_private_ack") as ack:
            result=private.apply_private_edit_choice(**self.args(),apply=False)
        self.assertEqual(result["status"],"V2_OWNER_SELECTION_AND_SOURCE_REPLAY_PASSED_NO_WRITE")
        self.assertFalse(result["canonical_applied"])
        self.assertNotIn("PUT",self.state.calls)
        stage.assert_not_called()
        snapshot.assert_not_called()
        ack.assert_not_called()

    def test_authenticated_apply_advances_blind_head_then_private_ack(self):
        candidate={
           "id":self.project,"stage":"EDIT_CHOICE_V2_RECORDED_AWAITING_PRIVATE_MONTAGE_PLAN",
           "assets":[{"id":"editorial synthetic metadata"}],
           "stage_handoffs":{"edit_choice":{"render_authorized":False}}
        }
        expected=(json.dumps(candidate,ensure_ascii=False,sort_keys=True,
                             indent=2)+"\n").encode()
        sha=hashlib.sha256(expected).hexdigest()
        observed=[]
        def store(folder,project,raw):
            observed.append("snapshot")
            self.assertEqual(raw,expected)
            self.assertNotIn("PUT",self.state.calls)
            return {"id":"private-owner-only-snapshot","sha256":sha}
        def writeack(svc,bundle,ack):
            observed.append("ack")
            self.assertIn("PUT",self.state.calls)
            self.assertEqual(ack["private_snapshot_sha256"],sha)
            self.assertFalse(ack["render_authorized"])
            return {"id":"private-owner-only-ack","sha256":"f"*64}
        bundle={"project_id":self.project,"receipt_id":"a"*36,
                "selection_sha256":"b"*64}
        with patch.object(private.source,"_read_private_canonical",
                          return_value=(self.source.raw,self.source.document,self.source.sha)), \
             patch.object(private.workspace,"private_stage",return_value=nullcontext(Path("/tmp/isolated"))), \
             patch.object(private.intake,"inspect_receipt",return_value=bundle), \
             patch.object(private.intake,"replay_private_canonical",
                          return_value=({},{"packageId":self.project},{"render_authorized":False})), \
             patch.object(private.cas,"stage_all_private_references",return_value={"test":"private"}) as refs, \
             patch.object(private.cas,"prepare_canonical_candidate",
                          return_value=(candidate,{"project_written":False,
                                                   "render_started":False})), \
             patch.object(private.cas,"github_cas_canonical") as validator, \
             patch.object(private,"store_immutable_snapshot",side_effect=store), \
             patch.object(private,"store_owner_private_ack",side_effect=writeack):
            result=private.apply_private_edit_choice(**self.args(),apply=True)
        self.assertEqual(result["status"],"V2_PRIVATE_DRIVE_EDIT_CHOICE_APPLIED_NO_RENDER")
        self.assertEqual(self.state.data["state"],"EDIT_CHOICE_RECORDED")
        self.assertNotIn("private-owner-only-snapshot",self.state.raw.decode())
        self.assertNotIn(sha,self.state.raw.decode())
        self.assertEqual(observed,["snapshot","ack"])
        self.assertEqual(refs.call_count,1)
        self.assertEqual(validator.call_count,1)

    def test_mismatched_owner_pinned_revision_rejected_before_receipt(self):
        badargs=self.args()
        badargs["expected_sha256"]="0"*64
        with patch.object(private.source,"_read_private_canonical",
                          return_value=(self.source.raw,self.source.document,"0"*64)), \
             patch.object(private.intake,"inspect_receipt") as ticket:
            with self.assertRaisesRegex(private.PrivateHeadError,"SOURCE_CHANGED"):
                private.apply_private_edit_choice(**badargs,apply=True)
            ticket.assert_not_called()


if __name__=="__main__":
    unittest.main()
