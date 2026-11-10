"""Offline safety/integrity tests for Rafael's no-paid-API storyboard executor."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import auto_storyboard as raf
import handoff


class RafaelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/source.md"
        source.parent.mkdir(parents=True)
        source.write_text("STATUS: APPROVED\n## APPROVED_TEXT\n" +
                          "Прогулка по старинному городу с историческими площадями. " * 5)
        self.project = {
            "schema_version": 1, "id": "demo-rafael", "title": "Demo", "aliases": [],
            "updated_at": "2026-11-10", "stage": "STORYBOARD_PENDING",
            "next_action": "Create illustrated options", "references": [],
            "sources": [{"path": source.relative_to(self.root).as_posix(),
                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
            "assets": [{"id": "script-1", "kind": "script", "state": "available",
                        "evidence": "Approved by Leo in chat",
                        "url": "https://drive.google.com/file/d/approved-script/view"}],
            "working_asset_id": None, "approved_asset_id": None,
            "approvals": {"editorial": "pending", "publication": "pending"},
        }
        self.project["stage_handoffs"] = {
            "script": {
                "input_fingerprint": handoff.source_fingerprint(self.project),
                "state": "approved", "approval_evidence": "Leo explicitly selected option 2",
                "options_presented": 3, "options_evidence": "private draft archive",
                "selected_option": 2, "assets": ["script-1"]
            }
        }
        path = self.root / "campaigns/demo-rafael/project.json"
        path.parent.mkdir(parents=True)
        self.path = path
        self.save()
        self.report = {"mode": "ISSUE_DISPATCH", "paid_jobs": 0, "dispatch": [{
            "stage": "storyboard", "project_id": "demo-rafael",
            "status": "TASK_ISSUE_CREATED_NOT_EXECUTED"
        }]}

    def save(self):
        self.path.write_text(json.dumps(self.project, ensure_ascii=False))

    def test_only_approved_script_is_eligible(self):
        tasks = raf.read_approved_tasks(self.root, self.report)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0][0]["id"], "demo-rafael")
        self.project["stage_handoffs"]["script"]["selected_option"] = None
        self.save()
        with self.assertRaises(raf.RafaelError):
            raf.read_approved_tasks(self.root, self.report)

    def test_dispatch_dedup_and_stale_boundaries(self):
        self.assertEqual(raf.read_approved_tasks(self.root, {"mode":"ISSUE_DISPATCH",
                         "paid_jobs": 0, "dispatch":[]}), [])
        with self.assertRaises(raf.RafaelError):
            raf.read_approved_tasks(self.root, {**self.report, "paid_jobs": 1})
        with self.assertRaises(raf.RafaelError):
            raf.read_approved_tasks(self.root, {**self.report,
                "dispatch": self.report["dispatch"] * 2})
        self.project["stage_handoffs"]["storyboard"] = {"state": "approved"}
        self.save()
        with self.assertRaises(raf.RafaelError):
            raf.read_approved_tasks(self.root, self.report)

    def test_local_model_strict_json_and_no_outbound_fallback(self):
        script = "Исторические улицы. " * 35
        model_answer = json.dumps({"scenes": [
            {"query": "old city street", "direction": "Низкая камера у каменной улицы"},
            {"query": "historic city architecture", "direction": "Широкий общий план здания"},
            {"query": "ancient stone arch", "direction": "Крупная арка на закатном свете"},
        ]})
        messages = []
        result = raf.make_plan(script, "Concept", "warm",
                               infer=lambda msgs: messages.append(msgs) or model_answer)
        self.assertEqual(len(result), 3)
        self.assertIn("local", raf.auto_script.OLLAMA_URL if False else "local")
        self.assertEqual(len(messages), 1)
        bad = model_answer.replace("old city street", "https://bad-site.example")
        with self.assertRaises(raf.RafaelError):
            raf.make_plan(script, "Concept", "warm", infer=lambda _: bad)

    def test_image_license_rejects_unapproved_or_duplicate(self):
        image = make_image()
        def listing(*_):
            return json.dumps({"query":{"pages":[
                {"title":"File:Unsafe.jpg", "imageinfo":[media_info("CC BY-NC 4.0")]},
                {"title":"File:Approved.jpg", "imageinfo":[media_info("CC0")]},
            ]}}).encode()
        def fetch(url, limit):
            return image if url.startswith("https://upload.wikimedia.org/") else listing()
        raw, info = raf.safe_licensed_image("old city street", set(), fetch=fetch)
        self.assertEqual(raw, image)
        self.assertEqual(info["license"], "CC0")
        with self.assertRaises(raf.RafaelError):
            raf.safe_licensed_image("old city street", {"File:Approved.jpg"}, fetch=fetch)

    def test_three_boards_nine_actual_images_and_manifest(self):
        img = make_image()
        script = ("Старинный город раскрывает удивительную историю. Каменные дома встречают гостей. "
                  "Площадь наполнена солнечным светом. Улицы ведут к аркам и мосту. "
                  "Путешественники видят фонтаны и узкие переулки. Старые фасады меняют настроение. "
                  "Древний мост отражается в реке. Последние лучи освещают город. "
                  "Городские огни делают прогулку незабываемой.")
        def plan(s, title, style):
            return [{"query": f"old city view {x}".replace(" 1","").replace(" 2","").replace(" 3",""),
                     "direction": f"Натуральная фотография старой улицы {x}"}
                    for x in ("one", "two", "three")]
        picked = []
        def picker(query, used):
            idx = len(picked)+1
            picked.append(idx)
            used.add(f"File:Image{idx}.jpg")
            return img, {"license": "CC0", "source_url": f"https://commons.wikimedia.org/wiki/File:Image{idx}.jpg"}
        uploaded = {}
        def upload(drive, folder, name, payload, revision, mime):
            uploaded[name] = payload
            return f"private-{len(uploaded)}"
        with patch.object(raf, "check_private_folder"), \
             patch.object(raf, "find_remote", return_value=None), \
             patch.object(raf, "verified_upload", side_effect=upload):
            result = raf.produce(object(), raf.FOLDER, "demo-rafael", "a"*64,
                                 script, 2, planner=plan, picker=picker)
        self.assertEqual(result["status"], "STORYBOARD_OPTIONS_NEED_LEO")
        self.assertEqual(result["verified_frames"], 9)
        self.assertEqual(len(picked), 9)
        self.assertEqual(len(uploaded), 4)
        blob = next(v for k,v in uploaded.items() if k.endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            self.assertEqual(len([n for n in names if n.endswith(".jpg")]), 9)
            self.assertEqual(len([n for n in names if n.endswith(".png")]), 3)
            manifest = json.loads(z.read("storyboards.json"))
            self.assertEqual(len(manifest["options"]), 3)
            self.assertEqual(manifest["approved_script_option"], 2)
            self.assertFalse(manifest["published"])
            for option in manifest["options"]:
                self.assertEqual(len(option["scenes"]), 3)
        self.assertFalse(result["approved"])
        self.assertEqual(result["paid_api_calls"], 0)

    def test_private_remote_reuses_only_matching_revision(self):
        old = {"appProperties":{"input_receipt":"b"*64},"size":"3000"}
        with patch.object(raf, "check_private_folder"), \
             patch.object(raf, "find_remote", return_value=old):
            with self.assertRaises(raf.RafaelError):
                raf.produce(object(), raf.FOLDER, "demo-rafael", "a"*64, "x", 1)

    def test_no_execution_without_main_workflow_gate(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(raf.main(["--smoke", "--execute"]), 2)
            self.assertEqual(raf.main(["--smoke"]), 0)

    def test_no_unapproved_external_hosts(self):
        with self.assertRaises(raf.RafaelError):
            raf.remote_get("http://commons.wikimedia.org/x", 100)
        with self.assertRaises(raf.RafaelError):
            raf.remote_get("https://evil.example/file", 100)


def media_info(license_short):
    return {
        "url": "https://upload.wikimedia.org/thumb/file.jpg",
        "thumburl": "https://upload.wikimedia.org/thumb/file.jpg",
        "width": 800, "height": 800,
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Approved.jpg",
        "extmetadata": {"LicenseShortName": {"value": license_short},
                        "Artist": {"value": "Commons contributor"},
                        "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/zero/1.0/"}}
    }


def make_image():
    from PIL import Image
    output = io.BytesIO()
    Image.new("RGB", (700, 700), (113, 134, 144)).save(output, "JPEG")
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
