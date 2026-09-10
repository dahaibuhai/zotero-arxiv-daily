import unittest

from classic_ranker import rank_classic_papers


class Candidate:
    def __init__(self, citations, influential, relevance, keyword_score=0.0):
        self.citation_count = citations
        self.influential_citation_count = influential
        self.score = relevance * 10
        self.keyword_score = keyword_score


class ClassicRankerTests(unittest.TestCase):
    def test_keeps_only_top_impact_quartile(self):
        candidates = [
            Candidate(citations=200 - index * 10, influential=20 - index, relevance=0.8)
            for index in range(12)
        ]

        ranked = rank_classic_papers(candidates)

        self.assertEqual(len(ranked), 3)
        self.assertEqual([paper.citation_count for paper in ranked], [200, 190, 180])

    def test_relevance_gate_can_leave_fewer_than_requested(self):
        candidates = [
            Candidate(citations=200, influential=20, relevance=0.60),
            Candidate(citations=190, influential=19, relevance=0.64),
            Candidate(citations=180, influential=18, relevance=0.90),
            Candidate(citations=170, influential=17, relevance=0.90),
        ]

        ranked = rank_classic_papers(candidates)

        self.assertEqual(ranked, [])

    def test_score_uses_55_35_10_weighting(self):
        high = Candidate(citations=100, influential=10, relevance=0.80, keyword_score=2.0)
        low = Candidate(citations=10, influential=0, relevance=0.90, keyword_score=0.0)

        ranked = rank_classic_papers(
            [high, low],
            relevance_threshold=0.65,
            impact_top_fraction=0.5,
        )

        self.assertEqual(ranked, [high])
        self.assertAlmostEqual(high.classic_score, 93.0)
        self.assertAlmostEqual(high.impact_percent, 100.0)
        self.assertAlmostEqual(high.relevance_percent, 80.0)


if __name__ == "__main__":
    unittest.main()
