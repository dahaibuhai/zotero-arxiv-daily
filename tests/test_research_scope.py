import unittest
from types import SimpleNamespace
from collections import Counter

from research_scope import classify_paper, apply_research_scope, scoped_queries, DEFAULT_QUERIES
from keyword_ranker import keyword_score
from classic_ranker import rank_classic_papers, _query_match_location, _query_phrases
from source_quota import select_source_quotas


def paper(title, summary="", source="Semantic Scholar", score=7.5):
    return SimpleNamespace(title=title, summary=summary, source=source, score=score,
                           citation_count=5, influential_citation_count=0,
                           keyword_score=1.0, keyword_hits=["research topic"])


class ResearchScopeTests(unittest.TestCase):
    def test_experimental_epitaxy_and_contextual_abbreviations(self):
        candidate = paper("Doubly Metastable Synthesis for Accelerated Quantum Materials Discovery",
                          "We develop diffusion-activated epitaxy, a technique combining diffusion and epitaxy. We experimentally identify four phases by X-ray diffraction.")
        self.assertEqual(classify_paper(candidate)[0], "films")
        for title in ("ALD of oxide films", "CVD deposition on copper substrates", "PLD growth of TiN films", "PVD coatings", "MBE growth of epitaxial layers"):
            self.assertEqual(classify_paper(paper(title))[0], "films")
        self.assertIsNone(classify_paper(paper("CVD risk in clinical patients"))[0])
        self.assertIsNone(classify_paper(paper("A new MBE algorithm"))[0])

    def test_method_exclusions_require_concrete_material_subject(self):
        exclusions = "neural network\nlarge language model\nquantum computing\nastrophysics"
        for title in ("Neural network prediction of sputtering yield", "MBE growth of thin films for quantum computing", "Magnetron sputtering of coatings for astrophysics"):
            self.assertIsNotNone(keyword_score(paper(title), exclude_raw=exclusions)[0])
        candidate = paper("Neural network for general classification", "Training data include papers about sputtering.")
        self.assertIsNone(keyword_score(candidate, exclude_raw=exclusions)[0])
        self.assertIsNone(keyword_score(paper("Large language model benchmark"), exclude_raw=exclusions)[0])

    def test_macroscopic_printed_layers_are_not_thin_film_filler(self):
        candidate = paper("Wrinkling of a bilayered cylinder under tension",
                          "A thin compressible film coats a core. We fabricated 3D-printed soft cylinders with stiff auxetic layers and bespoke microstructures.")
        self.assertIsNone(classify_paper(candidate)[0])
        deposited = paper("Magnetron sputtering of copper coatings on 3D-printed substrates")
        self.assertEqual(classify_paper(deposited)[0], "core")

    def test_md_background_does_not_reject_experimental_films(self):
        background = paper("Atomic layer deposition of oxide films", "We experimentally deposited oxide films. Previous molecular dynamics studies reported adsorption mechanisms.")
        self.assertEqual(classify_paper(background)[0], "films")
        self.assertIsNotNone(keyword_score(background)[0])
        own_md = paper("Atomic layer deposition of oxide films", "We use molecular dynamics to simulate film growth.")
        self.assertIsNone(classify_paper(own_md)[0])
        self.assertIsNone(keyword_score(own_md)[0])
        theoretical = paper("Atomic layer deposition of oxide films", "Previous molecular dynamics studies reported adsorption. We propose a theoretical growth model.")
        self.assertIsNone(classify_paper(theoretical)[0])

    def test_astrophysical_sputtering_is_not_laboratory_sputtering(self):
        astronomy = paper("Complex Organic Molecules in Protostars with ALMA Spectral Surveys",
                          "Spectral modeling supports the dust sputtering scenario induced by shocks.")
        self.assertIsNone(classify_paper(astronomy)[0])
        category_only = paper("Ion-driven erosion dynamics", "We model sputtering by shocks.")
        category_only.arxiv_categories = ("astro-ph.GA",)
        self.assertIsNone(classify_paper(category_only)[0])
        material = paper("Magnetron sputtering of tungsten coatings", "Coatings for astronomical instruments.")
        material.arxiv_categories = ("astro-ph.IM", "physics.app-ph")
        self.assertEqual(classify_paper(material)[0], "core")

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
            "Langmuir probe diagnostics of low-temperature plasma in a glow discharge": "plasma",
            "Particle-in-cell simulation of plasma sheath in a low-pressure discharge": "plasma",
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

    def test_rejects_actual_off_topic_arxiv_selections(self):
        titles = [
            "Imaging ablator-fuel mix of hot spot in inertial confinement fusion via resonant X-ray absorption using an X-ray free electron laser",
            "Beam filamentation instability drives deuterium-tritium fusion with polarized neutron emission",
            "The Richtmyer-Meshkov Instability of Thermal, Isotope, and Species Interfaces in a five-moment multi-fluid plasma",
            "Reconstruction of Multiscale Plasma Dynamics Across Operating Regimes",
            "Kinetic wave activity and proton heating in 3D hybrid simulations of decaying balanced and imbalanced Alfvénic turbulence",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assertIsNone(classify_paper(paper(title, "We use particle-in-cell simulation and plasma diagnostics to study tokamak dynamics."))[0])

    def test_requires_laboratory_context_for_generic_diagnostics_and_models(self):
        self.assertIsNone(classify_paper(paper("Particle-in-cell simulation of plasma sheath"))[0])
        self.assertIsNone(classify_paper(paper("Plasma diagnostics", "Simulation of plasma dynamics"))[0])
        for title in ["Plasma diagnostics in an inductively coupled reactor", "Fluid modeling of plasma sheath in a glow discharge", "Hybrid plasma model for magnetron sputtering", "Monte Carlo simulation of sputtering yield", "Hollow cathode discharge diagnostics", "Argon plasma surface treatment of polymers", "Radio-frequency plasma diagnostics", "Modeling of a plasma etching reactor"]:
            self.assertIsNotNone(classify_paper(paper(title))[0])

    def test_retains_material_processing_when_fusion_is_background(self):
        candidate = paper("Magnetron sputtering of tungsten thin films", "Coatings for tokamak walls are deposited using a magnetron plasma source.")
        self.assertEqual(classify_paper(candidate)[0], "core")

    def test_removes_legacy_unscoped_queries(self):
        queries = scoped_queries('"particle in cell" "plasma"\n"plasma diagnostics"\n"molybdenum" "magnetron sputtering"\n' + DEFAULT_QUERIES)
        self.assertNotIn('"particle in cell" "plasma"', queries.splitlines())
        self.assertNotIn('"plasma diagnostics"', queries.splitlines())
        self.assertIn('"plasma diagnostics" "discharge"', queries.splitlines())
        self.assertIn('"molybdenum" "magnetron sputtering"', queries.splitlines())

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
                                       + [paper("Plasma diagnostics in a glow discharge " + str(i)) for i in range(4)])
        selected, a, n, c = select_source_quotas(arxiv + semantic, [paper("classic")], arxiv_quota=5, semantic_scholar_quota=5, balance_topics=True)
        self.assertEqual((a, n, c), (5, 5, 0))
        self.assertEqual(Counter(p.research_topic for p in selected), {"core": 4, "films": 3, "plasma": 3})


if __name__ == "__main__":
    unittest.main()
