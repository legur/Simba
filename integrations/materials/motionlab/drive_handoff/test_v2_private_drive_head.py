"""No owner files or secrets: test blind GitHub CAS and private-Drive boundaries."""
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

import v2_private_drive_head as head


class InMemoryHeadGitHub:
    def __init__(self,project_id="synthetic-tour"):
        self.path=head.head_path(project_id)
        self.data={
            "schema":head.SCHEMA,"project_id":project_id,"revision":0,
            "state":"UNINITIALIZED","blind_commitment":None,
            "render_authorized":False,"publication_authorized":False,
        }
        self.raw=head._json_bytes(self.data)
        self.calls=[]

    def api(self,method,path,token,payload=None):
        self.calls.append(method)
        if method=="GET":
            if path!="/contents/"+self.path+"?ref=main":
                raise AssertionError("unexpected URL")
            return {"path":self.path,"type":"file",
                    "encoding":"base64","sha":head.cas.github_blob_sha(self.raw),
                    "content":base64.b64encode(self.raw).decode()}
        if method=="PUT":
            if path!="/contents/"+self.path:
                raise AssertionError("cannot write private project")
            if payload["sha"] != head.cas.github_blob_sha(self.raw):
                raise head.cas.V2CasError("V2_CANONICAL_CAS_CONFLICT")
            updated=base64.b64decode(payload["content"])
            self.data=json.loads(updated)
            self.raw=updated
            return {"content":{"sha":head.cas.github_blob_sha(self.raw)},
                    "commit":{"sha":"b"*40}}
        raise AssertionError("unexpected method")


class PrivateBlindHeadTests(unittest.TestCase):
    def setUp(self):
        self.project="synthetic-tour"
        self.key=b"private synthetic HMAC key; never use in production"
        self.git=InMemoryHeadGitHub(self.project)
        self.env=patch.object(head.cas,"_github",side_effect=self.git.api)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_initial_head_is_only_uninitialized_metadata(self):
        old_sha,actual=head.get_head(self.project,"fake-github-token-for-synthetic-tests")
        self.assertEqual(actual["state"],"UNINITIALIZED")
        self.assertEqual(actual["revision"],0)
        self.assertIsNone(actual["blind_commitment"])
        self.assertRegex(old_sha,"^[0-9a-f]{40}$")

    def test_head_bootstrap_writes_only_hmac_no_source_or_drive_id(self):
        digest="a"*64
        current,old=head.get_head(self.project,"fake")
        next_head=head.proposed_head(self.project,old,digest,self.key,bootstrap=True)
        self.assertNotEqual(next_head["blind_commitment"],digest)
        self.assertEqual(next_head["revision"],1)
        self.assertFalse(next_head["render_authorized"])
        result=head.update_blind_head(self.project,current,next_head,"fake",apply=True)
        self.assertEqual(result["status"],"V2_PRIVATE_BLIND_HEAD_CAS_APPLIED_NO_RENDER")
        self.assertNotIn(digest,self.git.raw.decode())
        self.assertNotIn("drive.google.com",self.git.raw.decode())
        self.assertNotIn("project.json",self.git.raw.decode())
        self.assertEqual(head.get_head(self.project,"fake")[1]["state"],"READY_FOR_EDIT_CHOICE")

    def test_dryrun_never_puts_public_pointer_or_drive_source(self):
        current,old=head.get_head(self.project,"fake")
        proposed=head.proposed_head(self.project,old,"c"*64,self.key,bootstrap=True)
        result=head.update_blind_head(self.project,current,proposed,"fake",apply=False)
        self.assertEqual(result["status"],"V2_PRIVATE_HEAD_CAS_VALIDATED_NO_WRITE")
        self.assertNotIn("PUT",self.git.calls)
        self.assertEqual(self.git.data["revision"],0)

    def test_wrong_hmac_key_or_source_sha_never_accepted(self):
        initial,old=head.get_head(self.project,"fake")
        proposed=head.proposed_head(self.project,old,"c"*64,self.key,bootstrap=True)
        head.update_blind_head(self.project,initial,proposed,"fake",apply=True)
        new=head.get_head(self.project,"fake")[1]
        head.require_ready_head(self.project,new,"c"*64,self.key)
        with self.assertRaisesRegex(head.PrivateHeadError,"SOURCE_CHANGED"):
            head.require_ready_head(self.project,new,"d"*64,self.key)
        with self.assertRaisesRegex(head.PrivateHeadError,"SOURCE_CHANGED"):
            head.require_ready_head(self.project,new,"c"*64,b"different synthetic key 32bytes long!")

    def test_second_concurrent_cas_commit_is_rejected(self):
        initial,old=head.get_head(self.project,"fake")
        next_head=head.proposed_head(self.project,old,"c"*64,self.key,bootstrap=True)
        head.update_blind_head(self.project,initial,next_head,"fake",apply=True)
        with self.assertRaisesRegex(head.PrivateHeadError,"UNCERTAIN_OR_CONFLICT"):
            head.update_blind_head(self.project,initial,next_head,"fake",apply=True)
        self.assertEqual(self.git.data["revision"],1)

    def test_explicit_owner_edit_revision_does_not_authorize_render(self):
        initial,old=head.get_head(self.project,"fake")
        bootstrap=head.proposed_head(self.project,old,"c"*64,self.key,bootstrap=True)
        head.update_blind_head(self.project,initial,bootstrap,"fake",apply=True)
        current,ready=head.get_head(self.project,"fake")
        changed=head.proposed_head(self.project,ready,"e"*64,self.key,bootstrap=False)
        report=head.update_blind_head(self.project,current,changed,"fake",apply=True)
        self.assertEqual(report["new_revision"],2)
        self.assertEqual(self.git.data["state"],"EDIT_CHOICE_RECORDED")
        self.assertEqual(self.git.data["render_authorized"],False)
        self.assertEqual(self.git.data["publication_authorized"],False)
        with self.assertRaisesRegex(head.PrivateHeadError,"WRONG_STAGE"):
            head.proposed_head(self.project,changed,"f"*64,self.key,bootstrap=False)

    def test_invalid_public_head_must_not_be_trusted(self):
        self.git.data["url"]="https://drive.google.com/file/private"
        self.git.raw=head._json_bytes(self.git.data)
        with self.assertRaisesRegex(head.PrivateHeadError,"METADATA_INVALID"):
            head.get_head(self.project,"fake")

    def test_genesis_cannot_skip_to_edit_choice(self):
        _,genesis=head.get_head(self.project,"fake")
        with self.assertRaisesRegex(head.PrivateHeadError,"WRONG_STAGE"):
            head.proposed_head(self.project,genesis,"a"*64,self.key,bootstrap=False)

    def test_source_sha_is_never_public_hash_digest(self):
        first=head.commitment(self.project,"a"*64,self.key)
        second=head.commitment(self.project,"a"*64,b"another owner private secret 32 bytes")
        self.assertNotEqual(first,second)
        self.assertNotEqual(first,hashlib.sha256(("a"*64).encode()).hexdigest())
        self.assertFalse(hmac.compare_digest(first,second))

    def test_project_id_path_traversal_rejected(self):
        for invalid in ("../src","x/../../a","ALASKA", "", "../"):
            with self.subTest(invalid=invalid),self.assertRaises(head.PrivateHeadError):
                head.head_path(invalid)


if __name__=="__main__":
    unittest.main()
