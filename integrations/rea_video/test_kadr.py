import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('kadr', Path(__file__).with_name('kadr.py'))
kadr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kadr)


class KadrTests(unittest.TestCase):
    def test_model_cache_stays_in_workspace(self):
        self.assertTrue(Path(kadr.environment()['REA_VIDEO_MODELS']).is_relative_to(kadr.LAB))

    def test_local_source_is_not_copied_or_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'референс.mp4'
            source.write_bytes(b'original')
            self.assertEqual(kadr.resolve_source(str(source), Path(tmp), {}), source.resolve())
            self.assertEqual(source.read_bytes(), b'original')

    def test_instagram_download_is_single_and_without_cookies(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            def download(cmd, env):
                (job / 'reference.mp4').write_bytes(b'video')
            with patch.object(kadr, 'run', side_effect=download) as call:
                self.assertEqual(kadr.resolve_source('https://www.instagram.com/reel/ABC/', job, {}), job / 'reference.mp4')
            args = call.call_args.args[0]
            self.assertIn('--no-playlist', args)
            self.assertNotIn('--cookies-from-browser', args)
            self.assertEqual(call.call_count, 1)

    def test_failed_download_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(kadr, 'run', side_effect=RuntimeError('blocked')):
                with self.assertRaises(RuntimeError):
                    kadr.resolve_source('https://www.instagram.com/reel/ABC/', Path(tmp), {})

    def test_unknown_url_rejected(self):
        with self.assertRaises(ValueError):
            kadr.resolve_source('https://example.com/a', Path('.'), {})

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                kadr.new_job(Path(tmp))

    def test_analysis_forces_no_paid_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.mp4'
            with patch.object(kadr, 'run') as call:
                kadr.decompose(source, Path(tmp), {}, quick=True)
            args = call.call_args.args[0]
            self.assertIn('--no-vlm', args)
            self.assertNotIn('--vlm', args)
            self.assertIn('--no-stems', args)
            self.assertIn('--no-ocr', args)


if __name__ == '__main__':
    unittest.main()
