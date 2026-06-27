import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lang5_system_pack import load_system_layout


class SystemLayoutTests(unittest.TestCase):
    SOURCE = {
        "table:08052:262": {"group": 0},
        "table:08052:264": {"group": 0},
        "offset:176A0": {"group": -1},
    }

    def load(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "system_layout.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_system_layout(path, self.SOURCE)

    def test_loads_default_and_stable_id_overrides(self):
        default, overrides = self.load({
            "default_max_grow": 4,
            "overrides": {
                "table:08052:262": 6,
                "table:08052:264": 5,
            },
        })
        self.assertEqual(default, 4)
        self.assertEqual(overrides, {
            "table:08052:262": 6,
            "table:08052:264": 5,
        })

    def test_rejects_unknown_stable_id(self):
        with self.assertRaisesRegex(SystemExit, "unknown SYSTEM id"):
            self.load({
                "default_max_grow": 4,
                "overrides": {"table:08052:999": 6},
            })

    def test_rejects_loose_string_override(self):
        with self.assertRaisesRegex(SystemExit, "loose SYSTEM string cannot grow"):
            self.load({
                "default_max_grow": 4,
                "overrides": {"offset:176A0": 6},
            })

    def test_rejects_negative_limit(self):
        with self.assertRaisesRegex(SystemExit, "non-negative integer"):
            self.load({
                "default_max_grow": -1,
                "overrides": {},
            })


if __name__ == "__main__":
    unittest.main()
