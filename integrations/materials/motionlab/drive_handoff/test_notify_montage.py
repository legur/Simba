"""No-network tests for safe Google Drive inbox -> GitHub issue handoff."""
import unittest
from unittest.mock import patch
import notify_montage as m

def record():
    selection={"schema":"bontours.motionlab.storyboard.selection/v1",
      "project_id":"prague","request_id":"session1",
      "expected_input_fingerprint":"a"*64,
      "decision":{"selected_option":2,"options_presented":3,"confirmation_scope":"EDIT_CHOICES_ONLY"},
      "scenes":[{"scene_id":"s1"}],
      "guards":{"run_render":False,"run_tts":False,"run_a2e":False,
       "run_paid_operations":False,"auto_publish":False,
       "preserve_approved_voice":True,"preserve_approved_music":True,
       "preserve_approved_narration":True}}
    return {
      "schema":"bontours.motionlab.drive-inbox/v1",
      "status":"SAVED_IN_DRIVE_PENDING_MONTAGE",
      "render_authorized":False,"paid_operations_authorized":False,
      "receipt_id":"22222222-2222-4222-8222-222222222222",
      "ticket_id":"A"*30,"project_id":"prague","session_id":"session1",
      "source_fingerprint":"a"*64,"selection_sha256":m.digest(selection) if hasattr(m,"digest") else __import__("hashlib").sha256(m.canonical(selection).encode()).hexdigest(),
      "selection":selection
    }
class Tests(unittest.TestCase):
    def test_normal_selection_and_consumed_ticket(self):
        data=record()
        ticket={"schema":"bontours.motionlab.drive-ticket/v1",
           "consumed_receipt_id":data["receipt_id"],
           "consumed_sha256":data["selection_sha256"],
           "project_id":data["project_id"],"session_id":data["session_id"]}
        with patch.object(m,"read_private",side_effect=[data,ticket]):
            self.assertEqual(m.validate(object(),"fake")["project_id"],"prague")
    def test_forged_hash_rejected(self):
        data=record()
        data["selection"]["decision"]["selected_option"]=3
        with patch.object(m,"read_private",return_value=data):
            with self.assertRaisesRegex(m.InboxError,"SELECTION_HASH_MISMATCH"):
                m.validate(object(),"fake")
    def test_paid_guard_rejected(self):
        data=record()
        data["selection"]["guards"]["run_render"]=True
        data["selection_sha256"]=__import__("hashlib").sha256(m.canonical(data["selection"]).encode()).hexdigest()
        with patch.object(m,"read_private",return_value=data):
            with self.assertRaisesRegex(m.InboxError,"PAID_OR_SOURCE_GUARD_VIOLATION"):
                m.validate(object(),"fake")
    def test_one_issue_when_retry_occurs(self):
        data=record()
        with patch.object(m,"notified_before",return_value=57):
            with patch.object(m,"github") as gh:
                self.assertEqual(m.notify(data,"file-id"),57)
                gh.assert_not_called()

if __name__=="__main__":unittest.main()
