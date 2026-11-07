import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
import make_video


class RendererChoiceTests(unittest.TestCase):
    def load(self, renderer=None):
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder)
            (job / 'photo.jpg').write_bytes(b'fixture')
            spec = {'packageId': 'example', 'sourcePost': 'unused.md',
                    'scenes': [{'image': 'photo.jpg', 'lines': []}]}
            if renderer is not None:
                spec['renderer'] = renderer
            (job / 'video-spec.json').write_text(json.dumps(spec), encoding='utf-8')
            with patch('music_input.validate_music', return_value=None):
                return make_video.load_spec(job)

    def test_existing_jobs_default_to_simba(self):
        self.assertEqual(self.load()['renderer'], 'simba')

    def test_editor_can_select_hyperframes_independently_of_motion(self):
        spec = self.load('hyperframes')
        self.assertEqual(spec['renderer'], 'hyperframes')
        self.assertEqual(spec['motion'], 'anime')

    def test_unknown_renderer_is_rejected(self):
        with self.assertRaisesRegex(make_video.Stop, 'renderer'):
            self.load('unknown')

    def test_missing_hyperframes_stops_at_spec_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(make_video, 'HERE', Path(folder)):
                with self.assertRaisesRegex(make_video.Stop, 'HyperFrames is not installed'):
                    self.load('hyperframes')


if __name__ == '__main__':
    unittest.main()
