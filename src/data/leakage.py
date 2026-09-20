"""Cross-split leakage detection.

The motivating fact, from docs/build-plan.md: the DS@GT team working on
CheckThat! 2025 found substantial claim overlap, to the point of duplication,
across train, dev and test. Leakage is not hypothetical in this data.

Four checks, cheapest first, all runnable from the committed ID manifests
alone -- no source text required, so this works in CI:

  1. uid overlap        -- the same row id in two splits
  2. source_id overlap  -- the same upstream record re-keyed under a new uid
  3. text_sha1 overlap  -- identical normalised text under different ids
  4. simhash proximity  -- near-duplicate text (paraphrase, added emoji,
                           an extra "Forwarded many times" line)

Check 4 over-reports slightly by design. When materialised text is available in
data/interim/ the caller can pass `texts=` and flagged pairs are confirmed with
an exact Jaccard, which clears the false positives.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any

from data.normalize import char_shingles
from data.simhash import candidate_pairs, hamming, jaccard

# Hamming distance over 64-bit SimHash. Calibrated on this project's own text
# rather than taken from convention -- see scripts/calibrate_simhash.py:
#
#   emoji / forward header / casing / URL / whitespace ....  0  (the normaliser
#                                       already collapses these to exact dupes)
#   punctuation variants .................................  ~4
#   single word substitution .............................  ~10
#   unrelated claims ..................... min 22, mean 32  (random is ~32)
#
# So there is real separation up to about 14, and 8 is comfortably inside the
# "same claim, retyped" region.
#
# LIMITATION, stated plainly: this catches duplicates and trivial variants, NOT
# semantic paraphrase. Two sentences that mean the same thing in different
# words score ~9-11 here, overlapping the warn band, and a genuine reworded
# claim can score above 22 and be missed entirely. Embedding-based duplicate
# detection belongs in Phase 4 alongside the claim-matching retriever; until
# then, `make leakage` passing means "no duplicates", not "no overlap".
FAIL_HAMMING = 8
WARN_HAMMING = 14

# Used only when texts are supplied to confirm a simhash hit.
FAIL_JACCARD = 0.90
WARN_JACCARD = 0.80


@dataclass(frozen=True)
class Finding:
    kind: str          # uid_overlap | source_id_overlap | exact_text | near_duplicate
    severity: str      # fail | warn
    dataset: str
    split_a: str
    split_b: str
    uid_a: str
    uid_b: str
    detail: str
    distance: int | None = None
    jaccard: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _overlap_findings(
    dataset: str, splits: dict[str, list[dict[str, Any]]], field: str, kind: str,
) -> list[Finding]:
    """Rows in two different splits sharing the same value of `field`."""
    findings: list[Finding] = []
    for a, b in combinations(sorted(splits), 2):
        by_value: dict[Any, str] = {}
        for rec in splits[a]:
            if rec.get(field) is not None:
                by_value[rec[field]] = rec["uid"]
        for rec in splits[b]:
            value = rec.get(field)
            if value is None or value not in by_value:
                continue
            findings.append(Finding(
                kind=kind, severity="fail", dataset=dataset, split_a=a, split_b=b,
                uid_a=by_value[value], uid_b=rec["uid"],
                detail=f"shared {field}={value!r} across {a} and {b}",
            ))
    return findings


def _near_duplicate_findings(
    dataset: str,
    splits: dict[str, list[dict[str, Any]]],
    texts: dict[str, str] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    zero = "0" * 16  # text too short to shingle; nothing to compare
    sha_by_uid = {r["uid"]: r["text_sha1"] for rows in splits.values() for r in rows}

    for a, b in combinations(sorted(splits), 2):
        items_a = [(r["uid"], int(r["simhash64"], 16)) for r in splits[a] if r["simhash64"] != zero]
        items_b = [(r["uid"], int(r["simhash64"], 16)) for r in splits[b] if r["simhash64"] != zero]
        hashes = dict(items_a) | dict(items_b)

        for uid_a, uid_b in candidate_pairs(items_a, items_b):
            dist = hamming(hashes[uid_a], hashes[uid_b])
            if dist > WARN_HAMMING:
                continue
            # An identical text_sha1 is already reported as exact_text; don't
            # report the same pair twice under a weaker heading.
            if sha_by_uid[uid_a] == sha_by_uid[uid_b]:
                continue

            jac: float | None = None
            if texts is not None and uid_a in texts and uid_b in texts:
                jac = jaccard(char_shingles(texts[uid_a]), char_shingles(texts[uid_b]))
                if jac < WARN_JACCARD:
                    continue  # simhash false positive, cleared by exact Jaccard
                severity = "fail" if jac >= FAIL_JACCARD else "warn"
            else:
                # No text, so the SimHash hit cannot be confirmed. On real data
                # a meaningful share of hits at this distance turn out to have
                # Jaccard below 0.8 -- close sketches, different claims. Failing
                # a build on an unconfirmable signal would contradict the
                # deduplication pass in scripts/build_splits.py, which drops a
                # row only when SimHash AND Jaccard agree. So this warns, and
                # says how to promote it to a real answer.
                severity = "warn"

            findings.append(Finding(
                kind="near_duplicate", severity=severity, dataset=dataset,
                split_a=a, split_b=b, uid_a=uid_a, uid_b=uid_b,
                detail=(f"near-duplicate text across {a} and {b} "
                        f"(simhash hamming={dist}"
                        + (f", jaccard={jac:.3f}" if jac is not None
                           else ", UNCONFIRMED: no text available, run `make data` "
                                "to materialise it and get a verdict")
                        + ")"),
                distance=dist, jaccard=jac,
            ))

    return findings


def find_leakage(
    dataset: str,
    splits: dict[str, list[dict[str, Any]]],
    *,
    texts: dict[str, str] | None = None,
) -> list[Finding]:
    """Run every check over one dataset's splits. Empty list means clean.

    `splits` maps split name -> the loaded rows. `texts` optionally maps uid ->
    source text, available only after `make data` has materialised it locally.
    """
    findings: list[Finding] = []
    findings += _overlap_findings(dataset, splits, "uid", "uid_overlap")
    findings += _overlap_findings(dataset, splits, "source_id", "source_id_overlap")
    findings += _overlap_findings(dataset, splits, "text_sha1", "exact_text")
    findings += _near_duplicate_findings(dataset, splits, texts)
    findings.sort(key=lambda f: (f.severity != "fail", f.kind, f.uid_a, f.uid_b))
    return findings


def failures(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "fail"]


ACCEPTED_PATH = "data/splits/KNOWN_LEAKAGE.json"


def load_accepted(path: str = ACCEPTED_PATH) -> set[tuple[str, str, str]]:
    """Load the allowlist of leaks that exist upstream and cannot be fixed here.

    Some overlap is irreducible. When the same post appears in a dataset's own
    official dev AND test splits, both sides are part of a published
    benchmark: dropping either changes the benchmark and makes our numbers
    incomparable with everyone else's. The honest move is to accept it, name
    it, quantify it in docs/data-profile.md, and make sure a NEW leak still
    fails loudly.

    So this is an allowlist, not a threshold change. Anything not listed here
    by exact uid pair still fails.
    """
    from pathlib import Path  # local: keeps this module import-light

    p = Path(path)
    if not p.is_file():
        return set()
    import json

    doc = json.loads(p.read_text(encoding="utf-8"))
    return {
        (entry["dataset"], entry["uid_a"], entry["uid_b"])
        for entry in doc.get("accepted", [])
    }


def filter_accepted(
    findings: list[Finding], accepted: set[tuple[str, str, str]],
) -> tuple[list[Finding], list[Finding]]:
    """Split findings into (unaccepted, accepted). Order-insensitive on the pair."""
    new: list[Finding] = []
    known: list[Finding] = []
    for f in findings:
        key_fwd = (f.dataset, f.uid_a, f.uid_b)
        key_rev = (f.dataset, f.uid_b, f.uid_a)
        (known if (key_fwd in accepted or key_rev in accepted) else new).append(f)
    return new, known


def per_split_counts(splits: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    """Counts by split x lang x script, for docs/data-profile.md."""
    out: dict[str, dict[str, int]] = {}
    for name, rows in splits.items():
        counts: dict[str, int] = defaultdict(int)
        counts["total"] = len(rows)
        for rec in rows:
            counts[f"lang={rec['lang']}"] += 1
            counts[f"script={rec['script']}"] += 1
            counts[f"{rec['lang']}/{rec['script']}"] += 1
        out[name] = dict(sorted(counts.items()))
    return out


def format_report(dataset: str, findings: list[Finding], *, limit: int = 20) -> str:
    """Markdown for reports/leakage-<dataset>.md. Actionable, not just red."""
    fails = failures(findings)
    warns = [f for f in findings if f.severity == "warn"]
    lines = [
        f"# Leakage report — {dataset}",
        "",
        f"- **{len(fails)} failing**, {len(warns)} warning",
        "",
    ]
    for title, group in (("Failures", fails), ("Warnings", warns)):
        if not group:
            continue
        lines += [f"## {title}", "",
                  "| kind | split A | uid A | split B | uid B | detail |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for f in group[:limit]:
            lines.append(
                f"| {f.kind} | {f.split_a} | `{f.uid_a}` | {f.split_b} | `{f.uid_b}` | {f.detail} |"
            )
        if len(group) > limit:
            lines.append(f"| … | | | | | {len(group) - limit} more |")
        lines.append("")
    return "\n".join(lines)
