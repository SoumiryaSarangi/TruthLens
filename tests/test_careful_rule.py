"""The "Be careful" cues and their gates (docs/careful-rule-protocol.md)."""
from __future__ import annotations

import pytest

from eval.metrics import careful_rule_metrics
from manipulation.hoax_cues import caution_cues, hoax_cues


def test_the_shapes_of_a_typical_hoax_are_named():
    assert "miracle_cure" in hoax_cues("Drinking lemon juice can cure cancer")
    assert "concealment" in hoax_cues("Drinking lemon juice can cure cancer but hospitals don't reveal this")
    assert "miracle_cure" in hoax_cues("Nimbu paani peene se cancer theek ho jata hai")
    assert "concealment" in hoax_cues("hospital wale ye baat chhupate hain")
    assert "threat_or_charge" in hoax_cues("WhatsApp will start charging users from next month")
    assert "giveaway" in hoax_cues("Government is giving a free laptop to every student")
    # Pinned as measured (protocol run e165f84eb4a9): the frozen rule matches whole words, so a plural giveaway noun is missed.
    assert "giveaway" not in hoax_cues("Government is giving free laptops to all students")


def test_ordinary_true_statements_carry_no_cue():
    for text in ("Methyl Phenidate is good medicine for ADHD.", "Lahore is the capital of Punjab, Pakistan",
                 "Hyderabad is the capital of Telangana", "Paris is the capital of France", "Good morning, stay blessed"):
        assert caution_cues(text) == [], text


def test_pressure_techniques_count_too():
    assert any(c.startswith("technique:") for c in caution_cues("Forward this URGENT!! Aage bhejo jaldi!!"))


def test_the_gates_pass_and_fail_as_fixed():
    ok = careful_rule_metrics([False] * 95 + [True] * 5, [True] * 20 + [False] * 80, [True] * 40 + [False] * 60, [True] * 25 + [False] * 5)
    assert ok["passes"] and ok["true_rate"] == pytest.approx(0.05)
    too_many = careful_rule_metrics([True] * 20 + [False] * 80, [True] * 50 + [False] * 50, [True] * 90 + [False] * 10, [True] * 30)
    assert not too_many["gates"]["false_warning_rate"] and not too_many["passes"]
    no_better = careful_rule_metrics([True] * 10 + [False] * 90, [True] * 50 + [False] * 50, [True] * 12 + [False] * 88, [True] * 30)
    assert not no_better["gates"]["at_most_half_of_baseline"]
    silent = careful_rule_metrics([False] * 100, [False] * 100, [True] * 50 + [False] * 50, [False] * 30)
    assert not silent["gates"]["false_claim_recall"] and not silent["gates"]["typical_hoaxes"]


def test_the_gates_refuse_empty_or_mismatched_sets():
    with pytest.raises(ValueError):
        careful_rule_metrics([], [True], [], [True])
    with pytest.raises(ValueError):
        careful_rule_metrics([True], [True], [True, False], [True])
