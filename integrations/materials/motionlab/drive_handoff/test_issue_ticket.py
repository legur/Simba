"""Tests for existing-GitHub-secrets Drive ticket issuance. No network."""
from __future__ import annotations
import importlib.util, pathlib, unittest
from unittest.mock import patch
import datetime as dt

p=pathlib.Path(__file__).resolve().with_name("issue_ticket.py")
spec=importlib.util.spec_from_file_location("motionlab_drive_issue",p)
issuer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(issuer)

def launch():
    return {
      "schema":"bontours.motionlab.storyboard.launch/v1",
      "request_id":"prague-2027-approved", "project_id":"prague",
      "expected_input_fingerprint":"a"*64,"stage":"edit_choice",
      "options":[{"name":"A"},{"name":"B"},{"name":"C"}],
      "scenes":[{"scene_id":"s1","name":"first"}]
    }
class Tickets(unittest.TestCase):
    def test_validate_exact_three_options(self):
        source=launch()
        self.assertEqual(issuer.validate_launch(source)["request_id"],"prague-2027-approved")
        source["options"]=[{"name":"A"}]
        with self.assertRaisesRegex(issuer.TicketError,"THREE_OPTIONS_REQUIRED"):
            issuer.validate_launch(source)

    def test_reject_project_without_fingerprint(self):
        source=launch()
        source["expected_input_fingerprint"]="not-a-hash"
        with self.assertRaisesRegex(issuer.TicketError,"INVALID_EXPECTED_INPUT_FINGERPRINT"):
            issuer.validate_launch(source)

    def test_ticket_keeps_only_hash_in_private_ticket_folder(self):
        source=launch()
        writes=[]
        def fake_upload(_svc,folder,name,body):
            writes.append((folder,name,body))
            return "f"*32 if len(writes)==1 else "l"*32
        with patch.object(issuer,"read_approved_launch",return_value=source),\
             patch.object(issuer,"upload",side_effect=fake_upload),\
             patch.object(issuer.secrets,"token_hex",return_value="b"*64):
            receipt=issuer.issue(object(),"fake-file-id",now=dt.datetime(2026,11,12,tzinfo=dt.timezone.utc))
        self.assertEqual(len(writes),2)
        self.assertEqual(writes[0][0],issuer.TICKET_DIR)
        self.assertEqual(writes[1][0],issuer.LAUNCH_DIR)
        self.assertNotIn("b"*64,str(writes[0]))
        self.assertEqual(writes[1][2]["handoff"]["ticket_token"],"b"*64)
        self.assertNotIn("ticket_token",receipt)
        self.assertEqual(receipt["authorized_launch_file_id"],"l"*32)

    def test_cannot_issue_from_signed_launch_to_avoid_reuse(self):
        source=launch();source["handoff"]={"ticket_token":"sensitive"}
        with self.assertRaisesRegex(issuer.TicketError,"LAUNCH_ALREADY_HAS_HANDOFF"):
            issuer.validate_launch(source)

if __name__=="__main__":
    unittest.main()
