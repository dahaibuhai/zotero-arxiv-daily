import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

if "loguru" not in sys.modules:
    sys.modules["loguru"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)
    )

from sent_history import load_sent_history


class SentHistoryTests(unittest.TestCase):
    def test_no_expiration_keeps_old_classic_records(self):
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=500)).isoformat()
        payload = {
            "version": 1,
            "papers": {
                "doi:10.1000/classic": {
                    "sent_at": old_timestamp,
                    "title": "Classic paper",
                    "source": "Semantic Scholar",
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            permanent = load_sent_history(str(path), None)
            recent = load_sent_history(str(path), 90)

        self.assertIn("doi:10.1000/classic", permanent)
        self.assertNotIn("doi:10.1000/classic", recent)


if __name__ == "__main__":
    unittest.main()
