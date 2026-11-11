"""Fail-closed contract tests for Motion Lab global style and per-scene exceptions."""
import unittest
import motionlab_typography_contract as typo


class TestTypography(unittest.TestCase):
    def setUp(self):
        self.theme = {k: dict(v) for k, v in typo.DEFAULT.items()}
        self.scenes = [{"scene_id": "s1", "asset_id": "a1"},
                       {"scene_id": "s2", "asset_id": "a2"}]
        self.overrides = [{"scene_id": "s1", "asset_id": "a1", "typography": {}},
                          {"scene_id": "s2", "asset_id": "a2",
                           "typography": {"title": {"family": "Georgia",
                                                   "color": "#AABBCC", "size": 110}}}]
    def test_theme_inherited_and_scene_exception(self):
        got = typo.resolve_scenes(self.theme, self.overrides, self.scenes)
        self.assertEqual(got[0]["typography"]["title"], self.theme["title"])
        self.assertEqual(got[1]["typography"]["title"]["color"], "#aabbcc")
        self.assertEqual(got[1]["typography"]["subtitle"], self.theme["subtitle"])
        self.assertNotEqual(got[0]["typography"]["title"], got[1]["typography"]["title"])
        self.assertFalse(typo.renderer_capability()["render_authorized"])

    def test_unapproved_fonts_and_sizes_rejected(self):
        for patch in ({"family": "Comic Sans", "color": "#ffffff", "size": 100},
                      {"family": "Arial", "color": "#ffffff", "size": 102},
                      {"family": "Arial", "color": "red", "size": 100},
                      {"family": "Arial", "color": "#fff", "size": 100}):
            with self.subTest(patch=patch), self.assertRaises(typo.TypographyError):
                typo.validate_style(patch)

    def test_foreign_scene_cannot_take_override(self):
        self.overrides[1]["asset_id"] = "other"
        with self.assertRaisesRegex(typo.TypographyError, "TYPOGRAPHY_SOURCE_MISMATCH"):
            typo.resolve_scenes(self.theme, self.overrides, self.scenes)

    def test_missing_or_ambiguous_override_rejected(self):
        with self.assertRaises(typo.TypographyError):
            typo.resolve_scenes(self.theme, self.overrides[:1], self.scenes)
        self.overrides[0]["typography"]["price"] = self.theme["title"]
        with self.assertRaises(typo.TypographyError):
            typo.resolve_scenes(self.theme, self.overrides, self.scenes)


if __name__ == "__main__":
    unittest.main()
