"""Which words of a claim, and which source sentence, the two NLI models leaned on for a verdict.

Occlusion with the same two models and the same premise as the live verdict (docs/word-highlight-protocol.md).
It explains the models' reading of the sources; it never changes a verdict and is computed only when asked.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from explain.occlusion import influences, source_sentences, split_words, top_indices, without

STANCE_OF = {"Supported": "Supports", "Refuted": "Refutes"}


def class_probs(models: Sequence[Any], pairs: list[tuple[str, str]], verdict: str) -> list[float]:
    """Mean over the models of P(the shown verdict's class) for each (premise, hypothesis) pair."""
    stance = STANCE_OF[verdict]
    per_model = [[r.probs.get(stance, 0.0) for r in m.score_pairs(pairs)] for m in models]
    return [sum(col) / len(per_model) for col in zip(*per_model, strict=True)]


def explain_words(models: Sequence[Any], hypothesis: str, premise: str, verdict: str) -> dict[str, Any]:
    """Word and source-sentence influence for one live verdict (Supported or Refuted)."""
    if verdict not in STANCE_OF:
        raise ValueError("a word view exists only for a Supported or Refuted verdict")
    words = split_words(hypothesis)
    sentences = source_sentences(premise)
    # one batch per model: the full pair, each claim word removed, each source sentence removed
    pairs = [(premise, hypothesis)]
    pairs += [(premise, without(words, [i])) for i in range(len(words))]
    pairs += [(" ".join(s for j, s in enumerate(sentences) if j != i), hypothesis) for i in range(len(sentences))]
    probs = class_probs(models, pairs, verdict)
    full, by_word, by_sentence = probs[0], probs[1:1 + len(words)], probs[1 + len(words):]
    word_inf = influences(full, by_word)
    sent_inf = influences(full, by_sentence) if len(sentences) > 1 else [0.0] * len(sentences)
    best = max(range(len(sent_inf)), key=lambda i: (sent_inf[i], -i)) if len(sentences) > 1 else None
    return {
        "verdict": verdict, "p_verdict": full, "claim": hypothesis,
        "words": [{"word": w, "influence": v} for w, v in zip(words, word_inf, strict=True)],
        "top": top_indices(word_inf),
        "sentences": [{"text": s, "influence": v, "marked": i == best}
                      for i, (s, v) in enumerate(zip(sentences, sent_inf, strict=True))],
    }
