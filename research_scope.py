"""Explicit editorial scope for thin-film and laboratory-plasma literature."""

import re
from collections import Counter

TOPIC_TARGETS = {"core": 4, "films": 3, "plasma": 3}
TOPIC_LABELS = {"core": "溅射与空心阴极", "films": "薄膜材料与制备", "plasma": "等离子体与模拟"}
DEFAULT_QUERIES = '\n'.join([
    '"magnetron sputtering"', '"reactive sputter deposition"',
    '"high power impulse magnetron sputtering"', '"hot target" "sputtering"',
    '"hollow cathode"', '"thin film" "deposition"',
    '"atomic layer deposition"', '"chemical vapor deposition" "film"',
    '"pulsed laser deposition"', '"cathodic arc" "coating"',
    '"ion beam deposition"', '"evaporation" "thin film"',
    '"low temperature plasma"', '"plasma diagnostics"',
    '"plasma sheath"', '"particle in cell" "plasma"',
    '"fluid model" "plasma"', '"hybrid model" "plasma"',
    '"molecular dynamics" "sputtering"', '"collision cascade" "sputtering"',
    '"Monte Carlo" "sputtering"',
])

MD_TERMS = ("molecular dynamics", "md simulation", "atomistic simulation", "lammps", "aimd", "ab initio molecular dynamics")
CORE_TERMS = ("magnetron sputtering", "magnetron sputter deposition", "reactive sputtering", "reactive sputter deposition", "hipims", "high power impulse magnetron sputtering", "hollow cathode", "hot target", "heated target", "high temperature target")
FILM_METHODS = ("atomic layer deposition", "chemical vapor deposition", "chemical vapour deposition", "pulsed laser deposition", "cathodic arc", "ion beam deposition", "physical vapor deposition", "physical vapour deposition", "electron beam evaporation", "thermal evaporation")
FILM_CONTEXT = ("thin film", "coating", "film growth", "film deposition", "deposited film")
FILM_EVIDENCE = ("deposition", "deposited", "growth", "microstructure", "adhesion", "residual stress", "film stress", "crystallinity", "structure property", "electrical properties", "optical properties", "mechanical properties", "synthesis")
PLASMA_TERMS = ("low temperature plasma", "non thermal plasma", "nonthermal plasma", "plasma diagnostics", "plasma diagnostic", "plasma sheath", "glow discharge", "radio frequency discharge", "microwave discharge", "electron energy distribution", "plasma surface interaction", "langmuir probe", "rf plasma", "capacitively coupled plasma", "inductively coupled plasma")
SIMULATION_TERMS = ("particle in cell", "pic mcc", "fluid model", "hybrid model", "monte carlo", "binary collision approximation", "collision cascade", "simulation", "modeling", "modelling")


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", (text or "").casefold())).strip()


def contains(text, phrase):
    term = normalize(phrase)
    plural = "" if term.endswith("s") else "s?"
    return bool(re.search(r"(?<!\w)" + re.escape(term) + plural + r"(?!\w)", text))


def hits(text, phrases):
    return [phrase for phrase in phrases if contains(text, phrase)]


def sputtering_related(text):
    return bool(re.search(r"\bsputter\w*\b", text))


def classify_paper(paper):
    title = normalize(getattr(paper, "title", ""))
    abstract = normalize(getattr(paper, "summary", ""))
    text = title + " " + abstract
    if hits(text, MD_TERMS) and not sputtering_related(text):
        return None, "none", "分子动力学主题与溅射无关"
    simulation = hits(text, MD_TERMS + SIMULATION_TERMS)
    if simulation and (sputtering_related(text) or contains(text, "plasma")):
        evidence = simulation[0]
        location = "title" if hits(title, MD_TERMS + SIMULATION_TERMS) and (sputtering_related(title) or contains(title, "plasma")) else "abstract"
        return "plasma", location, "等离子体或溅射模拟：" + evidence
    for topic, terms in (("core", CORE_TERMS), ("plasma", PLASMA_TERMS)):
        for location, field in (("title", title), ("abstract", abstract)):
            matches = hits(field, terms)
            if matches:
                return topic, location, "主题匹配：" + matches[0]
    # Specific deposition methods are sufficient in a title; abstracts also
    # need film/coating context to avoid unrelated chemical applications.
    if hits(title, FILM_METHODS):
        return "films", "title", "薄膜制备方法：" + hits(title, FILM_METHODS)[0]
    if hits(text, FILM_CONTEXT) and hits(text, FILM_METHODS + FILM_EVIDENCE):
        location = "title" if hits(title, FILM_CONTEXT) and hits(title, FILM_METHODS + FILM_EVIDENCE) else "abstract"
        return "films", location, "薄膜制备或结构性能关系"
    # General sputtering (including other metals and yield experiments).
    if sputtering_related(text):
        return "core", "title" if sputtering_related(title) else "abstract", "溅射过程或材料研究"
    return None, "none", "未匹配薄膜制备、实验室等离子体或溅射研究"


def apply_research_scope(papers):
    kept = []
    for paper in papers:
        topic, location, reason = classify_paper(paper)
        if topic:
            paper.research_topic = topic
            paper.topic_match_location = location
            paper.recommendation_reason = reason
            kept.append(paper)
    return kept


def select_balanced(ranked, count, selected):
    """Soft 4/3/3 targets; keep source/new-paper constraints authoritative."""
    remaining = list(ranked)
    chosen = []
    counts = Counter(getattr(p, "research_topic", "") for p in selected)
    while remaining and len(chosen) < count:
        eligible = [p for p in remaining if counts[getattr(p, "research_topic", "")] < TOPIC_TARGETS.get(getattr(p, "research_topic", ""), 0)]
        paper = eligible[0] if eligible else remaining[0]
        remaining.remove(paper)
        chosen.append(paper)
        counts[getattr(paper, "research_topic", "")] += 1
    return chosen
