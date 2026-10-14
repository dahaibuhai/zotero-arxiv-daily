import re


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower()).strip()


def paper_key(paper):
    doi = getattr(paper, "doi", "") or ""
    arxiv_id = getattr(paper, "arxiv_id", "") or ""
    title = normalize_title(getattr(paper, "title", ""))
    if doi:
        return ("doi", doi.lower())
    if arxiv_id:
        return ("id", arxiv_id.lower())
    return ("title", title)


def identity_keys(paper):
    """Compare all available identities, including versionless arXiv IDs."""
    keys = {paper_key(paper)}
    title = normalize_title(getattr(paper, "title", ""))
    if title:
        keys.add(("title", title))
    identifier = str(getattr(paper, "arxiv_id", "") or "").lower()
    identifier = re.sub(r"v\d+$", "", identifier.rsplit("/abs/", 1)[-1])
    if re.fullmatch(r"\d{4}\.\d{4,5}|[a-z.-]+/\d{7}", identifier):
        keys.add(("id", identifier))
    return keys


def history_identity_keys(history):
    keys = set()
    for key, record in history.items():
        kind, _, value = key.partition(":")
        if kind == "id":
            value = re.sub(r"v\d+$", "", value)
        keys.add((kind, value.lower()))
        title = normalize_title(record.get("title", ""))
        if title:
            keys.add(("title", title))
    return keys


def dedupe_papers(papers):
    seen = set()
    deduped = []
    for paper in papers:
        keys = identity_keys(paper)
        if keys & seen:
            seen.update(keys)
            continue
        seen.update(keys)
        deduped.append(paper)
    return deduped
