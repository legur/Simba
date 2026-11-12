"""Real local ffmpeg/ffprobe + private ZIP source handoff test.

Original MP4s and contact sheets exist ONLY in temporary test directories.
No real user assets, public GitHub artifacts, Wix uploads, model review, TTS,
A2E, render of a finished ad or publication.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import motionlab_analysis_bundle as pack
import motionlab_v2_contract as v2
import motionlab_render_contract as r


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "real ffmpeg and ffprobe required")
class PrivateBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.job=self.dir/"source"
        self.job.mkdir()
        self.asset=[]
        self.spec={
            "packageId":"test-private-only","size":"1080x1920",
            "sourcePost":"approved-ad-copy.md",
            "voice":{"source":"existing-approved"},
            "music":{"source":"licensed-existing"},
            "end":{"brand":"Bon Tours"},
            "scenes":[],
        }
        for i,color in enumerate(("red","blue"),1):
            name=f"clip-{i}.mp4"
            path=self.job/name
            subprocess.run([
                "ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i",f"color=c={color}:s=144x256:r=6:d=5",
                "-an","-c:v","mpeg4","-q:v","9",str(path),
            ],check=True,capture_output=True,timeout=45)
            info=r._ffprobe(path)
            self.asset.append({
                "scene_id":f"scene-{i}","asset_id":f"verified-a2e-{i}",
                "file":name,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "duration_s":info["duration_s"],
            })
            self.spec["scenes"].append({
                "clip":name,"title":f"Титр сцены {i}",
                "lines":[{"text":f"Утвержденная фраза {i}"}],
            })
        self.materials=v2.make_materials_v2(
            "private-demo-project","request-v2-package","b"*64,
            self.spec,self.asset,self.job)
        self.output=self.dir/"PRIVATE-MotionLab.zip"

    def test_full_mp4_and_timestamped_contact_sheets_in_owner_private_zip(self):
        result=pack.build_private_analysis_bundle(
            self.materials,self.asset,self.job,self.output)
        self.assertEqual(result["status"],
                         "PRIVATE_MOTIONLAB_ANALYSIS_BUNDLE_CREATED_NOT_DELIVERED")
        self.assertEqual(result["scene_count"],2)
        self.assertFalse(result["analysis_performed"])
        self.assertFalse(result["delivered_to_other_chat"])
        self.assertEqual(result["paid_calls"],0)
        self.assertEqual(result["bundle_sha256"],pack.sha_file(self.output))
        self.assertFalse(self.output.is_symlink())
        from PIL import Image
        from io import BytesIO
        with zipfile.ZipFile(self.output) as z:
            names=z.namelist()
            self.assertEqual(len(names),6)
            self.assertNotIn("private-drive-token",str(names))
            self.assertIsNone(z.testzip())
            orig=json.loads(z.read("materials.launch.v2.json"))
            self.assertEqual(orig,self.materials)
            evid=json.loads(z.read("analysis-evidence.json"))
            self.assertEqual(evid["analysis_status"],"NOT_YET_REVIEWED_BY_MOTIONLAB")
            self.assertEqual(evid["materials_sha256"],v2.digest(self.materials))
            for i,row in enumerate(evid["media"]):
                self.assertEqual(row["video_sha256"],self.asset[i]["sha256"])
                self.assertEqual(hashlib.sha256(z.read(row["video_file"])).hexdigest(),
                                 row["video_sha256"])
                raw=z.read(row["sheet_file"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row["sheet_sha256"])
                img=Image.open(BytesIO(raw))
                self.assertEqual(img.size,(1024,180))
                self.assertEqual(len(row["source_frame_seconds"]),4)
                self.assertTrue(all(0<t<5 for t in row["source_frame_seconds"]))

    def test_duplicate_bundle_cannot_overwrite_existing_private_copy(self):
        pack.build_private_analysis_bundle(self.materials,self.asset,self.job,self.output)
        before=self.output.read_bytes()
        with self.assertRaises(r.ContractError) as e:
            pack.build_private_analysis_bundle(self.materials,self.asset,self.job,self.output)
        self.assertEqual(e.exception.code,"PRIVATE_BUNDLE_ALREADY_EXISTS")
        self.assertEqual(self.output.read_bytes(),before)

    def test_tampered_media_cannot_be_packed(self):
        clip=self.job/"clip-2.mp4"
        raw=clip.read_bytes()
        clip.write_bytes(b"X"+raw[1:])  # same length, changed full-byte SHA
        with self.assertRaises(r.ContractError) as e:
            pack.build_private_analysis_bundle(self.materials,self.asset,self.job,self.output)
        self.assertEqual(e.exception.code,"MEDIA_SHA256_MISMATCH")
        self.assertFalse(self.output.exists())

    def test_public_repository_destination_disallowed(self):
        root=Path(__file__).resolve().parents[3]
        with self.assertRaises(r.ContractError) as e:
            pack.build_private_analysis_bundle(
                self.materials,self.asset,self.job,root/"DONT-PUBLISH.zip")
        self.assertEqual(e.exception.code,"PRIVATE_BUNDLE_MUST_LIVE_OUTSIDE_GIT_AND_JOB")
        self.assertFalse((root/"DONT-PUBLISH.zip").exists())


if __name__=="__main__":
    unittest.main()
