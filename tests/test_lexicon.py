"""Lexicon tagger: true hits, and the false friends we explicitly guard against."""

import pytest

from lexicon import Tags, describe, entity_overlap, normalize_iast, tag


@pytest.mark.parametrize("text, plant", [
    ("mustamAragvadhaH pAThA triphalA devadAru ca| khadiro nimbo haridre||12||", "turmeric"),
    ("pippalIpippalImUlacavya", "long_pepper"),
    ("yaShTImadhukasya cUrNam", "licorice"),
    ("kaM vacAm| viDa~ggam", "vacha"),
])
def test_sanskrit_plants_hit(text, plant):
    assert plant in tag(text, "sa").plants


@pytest.mark.parametrize("text, wrong", [
    ("dAruharidrA ca", "turmeric"),               # tree turmeric is a different plant
    ("haridrAmehashca", "turmeric"),              # a TYPE of prameha, not the plant
    ("pi tvacAM dArayati", "vacha"),              # tvacA = skin
    ("nimbUkasya rasaH", "neem"),                 # nimbU = lemon
])
def test_sanskrit_plant_false_friends(text, wrong):
    assert wrong not in tag(text, "sa").plants


@pytest.mark.parametrize("text, wrong", [
    ("darshanaM sparshanaM", "hemorrhoids"),      # seeing / touching
    ("prakAshayati", "cough"),                    # illuminates
    ("bhaviShyati", "poisoning"),                 # future tense of 'to be'
    ("viShayAn viShamAshanam", "poisoning"),      # object / irregular eating
    ("vishvAsaH", "asthma"),                      # trust
])
def test_sanskrit_condition_false_friends(text, wrong):
    assert wrong not in tag(text, "sa").conditions


def test_sanskrit_is_case_sensitive():
    # 'kAs' (cough) vs 'kas' (who) differ only by case of the vowel
    assert "cough" in tag("kAsashvAsau", "sa").conditions
    assert "cough" not in tag("kasmAt", "sa").conditions


def test_english_patent_text():
    t = tag("A Curcuma longa extract for treating psoriasis and wound healing", "en")
    assert t.plants == ["turmeric"]
    assert set(t.conditions) == {"skin_disease", "wound"}


def test_english_word_start_anchor():
    assert "pain" not in tag("Made in Spain", "en").conditions
    assert "alcoholism" not in tag("an alcoholic extract of the leaves", "en").conditions


def test_iast_query_normalized():
    assert normalize_iast("haridrā") == "haridrA"
    assert "turmeric" in tag("haridrā", "auto").plants
    assert "fever" in tag("jvara", "auto").conditions


def test_auto_mode_handles_both_languages():
    t = tag("turmeric and pippalI for kAsa", "auto")
    assert {"turmeric", "long_pepper"} <= set(t.plants)
    assert "cough" in t.conditions


def test_describe_is_english():
    d = describe(Tags(plants=["turmeric"], conditions=["fever"]))
    assert d == "Substances: Turmeric (Curcuma longa). Indications: Fever"


def test_entity_overlap_weights():
    q = Tags(plants=["turmeric"], conditions=["skin_disease"])
    assert entity_overlap(q, Tags(plants=["turmeric"], conditions=["skin_disease"]))[0] == 1.0
    assert entity_overlap(q, Tags(plants=["turmeric"]))[0] == pytest.approx(0.6)
    assert entity_overlap(q, Tags(conditions=["skin_disease"]))[0] == pytest.approx(0.4)
    assert entity_overlap(Tags(conditions=["fever"]), Tags(conditions=["fever"]))[0] == 1.0
    score, shared = entity_overlap(q, Tags(plants=["neem"]))
    assert score == 0 and shared == {"plants": [], "conditions": []}


@pytest.mark.parametrize("text, wrong", [
    ("kShitakamalashIlA", "water_lily"),          # a personal name
    ("vedaM pradarshayan", "gynecological"),      # 'showing'
    ("amedhyaM", "cognition"),                    # 'impure'
    ("abhiShyandi bhojanam", "eye"),              # channel-blocking food quality
    ("durbalAtivishuShka", "bala"),               # 'weak'
])
def test_more_false_friends(text, wrong):
    t = tag(text, "sa")
    assert wrong not in t.plants + t.conditions
