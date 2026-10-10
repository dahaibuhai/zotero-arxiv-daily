"""Skip scheduled sends after a successful delivery on the same Shanghai day."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")


def _day(timestamp):
    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(SHANGHAI).date()


def should_skip_scheduled(event, dry_run, ledger_path, history_path, now=None):
    if event != "schedule" or dry_run:
        return False
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SHANGHAI).date()
    ledger = Path(ledger_path)
    if ledger.exists():
        sent_at = json.loads(ledger.read_text(encoding="utf-8")).get("sent_at")
        if sent_at and _day(sent_at) == today:
            return True
    # Respect successful formal deliveries from before the ledger was added.
    history = Path(history_path)
    if history.exists():
        records = json.loads(history.read_text(encoding="utf-8")).get("papers", {})
        for record in records.values():
            sent_at = record.get("sent_at")
            if sent_at and _day(sent_at) == today:
                return True
    return False


def record_delivery(path, event, now=None):
    now = now or datetime.now(timezone.utc)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sent_at": now.isoformat(), "shanghai_date": now.astimezone(SHANGHAI).date().isoformat(), "event": event}
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
