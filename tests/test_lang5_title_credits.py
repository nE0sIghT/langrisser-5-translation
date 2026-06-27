import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lang5_imgdat import load_title_credit_lines


class TitleCreditTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "title_credits.json"
            path.write_text(
                json.dumps(value, ensure_ascii=False),
                encoding="utf-8",
            )
            return load_title_credit_lines(path, "0.1", "deadbeef")

    def test_formats_language_specific_lines(self):
        self.assertEqual(
            self.load({
                "lines": [
                    "Перевод v{version} ({commit})",
                    "Юрий Конотопов",
                ],
            }),
            ["Перевод v0.1 (deadbeef)", "Юрий Конотопов"],
        )

    def test_rejects_empty_line_list(self):
        with self.assertRaisesRegex(ValueError, "expected 1-3"):
            self.load({"lines": []})


if __name__ == "__main__":
    unittest.main()
