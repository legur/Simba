"""Step 5F contract tests: approved existing WAV + Music Editor track.

Mocked private Drive with actual PCM WAV bytes. No Gemini/TTS, music provider
downloads, A2E generation, publication, or actual GitHub writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import wave

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import handoff
import voice_music_writeback as bridge
from test_handoff import StageHandoffTests

FOLDER="1OwnerOnlyAudioFolder1234"
MANIFEST="1AudioApprovalManifest23456"
VOICE="1ExistingApprovedVoiceWav1234"
MUSIC="1LicensedSelectedMusicFile123"


def raw_wav(seconds=2.0, rate=24000):
    stream=io.BytesIO()
    with wave.open(stream,"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00"*int(rate*seconds))
    return stream.getvalue()


class Response:
    def __init__(self,obj):self.obj=obj
    def execute(self,num_retries=0):return self.obj


class PrivateDrive:
    def __init__(self):
        self.files_data={}
        self.folders={}
        self.reads=0
    def folder(self,name):
        self.folders[name]={
            "id":name, "mimeType":"application/vnd.google-apps.folder",
            "permissions":[{"type":"user","role":"owner"}],
        }
    def add(self,file_id,folder,mime,payload,*,properties=None):
        self.files_data[file_id]={
            "metadata":{
                "id":file_id,"name":file_id,"mimeType":mime,"parents":[folder],
                "size":str(len(payload)),"md5Checksum":hashlib.md5(payload).hexdigest(),
                "permissions":[{"type":"user","role":"owner"}],
                "appProperties":properties or {},
            },
            "payload":payload,
        }
    def files(self):return self
    def get(self,fileId,fields):
        if fileId in self.folders:return Response(self.folders[fileId])
        if fileId in self.files_data:return Response(self.files_data[fileId]["metadata"])
        raise AssertionError("unrecognized Drive ID in offline test")
    def get_media(self,fileId):
        self.reads+=1
        return Response(self.files_data[fileId]["payload"])


class VoiceMusicWritebackTests(unittest.TestCase):
    def setUp(self):
        self.fixture=StageHandoffTests("test_first_stage_requires_explicit_script_selection")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
        self.path=self.fixture.path
        # Real A2E output was already completed/archived by Step 5E; never
        # fabricate a new paid task in this handoff.
        receipt=handoff.source_fingerprint(self.fixture.project)
        for stage in ("script","storyboard","a2e_prompts","a2e_clips"):
            receipt=self.fixture.complete_stage(stage,receipt)
        self.fixture.project["assets"]=[
            row for row in self.fixture.project["assets"]
            if row["kind"] not in ("music","narration")
        ]
        self.fixture.save()
        self.input_receipt=receipt
        texts=[{"option":i,"sha256":hashlib.sha256(f"Sample narration {i}".encode()).hexdigest()}
               for i in range(1,4)]
        tracks=[{"option":i,"source":"mixkit",
                 "track_url":f"https://mixkit.co/free-stock-music/track/safe-example-{i}/"}
                for i in range(1,4)]
        self.wav=raw_wav(2.0)
        self.music=raw_wav(12.0,rate=24000)
        self.manifest={
            "schema_version":1, "project_id":"example",
            "input_fingerprint":receipt,
            "selection":{
                "texts":texts,"music":tracks,
                "text_option":2,"music_option":3,
                "leo_approval_evidence":"Explicit Leo selected option 2 text and option 3 music for the video."
            },
            "voice":{
                "profile":"simba_warmbaritone",
                "text_sha256":texts[1]["sha256"],
                "file_id":VOICE,"folder_id":FOLDER,
                "sha256":bridge.digest(self.wav)
            },
            "music":{
                "file_id":MUSIC,"folder_id":FOLDER,
                "sha256":bridge.digest(self.music),
                "source":"mixkit",
                "title":"Synthetic soundbed 3", "author":"Synthetic Musician",
                "track_url":tracks[2]["track_url"],
                "license_url":"https://mixkit.co/license/modal/musicFree/",
                "verified_at":datetime.now(timezone.utc).date().isoformat(),
                "commercial_use_verified":True,
                "online_ads_verified":True,
                "licensed_channels":["facebook","instagram","youtube"],
                "attribution_required":False,
                "license_evidence":"Music Editor tested commercial and ads license for listed channels",
            },
            "channels":["facebook","instagram"]
        }
        self.drive=PrivateDrive()
        self.drive.folder(FOLDER)
        self.drive.folder(bridge.rafael_archive.ARCHIVE_FOLDER)
        self.drive.add(VOICE,FOLDER,"audio/wav",self.wav,
                       properties={"simba_render_marker_id":"1AlreadyVerifiedTTSMarker123"})
        self.drive.add(MUSIC,FOLDER,"audio/wav",self.music)
        self.sync()
    def sync(self):
        binary=json.dumps(self.manifest,ensure_ascii=False).encode()
        self.drive.add(MANIFEST,bridge.rafael_archive.ARCHIVE_FOLDER,
                       "application/json",binary)
        self.sha=bridge.digest(binary)
    def candidate(self,**kwargs):
        return bridge.build_candidate(
            self.root,"example",MANIFEST,self.sha,
            drive=self.drive,probe_music=lambda data,mime:12.0,**kwargs)

    def test_approved_selected_text_and_track_to_existing_montage(self):
        path,project,report=self.candidate()
        self.assertEqual(path,self.path)
        self.assertEqual(report["status"],"VOICE_MUSIC_CANDIDATE_VERIFIED_NOT_WRITTEN")
        self.assertEqual(report["selected_text_option"],2)
        self.assertEqual(report["selected_music_option"],3)
        self.assertEqual(report["next_recipient"],"MONTAGE")
        self.assertEqual(report["next_stage"],"edit_choice")
        self.assertFalse(report["project_written"])
        self.assertEqual(report["paid_calls"],0)
        record=project["stage_handoffs"]["voice_music"]
        self.assertEqual(record["state"],"completed")
        self.assertEqual(record["input_fingerprint"],self.input_receipt)
        self.assertEqual(record["voice_profile"],"simba_warmbaritone")
        self.assertEqual(len(record["assets"]),2)
        self.assertEqual(project["approvals"],self.fixture.project["approvals"])
        self.assertNotIn("voice_music",json.loads(self.path.read_text())["stage_handoffs"])
        self.assertNotIn("voice_warmBaritone",json.dumps(project))
        self.assertNotIn("Leo selected option 2",json.dumps(project))

    def test_three_unique_options_and_approval_are_mandatory(self):
        for field,value in [
            ("texts",self.manifest["selection"]["texts"][:2]),
            ("music",self.manifest["selection"]["music"][:2]),
            ("text_option",True),
            ("music_option",4),
            ("leo_approval_evidence",""),
        ]:
            selection=self.manifest["selection"]
            saved=selection[field]
            selection[field]=value
            self.sync()
            with self.subTest(field=field), self.assertRaises(bridge.AudioHandoffError):
                self.candidate()
            selection[field]=saved
        self.sync()

    def test_upstream_sha_change_prevents_remote_file_reads(self):
        self.manifest["input_fingerprint"]="f"*64
        self.sync()
        with self.assertRaises(bridge.AudioHandoffError):
            self.candidate()
        self.assertEqual(self.drive.reads,1)  # Only plan was read, not media.

    def test_missing_license_or_wrong_channel_blocks(self):
        for key,value in [("commercial_use_verified",False),
                          ("online_ads_verified",False),
                          ("license_evidence",""),
                          ("licensed_channels",["youtube"]),
                          ("license_url","https://evil.example/license")]:
            track=self.manifest["music"]
            before=track[key]
            track[key]=value
            self.sync()
            with self.subTest(key=key), self.assertRaises(bridge.AudioHandoffError):
                self.candidate()
            track[key]=before
        self.sync()

    def test_wav_sha_mismatch_blocks(self):
        self.drive.files_data[VOICE]["payload"]+=b"tampered"
        with self.assertRaises(bridge.AudioHandoffError):
            self.candidate()

    def test_original_tts_marker_required(self):
        meta=self.drive.files_data[VOICE]["metadata"]
        meta["appProperties"]={}
        with self.assertRaises(bridge.AudioHandoffError):
            self.candidate()

    def test_shared_folder_or_music_file_rejected(self):
        self.drive.folders[FOLDER]["permissions"]=[{"type":"anyone","role":"reader"}]
        with self.assertRaises(bridge.AudioHandoffError): self.candidate()
        self.drive.folders[FOLDER]["permissions"]=[{"type":"user","role":"owner"}]
        self.drive.files_data[MUSIC]["metadata"]["permissions"]=[]
        with self.assertRaises(bridge.AudioHandoffError): self.candidate()

    def test_unsupported_voice_switch_is_rejected(self):
        self.manifest["voice"]["profile"]="new_unapproved_voice"
        self.sync()
        with self.assertRaises(bridge.AudioHandoffError):self.candidate()

    def test_silent_clips_have_no_tts_generation(self):
        self.manifest["voice"]={
            "profile":"none",
            "text_sha256":self.manifest["selection"]["texts"][1]["sha256"]
        }
        self.sync()
        _,project,report=self.candidate()
        self.assertEqual(report["voice_profile"],"none")
        record=project["stage_handoffs"]["voice_music"]
        self.assertEqual(len(record["assets"]),1)
        self.assertEqual([a["kind"] for a in project["assets"][-1:]],["music"])
        self.assertEqual(record["voice_profile"],"none")

    def test_no_double_registration(self):
        _,candidate,_=self.candidate()
        self.fixture.project=candidate
        self.fixture.save()
        with self.assertRaises(bridge.AudioHandoffError):self.candidate()

    def test_reuse_existing_atomic_write_guard(self):
        path,project,_=self.candidate()
        before=path.read_bytes()
        with patch.dict(os.environ,{},clear=True), self.assertRaises(bridge.a2e_writeback.WritebackError):
            bridge.a2e_writeback.apply_candidate(
                self.root,path,project,original_sha256=hashlib.sha256(before).hexdigest())
        self.assertEqual(path.read_bytes(),before)


if __name__=="__main__":
    unittest.main()
