import unittest
from pathlib import Path

from harness.character_loader import load_character, load_characters


class CharacterLoaderTests(unittest.TestCase):
    def test_private_seed_is_separated_from_public_identity(self):
        seed = load_character(Path(__file__).parents[2] / "docs/characters/chen-mo.md")
        self.assertIn("## Public", seed.identity)
        self.assertIn("He still remembers", seed.private_seed)
        self.assertNotIn("He still remembers", seed.identity)

    def test_all_seed_characters_load(self):
        seeds = load_characters(Path(__file__).parents[2] / "docs/characters")
        self.assertEqual(len(seeds), 8)
        self.assertIn("lin-yao", seeds)


if __name__ == "__main__":
    unittest.main()
