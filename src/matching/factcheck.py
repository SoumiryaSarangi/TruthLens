"""Claim matching against the global fact-check index (FR-8).

The fast path: a forward that matches an already-published fact-check closely
enough skips evidence retrieval entirely and answers *"Already checked by X"*.
`build-plan.md` lists it under Never cut and `SYSTEM_DESIGN.md` §7 calls it the
thing that makes the demo work on genuinely new forwards.

## Retrieve, rerank, then gate -- and the gate alone is not enough

Measured on the Phase 2 predictions before any of this was built: a correct
top-1 scores 0.7239 on average and a wrong one 0.6500, heavily overlapping. At
τ=0.90 the fast path fires on 1.7% of posts and still cites the WRONG fact-check
18% of the time. A wrong citation here is the worst failure this system has,
because it is confident, sourced, and shown as settled.

So `rerank` is a stage of its own rather than a tuning knob, and the gate is
applied to the reranked score. `task: fast_path` measures exactly that decision.

## Three ways this declines, all of which fall through to the evidence path

    below tau            the match is not close enough
    no verdict           the publisher's rating is outside the mapping
                         (79.2% of the pool maps; see src/data/verdicts.py)
    no metadata          the id is not in the sidecar, which should not happen
                         and is a corrupted index if it does

Declining costs a retrieval pass, which is where the request was going anyway.
Answering wrongly costs a user's trust, so the asymmetry is deliberate.

Imports are lazy throughout; `tests/test_contracts.py` fails the build if any
module under `src/` imports torch or transformers at module scope.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pipeline.contracts import Claim, FactCheckMatch

INDEX_DIR = Path("data/interim/index")
META = "factcheck_meta.jsonl"
SUPPORTED_LANGS = ("en", "hi", "pa")


class IndexUnavailable(RuntimeError):
    """The fact-check index or its metadata sidecar has not been built."""


@dataclass(frozen=True)
class FactCheckMeta:
    title: str
    text: str            # what the index was built from; what a reranker reads
    url: str | None
    publisher: str | None
    verdict: str | None
    lang: str


class FactCheckMatcher:
    """Retrieve candidate fact-checks, optionally rerank, then gate on score.

    `top1` serves one request; `top1_batch` scores a whole split. They share one
    code path on purpose -- `pipeline/batch.py`'s docstring promises that what is
    scored is what the API runs, and until Phase 4 the match stage was scored
    through the retriever directly, which quietly broke that promise.
    """

    name = "matching"
    impl = "factcheck"

    def __init__(self, retriever: str = "dense", encoder: str = "bge_m3",
                 reranker: str = "none", k: int = 10,
                 index_dir: str | os.PathLike[str] | None = None,
                 adapter: str | os.PathLike[str] | None = None,
                 **kwargs: object) -> None:
        self.retriever_impl = retriever
        self.encoder = encoder
        self.reranker_impl = reranker
        self.k = k
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self.adapter = adapter
        self._kwargs = kwargs
        self._retriever = None
        self._reranker = None
        self._meta: dict[str, FactCheckMeta] | None = None
        # The trace says what actually ran, not just which registry name was
        # asked for: "factcheck" would read the same for a raw bi-encoder and a
        # reranked one, and those are the two arms of this phase's ablation.
        stack = encoder if retriever == "dense" else retriever
        self.impl = f"{stack}+{reranker}" if reranker != "none" else stack

    @property
    def note(self) -> str | None:
        if self.reranker_impl == "none":
            return ("no reranker: the gate is a raw retrieval score, which "
                    "separates a right match from a wrong one poorly")
        return None

    # -- lazily loaded pieces -------------------------------------------------
    def _load_meta(self) -> dict[str, FactCheckMeta]:
        if self._meta is None:
            from common.io_jsonl import load_jsonl

            path = self.index_dir / META
            if not path.is_file():
                raise IndexUnavailable(
                    f"no fact-check metadata at {path}. Run "
                    "`python scripts/build_factcheck_meta.py`."
                )
            self._meta = {
                row["id"]: FactCheckMeta(
                    title=row.get("title") or "",
                    text=row.get("text") or row.get("title") or "",
                    url=row.get("url"),
                    publisher=row.get("publisher"),
                    verdict=row.get("verdict"),
                    lang=row.get("lang") or "other",
                )
                for row in load_jsonl(path)
            }
        return self._meta

    def _load_retriever(self):
        if self._retriever is None:
            from pipeline import registry

            if self.retriever_impl == "dense":
                self._retriever = registry.build(
                    "retrieval", "dense", encoder=self.encoder, k=self.k,
                    index_dir=self.index_dir,
                )
            else:
                self._retriever = registry.build(
                    "retrieval", self.retriever_impl, k=self.k,
                    index_dir=self.index_dir,
                )
        return self._retriever

    def _load_reranker(self):
        if self._reranker is None and self.reranker_impl != "none":
            from matching import rerankers

            self._reranker = rerankers.build(self.reranker_impl,
                                             adapter=self.adapter, **self._kwargs)
        return self._reranker

    # -- the stage ------------------------------------------------------------
    def top1(self, claim: Claim) -> FactCheckMatch | None:
        return self.top1_batch([claim.text])[0]

    def top1_batch(self, texts: list[str]) -> list[FactCheckMatch | None]:
        """One best match per query, or None where the fast path declines.

        The threshold is NOT applied here. `PipelineConfig.tau_match` is the
        orchestrator's to enforce (`SYSTEM_DESIGN.md` §6), and the harness needs
        the score of the best candidate whether or not it clears the bar --
        gating here would make every fast-path eval measure one operating point
        and nothing else.
        """
        meta = self._load_meta()
        ranked = self.rank_batch(texts)
        out: list[FactCheckMatch | None] = []
        for candidates in ranked:
            out.append(self._to_match(candidates, meta))
        return out

    def rank_batch(self, texts: list[str]) -> list[list[tuple[str, float]]]:
        """(doc_id, score) per query, best first, after any reranking."""
        retriever = self._load_retriever()
        ranked = [[(d.doc_id, float(d.score)) for d in docs]
                  for docs in retriever.rank_batch(texts, k=self.k)]
        reranker = self._load_reranker()
        if reranker is None:
            return ranked
        meta = self._load_meta()
        # The reranker reads the INDEXED text, not the display title: a
        # reranker judging a different string from the one the retriever matched
        # on would be answering a different question than the one being scored.
        return reranker.rerank(
            texts,
            [[(doc_id, meta[doc_id].text if doc_id in meta else "")
              for doc_id, _ in docs] for docs in ranked],
        )

    def _to_match(self, candidates: list[tuple[str, float]],
                  meta: dict[str, FactCheckMeta]) -> FactCheckMatch | None:
        """The TOP candidate, or None. It does not walk down the ranking.

        Walking past a top-1 whose rating will not map, to take rank 2 instead,
        was the other option and is worse for two reasons. It would answer with a
        match the model judged INFERIOR, on a lower score that is correspondingly
        more likely to be wrong -- in a phase whose whole finding is that this
        gate is already too permissive. And it would break the promise that what
        the harness scores is what the API serves: the predictions file carries
        the retriever's ranking, so a served answer taken from rank 2 would be a
        decision no eval ever measured.
        """
        if not candidates:
            return None
        doc_id, score = candidates[0]
        info = meta.get(doc_id)
        if info is None or info.verdict is None:
            return None
        return FactCheckMatch(
            factcheck_id=doc_id,
            score=score,
            verdict=info.verdict,
            title=info.title,
            url=info.url or "",
            publisher=info.publisher or "unknown",
            lang=info.lang if info.lang in SUPPORTED_LANGS else "other",
        )
