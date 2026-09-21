import unittest

from classic_ranker import rank_classic_papers


class Candidate:
    def __init__(self, citations, influential, relevance, keyword_score=0.0, title="", summary=""):
        self.citation_count = citations
        self.influential_citation_count = influential
        self.score = relevance * 10
        self.keyword_score = keyword_score
        self.keyword_hits = ["magnetron sputtering"] if keyword_score > 0 else []
        self.title = title
        self.summary = summary


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

    def test_high_impact_without_keyword_requires_higher_relevance(self):
        broad_high_impact = Candidate(
            citations=2000,
            influential=50,
            relevance=0.70,
        )
        topic_match = Candidate(
            citations=1000,
            influential=20,
            relevance=0.71,
            keyword_score=2.0,
        )

        ranked = rank_classic_papers(
            [broad_high_impact, topic_match],
            impact_top_fraction=1.0,
        )

        self.assertEqual(ranked, [topic_match])

    def test_quota_backfills_relevant_papers_outside_impact_quartile(self):
        candidates = [
            Candidate(citations=1000 - index * 50, influential=50 - index, relevance=0.80)
            for index in range(8)
        ]
        candidates[0].score = 6.0  # The most cited paper is off topic.

        ranked = rank_classic_papers(candidates, minimum_candidates=4)

        self.assertEqual(len(ranked), 4)
        self.assertEqual([paper.citation_count for paper in ranked], [950, 900, 850, 800])
        self.assertTrue(all(paper.relevance_percent >= 78 for paper in ranked))

    def test_topic_query_excludes_broad_thin_film_paper(self):
        focused = Candidate(400, 30, 0.72, 2.0, title="Magnetron sputtering of Mo films")
        broad = Candidate(1000, 100, 0.72, 2.0, title="Materials science of thin films")
        summary_only = Candidate(
            800, 60, 0.73, 2.0,
            title="Oblique angle deposition of thin films",
            summary="Includes magnetron sputtering and other deposition techniques.",
        )

        ranked = rank_classic_papers(
            [focused, broad, summary_only],
            impact_top_fraction=1.0,
            minimum_candidates=3,
            queries_raw='"magnetron sputtering"\n"reactive sputtering"',
        )

        self.assertEqual(ranked, [focused])


if __name__ == "__main__":
    unittest.main()
