import math


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
) -> list:
    """Rank historical papers after semantic relevance has been computed.

    The final score follows the configured editorial policy:
    55% citation impact, 35% Zotero-corpus relevance, and 10% keyword match.
    Only the top impact quartile and papers above the relevance threshold remain.
    """
    if not papers:
        return []

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
    ranked = []
    for index, paper in enumerate(papers):
        relevance = min(max(float(getattr(paper, "score", 0.0)) / 10.0, 0.0), 1.0)
        if index not in top_impact_indexes or relevance < relevance_threshold:
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
        ranked.append(paper)

    return sorted(ranked, key=lambda paper: paper.classic_score, reverse=True)
