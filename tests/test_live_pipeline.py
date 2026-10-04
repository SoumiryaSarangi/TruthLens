"""The live pass inside the orchestrator (post-test Phase 7).

A fake live source and a fake stance model stand in for the network and the
GPU, so what is tested is the pipeline's decisions: when live evidence replaces
an answer, when it must NOT, and what the user is told.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")

from pipeline.contracts import FactCheckMatch
from pipeline.live import LivePassage, LiveResult, live_verdict
from pipeline.orchestrator import Orchestrator, PipelineConfig

S = {"Supports": 0.95, "Refutes": 0.02, "Neutral": 0.03}
R = {"Supports": 0.02, "Refutes": 0.95, "Neutral": 0.03}
N = {"Supports": 0.05, "Refutes": 0.05, "Neutral": 0.90}


# -- the verdict rule ----------------------------------------------------------


def test_strong_support_is_supported():
    verdict, conf, dist = live_verdict([S, S], [0.8, 0.7])
    assert verdict == "Supported" and conf > 0.9 and dist["Refuted"] < 0.05


def test_a_doubtful_refuter_cannot_outvote_strong_supporters():
    """The weighted mean: a page that only half-refutes (P 0.3) does not move
    three strong supporters."""
    weak = {"Supports": 0.2, "Refutes": 0.3, "Neutral": 0.5}
    assert live_verdict([S, weak, S, S], [0.68, 0.65, 0.64, 0.56])[0] == "Supported"


def test_a_confident_refuter_blocks_supported_the_taj_mahal_pattern():
    """Probe run 1 called three false claims Supported. Supported cannot stand over
    a relevant passage that refutes: it is Conflicting. (The Taj Mahal's 'Black Taj
    Mahal' legend page refutes at cosine 0.65 among three supporters.)"""
    verdict, _, dist = live_verdict([S, R, S, S], [0.68, 0.65, 0.64, 0.56])
    assert verdict == "Conflicting" and dist["Conflicting"] > 0.9


def test_real_disagreement_is_conflicting():
    verdict, conf, _ = live_verdict([S, R], [0.7, 0.7])
    assert verdict == "Conflicting" and conf > 0.9


def test_neutral_evidence_is_nei_and_no_evidence_is_nei():
    assert live_verdict([N, N], [0.6, 0.6])[0] == "NEI"
    assert live_verdict([], []) == ("NEI", 0.0, {"Supported": 0.0, "Refuted": 0.0,
                                                  "Conflicting": 0.0, "NEI": 1.0})


# -- the three changes aimed at probe run 1's failures -------------------------


def test_a_fact_checks_stance_is_its_publishers_rating():
    from pipeline.live import rating_stance

    assert [rating_stance(x) for x in ("False", "Mostly False", "True", "Unproven", "")] == [
        "Refutes", "Refutes", "Supports", "Neutral", "Neutral"]


def test_nli_never_reads_a_fact_check_headline_in_the_verdict_path():
    """A headline that restates the rumour ('Can lemon water cure cancer?') was
    labelled Supports. The verdict path takes the rating instead."""
    rated = LivePassage("Can lemon water cure cancer? — FC rating: False", "FC", "https://fc/x",
                        "factcheck_live", 0.8, "en", rating_stance="Refutes")
    orch = make(FakeLive(LiveResult(passages=[rated], sources_used=["google_factcheck"])))
    orch.stance = Exploding(S)               # would label it Supports, and must not be asked
    res = orch.verify("Lemon water cures cancer", live=True).results[0]
    assert res.verdict == "Refuted" and res.passages[0].stance == "Refutes"


def test_nli_reads_the_focused_premise_not_the_whole_page():
    seen = []

    class Recorder(FakeStance):
        def label(self, claim, passages):
            seen.extend(passages)
            return super().label(claim, passages)

    page = LivePassage("A long lead about many things. Delhi is the capital of India. More text.",
                       "Delhi", "https://x/Delhi", "wikipedia", 0.8, "en",
                       premise="Delhi is the capital of India.")
    orch = make(FakeLive(LiveResult(passages=[page], sources_used=["wikipedia"])))
    orch.stance = Recorder(S)
    orch.verify("Delhi is the capital of India", live=True)
    assert seen == ["Delhi is the capital of India."]


def test_the_premise_is_the_two_sentences_closest_to_the_claim():
    from pipeline.live import LiveEvidence
    from retrieval.live.factcheck import GoogleFactCheck
    from retrieval.live.wikipedia import WikipediaLive

    def enc(texts):
        return [[1.0, 0.0] if "alpha" in t else [0.0, 1.0] for t in texts]

    live = LiveEvidence(WikipediaLive(), GoogleFactCheck(key=""), encode=enc)
    text = ("Opening sentence about nothing relevant here. The alpha sentence one is here. "
            "Filler sentence about unrelated matters again. The alpha sentence two is here.")
    assert live._premise(["alpha"], text) == "The alpha sentence one is here. The alpha sentence two is here."


# -- the orchestrator ----------------------------------------------------------


class FakeLive:
    def __init__(self, result=None, raises=None):
        self.result, self.raises, self.calls = result, raises, 0

    def gather(self, forms, lang):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.result


class FakeStance:
    impl = "fake"

    def __init__(self, probs):
        self.probs = probs

    def label(self, claim, passages):
        return [SimpleNamespace(stance=max(("Supports", "Refutes", "Neutral"),
                                           key=lambda k: self.probs[k]),
                                prob=max(self.probs.values()), probs=self.probs)
                for _ in passages]


def passage(cos=0.7, source="wikipedia", title="Delhi"):
    return LivePassage(f"{title} is the capital.", title, f"https://x/{title}", source, cos, "en")


def make(live=None, enabled=True, verdict=True):
    cfg = PipelineConfig(stages={"stance": "always_neutral"}, live_search=enabled,
                         live_verdict=verdict)
    orch = Orchestrator(cfg)
    orch._live = live
    orch.stance = FakeStance(S)
    return orch


def test_live_evidence_replaces_the_offline_answer_and_says_where_it_came_from():
    live = FakeLive(LiveResult(passages=[passage(0.8), passage(0.6, title="India")],
                               sources_used=["wikipedia"]))
    trace = make(live).verify("Delhi is the capital of India", live=True)
    res = trace.results[0]
    assert (res.verdict, res.path, res.explanation_source) == ("Supported", "evidence", "template")
    assert res.live_sources == ["wikipedia"]
    assert {p.source for p in res.passages} == {"wikipedia"} and res.passages[0].stance == "Supports"
    assert any("NOT calibrated" in (e.note or "") for e in trace.events)


# -- evidence-only mode (the served default) ----------------------------------


class Exploding(FakeStance):
    """Fails the test if anything asks the stance model about live evidence."""

    def label(self, claim, passages):
        raise AssertionError("evidence-only mode must not run NLI on live evidence")


def test_evidence_only_lists_the_sources_and_gives_no_verdict():
    live = FakeLive(LiveResult(passages=[passage(0.8), passage(0.6, title="India")],
                               sources_used=["wikipedia", "google_factcheck"]))
    orch = make(live, verdict=False)
    orch.stance = Exploding(S)
    trace = orch.verify("Delhi is the capital of India", live=True)
    res = trace.results[0]
    assert (res.verdict, res.abstained, res.confidence) == ("NEI", True, 0.0)
    assert [p.stance for p in res.passages] == [None, None]
    assert {p.source for p in res.passages} == {"wikipedia"}
    assert "Delhi" in res.explanation and "[1]" in res.explanation and "Read them" in res.explanation
    assert res.live_sources == ["wikipedia", "google_factcheck"]
    assert any("listed, not judged" in (e.note or "") for e in trace.events)


def test_a_false_claim_cannot_be_called_supported_by_a_model_misreading_the_evidence():
    """Probe run 1: NLI called fact-check headlines that restate a rumour, and pages
    on the same topic, 'Supports' -- and a false claim came out Supported. In
    evidence-only mode no NLI label can reach the verdict, whatever it says."""
    live = FakeLive(LiveResult(passages=[passage(0.8, source="factcheck_live", title="Does lemon cure cancer?")],
                               sources_used=["google_factcheck"]))
    orch = make(live, verdict=False)
    orch.stance = FakeStance(S)               # a stance model that says Supports to everything
    res = orch.verify("Lemon water cures cancer", live=True).results[0]
    assert res.verdict == "NEI" and res.abstained


def test_evidence_only_still_reports_nothing_relevant_honestly():
    live = FakeLive(LiveResult(passages=[passage(0.31, title="Britannica")], sources_used=["wikipedia"]))
    res = make(live, verdict=False).verify("Each student gets Rs 6000", live=True).results[0]
    assert res.verdict == "NEI" and res.abstained and "nothing relevant" in res.explanation


def test_the_served_config_serves_the_validated_live_verdict():
    cfg = PipelineConfig.load("configs/pipeline/dev.yaml")
    # Served WITH a verdict since protocol 2 (docs/live-fever-protocol-2.md) passed;
    # nothing else turns it on, so no evaluation config can reach it.
    assert cfg.live_search is True and cfg.live_verdict is True and cfg.live_translate is True
    assert PipelineConfig().live_verdict is False and PipelineConfig().live_translate is False


def test_a_published_fact_check_of_this_claim_answers_it_on_the_fast_path():
    match = FactCheckMatch(factcheck_id="u", score=0.95, verdict="Refuted", title="No, it does not",
                           url="https://fc/u", publisher="FC", lang="en")
    live = FakeLive(LiveResult(match=match, sources_used=["google_factcheck"]))
    res = make(live).verify("some rumour", live=True).results[0]
    assert (res.path, res.verdict, res.cited) == ("fast", "Refuted", ["u"])
    assert res.live_sources == ["google_factcheck"] and "FC" in res.explanation


def test_nothing_relevant_is_an_honest_not_enough_evidence():
    live = FakeLive(LiveResult(passages=[passage(0.31, title="Britannica")], sources_used=["wikipedia"]))
    trace = make(live).verify("Each student gets Rs 6000", live=True)
    res = trace.results[0]
    assert res.verdict == "NEI" and res.abstained and "nothing relevant" in res.explanation
    assert any("no live source is about this claim" in (e.note or "") for e in trace.events)


def test_a_source_that_is_down_leaves_the_offline_answer_untouched():
    offline = make(FakeLive(LiveResult())).verify("Delhi is the capital of India").results[0]
    down = FakeLive(LiveResult(notes=["degraded: wikipedia unavailable (HTTP 429)"]))
    live = make(down).verify("Delhi is the capital of India", live=True).results[0]
    assert live.model_dump() == offline.model_dump()


def test_a_crash_in_the_live_path_keeps_the_offline_answer_and_records_it():
    offline = make(FakeLive(LiveResult())).verify("Delhi is the capital of India").results[0]
    trace = make(FakeLive(raises=RuntimeError("boom"))).verify("Delhi is the capital of India", live=True)
    assert trace.results[0].model_dump() == offline.model_dump()
    assert any("live search failed (RuntimeError)" in (e.note or "") for e in trace.events)


def test_nothing_is_fetched_unless_the_request_asks():
    live = FakeLive(LiveResult(passages=[passage()]))
    orch = make(live)
    orch.verify("Delhi is the capital of India")                    # live=False, the default
    assert live.calls == 0 and orch._live is live


def test_a_config_without_live_search_refuses_visibly():
    live = FakeLive(LiveResult(passages=[passage()]))
    trace = make(live, enabled=False).verify("Delhi is the capital of India", live=True)
    assert live.calls == 0
    assert any("disabled in this pipeline config" in (e.note or "") for e in trace.events)


def test_an_averitec_claim_never_goes_live():
    live = FakeLive(LiveResult(passages=[passage()]))
    trace = make(live).verify("Were nursing posts restored?", claim_idx=7, live=True)
    assert live.calls == 0
    assert any("free text only" in (e.note or "") for e in trace.events)


def test_the_live_client_is_not_even_built_when_it_is_not_asked_for():
    orch = Orchestrator(PipelineConfig(stages={"stance": "always_neutral"}, live_search=True))
    assert orch._live is None


# -- the API ---------------------------------------------------------------------


def test_the_api_flag_defaults_off_and_is_passed_through(monkeypatch):
    pytest.importorskip("fastapi")
    import app.main as main
    from fastapi.testclient import TestClient

    seen = []
    orch = make(FakeLive(LiveResult()))
    real = orch.verify
    orch.verify = lambda text, claim_idx=None, live=False: (seen.append(live), real(text, claim_idx, live))[1]
    monkeypatch.setattr(main, "_orchestrator", orch)
    monkeypatch.setattr(main, "_config", orch.cfg)
    client = TestClient(main.app)
    client.post("/verify", json={"text": "Delhi is the capital of India"})
    client.post("/verify", json={"text": "Delhi is the capital of India", "live_search": True})
    assert seen == [False, True]


# -- route A: the claim judged in English --------------------------------------


class FakeTranslator:
    def __init__(self, english="Mumbai is the capital of India", raises=None):
        self.english, self.raises, self.seen = english, raises, []

    def to_english(self, text, lang):
        self.seen.append((text, lang))
        if self.raises:
            raise self.raises
        return self.english


def make_translating(live, translator):
    orch = make(live)
    orch.cfg.live_translate = True
    orch._translator = translator
    orch._live_nli = orch.stance            # the English NLI stands in as the fake too
    orch._live_partner_nli = Mirror(orch)   # by default the second model agrees with the first
    return orch


class Mirror:
    """A second NLI model that says whatever the first one says (the agreeing case)."""

    impl = "mirror"

    def __init__(self, orch):
        self.orch = orch

    def label(self, claim, passages):
        return self.orch._live_nli.label(claim, passages)


def test_a_hindi_claim_is_judged_in_english_against_english_pages():
    seen = {}

    class Recorder(FakeStance):
        def label(self, claim, passages):
            seen["claim"], seen["passages"] = claim, passages
            return super().label(claim, passages)

    page = LivePassage("Mumbai is the capital of Maharashtra.", "Mumbai", "https://en/Mumbai",
                       "wikipedia", 0.7, "en", premise="Mumbai is the capital of Maharashtra.")
    live = FakeLive(LiveResult(passages=[page], sources_used=["wikipedia"]))
    orch = make_translating(live, FakeTranslator())
    orch.stance = orch._live_nli = Recorder(R)
    res = orch.verify("मुंबई भारत की राजधानी है", live=True).results[0]
    assert seen["claim"] == "Mumbai is the capital of India"
    assert seen["passages"] == ["Mumbai is the capital of Maharashtra."]
    assert res.verdict == "Refuted"


def test_the_english_claim_is_added_to_the_search_forms():
    live = FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"]))
    forms = []
    live.gather = lambda f, lang: (forms.extend(f), live.result)[1]
    orch = make_translating(live, FakeTranslator())
    orch.verify("मुंबई भारत की राजधानी है", live=True)
    assert forms[0] == "मुंबई भारत की राजधानी है" and forms[-1] == "Mumbai is the capital of India"


def test_a_page_left_in_hindi_is_listed_but_not_judged_in_translate_mode():
    hi = LivePassage("मुंबई एक शहर है।", "मुंबई", "https://hi/x", "wikipedia", 0.8, "hi")
    en = LivePassage("Mumbai is the capital of Maharashtra.", "Mumbai", "https://en/Mumbai",
                     "wikipedia", 0.6, "en")
    orch = make_translating(FakeLive(LiveResult(passages=[hi, en], sources_used=["wikipedia"])),
                            FakeTranslator())
    orch.stance = orch._live_nli = FakeStance(R)
    res = orch.verify("मुंबई भारत की राजधानी है", live=True).results[0]
    assert res.verdict == "Refuted" and len(res.passages) == 2
    assert res.passages[0].stance is None or res.passages[0].stance == ""


def test_a_translation_failure_keeps_the_offline_answer():
    live = FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"]))
    orch = make_translating(live, FakeTranslator(raises=RuntimeError("no model")))
    offline = orch.verify("मुंबई भारत की राजधानी है").results[0]
    trace = orch.verify("मुंबई भारत की राजधानी है", live=True)
    assert trace.results[0].verdict == offline.verdict      # the offline answer is kept, not a blind judgement
    assert any("claim translation failed" in (e.note or "") for e in trace.events)


def test_translate_mode_never_runs_on_an_english_claim_or_when_off():
    tr = FakeTranslator()
    orch = make_translating(FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"])), tr)
    orch.verify("Delhi is the capital of India", live=True)
    assert tr.seen == []
    off = make(FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"])))
    off._translator = tr
    off.verify("मुंबई भारत की राजधानी है", live=True)
    assert tr.seen == []


def test_live_translate_does_not_move_any_existing_config_hash():
    assert "live_translate" not in PipelineConfig().describe()
    assert PipelineConfig(live_translate=True).describe()["live_translate"] is True


def test_translate_mode_reads_live_evidence_with_the_english_nli_not_the_served_stance():
    served = FakeStance(S)
    orch = make_translating(FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"])),
                            FakeTranslator())
    orch.stance, orch._live_nli = served, FakeStance(R)
    assert orch.verify("Delhi is the capital of India", live=True).results[0].verdict == "Refuted"
    assert make(None)._live_stance() is not None


def test_without_translate_mode_the_served_stance_reads_live_evidence():
    orch = make(FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"])))
    assert orch._live_stance() is orch.stance


# -- entity grounding ------------------------------------------------------------


@pytest.mark.parametrize("claim,title,expected", [
    ("Ganga falls into the Arabian Sea", "Arabian Sea", True),
    ("Ganga falls into the Arabian Sea", "Ganges", True),                  # spelling variant
    ("Ganga falls into the Arabian Sea", "Daman Ganga River", False),     # a different river
    ("Ganga falls into the Arabian Sea", "Varahi River", False),
    ("Bangalore is the capital of Tamil Nadu", "Bengaluru", True),         # consonant skeleton
    ("The tea stall near our office closes at 9 pm on Sundays", "Brick Lane Market", False),
    ("Mumbai is the capital of India", "List of state and union territory capitals in India", False),
    ("Indira Gandhi was India's first woman Prime Minister", "Indira Gandhi (disambiguation)", True),
    ("Indira Gandhi was India's first woman Prime Minister", "Assassination of Indira Gandhi", False),
    ("Delhi is the capital", "List of", False),                            # nothing but generic words
])
def test_title_grounding(claim, title, expected):
    from pipeline.live import title_grounded

    assert title_grounded(title, [claim]) is expected


def test_a_native_script_form_does_not_ground_an_english_title():
    from pipeline.live import title_grounded

    assert title_grounded("Mumbai", ["मुंबई भारत की राजधानी है"]) is False
    assert title_grounded("Mumbai", ["मुंबई भारत की राजधानी है", "Mumbai is the capital of India"]) is True


def test_a_page_about_another_subject_is_not_judged_so_it_cannot_make_a_false_claim_supported():
    """The Ganges/Arabian Sea error of probe set 3: pages about two OTHER rivers said
    'flows into the Arabian Sea' and the claim was called Supported."""
    other = LivePassage("The Daman Ganga River flows into the Arabian Sea.", "Daman Ganga River",
                        "https://en/Daman_Ganga_River", "wikipedia", 0.7, "en",
                        premise="The Daman Ganga River flows into the Arabian Sea.")
    orch = make_translating(FakeLive(LiveResult(passages=[other], sources_used=["wikipedia"])),
                            FakeTranslator("The Ganga falls into the Arabian Sea"))
    orch.stance = orch._live_nli = FakeStance(S)           # a model that WOULD say Supports
    trace = orch.verify("गंगा नदी अरब सागर में गिरती है", live=True)
    assert trace.results[0].verdict == "NEI"
    assert any(e.stage == "live" and "not a page about the claim's subject" in (e.note or "") for e in trace.events)


def test_a_page_about_the_subject_is_still_judged():
    ganges = LivePassage("The Ganges empties into the Bay of Bengal.", "Ganges", "https://en/Ganges",
                         "wikipedia", 0.7, "en", premise="The Ganges empties into the Bay of Bengal.")
    orch = make_translating(FakeLive(LiveResult(passages=[ganges], sources_used=["wikipedia"])),
                            FakeTranslator("The Ganga falls into the Arabian Sea"))
    orch.stance = orch._live_nli = FakeStance(R)
    assert orch.verify("गंगा नदी अरब सागर में गिरती है", live=True).results[0].verdict == "Refuted"


def test_grounding_is_only_applied_in_translate_mode():
    other = LivePassage("A page.", "Some Other Page", "https://x/o", "wikipedia", 0.7, "en")
    orch = make(FakeLive(LiveResult(passages=[other], sources_used=["wikipedia"])))
    assert orch.verify("Delhi is the capital of India", live=True).results[0].verdict == "Supported"


def test_a_fact_check_of_a_different_claim_is_listed_not_judged_on_the_english_route():
    """A False-rated story about Modi must not refute 'Modi is the Prime Minister'."""
    review = LivePassage("Viral video of Modi is fake — Alt News rating: False", "Alt News",
                         "https://altnews/x", "factcheck_live", 0.7, "en", rating_stance="Refutes")
    page = LivePassage("Narendra Modi is the prime minister of India.", "Narendra Modi",
                       "https://en/Narendra_Modi", "wikipedia", 0.75, "en",
                       premise="Narendra Modi is the prime minister of India.")
    orch = make_translating(FakeLive(LiveResult(passages=[review, page], sources_used=["wikipedia"])),
                            FakeTranslator())
    orch.stance = orch._live_nli = FakeStance(S)
    res = orch.verify("Narendra Modi is the Prime Minister of India", live=True).results[0]
    assert res.verdict == "Supported"
    assert len(res.passages) == 2             # the review is still shown


# -- the validated rule: two models must agree (protocol 2, variant V2) -------------


def _grounded_page(title="Mumbai"):
    return LivePassage(f"{title} is a city.", title, f"https://en/{title}", "wikipedia", 0.7, "en",
                       premise=f"{title} is a city in India.")


def test_two_agreeing_models_give_a_verdict_with_the_lower_confidence():
    orch = make_translating(FakeLive(LiveResult(passages=[_grounded_page()], sources_used=["wikipedia"])),
                            FakeTranslator("Mumbai is a city in India"))
    orch.stance = orch._live_nli = FakeStance({"Supports": 0.97, "Refutes": 0.01, "Neutral": 0.02})
    orch._live_partner_nli = FakeStance({"Supports": 0.80, "Refutes": 0.05, "Neutral": 0.15})
    res = orch.verify("मुंबई भारत का एक शहर है", live=True).results[0]
    assert res.verdict == "Supported" and not res.abstained
    assert res.confidence == pytest.approx(0.80)          # the LOWER of the two


def test_disagreeing_models_give_no_verdict_and_say_so():
    orch = make_translating(FakeLive(LiveResult(passages=[_grounded_page()], sources_used=["wikipedia"])),
                            FakeTranslator("Mumbai is a city in India"))
    orch.stance = orch._live_nli = FakeStance(S)
    orch._live_partner_nli = FakeStance(R)                 # the second model says Refutes
    trace = orch.verify("मुंबई भारत का एक शहर है", live=True)
    res = trace.results[0]
    assert res.verdict == "NEI" and res.abstained
    assert any("did not agree" in (e.note or "") for e in trace.events)


def test_agreement_on_something_other_than_supported_or_refuted_is_no_verdict():
    """Both models Neutral -> NEI, and both 'Conflicting' is also not shown: only the two
    verdicts the protocol validated are ever shown."""
    orch = make_translating(FakeLive(LiveResult(passages=[_grounded_page()], sources_used=["wikipedia"])),
                            FakeTranslator("Mumbai is a city in India"))
    orch.stance = orch._live_nli = FakeStance(N)
    orch._live_partner_nli = FakeStance(N)
    assert orch.verify("मुंबई भारत का एक शहर है", live=True).results[0].verdict == "NEI"


def test_a_failing_second_model_keeps_the_offline_answer():
    class Broken:
        impl = "broken"

        def label(self, claim, passages):
            raise RuntimeError("out of memory")

    orch = make_translating(FakeLive(LiveResult(passages=[_grounded_page()], sources_used=["wikipedia"])),
                            FakeTranslator("Mumbai is a city in India"))
    orch._live_partner_nli = Broken()
    offline = orch.verify("मुंबई भारत का एक शहर है").results[0]
    trace = orch.verify("मुंबई भारत का एक शहर है", live=True)
    assert trace.results[0].verdict == offline.verdict
    assert any("second NLI model failed" in (e.note or "") for e in trace.events)


def test_the_second_model_is_not_consulted_off_the_english_route():
    class Exploding2:
        impl = "x"

        def label(self, claim, passages):
            raise AssertionError("the partner must not run when live_translate is off")

    orch = make(FakeLive(LiveResult(passages=[passage()], sources_used=["wikipedia"])))
    orch._live_partner_nli = Exploding2()
    assert orch.verify("Delhi is the capital of India", live=True).results[0].verdict == "Supported"


def test_warm_live_is_a_no_op_unless_the_live_verdict_is_on():
    orch = make(None)
    orch.cfg.live_verdict = False
    orch.warm_live()                       # must not load anything or raise
    assert orch._translator is None and orch._live_partner_nli is None
