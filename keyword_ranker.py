import math
import re


def parse_weighted_keywords(raw: str) -> dict[str, float]:
    rules = {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, weight = line.rsplit(":", 1)
            rules[key.strip().lower()] = float(weight.strip())
        else:
            rules[line.lower()] = 1.0
    return rules


def parse_keywords(raw: str) -> list[str]:
    return [line.strip().lower() for line in (raw or "").splitlines() if line.strip()]


def contains_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    if " " in phrase or "-" in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def keyword_score(paper, boost_raw="", require_raw="", exclude_raw="", mode="boost"):
    title = getattr(paper, "title", "") or ""
    summary = getattr(paper, "summary", "") or ""
    text = f"{title}\n{summary}".lower()

    exclude = parse_keywords(exclude_raw)
    if any(contains_phrase(text, keyword) for keyword in exclude):
        return None, []

    required = parse_keywords(require_raw)
    if mode == "hard" and required and not any(contains_phrase(text, keyword) for keyword in required):
        return None, []

    boost = parse_weighted_keywords(boost_raw)
    hits = []
    raw_score = 0.0

    for keyword, weight in boost.items():
        if contains_phrase(text, keyword):
            hits.append(keyword)
            raw_score += weight

    return math.log1p(raw_score), hits


def apply_keyword_rules(papers, boost_raw="", require_raw="", exclude_raw="", mode="boost"):
    kept = []
    for paper in papers:
        score, hits = keyword_score(
            paper,
            boost_raw=boost_raw,
            require_raw=require_raw,
            exclude_raw=exclude_raw,
            mode=mode,
        )
        if score is None:
            continue
        paper.keyword_score = score
        paper.keyword_hits = hits
        kept.append(paper)
    return kept
