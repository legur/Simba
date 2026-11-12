"""Security and contract tests for no-paid MotionLab Drive automatic renderer."""
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import auto_render as m

SHA="a"*64
def fixture():
    profile=m.get_profile("alaska-voyager-2027")
    scene_ids=[f"alaska-{i:02}" for i in range(1,11)]
    originals=[];rows=[]
    for i,sid in enumerate(scene_ids):
        asset_id="a2e:test"
        originals.append({"scene_id":sid,"asset_id":asset_id,
          "duration_s":2.0,"title_text":"SCENE "+sid,
          "subtitle_preview":"Text "+sid,
          "media":{"kind":"video","asset_sha256":SHA,"duration_s":5.0625}})
        rows.append({"scene_id":sid,"asset_id":asset_id,"order":i+1,
          "duration_seconds":2.0,"title":{"display_text":"SCENE "+sid},
          "camera":{"id":"cinematic-zoom","intensity_percent":0},
          "subtitles":{"style_id":"clean","word_motion_id":"karaoke",
                       "preview_text":"Text "+sid},
          "transition":None if i==0 else {"id":"crossfade","duration_ms":900}})
    launch={"scenes":originals,"preview_assets":[{"asset_id":"a2e:test",
       "mime_type":"video/mp4","file_id":"abc",
       "size_bytes":5000000,"sha256":SHA}]}
    record={"receipt_id":profile["approved_receipt_id"],
      "selection_sha256":profile["approved_selection_sha256"],
      "source_fingerprint":profile["input_fingerprint"],
      "ticket_id":"abc","project_id":profile["project_id"],
      "session_id":"alaska-voyager-edit-20261112",
      "selection":{"format":"9:16","next_stage":"MONTAGE_PLANNING_REVIEW",
        "decision":{"selected_option":1},"scenes":rows}}
    return record,launch

class RenderChecks(unittest.TestCase):
    def test_profile_requires_exact_real_approval_and_no_publication(self):
        profile=m.get_profile("alaska-voyager-2027")
        self.assertFalse(profile["publication_authorized"])
        self.assertEqual(profile["approved_selection_sha256"],
                         "9580ce34d60afd47c213270a5b9142a9d81ed93caaff179956d98720e4e2a2e3")
        with self.assertRaisesRegex(m.RenderError,"NO_OWNER_APPROVED_RENDER_PROFILE"):
            m.get_profile("invented-project")

    def test_real_receipt_contract_rejects_scene_source_change(self):
        record,launch=fixture()
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            p=m.prepare(object(),"private-receipt")
            self.assertEqual(p["duration"],20.0)
        record["selection"]["scenes"][0]["asset_id"]="a2e:forged"
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            with self.assertRaisesRegex(m.RenderError,"SCENE_ORDER_OR_SOURCE_CHANGED"):
                m.prepare(object(),"private-receipt")

    def test_unsupported_effect_rejected(self):
        record,launch=fixture()
        record["selection"]["scenes"][1]["transition"]["id"]="zoom"
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            with self.assertRaisesRegex(m.RenderError,"UNIMPLEMENTED_TRANSITION"):
                m.prepare(object(),"private-receipt")

    def test_wrong_receipt_blocked(self):
        record,launch=fixture();record["receipt_id"]="wrong"
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            with self.assertRaisesRegex(m.RenderError,"NOT_EXACT_OWNER_APPROVED_SELECTION"):
                m.prepare(object(),"private-receipt")

    def test_unimplemented_layout_changes_blocked(self):
        record,launch=fixture()
        record["selection"]["visual_draft"]={"font_size":72}
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            with self.assertRaisesRegex(m.RenderError,"UNIMPLEMENTED_VISUAL_OVERRIDES"):
                m.prepare(object(),"private-receipt")

    def test_subtitle_profile_produces_real_ass_and_facts(self):
        profile=m.get_profile("alaska-voyager-2027")
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/"caption.ass"
            m.create_ass(profile,path)
            data=path.read_text(encoding="utf-8")
        self.assertIn("Dialogue:",data)
        self.assertIn("2249 $",data)
        self.assertIn("08-996-1127",data)
        self.assertIn("27.08",data)
        self.assertIn("DejaVu Sans",data)
        self.assertIn("Caption",data)

    def test_no_apply_does_not_render_or_upload(self):
        record,launch=fixture()
        with patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch),\
             patch.object(m,"render") as render:
            result=m.run(object(),"private-receipt",do_apply=False)
            render.assert_not_called()
        self.assertEqual(result["status"],"VALIDATED_NOT_RENDERED")

    def test_enabling_nonfree_api_is_fail_closed(self):
        record,launch=fixture()
        with patch.dict("os.environ",{"MOTIONLAB_NO_PAID_APIS":"false"}),\
             patch.object(m,"validate_receipt",return_value=record),\
             patch.object(m,"source_launch",return_value=launch):
            with self.assertRaisesRegex(m.RenderError,"NONFREE_RUNTIME_DISABLED"):
                m.run(object(),"receipt")

    def test_no_direct_public_drive_links(self):
        src=(pathlib.Path(m.__file__).read_text())
        self.assertNotIn("permissions().create(",src)
        self.assertNotIn("run_a2e",src)
        self.assertIn('"published":False',src)
        self.assertIn("VIDEO",src)

if __name__=="__main__":unittest.main()
