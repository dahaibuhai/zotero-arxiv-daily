"""Source-specific selection for the daily literature email."""


ARXIV_SOURCE = "arXiv"
SEMANTIC_SCHOLAR_SOURCE = "Semantic Scholar"


def semantic_shortfall(new_semantic_count: int, semantic_scholar_quota: int) -> int:
    """Return how many vetted historical Semantic papers are needed."""
    return max(semantic_scholar_quota - new_semantic_count, 0)


def select_source_quotas(
    papers: list,
    classic_papers: list,
    *,
    arxiv_quota: int,
    semantic_scholar_quota: int,
) -> tuple[list, int, int, int]:
    """Select ranked papers without allowing one source to crowd out another.

    ``papers`` must already be ranked.  Classic papers are deliberately used
    only for the unfilled part of the Semantic Scholar quota; they never
    replace a new Semantic Scholar result or take an arXiv slot.
    """
    if arxiv_quota < 0 or semantic_scholar_quota < 0:
        raise ValueError("Source quotas must be zero or greater.")

    arxiv = [
        paper
        for paper in papers
        if getattr(paper, "source", "") == ARXIV_SOURCE
    ][:arxiv_quota]
    new_semantic = [
        paper
        for paper in papers
        if getattr(paper, "source", "") == SEMANTIC_SCHOLAR_SOURCE
    ][:semantic_scholar_quota]
    classic_needed = semantic_shortfall(len(new_semantic), semantic_scholar_quota)
    classic = classic_papers[:classic_needed]

    return arxiv + new_semantic + classic, len(arxiv), len(new_semantic), len(classic)
