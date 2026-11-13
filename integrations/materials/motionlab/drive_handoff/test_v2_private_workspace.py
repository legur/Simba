"""Synthetic private owner-source integration tests; never use real media."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import v2_private_workspace as workspace
from test_v2_private_canonical_source import FakeDrive


class PrivateWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.repo=tempfile.TemporaryDirectory()
        self.owner=tempfile.TemporaryDirectory()
        self.addCleanup(self.repo.cleanup)
        self.addCleanup(self.owner.cleanup)
        self.path="campaigns/synthetic-tour/approved-script.txt"
        self.original=b"approved sample source exact bytes"
        self.doc={
            "id":"synthetic-tour", "stage":"VOICE_MUSIC_APPROVED",
            "sources":[{"path":self.path,
                       "sha256":hashlib.sha256(self.original).hexdigest()}],
            "references":[], "assets":[{"id":"clip-1"}],
            "stage_handoffs":{
                "a2e_clips":{"assets":["clip-1"]},
                "voice_music":{"state":"completed",
                    "audio_lock":{"audio_revision_sha256":"a"*64}}
            }
        }

    def stage(self,document=None,source=None,root=None):
        doc=document or self.doc
        raw=json.dumps(doc).encode()
        return workspace.private_stage(
            Path(root or self.owner.name),Path(self.repo.name),
            "synthetic-tour",raw,doc,{self.path: self.original if source is None else source})

    def test_private_source_staged_exactly_outside_public_repo_then_removed(self):
        with self.stage() as p:
            self.assertFalse(p.is_relative_to(Path(self.repo.name)))
            self.assertEqual((p/self.path).read_bytes(),self.original)
            self.assertEqual((p/"campaigns/synthetic-tour/project.json").read_bytes(),
                             json.dumps(self.doc).encode())
            self.assertEqual((p.stat().st_mode & 0o077),0)
        self.assertFalse(p.exists())

    def test_modified_script_fails_closed_before_stage(self):
        with self.assertRaisesRegex(workspace.PrivateWorkspaceError,
                                    "SOURCE_SHA_CHANGED"):
            with self.stage(source=b"modified, not approved"):
                self.fail("must not open workspace")

    def test_private_source_cannot_be_written_in_public_repo(self):
        with self.assertRaisesRegex(workspace.PrivateWorkspaceError,
                                    "OVERLAPS_PUBLIC_GIT"):
            with self.stage(root=self.repo.name):
                self.fail("must not open workspace")

    def test_historical_candidate_never_admitted(self):
        stale=copy.deepcopy(self.doc)
        stale["private_staging_status"]="OWNER_PRIVATE_CANDIDATE_NOT_APPROVED"
        with self.assertRaisesRegex(workspace.owner.PrivateCanonicalError,
                                    "CANDIDATE_NOT_APPROVED"):
            with self.stage(document=stale):
                self.fail("must not open workspace")

    def test_unpinned_reference_rejected(self):
        stale=copy.deepcopy(self.doc)
        stale["references"]=[{"path":"campaigns/synthetic-tour/reference.txt"}]
        with self.assertRaisesRegex(workspace.PrivateWorkspaceError,
                                    "REQUIRES_CANONICAL_SHA"):
            with self.stage(document=stale):
                self.fail("must not open workspace")

    def test_actual_studio_v2_preparer_called_from_detached_source(self):
        drive=FakeDrive(self.doc)
        sha=hashlib.sha256(drive.raw).hexdigest()
        visited=[]
        def real_stage_contract_check(root,media_root,project_id,request_id):
            self.assertEqual(project_id,"synthetic-tour")
            self.assertEqual(request_id,"synthetic-request")
            self.assertEqual((root/self.path).read_bytes(),self.original)
            self.assertFalse(root.is_relative_to(Path(self.repo.name)))
            visited.append(root)
            return {"materials":{"audio_alignment_status":"AUDIO_ALIGNMENT_VERIFIED_AUTO"},
                    "proposals":{"schema":"test-only"},
                    "owner_selection_required":True,
                    "run_render":False,"run_paid_operations":False,
                    "auto_publish":False}
        with patch("motionlab_v2_stage_writeback.prepare_automatic_v2_proposals",
                   side_effect=real_stage_contract_check) as fake:
            report=workspace.prepare_real_private_studio(
                drive,folder_id="F"*26,file_id="X"*26,
                expected_sha256=sha,project_id="synthetic-tour",
                request_id="synthetic-request",
                owner_source_bytes={self.path:self.original},
                workspace_parent=Path(self.owner.name),
                public_repo=Path(self.repo.name),
                private_media_root=Path(self.owner.name))
        self.assertTrue(visited)
        self.assertFalse(visited[0].exists())
        self.assertEqual(fake.call_count,1)
        self.assertFalse(report["run_render"])

    def test_no_auto_audio_qa_never_prepares_owner_selection(self):
        drive=FakeDrive(self.doc)
        sha=hashlib.sha256(drive.raw).hexdigest()
        with patch("motionlab_v2_stage_writeback.prepare_automatic_v2_proposals",
                   return_value={"materials":{"audio_alignment_status":"TIMINGS_NOT_VERIFIED"},
                                 "owner_selection_required":True,
                                 "run_render":False,
                                 "run_paid_operations":False,
                                 "auto_publish":False}):
            with self.assertRaisesRegex(workspace.PrivateWorkspaceError,
                                        "PREPARATION_NOT_AUTHORIZED"):
                workspace.prepare_real_private_studio(
                    drive,folder_id="F"*26,file_id="X"*26,
                    expected_sha256=sha,project_id="synthetic-tour",
                    request_id="synthetic-request",
                    owner_source_bytes={self.path:self.original},
                    workspace_parent=Path(self.owner.name),
                    public_repo=Path(self.repo.name),
                    private_media_root=Path(self.owner.name))


if __name__=="__main__":
    unittest.main()
