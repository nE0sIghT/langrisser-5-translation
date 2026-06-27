import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lang5_assign_font_slots import needed_units, word_pairs


class FontUnitTests(unittest.TestCase):
    def test_cyrillic_word_pairs_follow_the_existing_greedy_rules(self):
        self.assertEqual(list(word_pairs("Привет")), ["Пр", "ив", "ет"])
        self.assertEqual(list(word_pairs("мир.")), ["ми", "р."])

    def test_collects_cyrillic_singles_pairs_and_spacing_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "SCEN"
            script.mkdir()
            (script / "chunk_000.txt").write_text(
                "1\tПривет мир.<$FFFE>\n",
                encoding="utf-8",
            )
            menu = root / "system_strings.json"
            menu.write_text(
                json.dumps({"table:08052:211": "Начать"}, ensure_ascii=False),
                encoding="utf-8",
            )

            singles, menu_pairs, spacing_pairs, script_pairs = needed_units(
                root, [menu], "ПН"
            )

        self.assertTrue(set("ПНриветмачь").issubset(singles))
        self.assertIn("На", menu_pairs)
        self.assertIn("Пр", script_pairs)
        self.assertIn("т ", spacing_pairs)
        self.assertIn(" м", spacing_pairs)


if __name__ == "__main__":
    unittest.main()
