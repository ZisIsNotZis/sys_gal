import unittest
from pathlib import Path

from harness.character_loader import load_character, load_characters


class CharacterLoaderTests(unittest.TestCase):
    def test_private_seed_is_separated_from_public_identity(self):
        seed = load_character(Path(__file__).parents[2] / "world/characters/陈默.md")
        self.assertIn("## Public", seed.identity)
        self.assertTrue(seed.private_seed.strip())
        self.assertNotIn(seed.private_seed[:20], seed.identity)

    def test_all_seed_characters_load(self):
        seeds = load_characters(Path(__file__).parents[2] / "world/characters")
        # v4 首验日 slice：三个角色（陈默/林瑶/唐小岚）。
        self.assertEqual(len(seeds), 10)
        self.assertIn("林瑶", seeds)
        self.assertIn("唐小岚", seeds)


if __name__ == "__main__":
    unittest.main()
