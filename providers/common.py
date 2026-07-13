from functools import cached_property

from llm import get_llm


class SimpleAuthor:
    def __init__(self, name: str):
        self.name = name


class ExternalPaper:
    def __init__(
        self,
        title="",
        summary="",
        authors=None,
        paper_id="",
        pdf_url="",
        source="External",
        venue="",
        publication_date="",
        doi="",
        keyword_score=0.0,
        journal_weight=0.0,
        link_label="PDF",
    ):
        self.title = title or ""
        self.summary = summary or ""
        self.authors = [SimpleAuthor(author) for author in (authors or [])]
        self.arxiv_id = paper_id or doi or title
        self.pdf_url = pdf_url or ""
        self.source = source
        self.venue = venue or ""
        self.publication_date = publication_date or ""
        self.doi = doi or ""
        self.score = 0.0
        self.keyword_score = keyword_score
        self.journal_weight = journal_weight
        self.link_label = link_label or "Paper link"
        self.keyword_hits = []
        self.code_url = None
        self.affiliations = None

    @cached_property
    def tldr(self) -> str:
        llm = get_llm()
        prompt = (
            f"Given the title and abstract of a scientific paper, "
            f"generate a one-sentence TLDR summary in {llm.lang}.\n\n"
            f"Title: {self.title}\n\n"
            f"Abstract: {self.summary}"
        )
        return llm.generate(
            messages=[
                {
                    "role": "system",
                    "content": "You summarize scientific papers accurately and concisely.",
                },
                {"role": "user", "content": prompt},
            ]
        )
