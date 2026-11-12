"""Offline Step 5G: existing PR112 Motion Lab -> current Simba handoff.

Never generates video, voice, paid tasks, uploads files, or fakes web ACK.
All artifacts are mocked PRIVATE Drive JSON with real SHA-256/MD5 bytes.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import handoff
import motionlab_stage_writeback as m
from test_handoff import StageHandoffTests


class Reply:
    def __init__(self,x):self.x=x
    def execute(self,num_retries=0):return self.x


class PrivateDrive:
    def __init__(self):
        self.data={}
        self.folder_permissions=[{"type":"user","role":"owner"}]
        self.reads=0
    def files(self):return self
    def get(self,fileId,fields):
        if fileId==m.rafael_archive.ARCHIVE_FOLDER:
            return Reply({
                "id":fileId,"mimeType":"application/vnd.google-apps.folder",
                "permissions":self.folder_permissions,
                "capabilities":{"canAddChildren":True},
            })
        return Reply(self.data[fileId][1])
    def get_media(self,fileId):
        self.reads+=1
        return Reply(self.data[fileId][0])
    def add(self,file_id,value):
        b=json.dumps(value,ensure_ascii=False).encode("utf-8")
        self.data[file_id]=(b,{
            "id":file_id,"name":file_id+".json","mimeType":"application/json",
            "size":str(len(b)), "md5Checksum":hashlib.md5(b).hexdigest(),
            "parents":[m.rafael_archive.ARCHIVE_FOLDER],
            "permissions":[{"type":"user","role":"owner"}],
        })
        return m.digest(b)


OPTS=[
    {"name":"Классическое кино","description":"Спокойные растворения, мягкие заголовки и плавная камера",
     "label":"ЭЛЕГАНТНЫЙ",
     "settings":{"camera":"cinematic-zoom","transition":"crossfade","titleFx":"fade-rise",
                 "subtitleStyle":"clean","wordMotion":"karaoke","intensity":25}},
    {"name":"Энергичный трейлер","description":"Быстрые перемещения, динамичные титры и заметные акценты",
     "label":"ДИНАМИЧНЫЙ",
     "settings":{"camera":"push-through","transition":"whip","titleFx":"punch-zoom",
                 "subtitleStyle":"outline","wordMotion":"active-pop","intensity":70}},
    {"name":"Премиальная открытка","description":"Плавные кадры, аккуратные акценты и дорогой визуальный ритм",
     "label":"ПРЕМИУМ",
     "settings":{"camera":"float","transition":"postcard","titleFx":"light-sweep",
                 "subtitleStyle":"luxury","wordMotion":"highlight-strip","intensity":40}},
]


class MotionLabStageWriteback(unittest.TestCase):
    def setUp(self):
        f=StageHandoffTests("test_first_stage_requires_explicit_script_selection")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f=f
        receipt=handoff.source_fingerprint(f.project)
        for stage in ("script","storyboard","a2e_prompts","a2e_clips","voice_music"):
            receipt=f.complete_stage(stage,receipt)
        for row in f.project["assets"]:
            if row["kind"]=="animated_clip":
                row.update(recorded_duration_seconds=5.0,recorded_sha256="a"*64,
                           drive_file_id="1VerifiedOriginalMP4Media123")
        f.save()
        self.input_receipt=receipt
        self.drive=PrivateDrive()
        self.launch_id="1LaunchPrivateMotionLab123456"
        self.selection_id="1SelectedPrivateMotionLab1234"
        self.launch=m.build_launch(f.root,"example",OPTS,"simba-test-001")
        self.selection=self._choice()
        self.sync()

    def _choice(self):
        lines=[]
        for i,row in enumerate(self.launch["scenes"]):
            lines.append({
                "scene_id":row["scene_id"],"order":i+1,"name":row["name"],
                "duration_seconds":4.0,"asset_id":row["asset_id"],
                "camera":{"id":"float","intensity_percent":40,"approximate_3d":False},
                "transition":None if i==0 else {"id":"postcard","duration_ms":900},
                "title":{"effect_id":"light-sweep","display_text":row["title_text"]},
                "subtitles":{"style_id":"luxury","word_motion_id":"highlight-strip",
                             "preview_text":row["subtitle_preview"],
                             "timing_source":"NOT_PROVIDED_IN_STORYBOARD"},
            })
        return {
            "schema":m.selector.SCHEMA_SELECTION,
            "request_id":self.launch["request_id"],
            "project_id":"example","stage":"edit_choice",
            "expected_input_fingerprint":self.launch["expected_input_fingerprint"],
            "decision":{"selected_option":3,"options_presented":3,
                        "user_selected_at":datetime.now(timezone.utc).isoformat(),
                        "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                        "confirmation_scope":"EDIT_CHOICES_ONLY"},
            "format":"9:16","scenes":lines,
            "provenance":{"origin":"motion-lab-storyboard","mode":"embedded-bridge",
                          "requires_trusted_agent_validation":True},
            "guards":{"production_state":"PREPRODUCTION",
                      "run_render":False,"run_tts":False,"run_a2e":False,
                      "run_paid_operations":False,"auto_publish":False,
                      "preserve_approved_voice":True,
                      "preserve_approved_music":True,
                      "preserve_approved_narration":True},
            "next_stage":"MONTAGE_PLANNING_REVIEW",
        }

    def sync(self):
        self.launch_sha=self.drive.add(self.launch_id,self.launch)
        self.selection_sha=self.drive.add(self.selection_id,self.selection)

    def candidate(self):
        return m.build_candidate(
            self.f.root,"example",launch_file_id=self.launch_id,
            launch_sha256=self.launch_sha,selection_file_id=self.selection_id,
            selection_sha256=self.selection_sha,drive=self.drive)

    def test_three_existing_edit_options_launch_and_selection_to_existing_render_stage(self):
        self.assertEqual(len(self.launch["options"]),3)
        self.assertEqual(self.launch["expected_input_fingerprint"],self.input_receipt)
        self.assertEqual(self.launch["scenes"][0]["asset_id"],"animated_clip")
        self.assertNotIn("preview_url",self.launch["scenes"][0])
        path,updated,receipt=self.candidate()
        self.assertEqual(path,self.f.path)
        self.assertEqual(receipt["selection_number"],3)
        self.assertEqual(receipt["next_recipient"],"MONTAGE_RENDERER")
        self.assertEqual(receipt["next_stage"],"render")
        self.assertEqual(receipt["selection_receipt_id"],m.selector.validate(self.launch,self.selection)["receipt_id"])
        self.assertFalse(receipt["actual_render_started"])
        self.assertFalse(receipt["project_written"])
        self.assertFalse(receipt["browser_ack_sent"])
        self.assertEqual(receipt["paid_calls"],0)
        self.assertEqual(updated["stage_handoffs"]["edit_choice"]["state"],"approved")
        self.assertEqual(updated["stage_handoffs"]["edit_choice"]["assets"],
                         [updated["assets"][-1]["id"]])
        self.assertEqual(updated["approvals"],self.f.project["approvals"])
        self.assertEqual(updated["stage_handoffs"]["voice_music"],
                         self.f.project["stage_handoffs"]["voice_music"])
        self.assertFalse("edit_choice" in json.loads(path.read_text())["stage_handoffs"])
        outgoing=handoff.make_handoff(self.f.root,path,updated)
        self.assertEqual(outgoing["recipient"],"MONTAGE_RENDERER")

    def test_demo_draft_does_not_become_user_approval(self):
        self.selection["decision"]["state"]="DRAFT_NOT_DELIVERED"
        self.selection["provenance"]["mode"]="local-export"
        self.sync()
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_spoofed_source_id_and_fingerprint_block(self):
        self.selection["scenes"][0]["asset_id"]="foreign-media"
        self.sync()
        with self.assertRaises(m.MotionLabStageError):self.candidate()
        self.selection=self._choice()
        self.launch["expected_input_fingerprint"]="f"*64
        self.sync()
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_more_than_verified_clip_duration_blocks(self):
        self.selection["scenes"][0]["duration_seconds"]=15
        self.sync()
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_missing_three_distinct_options_blocks_before_read(self):
        with self.assertRaises(m.MotionLabStageError):
            m.build_launch(self.f.root,"example",[OPTS[0]]*3,"abc-123")
        broken=copy.deepcopy(self.launch)
        broken["options"][1]["settings"]=broken["options"][0]["settings"]
        self.launch=broken
        self.sync()
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_broad_drive_permissions_and_modified_bytes_block(self):
        self.drive.folder_permissions.append({"type":"anyone","role":"reader"})
        with self.assertRaises(m.MotionLabStageError):self.candidate()
        self.drive.folder_permissions.pop()
        payload,metadata=self.drive.data[self.selection_id]
        self.drive.data[self.selection_id]=(payload+b"change",metadata)
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_double_write_or_missing_current_voice_stage_block(self):
        _,candidate,_=self.candidate()
        self.f.project=candidate
        self.f.save()
        with self.assertRaises(m.MotionLabStageError):self.candidate()
        del candidate["stage_handoffs"]["voice_music"]
        self.f.project=candidate
        self.f.save()
        with self.assertRaises(m.MotionLabStageError):self.candidate()

    def test_no_write_when_not_trusted_owner_dispatch(self):
        path,updated,_=self.candidate()
        original=path.read_bytes()
        with patch.dict(os.environ,{},clear=True),self.assertRaises(
                m.a2e_writeback.WritebackError):
            m.a2e_writeback.apply_candidate(self.f.root,path,updated,
                                             original_sha256=m.digest(original))
        self.assertEqual(path.read_bytes(),original)

    def test_no_legacy_project_reused_as_new_montage(self):
        root=Path(__file__).resolve().parents[2]
        for project_id in ("prague-new-year-2027","bavaria-new-year-2027"):
            with self.subTest(project=project_id),self.assertRaises(m.MotionLabStageError):
                m._open_stage(root,project_id)


if __name__=="__main__":
    unittest.main()
