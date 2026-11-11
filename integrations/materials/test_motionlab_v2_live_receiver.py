"""End-to-end offline v2 receiver tests: authenticated materials -> agent
proposals -> explicit WYSIWYG approval -> durable SQLite -> private archive ->
canonical MONTAGE_RENDERER handoff. No actual AI review is claimed here.

Uses real bytes/SHA and SQLite; fake ffprobe describes synthetic clips,
fake Google Drive/commit avoids all network, API keys and paid calls.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import motionlab_live_receiver as live
import motionlab_v2_stage_writeback as gate
import motionlab_v2_contract as v2
import motionlab_render_contract as renderer
from test_motionlab_stage_writeback import MotionLabStageWriteback


class V2LiveReceiverTests(unittest.TestCase):
    def setUp(self):
        fx=MotionLabStageWriteback(
            "test_three_existing_edit_options_launch_and_selection_to_existing_render_stage")
        fx.setUp()
        self.addCleanup(fx.doCleanups)
        self.fx=fx
        self.pvt=tempfile.TemporaryDirectory(prefix="simba-v2-private-")
        self.addCleanup(self.pvt.cleanup)
        self.root=Path(self.pvt.name)
        self.job=self.root/"example"
        self.job.mkdir()
        self.files=[]
        spec={
            "packageId":"example","size":"1080x1920",
            "sourcePost":"approved-post.md",
            "voice":{"source":"approved-voice.wav","status":"approved"},
            "music":{"source":"approved-licensed-music.mp3","status":"approved"},
            "end":{"brand":"Bon Tours"},
            "scenes":[],
        }
        for i,asset in enumerate(gate.old._clips(fx.f.project),1):
            name=f"scene-{i:02d}.mp4"
            raw=(b"v2-synthetic-clip-"+bytes([i]))*300
            (self.job/name).write_bytes(raw)
            sha=hashlib.sha256(raw).hexdigest()
            project_asset=next(x for x in fx.f.project["assets"] if x["id"]==asset["id"])
            project_asset["recorded_sha256"]=sha
            project_asset["recorded_duration_seconds"]=5.0
            project_asset["drive_file_id"]="1OriginalMP4ArchiveABCD1234"
            self.files.append({
                "scene_id":f"clip-{i:02d}","asset_id":asset["id"],
                "file":name,"duration_s":5.0,"sha256":sha,
            })
            spec["scenes"].append({
                "clip":name,"title":f"Заголовок {i}",
                "lines":[{"text":f"Подтвержденная озвучка сцены {i}"}],
                "move":"none",
            })
        fx.f.save()
        (self.job/"approved-video-spec.json").write_text(
            json.dumps(spec,ensure_ascii=False),encoding="utf-8")
        (self.job/"verified-media.json").write_text(json.dumps(self.files),encoding="utf-8")
        self.db=self.root/"sqlite"/"receiver.sqlite"
        self._patch=patch.object(renderer,"_ffprobe",side_effect=lambda path:{
            "duration_s":5.0,"width":1080,"height":1920,"fps":24.0,"has_audio":False})
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.store=live.SessionStore(self.db,self.root)
        self.session=self.store.create_v2(fx.f.root,"example")
        self.materials=self.session["launch"]
        self.proposals=self._proposals()
        self.selection=self._selection()

    def _proposals(self):
        materials=self.materials
        def layout():
            return [
                {"scene_id":s["scene_id"],"asset_id":s["asset_id"],
                 "layout":{
                     "title":{"x":50,"y":47,"scale":100},
                     "subtitle":{"x":50,"y":82,"scale":100},
                 }} for s in materials["scenes"]
            ]
        entries=[]
        for i,(camera,transition) in enumerate(
                [("cinematic-zoom","crossfade"),("float","postcard"),("push-through","whip")],1):
            entries.append({
                "option":i,"title":f"Motion Lab вариант {i}",
                "rationale":f"Actual clip observations would be entered by Motion Lab, variant {i}.",
                "recommended":i==1,
                "scenes":[{
                    "scene_id":s["scene_id"],
                    "camera":{"id":camera,"intensity_percent":30+i*5},
                    "transition":None if n==0 else {
                        "id":transition,"duration_ms":900,
                    },
                    "title_fx":"fade-rise",
                    "subtitle":{"style_id":"clean","word_motion_id":"karaoke"},
                } for n,s in enumerate(materials["scenes"])],
                "scene_layout":layout(),
            })
        return {
            "schema":v2.PROPOSALS,"project_id":"example",
            "request_id":materials["request_id"],
            "expected_input_fingerprint":materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(materials),
            "renderer_revision_sha256":renderer.revision(),
            "analysis":{
                "status":"REAL_VIDEO_REVIEWED",
                "access_mode":"owner_private_material_bundle",
                "review_notes":"Synthetic verified v2 test notes, not actual AI visual inspection.",
                "inspected_assets":[{
                    "scene_id":s["scene_id"],
                    "asset_sha256":s["media"]["asset_sha256"],
                    "evidence_kind":"full_original_mp4",
                    "scene_notes":"Synthetic unit test attestation, no real model/video review.",
                } for s in materials["scenes"]],
            },
            "proposals":entries,
        }

    def _selection(self):
        return {
            "schema":v2.SELECTION,"project_id":"example",
            "request_id":self.materials["request_id"],
            "expected_input_fingerprint":self.materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.materials),
            "proposals_sha256":v2.digest(self.proposals),
            "format":"9:16","next_stage":"MONTAGE_PLANNING_REVIEW",
            "decision":{
                "selected_option":1,"options_presented":3,
                "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                "explicit_approval":True,"visual_layout_edited":True,
                "user_selected_at":datetime.now(timezone.utc).isoformat(),
            },
            "guards":{
                "run_render":False,"run_tts":False,"run_a2e":False,
                "run_paid_operations":False,"auto_publish":False,
                "preserve_approved_voice":True,
                "preserve_approved_music":True,
                "preserve_approved_narration":True,
            },
            "scenes":copy.deepcopy(self.proposals["proposals"][0]["scenes"]),
            "scene_layout":[{
                "scene_id":s["scene_id"],"asset_id":s["asset_id"],
                "layout":{"title":{"x":55,"y":42,"scale":110},
                          "subtitle":{"x":45,"y":80,"scale":90}},
            } for s in self.materials["scenes"]],
        }

    def submit(self,selection=None):
        return self.store.accept(
            self.fx.f.root,self.session["session_id"],self.session["capability"],
            selection or self.selection)

    def test_two_phase_source_first_then_real_agent_options_then_durable_selection(self):
        self.assertEqual(self.session["status"],"AWAITING_REAL_MOTIONLAB_PROPOSALS")
        self.assertNotIn("options",self.materials)
        with self.assertRaises(Exception):
            self.submit()
        self.assertNotIn("proposals",self.store.browser_session(
            self.session["session_id"],self.session["capability"]))
        out=self.store.set_proposals_v2(self.fx.f.root,self.session["session_id"],self.proposals)
        self.assertTrue(out["proposals_saved"])
        assert self.store.set_proposals_v2(
            self.fx.f.root,self.session["session_id"],self.proposals)["idempotent"]
        view=self.store.browser_session(self.session["session_id"],self.session["capability"])
        self.assertEqual(view["proposals"],self.proposals)
        receipt=self.submit()
        self.assertTrue(receipt["persisted"])
        self.assertEqual(receipt["stage_status"],"QUEUED")
        self.assertEqual(receipt["receipt_id"],self.submit()["receipt_id"])
        with self.store.open() as db:
            row=db.execute("SELECT spec_json,selection_json FROM sessions WHERE sid=?",
                           (self.session["session_id"],)).fetchone()
        spec=json.loads(row["spec_json"])
        self.assertEqual(spec["scenes"][0]["visualLayout"]["title"]["x"],55)
        self.assertEqual(spec["scenes"][0]["visualLayout"]["subtitle"]["scale"],90)
        self.assertEqual(spec["scenes"][0]["title"],"Заголовок 1")
        self.assertEqual(json.loads(row["selection_json"])["decision"]["explicit_approval"],True)
        self.assertEqual(self.store.status(
            self.session["session_id"],self.session["capability"])["status"],"QUEUED")

    def test_tampered_media_or_visual_draft_never_acks(self):
        self.store.set_proposals_v2(self.fx.f.root,self.session["session_id"],self.proposals)
        invalid=copy.deepcopy(self.selection)
        invalid["decision"]["explicit_approval"]=False
        with self.assertRaises(Exception):self.submit(invalid)
        invalid=copy.deepcopy(self.selection)
        invalid["scene_layout"][0]["layout"]["title"]["x"]=95
        with self.assertRaises(Exception):self.submit(invalid)
        raw=(self.job/"scene-01.mp4").read_bytes()
        (self.job/"scene-01.mp4").write_bytes(b"x"+raw[1:])
        with self.assertRaises(Exception):self.submit()
        self.assertEqual(self.store.status(
            self.session["session_id"],self.session["capability"])["status"],"OPEN")

    def test_owner_only_endpoints_and_private_session_capability(self):
        api=live.API(live.Relay(self.fx.f.root,self.store),
                     "owner-key-"+"a"*48,"https://studio-owner.example")
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/v2/session",{"project_id":"example"},
                     {"Authorization":"Bearer wrong"})
        code,new=api.post("/api/motionlab/v2/session",{"project_id":"example"},
                          {"Authorization":"Bearer owner-key-"+"a"*48})
        self.assertEqual(code,201)
        self.assertNotIn("options",new["launch"])
        self.assertTrue(new["studio_url"].startswith("https://studio-owner.example/studio#"))
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/v2/proposals",{
                "session_id":self.session["session_id"],"proposals":self.proposals
            },{"Authorization":"Bearer invalid"})
        sc,response=api.post("/api/motionlab/v2/proposals",{
            "session_id":self.session["session_id"],"proposals":self.proposals
        },{"Authorization":"Bearer owner-key-"+"a"*48})
        self.assertEqual(sc,200)
        self.assertTrue(response["proposals_saved"])
        sc,result=api.post("/api/motionlab/v2/selection",{
            "session_id":self.session["session_id"],"selection":self.selection
        },{"Origin":"https://studio-owner.example",
           "X-Simba-Capability":self.session["capability"]})
        self.assertEqual(sc,200)
        self.assertTrue(result["persisted"])
        with self.assertRaises(live.ReceiverError):
            api.post("/api/motionlab/v2/selection",{
                "session_id":self.session["session_id"],"selection":self.selection
            },{"Origin":"https://other.example",
               "X-Simba-Capability":self.session["capability"]})

    def test_worker_maps_full_spec_to_private_drive_and_project_only_once(self):
        self.store.set_proposals_v2(self.fx.f.root,self.session["session_id"],self.proposals)
        receipt=self.submit()
        writes=[]
        uploaded={}
        def archive(drive,sid,kind,raw):
            sha=gate.old.digest(raw)
            fid="1MotionLabV2"+kind.replace("-","")+"987654321"
            uploaded[kind]=(fid,sha,json.loads(raw))
            return fid,sha
        def commit(root,project_id,candidate):
            writes.append(candidate)
            handoff=candidate["stage_handoffs"]["edit_choice"]
            self.assertTrue(handoff["visual_layout_preserved"])
            self.assertEqual(handoff["selected_option"],1)
            self.assertFalse(handoff["render_authorized"])
            self.assertEqual(handoff["motionlab_receipt_id"],receipt["receipt_id"])
            self.assertEqual(handoff["source_clip_ids"],[x["asset_id"] for x in self.files])
            self.assertEqual(candidate["stage_handoffs"]["voice_music"],
                             self.fx.f.project["stage_handoffs"]["voice_music"])
            return "f"*40
        relay=live.Relay(self.fx.f.root,self.store,
                         drive_factory=lambda:self.fx.drive,commit_project=commit)
        with patch.object(live,"_drive_json",side_effect=archive):
            self.assertTrue(relay.process_once())
        self.assertEqual(set(uploaded),{"materials","proposals","selection-v2","video-spec"})
        self.assertEqual(len(writes),1)
        with self.store.open() as db:
            row=db.execute("SELECT status,applied_commit FROM sessions WHERE sid=?",
                           (self.session["session_id"],)).fetchone()
        self.assertEqual(row["status"],"APPLIED")
        self.assertEqual(row["applied_commit"],"f"*40)
        self.assertFalse(relay.process_once())

    def test_restarted_worker_does_not_repeat_ambiguous_external_upload(self):
        self.store.set_proposals_v2(self.fx.f.root,self.session["session_id"],self.proposals)
        self.submit()
        # Simulate a crash after the worker claims the task, before the
        # remote provider outcome becomes known.
        claimed=self.store.next_pending()
        self.assertEqual(claimed["status"],"QUEUED")
        restarted=live.SessionStore(self.db,self.root)
        current=restarted.status(self.session["session_id"],self.session["capability"])
        self.assertEqual(current["status"],"BLOCKED")
        self.assertEqual(current["error_code"],"WORKER_INTERRUPTED_REQUIRES_RECONCILIATION")
        self.assertIsNone(restarted.next_pending())
        self.assertFalse(current["project_applied"])

    def test_after_ack_source_change_blocks_cas_not_false_applied(self):
        self.store.set_proposals_v2(self.fx.f.root,self.session["session_id"],self.proposals)
        self.submit()
        self.fx.f.project["stage_handoffs"]["voice_music"]["state"]="pending"
        self.fx.f.save()
        relay=live.Relay(self.fx.f.root,self.store,
                         drive_factory=lambda:self.fx.drive,
                         commit_project=lambda *args: self.fail("Unexpected GitHub commit"))
        self.assertTrue(relay.process_once())
        status=self.store.status(self.session["session_id"],self.session["capability"])
        self.assertEqual(status["status"],"BLOCKED")
        self.assertFalse(status["project_applied"])

if __name__=="__main__":
    unittest.main()
