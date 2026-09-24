"""Render results/*.json into the markdown tables the report is built from.

    make table

Two tables, because docs/build-plan.md asks for two different things:

  1. The results log: one row per run, always beside its baseline. A row
     without a baseline is not a result, so the baseline column is never
     optional here.
  2. The native-vs-romanized table: the same metric on native script and on
     romanized, and the gap between them. "The gap between the two columns is
     the finding."
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common.io_jsonl import load_json

RESULTS_DIR = Path("results")


def load_results(results_dir: str | Path = RESULTS_DIR) -> list[dict[str, Any]]:
    """Newest run first."""
    docs = []
    for path in sorted(Path(results_dir).glob("*.json")):
        try:
            docs.append(load_json(path))
        except (OSError, ValueError):
            continue
    docs.sort(key=lambda d: d.get("created_utc", ""), reverse=True)
    return docs


def _fmt(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


# The metric each task leads with. **The single definition** -- `evaluate.py`
# imports this one rather than keeping its own, because for three phases there
# were two copies and nothing compared them: a task added to the scorer's map and
# missed here rendered every row of its table against `mrr`, with a wrong label
# and a blank score.
HEADLINE = {
    "classification": "macro_f1",
    "retrieval": "mrr",
    # The fast path's headline is a summary of a curve, not the result. The
    # result is the tau table in `curve`; this exists because a table needs one
    # column and because AUCC is the only candidate a threshold cannot move.
    "fast_path": "fastpath_aucc",
    "transliteration": "cer",
    "span": "token_f1",
    "normalization": "chrf",
}
LOWER_IS_BETTER = {"cer", "wer"}


def results_table(docs: list[dict[str, Any]]) -> str:
    lines = [
        "| Experiment | Task | Headline | Score | Baseline | Base score | Delta | n | Flags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for doc in docs:
        overall = doc.get("metrics", {}).get("overall", {})
        # An unregistered task renders as a blank rather than borrowing `mrr`.
        # Falling back to another task's metric produces a row that looks
        # populated and is measuring something else.
        headline = HEADLINE.get(doc.get("task"))
        if headline is None:
            lines.append(f"| {doc.get('experiment', '?')} | {doc.get('task')} | "
                         "— | — | — | — | — | — | task not in HEADLINE |")
            continue
        score = overall.get(headline)
        delta = doc.get("delta_vs_baseline", {}).get(headline)
        base_score = score - delta if (score is not None and delta is not None) else None

        flags = []
        if headline in LOWER_IS_BETTER:
            # CER and WER are error rates, so a NEGATIVE delta is the model
            # winning. Without this the ladder reads upside down.
            flags.append("lower is better")
        if doc.get("warnings"):
            flags.append(f"{len(doc['warnings'])} warning(s)")
        if doc.get("git", {}).get("dirty"):
            flags.append("dirty tree")
        if doc.get("coverage", {}).get("n_missing"):
            flags.append(f"{doc['coverage']['n_missing']} uncovered")

        lines.append(
            f"| {doc.get('experiment', '?')} "
            f"| {doc.get('task', '?')} "
            f"| {headline} "
            f"| {_fmt(score)} "
            f"| {doc.get('baseline', {}).get('name', '—')} "
            f"| {_fmt(base_score)} "
            f"| {_fmt(delta)} "
            f"| {int(overall.get('n', 0))} "
            f"| {', '.join(flags) or '—'} |"
        )
    return "\n".join(lines)


def romanization_table(docs: list[dict[str, Any]]) -> str:
    """The comparison the project exists to make."""
    lines = [
        "| Experiment | Lang | Metric | Native | Romanized | Gap | n native | n roman |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    any_row = False
    for doc in docs:
        block = doc.get("native_vs_romanized", {})
        metric = block.get("metric", "?")
        for lang, entry in (block.get("by_lang") or {}).items():
            if "gap" not in entry:
                continue  # English has no native/romanized split
            any_row = True
            lines.append(
                f"| {doc.get('experiment', '?')} | {lang} | {metric} "
                f"| {_fmt(entry.get('native'))} | {_fmt(entry.get('romanized'))} "
                f"| {_fmt(entry.get('gap'))} "
                f"| {int(entry.get('n_native') or 0)} | {int(entry.get('n_romanized') or 0)} |"
            )
    if not any_row:
        return ("_No run yet reports both a native and a romanized cell for the same "
                "language. The romanized eval sets are built in Phase 2._")
    return "\n".join(lines)


def render(results_dir: str | Path = RESULTS_DIR) -> str:
    docs = load_results(results_dir)
    if not docs:
        return f"# Results\n\n_No runs in {results_dir}/ yet._\n"
    return (
        "# Results\n\n"
        f"_{len(docs)} run(s). Generated by `make table`; do not edit by hand._\n\n"
        "## Results log\n\n"
        "A row without a baseline is not a result, it is a number.\n\n"
        + results_table(docs)
        + "\n\n## Native vs romanized\n\n"
        "The gap column is the finding. Where it is largest is where the pipeline "
        "is most fragile.\n\n"
        + romanization_table(docs)
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.report")
    parser.add_argument("--results", default=str(RESULTS_DIR))
    parser.add_argument("--out", default=None,
                        help="write to this file instead of stdout")
    args = parser.parse_args(argv)

    text = render(args.results)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
