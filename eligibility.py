"""The same auditable gates for daily candidates and arXiv backfill."""

from collections import Counter
from dedupe import identity_keys, history_identity_keys
from keyword_ranker import keyword_score, parse_keywords
from research_scope import classify_paper, exclusion_reason


def filter_candidates(papers, sent_history, *, seen=(), boost_raw="", require_raw="",
                      exclude_raw="", mode="boost", expanded_scope=True, history_label="近90天已推送"):
    stages = {name: Counter() for name in ("fetched", "deduplicated", "history", "keywords", "topic")}
    rows = []
    kept = []
    seen_keys = set().union(*(identity_keys(p) for p in seen)) if seen else set()
    sent_keys = history_identity_keys(sent_history)
    for paper in papers:
        source = getattr(paper, "source", "")
        stages["fetched"][source] += 1
        keys = identity_keys(paper)
        reason = ""
        stage = "deduplication"
        if keys & seen_keys:
            reason = "同批、跨来源或跨日期重复"
        seen_keys.update(keys)
        if not reason:
            stages["deduplicated"][source] += 1
            stage = "history"
            if keys & sent_keys:
                reason = history_label
        if not reason:
            stages["history"][source] += 1
            stage = "keywords"
            score, hits = keyword_score(paper, boost_raw, require_raw, exclude_raw, mode)
            if score is None:
                reason = exclusion_reason(paper, parse_keywords(exclude_raw)) or "未满足必需关键词"
            else:
                paper.keyword_score, paper.keyword_hits = score, hits
        if not reason:
            stages["keywords"][source] += 1
            stage = "topic"
            if expanded_scope:
                topic, location, topic_reason = classify_paper(paper)
                if topic is None:
                    reason = topic_reason
                else:
                    paper.research_topic = topic
                    paper.topic_match_location = location
                    paper.recommendation_reason = topic_reason
        if not reason:
            stages["topic"][source] += 1
            kept.append(paper)
            stage = "eligible"
            reason = getattr(paper, "recommendation_reason", "合格候选")
        rows.append({"title": paper.title, "source": source,
                     "id": str(getattr(paper, "arxiv_id", "")),
                     "stage": stage, "reason": reason,
                     "backfill_days": getattr(paper, "arxiv_backfill_days", 0)})
    return kept, {"counts": {name: dict(count) for name, count in stages.items()}, "papers": rows}


def collect_arxiv_backfill(papers, sent_history, quota, fetch, *, filter_options=None,
                          max_days=14, on_audit=None, on_error=None):
    """Search 0..7 then 7..14 days only while the arXiv quota is short."""
    combined = list(papers)
    if quota <= 0:
        return combined
    for days, skip_days in ((7, 0), (14, 7)):
        if days > max_days or sum(p.source == "arXiv" for p in combined) >= quota:
            break
        try:
            candidates = fetch(days=days, skip_days=skip_days)
        except Exception as exc:
            if on_error:
                on_error(days, exc)
            continue
        for paper in candidates:
            paper.arxiv_backfill_days = days
        accepted, audit = filter_candidates(candidates, sent_history, seen=combined, **(filter_options or {}))
        if on_audit:
            on_audit(days, audit)
        combined.extend(accepted)
    return combined
