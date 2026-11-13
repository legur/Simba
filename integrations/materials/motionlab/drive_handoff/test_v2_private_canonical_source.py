"""Synthetic-only owner-private canonical intake tests; no Drive/secrets."""
import hashlib
import json
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v2_private_canonical_source as source


class Exec:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeDrive:
    def __init__(self, data, *, shared=False, name="project.json",
                 folder_shared=False, extra_user=False):
        self.raw = json.dumps(data).encode()
        self.shared, self.folder_shared, self.name = shared, folder_shared, name
        self.extra_user = extra_user

    def files(self):
        return self

    def permissions(self):
        return self

    def get(self, fileId, fields):
        if fileId == "F" * 26:
            return Exec({"id":fileId,"mimeType":
                         "application/vnd.google-apps.folder","trashed":False})
        return Exec({"id":fileId,"name":self.name,"mimeType":"application/json",
                     "size":len(self.raw),"parents":["F"*26],"trashed":False})

    def list(self, fileId, fields, pageSize):
        bad = self.folder_shared if fileId == "F"*26 else self.shared
        return Exec({"permissions":[{"type":"anyone" if bad else "user",
                                      "role":"owner"}] +
                     ([{"type":"user","role":"reader"}] if self.extra_user else [])})

    def get_media(self, fileId):
        return Exec(self.raw)


class PrivateSourceTests(unittest.TestCase):
    def setUp(self):
        self.doc = {
            "id":"synthetic-tour", "stage":"VOICE_MUSIC_APPROVED",
            "sources":[], "assets":[{"id":"clip-1"}],
            "stage_handoffs":{
                "a2e_clips":{"assets":["clip-1"]},
                "voice_music":{"state":"completed",
                               "audio_lock":{"audio_revision_sha256":"a"*64}},
            }
        }

    def runcheck(self, data=None, **kwargs):
        drive = FakeDrive(data if data is not None else self.doc, **kwargs)
        return source.inspect_private_canonical(drive,
                 folder_id="F"*26,file_id="X"*26,project_id="synthetic-tour",
                 expected_sha256=hashlib.sha256(drive.raw).hexdigest())

    def test_exact_valid_private_bytes_do_not_advance_pipeline(self):
        result = self.runcheck()
        self.assertFalse(result["canonical_applied"])
        self.assertFalse(result["audio_alignment_verified"])
        self.assertFalse(result["render_authorized"])

    def test_candidate_with_historical_v1_script_rejected(self):
        doc = {**self.doc,
               "stage_handoffs":{"script":{"state":"completed"}},
               "private_staging_status":"CANDIDATE_NOT_APPROVED"}
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "CANDIDATE_NOT_APPROVED"):
            self.runcheck(doc)

    def test_file_and_folder_public_sharing_rejected(self):
        for flag in ("shared","folder_shared"):
            with self.subTest(flag=flag),self.assertRaises(
                    source.PrivateCanonicalError):
                self.runcheck(**{flag:True})

    def test_second_named_user_is_not_owner_only(self):
        with self.assertRaisesRegex(source.PrivateCanonicalError,"ACL_UNTRUSTED"):
            self.runcheck(extra_user=True)

    def test_filename_rejected(self):
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "FILE_NOT_TRUSTED"):
            self.runcheck(name="private_candidate.json")

    def test_no_voice_lock_is_not_approval(self):
        doc = {**self.doc,
               "stage_handoffs":{"a2e_clips":{"assets":["clip-1"]}}}
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "AUDIO_LOCK_REQUIRED"):
            self.runcheck(doc)

    def test_sha_mismatch(self):
        drive=FakeDrive(self.doc)
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "SHA_MISMATCH"):
            source.inspect_private_canonical(drive,folder_id="F"*26,
                file_id="X"*26,project_id="synthetic-tour",
                expected_sha256="0"*64)

    def test_duplicate_clip_approval_rejected(self):
        doc=json.loads(json.dumps(self.doc))
        doc["stage_handoffs"]["a2e_clips"]["assets"]=["clip-1","clip-1"]
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "A2E_APPROVAL_REQUIRED"):
            self.runcheck(doc)

    def test_selection_cannot_be_preapproved(self):
        doc=json.loads(json.dumps(self.doc))
        doc["stage_handoffs"]["edit_choice"]={"state":"completed"}
        with self.assertRaisesRegex(source.PrivateCanonicalError,
                                    "STAGE_INVALID"):
            self.runcheck(doc)


if __name__ == "__main__":
    unittest.main()
