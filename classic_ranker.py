import math
import re
from research_scope import normalize, contains, classify_paper


def _query_phrases(queries_raw: str) -> list[list[str]]:
    """Keep quoted search concepts together for topic checks."""
    phrase_groups = []
    for query in (queries_raw or "").splitlines():
        query = query.strip()
        if not query:
            continue
        quoted = re.findall(r'"([^"]+)"', query)
        phrase_groups.append([part.casefold().strip() for part in (quoted or [query])])
    return phrase_groups


def _query_match_location(paper, phrase_groups: list[list[str]]) -> str:
    """Return title, abstract, or none for the configured search topics."""
    title = normalize(getattr(paper, "title", ""))
    abstract = normalize(getattr(paper, "summary", ""))
    aliases = {
        "reactive sputtering": ("reactive sputtering", "reactive sputter deposition"),
        "magnetron sputtering": ("magnetron sputtering", "magnetron sputter deposition"),
        "hipims": ("hipims", "high power impulse magnetron sputtering"),
        "high power impulse magnetron sputtering": ("hipims", "high power impulse magnetron sputtering"),
        "hot target": ("hot target", "heated target", "high temperature target"),
    }
    def matches(field):
        return any(all(any(contains(field, alias) for alias in aliases.get(normalize(phrase), (phrase,))) for phrase in group) for group in phrase_groups)
    if matches(title):
        return "title"
    if matches(abstract):
        return "abstract"
    return "none"


def _percentile_ranks(values: list[float]) -> list[float]:
    """Return tie-aware percentile ranks in the inclusive range 0..1."""
    if not values:
        return []
    if len(values) == 1:
        return [1.0]

    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        end = position
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[position][1]:
            end += 1
        average_rank = (position + end) / 2
        percentile = average_rank / (len(values) - 1)
        for index_in_sorted in range(position, end + 1):
            original_index = indexed[index_in_sorted][0]
            ranks[original_index] = percentile
        position = end + 1
    return ranks


def rank_classic_papers(
    papers: list,
    relevance_threshold: float = 0.65,
    impact_top_fraction: float = 0.25,
    no_keyword_relevance_threshold: float = 0.78,
    minimum_candidates: int = 0,
    queries_raw: str = "",
    expanded_scope: bool = False,
) -> list:
    """Rank historical papers after semantic relevance has been computed.

    The final score follows the configured editorial policy:
    55% citation impact, 35% Zotero-corpus relevance, and 10% keyword match.
    Prefer the top impact quartile. When filling a quota, allow further papers
    that meet the same relevance gates to fill any remaining slots.
    """
    if not papers:
        return []
    phrase_groups = _query_phrases(queries_raw)

    citation_percentiles = _percentile_ranks(
        [float(getattr(paper, "citation_count", 0) or 0) for paper in papers]
    )
    influential_percentiles = _percentile_ranks(
        [
            float(getattr(paper, "influential_citation_count", 0) or 0)
            for paper in papers
        ]
    )
    impact_scores = [
        (0.70 * citation_percentile) + (0.30 * influential_percentile)
        for citation_percentile, influential_percentile in zip(
            citation_percentiles, influential_percentiles
        )
    ]

    bounded_fraction = min(max(impact_top_fraction, 0.0), 1.0)
    top_count = max(1, math.ceil(len(papers) * bounded_fraction))
    top_impact_indexes = set(
        sorted(
            range(len(papers)),
            key=lambda index: impact_scores[index],
            reverse=True,
        )[:top_count]
    )

    max_keyword_score = max(
        float(getattr(paper, "keyword_score", 0.0) or 0.0) for paper in papers
    )
    high_impact_ranked = []
    other_relevant_ranked = []
    for index, paper in enumerate(papers):
        relevance = min(max(float(getattr(paper, "score", 0.0)) / 10.0, 0.0), 1.0)
        has_keyword_hit = bool(getattr(paper, "keyword_hits", []))
        query_location = _query_match_location(paper, phrase_groups) if phrase_groups else "title"
        if expanded_scope:
            topic, location, reason = classify_paper(paper)
            if topic is None:
                continue
            paper.research_topic = topic
            paper.topic_match_location = location
            paper.recommendation_reason = reason
            query_location = location
            # Broader film/plasma papers are vetted by specific topic evidence,
            # not a hard similarity threshold against a Mo-focused library.
        if (not expanded_scope or paper.research_topic == "core") and (
            relevance < relevance_threshold
            or (not has_keyword_hit and relevance < no_keyword_relevance_threshold)
            or query_location == "none"
            or (query_location == "abstract" and relevance < no_keyword_relevance_threshold)
        ):
            continue

        keyword_score = float(getattr(paper, "keyword_score", 0.0) or 0.0)
        keyword_component = (
            min(max(keyword_score / max_keyword_score, 0.0), 1.0)
            if max_keyword_score > 0
            else 0.0
        )
        impact = impact_scores[index]
        final_score = (0.55 * impact) + (0.35 * relevance) + (0.10 * keyword_component)

        paper.classic_score = final_score * 100.0
        paper.relevance_percent = relevance * 100.0
        paper.impact_percent = impact * 100.0
        paper.keyword_percent = keyword_component * 100.0
        # The existing email star renderer expects a score on an approximately
        # 0..10 scale. Keep that contract while retaining the 0..100 breakdown.
        paper.score = final_score * 10.0
        if index in top_impact_indexes:
            high_impact_ranked.append(paper)
        else:
            other_relevant_ranked.append(paper)

    high_impact_ranked.sort(key=lambda paper: paper.classic_score, reverse=True)
    other_relevant_ranked.sort(key=lambda paper: paper.classic_score, reverse=True)
    fallback_count = max(minimum_candidates - len(high_impact_ranked), 0)
    return high_impact_ranked + other_relevant_ranked[:fallback_count]
