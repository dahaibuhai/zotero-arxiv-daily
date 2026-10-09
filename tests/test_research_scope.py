import unittest
from types import SimpleNamespace
from collections import Counter

from research_scope import classify_paper, apply_research_scope
from keyword_ranker import keyword_score
from classic_ranker import rank_classic_papers, _query_match_location, _query_phrases
from source_quota import select_source_quotas


def paper(title, summary="", source="Semantic Scholar", score=7.5):
    return SimpleNamespace(title=title, summary=summary, source=source, score=score,
                           citation_count=5, influential_citation_count=0,
                           keyword_score=1.0, keyword_hits=["research topic"])


class ResearchScopeTests(unittest.TestCase):
    def test_md_allowed_only_for_sputtering_even_with_legacy_exclusions(self):
        for title in ("Molecular-dynamics simulation of argon sputtering", "LAMMPS study of sputter-deposited film growth"):
            candidate = paper(title)
            self.assertEqual(classify_paper(candidate)[0], "plasma")
            self.assertIsNotNone(keyword_score(candidate, exclude_raw="molecular dynamics\nmolecular-dynamics\nLAMMPS\nAIMD")[0])
        for title in ("Molecular dynamics of thermal conductivity", "AIMD study of battery electrolytes"):
            self.assertIsNone(classify_paper(paper(title))[0])
            self.assertIsNone(keyword_score(paper(title))[0])

    def test_specific_topics_accept_other_metals_and_methods(self):
        examples = {
            "Hollow-cathode discharge characteristics": "core",
            "Reactive sputter deposition of chromium nitride": "core",
            "Atomic layer deposition of oxide films": "films",
            "Pulsed laser deposition of TiN": "films",
            "Microstructure and adhesion of copper thin films": "films",
            "Langmuir probe diagnostics of low-temperature plasma": "plasma",
            "Particle-in-cell simulation of plasma sheath": "plasma",
        }
        for title, topic in examples.items():
            with self.subTest(title=title):
                self.assertEqual(classify_paper(paper(title))[0], topic)
        self.assertIsNone(classify_paper(paper("Thin film"))[0])
        self.assertIsNone(classify_paper(paper("Plasma biomarkers in human blood"))[0])

    def test_aliases_keep_conjunctions(self):
        groups = _query_phrases('"molybdenum" "magnetron sputtering"')
        self.assertEqual(_query_match_location(paper("Molybdenum films by magnetron sputter deposition"), groups), "title")
        self.assertEqual(_query_match_location(paper("Titanium films by magnetron sputter deposition"), groups), "none")

    def test_expansion_does_not_require_similarity_to_mo_library(self):
        film = paper("Atomic layer deposition of oxide films", score=4.0)
        core = paper("Magnetron sputtering of Mo films", score=4.0)
        unrelated = paper("Molecular dynamics of thermal conductivity", score=9.0)
        ranked = rank_classic_papers([film, core, unrelated], minimum_candidates=3, expanded_scope=True)
        self.assertEqual(ranked, [film])

    def test_balancing_keeps_source_and_new_paper_priority(self):
        arxiv = apply_research_scope([paper("Magnetron sputtering " + str(i), source="arXiv") for i in range(6)]
                                    + [paper("Atomic layer deposition " + str(i), source="arXiv") for i in range(3)])
        semantic = apply_research_scope([paper("Atomic layer deposition " + str(i)) for i in range(4)]
                                       + [paper("Plasma diagnostics " + str(i)) for i in range(4)])
        selected, a, n, c = select_source_quotas(arxiv + semantic, [paper("classic")], arxiv_quota=5, semantic_scholar_quota=5, balance_topics=True)
        self.assertEqual((a, n, c), (5, 5, 0))
        self.assertEqual(Counter(p.research_topic for p in selected), {"core": 4, "films": 3, "plasma": 3})


if __name__ == "__main__":
    unittest.main()
