"""No-provider contract checks: Motion Lab subtitle styles / real Whisper word timestamps."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import make_video


class SubtitleStyleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.job = Path(tmp.name)
        (self.job / 'scene.jpg').write_bytes(b'decoding not needed to validate spec')
        self.spec = {
            'packageId': 'motionlab-subtitles-smoke',
            'sourcePost': 'some_approved_post.md',
            'scenes': [{'image': 'scene.jpg'}],
            'end': {'cta': 'Contact Bon Tours'},
        }

    def read(self):
        (self.job / 'video-spec.json').write_text(
            json.dumps(self.spec, ensure_ascii=False), encoding='utf-8'
        )
        return make_video.load_spec(self.job)

    def test_style_ids_match_browser_catalog(self):
        source = (ROOT / 'template' / 'subtitle_styles.js').read_text(encoding='utf-8')
        styles = source.split('export const STYLE_IDS =', 1)[1].split(']);', 1)[0]
        motions = source.split('export const MOTION_IDS =', 1)[1].split(']);', 1)[0]
        js_styles = set(re.findall(r"'([a-z-]+)'", styles))
        js_motions = set(re.findall(r"'([a-z-]+)'", motions))
        self.assertEqual(js_styles, make_video.SUBTITLE_STYLES)
        self.assertEqual(js_motions, make_video.SUBTITLE_MOTIONS)
        self.assertEqual(len(js_styles), 24)
        self.assertEqual(len(js_motions), 5)

    def test_style_roundtrip_into_timeline_without_touching_script(self):
        self.spec['subtitleStyle'] = {
            'style': 'luxury', 'motion': 'active-pop',
            'color': 'gold', 'scale_percent': 110, 'position': 'bottom'
        }
        before_lines = json.dumps(self.spec['scenes'], ensure_ascii=False)
        normalized = self.read()
        timeline = make_video.timeline(normalized)
        self.assertEqual(timeline['subtitleStyle'], self.spec['subtitleStyle'])
        self.assertEqual(json.dumps(normalized['scenes'], ensure_ascii=False), before_lines)

    def test_old_specs_preserve_legacy_subtitles(self):
        spec = self.read()
        self.assertNotIn('subtitleStyle', spec)
        self.assertIsNone(make_video.timeline(spec)['subtitleStyle'])

    def test_defaults_are_safe(self):
        self.spec['subtitleStyle'] = {'style': 'clean', 'motion': 'karaoke'}
        spec = self.read()
        self.assertEqual(spec['subtitleStyle'], {
            'style': 'clean', 'motion': 'karaoke', 'position': 'bottom',
            'color': 'lime', 'scale_percent': 100,
        })

    def test_invalid_values_do_not_reach_renderer(self):
        invalid = [
            'luxury',
            {'style': 'new-unknown', 'motion': 'karaoke'},
            {'style': 'clean', 'motion': 'robot'},
            {'style': 'clean', 'motion': 'karaoke', 'color': 'transparent'},
            {'style': 'clean', 'motion': 'karaoke', 'position': 'left'},
            {'style': 'clean', 'motion': 'karaoke', 'scale_percent': True},
            {'style': 'clean', 'motion': 'karaoke', 'scale_percent': 501},
            {'style': 'clean', 'motion': 'karaoke', 'scale_percent': 79},
            {'style': 'clean', 'motion': 'karaoke', 'scale_percent': '100'},
        ]
        for value in invalid:
            with self.subTest(value=value):
                self.spec['subtitleStyle'] = value
                with self.assertRaises(make_video.Stop):
                    self.read()


if __name__ == '__main__':
    unittest.main()
