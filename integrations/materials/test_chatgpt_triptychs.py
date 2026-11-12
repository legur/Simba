"""Offline test for three ChatGPT native triptych imports."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
import chatgpt_triptychs as triptychs


class TriptychTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.sources = []
        self.output = self.root / "frames"
        for option in range(1, 4):
            img = Image.new("RGB", (1800, 600), "#ededed")
            draw = ImageDraw.Draw(img)
            for scene in range(3):
                draw.rectangle((scene*600+5, 5, (scene+1)*600-5, 595),
                               fill=(option*30, (scene+1)*60, 30+scene*60))
                draw.ellipse((scene*600+40, 100, scene*600+400, 520),
                             fill=(220, option*40, scene*30))
            path = self.root / f"story_{option}.png"
            img.save(path)
            self.sources.append(path)
        self.ids = ["chatgpt-img-1", "chatgpt-img-2", "chatgpt-img-3"]

    def test_real_nine_distinct_png_and_manifest(self):
        info = triptychs.import_triptychs(self.sources,self.output,generation_ids=self.ids)
        self.assertEqual(info["image_count"],9)
        self.assertFalse(info["ready_for_a2e"])
        self.assertEqual(len(list(self.output.glob("option_*/scene_*.png"))),9)
        text = json.loads((self.output/"chatgpt_provenance.json").read_text())
        self.assertEqual(text["source_image_count"],3)
        self.assertEqual(len(set(row["sha256"] for row in text["frames"])),9)
        self.assertFalse(text["approval_recorded"])
        self.assertTrue(all(row["generation_id"] in self.ids for row in text["input_composites"]))

    def test_blocks_missing_unique_receipts_and_overwrite(self):
        with self.assertRaises(triptychs.ImportErrorRafael):
            triptychs.import_triptychs(self.sources,self.output,generation_ids=["same"]*3)
        triptychs.import_triptychs(self.sources,self.output,generation_ids=self.ids)
        with self.assertRaises(triptychs.ImportErrorRafael):
            triptychs.import_triptychs(self.sources,self.output,generation_ids=self.ids)

    def test_blocks_non_triptych(self):
        bad = Image.new("RGB",(1000,1000),"#444444")
        bad.save(self.sources[0])
        with self.assertRaises(triptychs.ImportErrorRafael):
            triptychs.import_triptychs(self.sources,self.output,generation_ids=self.ids)


if __name__ == "__main__":
    unittest.main()
