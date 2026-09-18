import unittest

from source_quota import select_source_quotas, semantic_shortfall


class Paper:
    def __init__(self, title, source):
        self.title = title
        self.source = source


class SourceQuotaTests(unittest.TestCase):
    def test_classics_fill_only_the_missing_semantic_slots(self):
        arxiv = [Paper(f"arxiv-{index}", "arXiv") for index in range(5)]
        semantic = [Paper(f"semantic-{index}", "Semantic Scholar") for index in range(2)]
        crossref = Paper("crossref", "Crossref")
        classics = [Paper(f"classic-{index}", "Semantic Scholar") for index in range(4)]

        selected, arxiv_count, new_semantic_count, classic_count = select_source_quotas(
            arxiv + semantic + [crossref],
            classics,
            arxiv_quota=5,
            semantic_scholar_quota=5,
        )

        self.assertEqual(arxiv_count, 5)
        self.assertEqual(new_semantic_count, 2)
        self.assertEqual(classic_count, 3)
        self.assertEqual([paper.title for paper in selected], [
            "arxiv-0", "arxiv-1", "arxiv-2", "arxiv-3", "arxiv-4",
            "semantic-0", "semantic-1", "classic-0", "classic-1", "classic-2",
        ])

    def test_surplus_semantic_papers_do_not_use_classics(self):
        semantic = [Paper(f"semantic-{index}", "Semantic Scholar") for index in range(6)]
        classics = [Paper("classic-0", "Semantic Scholar")]

        selected, arxiv_count, new_semantic_count, classic_count = select_source_quotas(
            semantic,
            classics,
            arxiv_quota=5,
            semantic_scholar_quota=5,
        )

        self.assertEqual(arxiv_count, 0)
        self.assertEqual(new_semantic_count, 5)
        self.assertEqual(classic_count, 0)
        self.assertEqual([paper.title for paper in selected], [
            "semantic-0", "semantic-1", "semantic-2", "semantic-3", "semantic-4",
        ])

    def test_shortfall_and_invalid_quotas(self):
        self.assertEqual(semantic_shortfall(0, 5), 5)
        self.assertEqual(semantic_shortfall(2, 5), 3)
        self.assertEqual(semantic_shortfall(6, 5), 0)

        with self.assertRaises(ValueError):
            select_source_quotas([], [], arxiv_quota=-1, semantic_scholar_quota=5)


if __name__ == "__main__":
    unittest.main()
