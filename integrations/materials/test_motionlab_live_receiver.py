"""Offline authenticated browser receiver tests, with real SQLite transactions.

Uses the existing Motion Lab test's approved stage fixture and synthetic
private Drive bytes. Never contacts GitHub, Wix, A2E, or Google in CI.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import motionlab_live_receiver as live
from test_motionlab_stage_writeback import MotionLabStageWriteback, OPTS


class TestMotionLabLiveReceiver(unittest.TestCase):
    def setUp(self):
        fx=MotionLabStageWriteback("test_three_existing_edit_options_launch_and_selection_to_existing_render_stage")
        fx.setUp()
        self.addCleanup(fx.doCleanups)
        self.fx=fx
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbpath=Path(self.tmp.name)/"durable.sqlite"
        self.store=live.SessionStore(self.dbpath)
        self.sess=self.store.create(fx.f.root,"example",OPTS)
        self.fx.launch=self.sess["launch"]
        self.choice=self.fx._choice()

    def accept(self,choice=None,token=None):
        return self.store.accept(self.fx.f.root,self.sess["session_id"],
                                 token or self.sess["capability"],choice or self.choice)

    def test_actual_connected_selection_durable_receipt_and_no_false_render(self):
        receipt=self.accept()
        self.assertTrue(receipt["persisted"])
        self.assertEqual(receipt["stage_status"],"QUEUED")
        self.assertFalse(receipt["render_started"])
        reopened=live.SessionStore(self.dbpath)
        status=reopened.status(self.sess["session_id"],self.sess["capability"])
        self.assertEqual(status["status"],"QUEUED")
        self.assertFalse(status["project_applied"])
        self.assertEqual(status["receipt_id"],receipt["receipt_id"])
        self.assertNotIn("edit_choice",self.fx.f.project["stage_handoffs"])
        self.assertEqual(self.accept(),receipt)
        other=copy.deepcopy(self.choice)
        other["decision"]["selected_option"]=1
        with self.assertRaises(live.ReceiverError):
            self.accept(choice=other)

    def test_invalid_selection_and_stale_source_never_ack(self):
        invalid=copy.deepcopy(self.choice)
        invalid["decision"]["state"]="DRAFT_NOT_DELIVERED"
        with self.assertRaises(Exception):
            self.accept(choice=invalid)
        self.assertEqual(self.store.status(
            self.sess["session_id"],self.sess["capability"])["status"],"OPEN")
        self.fx.f.project["stage_handoffs"]["voice_music"]["state"]="pending"
        self.fx.f.save()
        with self.assertRaises(Exception):
            self.accept()
        self.assertEqual(self.store.status(
            self.sess["session_id"],self.sess["capability"])["status"],"OPEN")

    def test_wrong_capability_and_expired_session_rejected(self):
        with self.assertRaises(live.ReceiverError):
            self.accept(token="attack"*10)
        with self.store.open() as db:
            db.execute("UPDATE sessions SET expires=0 WHERE sid=?",(self.sess["session_id"],))
        with self.assertRaises(live.ReceiverError):
            self.accept()
        self.assertEqual(self.store.status(
            self.sess["session_id"],self.sess["capability"])["status"],"OPEN")

    def test_authenticated_api_origin_owner_and_capability(self):
        relay=live.Relay(self.fx.f.root,self.store,drive_factory=lambda:self.fx.drive)
        api=live.API(relay,"owner-secret-"+("q"*36),"https://owner.example")
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/session",{"project_id":"example","options":OPTS},{
                "Authorization":"Bearer wrong","Origin":"https://owner.example"})
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/session",{"project_id":"example","options":OPTS},{
                "Authorization":"Bearer "+"owner-secret-"+("q"*36),
                "Origin":"https://evil.example"})
        new_status,new=api.post("/api/motionlab/session",{"project_id":"example","options":OPTS},{
            "Authorization":"Bearer "+"owner-secret-"+("q"*36),
            "Origin":"https://owner.example"})
        self.assertEqual(new_status,201)
        self.assertEqual(new["launch"]["stage"],"edit_choice")
        # Browser cannot access owner token to create future sessions.
        self.assertNotIn("owner-secret",json.dumps(new))
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/selection",{
                "session_id":self.sess["session_id"],"selection":self.choice
            },{"Origin":"https://owner.example","X-Simba-Capability":"bad"})
        status,value=api.post("/api/motionlab/selection",{
            "session_id":self.sess["session_id"],"selection":self.choice
        },{"Origin":"https://owner.example",
           "X-Simba-Capability":self.sess["capability"]})
        self.assertEqual(status,200)
        self.assertTrue(value["persisted"])
        _,result=api.get("/api/motionlab/status/"+self.sess["session_id"],{
            "X-Simba-Capability":self.sess["capability"],
            "Origin":"https://owner.example"})
        self.assertEqual(result["status"],"QUEUED")

    def test_worker_drains_durable_selection_using_existing_stage_validator(self):
        receipt=self.accept()
        files={}
        writes=[]
        def upload(drive,sid,kind,raw):
            payload=json.loads(raw)
            fileid="1LiveMotionLab"+("Launch" if kind=="launch" else "Choice")+"98765432"
            sha=drive.add(fileid,payload)
            files[kind]=(fileid,sha)
            return fileid,sha
        def commit(root,project,candidate):
            writes.append(candidate)
            self.assertEqual(candidate["stage_handoffs"]["edit_choice"]["state"],"approved")
            self.assertEqual(candidate["stage_handoffs"]["edit_choice"]["selected_option"],3)
            self.assertEqual(candidate["stage_handoffs"]["voice_music"],self.fx.f.project["stage_handoffs"]["voice_music"])
            return "f"*40
        relay=live.Relay(self.fx.f.root,self.store,
                         drive_factory=lambda:self.fx.drive,commit_project=commit)
        with patch.object(live,"_drive_json",side_effect=upload):
            self.assertTrue(relay.process_once())
        self.assertEqual(len(writes),1)
        self.assertEqual(set(files),{"launch","selection"})
        result=self.store.status(self.sess["session_id"],self.sess["capability"])
        self.assertEqual(result["receipt_id"],receipt["receipt_id"])
        self.assertTrue(result["project_applied"])
        self.assertEqual(result["status"],"APPLIED")
        self.assertFalse(relay.process_once())
        self.assertEqual(len(writes),1)
        # Only commit callback may write the project. No original modified by tests.
        self.assertNotIn("edit_choice",json.loads(self.fx.f.path.read_text())["stage_handoffs"])

    def test_worker_blocks_ambiguous_write_without_silent_retry(self):
        self.accept()
        def upload(drive,sid,kind,raw):
            fileid="1LiveMotionLab"+("Launch" if kind=="launch" else "Choice")+"98765432"
            return fileid,drive.add(fileid,json.loads(raw))
        relay=live.Relay(self.fx.f.root,self.store,drive_factory=lambda:self.fx.drive,
                         commit_project=lambda *args: (_ for _ in ()).throw(RuntimeError("network ambiguous")))
        with patch.object(live,"_drive_json",side_effect=upload):
            self.assertTrue(relay.process_once())
        self.assertEqual(self.store.status(
            self.sess["session_id"],self.sess["capability"])["status"],"BLOCKED")
        self.assertFalse(relay.process_once())


if __name__=="__main__":
    unittest.main()
