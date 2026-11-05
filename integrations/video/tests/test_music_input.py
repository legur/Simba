"""Actual MP3 decode/loop/fade tests; no network or paid accounts required."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_input import AUDIO_SR, external_music_bed, prepare_music, validate_music


class ExternalMusicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name)
        t = np.arange(AUDIO_SR) / AUDIO_SR
        sf.write(self.job / 'source.wav', .15 * np.sin(2 * np.pi * 440 * t), AUDIO_SR)
        self.ffmpeg = shutil.which('ffmpeg')
        if not self.ffmpeg:
            self.skipTest('ffmpeg is required')

    def test_validation_and_safe_paths(self):
        self.assertEqual(validate_music(self.job, {'file': 'source.wav', 'rights_confirmed': True}),
                         (self.job / 'source.wav').resolve())
        for music in (
            {'file': '../secret.mp3', 'rights_confirmed': True},
            {'file': '/etc/passwd', 'rights_confirmed': True},
            {'file': 'source.wav', 'rights_confirmed': False},
            {'file': 'source.wav', 'rights_confirmed': True, 'fade_out_s': -1},
            {'file': 'source.wav', 'rights_confirmed': True, 'loop': 'yes'},
            {'file': 'source.wav', 'rights_confirmed': True, 'gain_db': float('nan')},
            {'file': 'source.exe', 'rights_confirmed': True},
        ):
            with self.subTest(music=music), self.assertRaises(ValueError):
                validate_music(self.job, music)

    def test_mp3_import_loop_and_fades(self):
        mp3 = self.job / 'licensed_test.mp3'
        subprocess.run([self.ffmpeg, '-y', '-loglevel', 'error', '-i', str(self.job / 'source.wav'),
                        '-codec:a', 'libmp3lame', '-qscale:a', '7', str(mp3)], check=True)
        spec = {'file': 'licensed_test.mp3', 'loop': True, 'gain_db': -6,
                'rights_confirmed': True, 'fade_in_s': .2, 'fade_out_s': .5}
        output = prepare_music(self.job, spec, 2.4, self.ffmpeg)
        self.assertAlmostEqual(sf.info(output).duration, 2.4, places=2)
        n = int(2.4 * AUDIO_SR) + AUDIO_SR
        bed = external_music_bed(self.job, spec, 2.4, n, AUDIO_SR)
        self.assertEqual(bed.shape, (n, 2))
        self.assertLess(abs(bed[0, 0]), 1e-7)
        self.assertGreater(float(np.sqrt(np.mean(bed[AUDIO_SR:AUDIO_SR * 2, 0]**2))), .01)
        self.assertLess(abs(bed[int(2.4 * AUDIO_SR) - 1, 0]), .002)
        self.assertTrue(np.all(bed[int(2.4 * AUDIO_SR):] == 0))

    def test_short_track_must_explicitly_loop(self):
        spec = {'file': 'source.wav', 'loop': False, 'rights_confirmed': True}
        with self.assertRaisesRegex(ValueError, 'shorter'):
            prepare_music(self.job, spec, 2.4, self.ffmpeg)

    def test_old_synth_music_is_still_supported(self):
        self.assertIsNone(validate_music(self.job, {'style': 'calm'}))
        self.assertIsNone(validate_music(self.job, None))


if __name__ == '__main__':
    unittest.main()
