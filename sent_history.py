import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from dedupe import paper_key


def history_key(paper) -> str:
    kind, value = paper_key(paper)
    return f"{kind}:{value}"


def _parse_sent_at(value: str) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def load_sent_history(path: str, retention_days: int) -> dict[str, dict]:
    history_path = Path(path)
    if not history_path.exists():
        logger.info("No sent-history file found; all papers are eligible for delivery.")
        return {}

    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Unable to read sent history from {history_path}: {exc}")
        return {}

    records = payload.get("papers", {})
    if not isinstance(records, dict):
        logger.warning(f"Invalid sent-history format in {history_path}; ignoring it.")
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 0))
    recent_records = {}
    for key, record in records.items():
        if not isinstance(record, dict):
            continue
        sent_at = _parse_sent_at(record.get("sent_at"))
        if sent_at is not None and sent_at >= cutoff:
            recent_records[key] = record

    logger.info(
        f"Loaded {len(recent_records)} sent paper records from the last {retention_days} days."
    )
    return recent_records


def filter_previously_sent_papers(papers: list, sent_history: dict[str, dict]) -> tuple[list, int]:
    unseen_papers = []
    skipped_count = 0

    for paper in papers:
        if history_key(paper) in sent_history:
            skipped_count += 1
            continue
        unseen_papers.append(paper)

    return unseen_papers, skipped_count


def record_sent_papers(
    papers: list,
    sent_history: dict[str, dict],
    path: str,
    retention_days: int,
) -> None:
    sent_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records = dict(sent_history)

    for paper in papers:
        records[history_key(paper)] = {
            "sent_at": sent_at,
            "title": getattr(paper, "title", "") or "",
            "source": getattr(paper, "source", "") or "",
        }

    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "papers": records,
    }
    temporary_path = history_path.with_suffix(history_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(history_path)
    logger.info(
        f"Recorded {len(papers)} delivered papers in sent history ({history_path})."
    )
