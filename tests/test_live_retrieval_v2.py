"""Live retrieval v2 (docs/live-retrieval-v2-protocol.md, stage 1): entity and acronym queries, deeper candidates.

No network and no model: queries are built from text, and the Wikipedia calls go through a fake opener.
"""
from __future__ import annotations

import io
import json

from pipeline.live import LiveEvidence
from pipeline.orchestrator import PipelineConfig
from retrieval.live.http import Fetcher
from retrieval.live.wikipedia import (
    DEEP_PER_SEARCH,
    WikipediaLive,
    acronyms,
    build_queries,
    build_queries_v2,
    entity_phrases,
)


class Opener:
    def __init__(self, search_hits):
        self.calls: list[str] = []
        self.search_hits = search_hits

    def __call__(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        if "list=search" in url:
            return io.BytesIO(json.dumps({"query": {"search": self.search_hits}}).encode("utf-8"))
        return io.BytesIO(json.dumps({"query": {"pages": {}}}).encode("utf-8"))


class NoFactCheck:
    available = False


def fetcher(tmp_path, opener):
    return Fetcher(cache_dir=tmp_path / "cache", opener=opener, sleep=lambda s: None, min_gap_s=0.0)


def test_entity_phrases_find_named_things_and_skip_sentence_openers():
    assert entity_phrases("Sukanya Samriddhi Account eligible girl child ke liye hota hai") == ["Sukanya Samriddhi Account"]
    assert entity_phrases("India's first general election was held in 1951-52.") == ["India"]
    assert entity_phrases("With PM Free Recharge Yojana, every Indian will get 3 months")[0] == "PM Free Recharge Yojana"
    assert entity_phrases("Reserve Bank of India ne naya rule diya") == ["Reserve Bank of India"]
    assert entity_phrases("the moon has gravity") == []
    assert entity_phrases("Chandrayaan-3 landed on the Moon on 23 August 2023") == ["Chandrayaan-3", "Moon"]   # a month is not an entity


def test_acronyms_are_all_capitals_of_three_to_six_letters_in_order_without_repeats():
    assert acronyms(["The UPI PIN is secret, the UPI app"]) == ["UPI", "PIN"]
    assert acronyms(["RBI says never share OTP, PIN or CVV"]) == ["RBI", "OTP", "PIN"]
    assert acronyms(["PM Modi is in OK shape"]) == []          # two letters, or too short
    assert acronyms(["upi pin"]) == []


def test_v2_keeps_the_v1_queries_and_adds_an_entity_query_and_acronym_searches():
    forms = ["UPI PIN kisi ko mat batao", "The UPI PIN of Unified Payments Interface should be kept secret"]
    v1 = build_queries(forms, "en")
    v2 = build_queries_v2(forms, "en")
    assert [(lang, q) for lang, q, _ in v2[:len(v1)]] == v1                       # nothing that worked is lost
    assert all(limit == DEEP_PER_SEARCH for _, _, limit in v2[:len(v1)])
    assert ("en", '"Unified Payments Interface"', DEEP_PER_SEARCH) in v2           # the entity query is quoted phrases
    assert ("en", "UPI", 2) in v2 and ("en", "PIN", 2) in v2                       # an acronym is searched alone
    assert len({(lang, q) for lang, q, _ in v2}) == len(v2)                        # no duplicates


def test_v2_queries_for_a_claim_without_entities_or_acronyms_are_just_the_deeper_v1():
    v2 = build_queries_v2(["the moon has gravity"], "en")
    assert len(v2) == 1 and v2[0][2] == DEEP_PER_SEARCH


def test_search_takes_the_per_query_limit_from_the_third_element(tmp_path):
    opener = Opener([])
    WikipediaLive(fetcher(tmp_path, opener)).search([("en", "a OR b", 8), ("en", "UPI", 2), ("en", "c OR d")])
    limits = [c.split("srlimit=")[1].split("&")[0] for c in opener.calls if "list=search" in c]
    assert limits == ["8", "2", "5"]                                               # a two-element query keeps the v1 default


def test_the_flag_is_off_by_default_and_absent_from_the_config_description_unless_on():
    cfg = PipelineConfig(name="x", split="dev", k=5)
    assert cfg.live_retrieval_v2 is False and "live_retrieval_v2" not in cfg.describe()
    cfg_on = PipelineConfig(name="x", split="dev", k=5, live_retrieval_v2=True)
    assert cfg_on.describe()["live_retrieval_v2"] is True


def test_live_evidence_uses_v2_queries_only_when_asked(tmp_path):
    for v2, expect_acronym_search in ((False, False), (True, True)):
        opener = Opener([])
        live = LiveEvidence(wikipedia=WikipediaLive(fetcher(tmp_path / str(v2), opener)), factcheck=NoFactCheck(), retrieval_v2=v2,
                            encode=lambda texts: [[1.0, 0.0] for _ in texts])
        live.gather(["The UPI PIN should be kept secret"], "en")
        searched_upi_alone = any("srsearch=UPI&" in c or c.endswith("srsearch=UPI") for c in opener.calls)
        assert searched_upi_alone is expect_acronym_search


def test_the_live_match_threshold_is_a_separate_key_served_at_0_70_and_absent_unless_set():
    assert PipelineConfig().tau_live_match is None and "tau_live_match" not in PipelineConfig().describe()
    served = PipelineConfig.load("configs/pipeline/dev.yaml")
    assert served.tau_live_match == 0.70
    assert served.describe()["tau_live_match"] == 0.70
    assert served.tau_match == 0.90                       # the OFFLINE fast path is untouched


def test_a_live_fact_check_hit_counts_as_this_claim_only_at_or_above_the_live_threshold(tmp_path):
    from retrieval.live.factcheck import FactCheckHit

    class OneHit:
        available = True

        def search(self, query):
            return [FactCheckHit(claim_text="Great Wall visible from space", publisher="Snopes", title="t", url="https://s/1",
                                 rating="False", lang="en")]

    def run(tau):
        live = LiveEvidence(wikipedia=WikipediaLive(fetcher(tmp_path / str(tau), Opener([]))), factcheck=OneHit(), tau_match=tau,
                            encode=lambda texts: [[0.8, 0.6] if i == 0 else [1.0, 0.0] for i, _ in enumerate(texts)])
        return live.gather(["the wall is visible"], "en").match

    assert run(0.90) is None and run(0.70) is not None and run(0.70).verdict == "Refuted"      # cosine 0.80 sits between
