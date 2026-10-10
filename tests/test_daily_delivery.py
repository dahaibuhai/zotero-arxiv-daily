import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from daily_delivery import record_delivery, should_skip_scheduled


class DailyDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Path(self.directory.name) / "daily.json"
        self.history = Path(self.directory.name) / "history.json"
        self.sent = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)  # 23:30 Shanghai

    def skip(self, now, event="schedule", dry=False):
        return should_skip_scheduled(event, dry, self.ledger, self.history, now)

    def test_successful_manual_send_skips_only_same_local_day(self):
        record_delivery(self.ledger, "workflow_dispatch", self.sent)
        self.assertTrue(self.skip(datetime(2026, 10, 10, 15, 59, tzinfo=timezone.utc)))
        self.assertFalse(self.skip(datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc)))

    def test_utc_midnight_does_not_reset_shanghai_day(self):
        record_delivery(self.ledger, "workflow_dispatch", datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc))
        self.assertTrue(self.skip(datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)))

    def test_manual_and_dry_runs_still_allowed(self):
        record_delivery(self.ledger, "workflow_dispatch", self.sent)
        self.assertFalse(self.skip(self.sent, event="workflow_dispatch"))
        self.assertFalse(self.skip(self.sent, dry=True))

    def test_no_success_record_does_not_skip_or_create_ledger(self):
        self.assertFalse(self.skip(self.sent))
        self.assertFalse(self.ledger.exists())

    def test_preexisting_formal_send_history_is_respected(self):
        self.history.write_text(json.dumps({"papers": {"doi:test": {"sent_at": self.sent.isoformat()}}}), encoding="utf-8")
        self.assertTrue(self.skip(self.sent))
