"""Template explanations. Always available, never generated prose.

FR-18: a template explanation must always exist, and is used whenever
generation is unavailable, times out, or fails the faithfulness check. In
Phase 1 it is the only explainer -- IndicBART arrives in Phase 6 and registers
alongside this one.

The wording follows `UI_UX.md` §8: plain words, no "true" or "false" (the
system judges evidence, not truth), no alarm language even for Refuted.
Citation markers are `[n]`, matching the evidence trail's numbering.
"""

from __future__ import annotations

VERDICT_PHRASE = {
    "Supported": "The evidence found supports this claim",
    "Refuted": "The evidence found contradicts this claim",
    "Conflicting": "The evidence found disagrees with itself about this claim",
    "NEI": "There is not enough evidence to judge this claim",
    "NotAClaim": "There is no checkable factual claim here",
}

STANCE_PHRASE = {
    "Supports": "supports it",
    "Refutes": "contradicts it",
    "Neutral": "is related but does not settle it",
}


class TemplateExplainer:
    name = "generation"
    impl = "template"

    def __init__(self, max_cited: int = 3, **_: object):
        self.max_cited = max_cited

    def explain(self, verdict: str, passages: list, *, abstained: bool = False) -> tuple[str, list[str]]:
        """Returns (explanation, cited passage ids)."""
        head = VERDICT_PHRASE.get(verdict, VERDICT_PHRASE["NEI"])

        if abstained:
            # UI_UX.md §6: an abstained card shows the leaning, greyed. The text
            # has to say the system declined, not hedge about the evidence.
            head = ("Not confident enough to judge this claim. "
                    f"Leaning: {verdict.lower()}")

        if not passages:
            return head + ". No sources were retrieved.", []

        cited: list[str] = []
        parts: list[str] = []
        for i, p in enumerate(passages[: self.max_cited], start=1):
            stance = getattr(p, "stance", None) or "Neutral"
            title = getattr(p, "title", None) or getattr(p, "doc_id", "source")
            parts.append(f"[{i}] {title} {STANCE_PHRASE.get(stance, STANCE_PHRASE['Neutral'])}")
            cited.append(getattr(p, "passage_id", f"e{i}"))

        return f"{head}. " + "; ".join(parts) + ".", cited
