"""Dataset loaders. Every source becomes the same record shape.

Each loader yields the split-manifest record defined in src/data/splits.py:
identifiers, language, detected script, hashes. Source TEXT is returned
separately, by `materialize`, and written to the gitignored data/interim/ --
never into a committed split file. See data/CLAUDE.md for why.

Adding a dataset means adding a loader here and a registry entry. Nothing
else in the pipeline should know which dataset a row came from.
"""

from __future__ import annotations

import ast
import csv
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

from common.hashing import sha1_text
from common.io_jsonl import load_json, load_jsonl
from common.seeds import SEED
from data.labels import map_averitec_label, map_averitec_stance
from data.normalize import char_shingles, normalize_for_hashing
from data.script_id import detect_script, script_purity
from data.simhash import simhash_hex

RAW = Path("data/raw")

# X-CLAIM's own splits, which we keep as-is.
XCLAIM_LANGS = ("en", "hi", "pa")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


class Row(NamedTuple):
    """A loaded example: the manifest record, plus the text that stays local.

    `extra` carries fields beyond the single `text` into the gitignored interim
    file -- a pair task's two halves, for instance. It never reaches the split
    record, which `validate_split_record` keeps to a fixed schema.
    """

    record: dict[str, Any]
    text: str
    extra: dict[str, str] | None = None


def _make_record(
    *,
    dataset: str,
    split: str,
    index: int,
    lang: str,
    text: str,
    source_id: str,
    label: str | None,
    label_set: str | None,
) -> dict[str, Any]:
    script = detect_script(text)
    normalised = normalize_for_hashing(text)
    record: dict[str, Any] = {
        "uid": f"{dataset}:{lang}:{split}:{index:05d}",
        "dataset": dataset,
        "split": split,
        "lang": lang,
        "script": script,
        "source_id": source_id,
        "text_sha1": sha1_text(normalised),
        "simhash64": simhash_hex(text),
        "n_chars": len(text),
    }
    if label is not None:
        record["label"] = label
        record["label_set"] = label_set
    return record


# -----------------------------------------------------------------------------
# AVeriTeC
# -----------------------------------------------------------------------------


def load_averitec(split_file: str, split_name: str) -> Iterator[Row]:
    """Load AVeriTeC train.json or dev.json.

    AVeriTeC ships no per-claim identifier, so the record's position in the
    file IS its identity. That is only safe because the file's sha256 is
    recorded in data/raw/DOWNLOADS.json and in the split MANIFEST: if upstream
    re-releases with a different ordering, the hash changes and the mismatch
    is visible rather than silent.
    """
    path = RAW / "averitec" / split_file
    records = load_json(path)
    for i, item in enumerate(records):
        claim = (item.get("claim") or "").strip()
        if not claim:
            continue
        yield Row(
            record=_make_record(
                dataset="averitec",
                split=split_name,
                index=i,
                lang="en",
                text=claim,
                source_id=f"averitec:{split_file}:{i}",
                label=map_averitec_label(item["label"]),
                label_set="verdict_5class",
            ),
            text=claim,
        )


# -----------------------------------------------------------------------------
# X-CLAIM
# -----------------------------------------------------------------------------


def _join_tokens(raw: str) -> str:
    """X-CLAIM stores a Python list literal in the `tokens` column."""
    try:
        tokens = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw.strip()
    if isinstance(tokens, list):
        return " ".join(str(t) for t in tokens).strip()
    return str(tokens).strip()


def _parse_span_row(item: dict[str, str]) -> tuple[list[str], int, int] | None:
    """(tokens, start, end_INCLUSIVE) for one raw X-CLAIM row, or None.

    The end index being inclusive is measured, not assumed: across all of
    X-CLAIM, `span_end_index == len(tokens)` occurs 0 times while
    `== len(tokens) - 1` occurs 2,897 times. `scripts/build_span_gold.py`
    re-checks it on every build and refuses if it ever flips.
    """
    try:
        tokens = ast.literal_eval(item["tokens"])
        starts = ast.literal_eval(item["span_start_index"])
        ends = ast.literal_eval(item["span_end_index"])
    except (ValueError, SyntaxError, KeyError):
        return None
    if not isinstance(tokens, list) or not tokens:
        return None
    if len(starts) != 1 or len(ends) != 1:
        return None
    start, end = int(starts[0]), int(ends[0])
    if not (0 <= start <= end < len(tokens)):
        return None
    return [str(t) for t in tokens], start, end


def load_xclaim(lang: str, split_name: str) -> Iterator[Row]:
    """Load one X-CLAIM language/split CSV.

    This is a span-identification dataset: the columns are the post's tokens
    and the start/end indices of the claim span. There is no verdict label, so
    the manifest record carries none -- `label` is optional by design.
    """
    path = RAW / "x_claim" / f"{split_name}-{lang}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        for i, item in enumerate(csv.DictReader(fh)):
            text = _join_tokens(item.get("tokens", ""))
            if not text:
                continue
            yield Row(
                record=_make_record(
                    dataset="x_claim",
                    split=split_name,
                    index=i,
                    lang=lang,
                    text=text,
                    source_id=f"x_claim:{split_name}-{lang}:{i}",
                    label=None,
                    label_set=None,
                ),
                text=text,
            )


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# MultiClaim / SemEval-2025 Task 7
# -----------------------------------------------------------------------------


MULTICLAIM_SPLIT_FRACTIONS = {"train": 0.8, "dev": 0.1, "test": 0.1}


def load_multiclaim(langs: tuple[str, ...] = ("en", "hi", "pa")) -> dict[str, list[Row]]:
    """Posts as retrieval queries, split 80/10/10 stratified by language.

    MultiClaim ships no official split, so one is made here and frozen like any
    other. Stratifying by language matters more than usual: Punjabi has only 91
    posts in the entire corpus, and an unstratified random split could leave a
    test set with almost none.

    Only posts that have at least one annotated fact-check are kept. A post with
    no pair has no gold, cannot be scored, and would silently vanish from the
    denominator.
    """
    import random

    from data.multiclaim import load_pairs, load_posts

    posts = load_posts(langs=set(langs))
    paired: dict[str, list[str]] = {}
    for post_id, fc_id, _rel in load_pairs():
        if post_id in posts:
            paired.setdefault(post_id, []).append(fc_id)

    # Deduplicate BEFORE splitting, not after.
    #
    # MultiClaim ships no official splits, so these are ours -- which means a
    # duplicated post appearing in both dev and test is a bug in this function,
    # not upstream leakage to be allowlisted. The allowlist in
    # data/splits/KNOWN_LEAKAGE.json exists for overlap we cannot fix without
    # altering a published benchmark; this we can fix, so we do.
    #
    # Measured before this: 13 posts appeared in both dev and test. Keeping the
    # lowest post_id makes the choice deterministic rather than dependent on
    # CSV order.
    # Exact duplicates first, then NEAR duplicates. Exact alone is not enough:
    # the same viral post gets reposted with an emoji changed or a URL dropped,
    # which normalises to different text but is plainly the same item. Measured
    # after exact-only dedup: 30 near-duplicate pairs still straddled splits,
    # at Jaccard 0.92-0.97.
    seen: dict[str, str] = {}
    for post_id in sorted(paired, key=lambda x: (len(x), x)):
        key = normalize_for_hashing(posts[post_id].text)
        seen.setdefault(key, post_id)
    unique_ids = _drop_near_duplicates(
        {pid: posts[pid].text for pid in seen.values()}
    )

    by_lang: dict[str, list[str]] = {}
    for post_id in sorted(paired):
        if post_id not in unique_ids:
            continue
        by_lang.setdefault(posts[post_id].lang or "en", []).append(post_id)

    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    rng = random.Random(SEED)
    for lang in sorted(by_lang):
        ids = sorted(by_lang[lang])
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(n * MULTICLAIM_SPLIT_FRACTIONS["train"])
        n_dev = int(n * MULTICLAIM_SPLIT_FRACTIONS["dev"])
        chunks = {"train": ids[:n_train],
                  "dev": ids[n_train:n_train + n_dev],
                  "test": ids[n_train + n_dev:]}
        for split, chunk in chunks.items():
            for i, post_id in enumerate(chunk):
                text = posts[post_id].text
                out[split].append(Row(
                    record=_make_record(
                        dataset="multiclaim", split=split, index=i, lang=lang,
                        text=text, source_id=f"multiclaim:post:{post_id}",
                        label=None, label_set=None,
                    ),
                    text=text,
                ))
    return out


def _drop_near_duplicates(texts: dict[str, str]) -> set[str]:
    """Keep one representative per near-duplicate cluster.

    Reuses the same signals and thresholds as the split-building dedup pass in
    scripts/build_splits.py -- SimHash proximity confirmed by exact Jaccard --
    so "near duplicate" means one thing across the project.

    Union-find over candidate pairs rather than an all-pairs comparison: 32k
    posts would be half a billion comparisons, while the banded SimHash index
    only proposes plausible ones.
    """
    from data.leakage import FAIL_JACCARD, WARN_HAMMING
    from data.simhash import candidate_pairs, hamming, jaccard, simhash64

    # Thresholds are IMPORTED from the detector, never redeclared. They drifted
    # once already: this clustered at Hamming <= 8 while tests/test_no_leakage
    # failed anything with Jaccard >= 0.90 out to Hamming 14, leaving a band the
    # clusterer never considered and the detector rejected. Cluster exactly what
    # the detector would fail on, and it cannot fail by construction.
    HAMMING, JACCARD = WARN_HAMMING, FAIL_JACCARD

    items = [(pid, simhash64(text)) for pid, text in sorted(texts.items())]
    parent: dict[str, str] = {pid: pid for pid, _ in items}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    shingles: dict[str, set[str]] = {}
    hashes = dict(items)
    for a, b in candidate_pairs(items, items):
        if a == b or find(a) == find(b):
            continue
        if hamming(hashes[a], hashes[b]) > HAMMING:
            continue
        for pid in (a, b):
            if pid not in shingles:
                shingles[pid] = char_shingles(texts[pid])
        if jaccard(shingles[a], shingles[b]) >= JACCARD:
            parent[find(a)] = find(b)

    # Lowest id per cluster, so the choice is deterministic.
    keep: dict[str, str] = {}
    for pid in sorted(parent, key=lambda x: (len(x), x)):
        root = find(pid)
        keep.setdefault(root, pid)
    return set(keep.values())


def multiclaim_rows() -> dict[str, list[Row]]:
    return load_multiclaim()


# The seven rows their collector labelled `lang=mixed`. The split schema has no
# such value, and SYSTEM_DESIGN 4 refuses to add one for the same reason it
# refuses a `mixed` SCRIPT value: code-mixing is a continuous property that
# `script_purity` already reports, and a fourth category would add a cell to
# every per-language breakdown the research contribution rests on.
#
# So each is assigned its DOMINANT language here, by grammatical markers rather
# than vocabulary -- English and Hindi/Punjabi nouns are shared, but case
# markers and verb endings are not. The declaration is kept in `notes` so the
# row can still be found later. Assigned by hand, deliberately: deriving these
# from fastText would make them useless as gold for scoring fastText (FR-3).
MIXED_LANG: dict[str, tuple[str, str]] = {
    # id:      (lang, the marker that decided it)
    "hw012": ("hi", "Hindi throughout ('roz 3 bar'); one Punjabi postposition, 'ghante ch'"),
    "hw035": ("hi", "Hindi case and verb: 'ko ... se ... karte hi ... milta hai'"),
    "hw060": ("hi", "Hindi ergative and past: 'ne ... likh diya tha'"),
    "hw069": ("hi", "Hindi frame ('hote hain', 'nahi hota') around one Punjabi clause"),
    "hw073": ("pa", "Punjabi verbs: 'rehnde', 'milde ne', 'sakdi'; conjunction 'te'"),
    "hw088": ("pa", "Punjabi copula 'aa', 'jinna marzi', dative 'sab nu'"),
    "hw094": ("hi", "Hindi adjective and copula: 'pehla chhota sa ... hai'"),
}

# hw012 is the one genuinely close call: its only grammatical marker is Punjabi
# ('ch'), while everything else about it reads Hindi. It is one row in 100 and
# it is recorded here rather than smoothed over.
MIXED_UNCERTAIN = ("hw012",)


def load_handtyped() -> Iterator[Row]:
    """The ~100 hand-typed romanized forwards collected for FR-26.

    The only dataset here that was not published by someone else: real people
    typing Hindi and Punjabi in Latin script, with their own spelling. That is
    the point -- MultiClaim's naturally romanized posts are public posts, and a
    transliterator's output is consistent by construction. Neither is a
    substitute for messy personal typing, which is what the system actually
    receives and what this project's contribution is about.

    `label` is CHECK-WORTHINESS, not a verdict: these forwards have no verified
    answer, and inventing one would be worse than having none. The 15 rows whose
    claim summary is "no claim" are the negatives, and they are the reason the
    set exists in this shape -- a system that returns a confident verdict for a
    good-morning blessing is broken in a way no accuracy number would show.

    The Gurmukhi rewrites in `native_script` are NOT loaded here. They are
    transliteration references, so they become gold in data/gold/ via
    scripts/build_translit_gold.py, the same way retrieval gold is built.
    """
    path = RAW / "handtyped" / "forwards.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        for item in csv.DictReader(fh):
            text = (item.get("message") or "").strip()
            row_id = (item.get("id") or "").strip()
            if not text or not row_id:
                continue
            declared = (item.get("lang") or "").strip()
            lang, note = MIXED_LANG.get(row_id, (declared, ""))
            checkworthy = "No" if item["claim_summary"].strip().lower() == "no claim" else "Yes"
            record = _make_record(
                dataset="handtyped",
                split="dev",
                # The index is the collector's own id, not a running counter, so
                # a uid survives rows being added, removed or relabelled later.
                index=int(row_id[2:]),
                lang=lang,
                text=text,
                source_id=f"handtyped:{row_id}",
                label=checkworthy,
                label_set="checkworthy_binary",
            )
            if note:
                record["notes"] = f"declared mixed; assigned {lang} -- {note}"
            yield Row(record=record, text=text)


def handtyped_rows() -> dict[str, list[Row]]:
    """One split only.

    All 100 rows are `dev`, not `test`. They are a measurement set reported
    while building, and `test` would lock them behind TRUTHLENS_ALLOW_TEST=1 --
    correct for a final held-out number, wrong for the set whose whole job is to
    be looked at during development. Nothing is ever trained on them.
    """
    return {"dev": list(load_handtyped())}


# -----------------------------------------------------------------------------
# Check-worthiness, derived from X-CLAIM's span annotations
# -----------------------------------------------------------------------------

# A negative shorter than this is a fragment, not a message. Three tokens is
# where "Jai Hind" and "Forward to all" stop being plausible standalone forwards
# and start being debris.
MIN_NEGATIVE_TOKENS = 3


def load_xclaim_checkworthy(lang: str, split_name: str) -> Iterator[Row]:
    """Check-worthy / not, derived from where X-CLAIM says the claim IS.

    FR-6 has no training data anywhere and none can be acquired. X-CLAIM rows all
    contain a claim and CheckThat! Task 2 posts all have a normalized claim, so
    both are 100% positive; CheckThat!'s Task 1 is a subjectivity task but covers
    no Indic language. The only real gold in the project is 100 hand-typed rows,
    which are `dev`.

    So the negatives are constructed, from the one annotation that can support
    them: X-CLAIM marked exactly which token range is the claim, which means the
    REMAINDER of that post demonstrably is not. A post reading "Good morning all.
    The govt announced X. Forward this" with the middle sentence annotated yields
    a genuine no-claim message from the other two.

    Two things this is not, both stated wherever the number appears:

    - It is not naturally occurring. The negatives are fragments of posts that
      did contain a claim, so they share vocabulary and register with their own
      positives -- which makes this set EASIER than reality. The 100 hand-typed
      forwards remain the honest held-out test.
    - It is not every post. Only posts whose span is a strict subset can yield a
      negative; a post that is entirely claim has no remainder.

    Split assignment is inherited from X-CLAIM's own, so a post's positive and
    its negative can never straddle train and eval.
    """
    path = RAW / "x_claim" / f"{split_name}-{lang}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        for i, item in enumerate(csv.DictReader(fh)):
            parsed = _parse_span_row(item)
            if parsed is None:
                continue
            tokens, start, end = parsed
            positive = " ".join(tokens).strip()
            if positive:
                yield Row(
                    record=_make_record(
                        dataset="xclaim_cw", split=split_name, index=i * 2,
                        lang=lang, text=positive,
                        source_id=f"xclaim_cw:{split_name}-{lang}:{i}:pos",
                        label="Yes", label_set="checkworthy_binary",
                    ),
                    text=positive,
                )
            # `end` is INCLUSIVE -- measured, see scripts/build_span_gold.py.
            remainder = tokens[:start] + tokens[end + 1:]
            if len(remainder) >= MIN_NEGATIVE_TOKENS:
                negative = " ".join(remainder).strip()
                if negative:
                    yield Row(
                        record=_make_record(
                            dataset="xclaim_cw", split=split_name, index=i * 2 + 1,
                            lang=lang, text=negative,
                            source_id=f"xclaim_cw:{split_name}-{lang}:{i}:neg",
                            label="No", label_set="checkworthy_binary",
                        ),
                        text=negative,
                    )


def xclaim_checkworthy_rows() -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    for split in out:
        for lang in XCLAIM_LANGS:
            out[split].extend(load_xclaim_checkworthy(lang, split))
    return out


# -----------------------------------------------------------------------------
# Stance, derived from AVeriTeC's QA annotations (FR-10)
# -----------------------------------------------------------------------------

# ALWAYS the committed splits -- never a build's output directory. A
# reproducibility check rebuilds into a temporary directory, and reading splits
# from there would find none; this is the same trap `build_splits.py` documents
# for cross-dataset dedup.
AVERITEC_SPLITS = Path("data/splits/averitec")
UNANSWERABLE = "Unanswerable"


def averitec_split_membership(root: Path = AVERITEC_SPLITS) -> dict[str, str]:
    """`averitec:train.json:2557` -> the split that claim was frozen into."""
    membership: dict[str, str] = {}
    for split in ("train", "dev", "test"):
        path = root / f"{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} is missing. averitec_stance inherits its splits from the "
                "committed AVeriTeC splits, so those must exist first."
            )
        for record in load_jsonl(path):
            membership[record["source_id"]] = split
    return membership


def averitec_evidence(question: dict[str, Any], answer: dict[str, Any]) -> str:
    """The evidence text for one QA answer: question, answer, explanation.

    The question is kept because the answer alone is often meaningless -- a
    Boolean answer is literally "No", and "No" to WHAT is the whole content.
    """
    parts = [(question.get("question") or "").strip(),
             (answer.get("answer") or "").strip(),
             (answer.get("boolean_explanation") or "").strip()]
    return " ".join(p for p in parts if p)


def pair_text(claim: str, evidence: str) -> str:
    """The single string a pair is hashed and SimHashed by.

    The PAIR, not the claim: every answer of one claim shares the claim text, so
    hashing the claim alone would let within-train dedup keep one arbitrary
    answer per claim and cut ~6.6k training rows to ~2.6k.
    """
    return f"{claim}\n{evidence}"


def stance_parent_source_id(source_id: str) -> str:
    """`averitec_stance:train.json:2557:q0:a1` -> `averitec:train.json:2557`."""
    _, file_part, index = source_id.split(":")[:3]
    return f"averitec:{file_part}:{index}"


def averitec_stance_rows(splits_root: Path = AVERITEC_SPLITS) -> dict[str, list[Row]]:
    """(claim, evidence) -> Supports / Refutes / Neutral, one row per QA answer.

    FR-10 needs stance gold and none exists: AVeriTeC annotates a verdict per
    CLAIM and QA evidence per claim, but no stance per piece of evidence. So each
    answer inherits its claim's verdict (`labels.map_averitec_stance`), with two
    exceptions that are deviations worth stating:

    * **Conflicting claims are excluded** -- their evidence points both ways, so
      no one stance is right for a given answer.
    * **Unanswerable answers are Neutral, whatever the verdict.** They are all
      the literal string "No answer could be found."; labelled with the verdict,
      ~5% of rows would teach a model that finding nothing means Refutes.

    **Split membership is inherited, never recomputed.** The local AVeriTeC test
    split is 307 claims held out of the public train.json, so a derived row's
    split comes from its parent claim's frozen split -- otherwise answers from a
    test claim could train the stance model. Claims AVeriTeC's own dedup dropped
    are dropped here too.

    Duplicate answers within one claim are emitted once, so dev and test are
    de-duplicated the same way train is even though the build's dedup never
    touches eval splits.
    """
    membership = averitec_split_membership(splits_root)
    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    counters = {split: 0 for split in out}
    for file_name in ("train.json", "dev.json"):
        for i, item in enumerate(load_json(RAW / "averitec" / file_name)):
            parent = f"averitec:{file_name}:{i}"
            split = membership.get(parent)
            if split is None:
                continue
            verdict_stance = map_averitec_stance(item["label"])
            if verdict_stance is None:
                continue
            claim = (item.get("claim") or "").strip()
            if not claim:
                continue
            seen: set[str] = set()
            for qi, question in enumerate(item.get("questions") or []):
                for ai, answer in enumerate(question.get("answers") or []):
                    evidence = averitec_evidence(question, answer)
                    key = normalize_for_hashing(evidence)
                    if not evidence or key in seen:
                        continue
                    seen.add(key)
                    label = ("Neutral" if answer.get("answer_type") == UNANSWERABLE
                             else verdict_stance)
                    text = pair_text(claim, evidence)
                    record = _make_record(
                        dataset="averitec_stance", split=split,
                        index=counters[split], lang="en", text=text,
                        source_id=f"averitec_stance:{file_name}:{i}:q{qi}:a{ai}",
                        label=label, label_set="stance_3class",
                    )
                    counters[split] += 1
                    out[split].append(Row(
                        record=record, text=text,
                        extra={"claim": claim, "evidence": evidence,
                               "answer_type": answer.get("answer_type") or ""},
                    ))
    return out


# CheckThat! ships each language under its own code, and they are not uniform:
# English is `eng` while Hindi and Punjabi are `hi` and `pa`.
CHECKTHAT_LANGS = {"en": "eng", "hi": "hi", "pa": "pa"}


def load_checkthat(lang: str, split_name: str) -> Iterator[Row]:
    """One CheckThat! 2025 Task 2 file: a noisy post and its normalized claim.

    The label is the NORMALIZED CLAIM itself -- free text, not a class -- so it
    does not go in `label`, which is validated against a fixed label set. It is
    carried in the materialised text alongside the post and becomes generation
    gold in Phase 3, the same way the hand-typed Gurmukhi rewrites became
    transliteration gold.

    The test split is read from `test_gold-*.csv`, NOT `test-*.csv`. The latter
    is the shared-task release and ships with a `post` column only; a loader
    pointed at it gets a file with no answers in it and no error.
    """
    code = CHECKTHAT_LANGS[lang]
    stem = "test_gold" if split_name == "test" else split_name
    path = RAW / "checkthat25_t2" / f"{stem}-{code}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        for i, item in enumerate(csv.DictReader(fh)):
            text = (item.get("post") or "").strip()
            if not text:
                continue
            yield Row(
                record=_make_record(
                    dataset="checkthat25_t2",
                    split=split_name,
                    index=i,
                    lang=lang,
                    text=text,
                    source_id=f"checkthat25_t2:{stem}-{code}:{i}",
                    label=None,
                    label_set=None,
                ),
                text=text,
            )


def checkthat_rows() -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    for split in out:
        for lang in CHECKTHAT_LANGS:
            out[split].extend(load_checkthat(lang, split))
    return out


def averitec_rows() -> dict[str, list[Row]]:
    """AVeriTeC's public release: train and dev only.

    The test split is withheld for the FEVER shared task. Carving a local test
    set out of train is handled by scripts/build_splits.py, not here, so the
    loader stays a faithful reading of what upstream actually published.
    """
    return {
        "train": list(load_averitec("train.json", "train")),
        "dev": list(load_averitec("dev.json", "dev")),
    }


def xclaim_rows() -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    for split in out:
        for lang in XCLAIM_LANGS:
            out[split].extend(load_xclaim(lang, split))
    return out


def xclaim_romanized_rows() -> dict[str, list[Row]]:
    """X-CLAIM's native-script Hindi and Punjabi dev/test posts, romanized (FR-26).

    The synthetic half of the romanized evaluation (the natural half is the
    hand-typed forwards and MultiClaim's own Latin-script posts). Built by
    `preprocess/romanize.py` -- Dakshina's train lexicon, rules for the rest --
    one whitespace token to one token, so X-CLAIM's token-indexed span gold
    applies unchanged and `scripts/build_span_gold.py --dataset
    x_claim_romanized` rebuilds it through `source_id`.

    Eval splits only: nothing trains on synthetic romanization, so there is no
    train split to leak into. Rows already in Latin script are left out -- they
    are real romanized text and are scored in x_claim itself. English is left
    out by definition.
    """
    from preprocess.romanize import romanize

    out: dict[str, list[Row]] = {"dev": [], "test": []}
    for split in out:
        for lang in ("hi", "pa"):
            for row in load_xclaim(lang, split):
                if row.record["script"] not in ("deva", "guru"):
                    continue
                index = int(row.record["source_id"].rsplit(":", 1)[1])
                text = romanize(row.text)
                out[split].append(Row(
                    record=_make_record(
                        dataset="x_claim_romanized", split=split, index=index,
                        lang=lang, text=text,
                        source_id=f"x_claim_romanized:{split}-{lang}:{index}",
                        label=None, label_set=None,
                    ),
                    text=text,
                ))
    return out


# -----------------------------------------------------------------------------
# FEVER, for measuring the live verdict (docs/live-fever-protocol.md)
# -----------------------------------------------------------------------------

FEVER_REPO = "copenlu/fever_gold_evidence"
FEVER_FILE = "valid.jsonl"
FEVER_LABELS = {"SUPPORTS": "Supported", "REFUTES": "Refuted", "NOT ENOUGH INFO": "NEI"}
FEVER_SELECT_PER_CLASS = 50
FEVER_CONFIRM_PER_CLASS = 100
FEVER_SUB_PER_CLASS = 20
FEVER_FRESH_COUNTS = {"Supported": 100, "Refuted": 150, "NEI": 100}
FEVER_FRESH_SUB_PER_CLASS = 20


def fever_path() -> Path:
    """FEVER dev as cached by huggingface_hub (downloaded once with `hf_hub_download`).

    Read from the Hugging Face cache, not copied under data/raw, so there is no second
    copy to drift; a path that does not exist means "not downloaded", which
    `sources_available` reports as a skipped dataset, not a failure.
    """
    try:
        from huggingface_hub import try_to_load_from_cache

        found = try_to_load_from_cache(FEVER_REPO, FEVER_FILE, repo_type="dataset")
        if isinstance(found, str):
            return Path(found)
    except Exception:       # no huggingface_hub (core CI lock), or no cache
        pass
    return Path("data/raw/fever_live") / FEVER_FILE


def fever_samples() -> dict[str, list[dict[str, str]]]:
    """The three FEVER-dev samples, deterministic from the file alone (seed 42).

    Claims are de-duplicated on normalised text, shuffled within each label, and dealt
    out: `select` first, `confirm` from what is left (so they are disjoint), and
    `confirm_sub` is the first 20 per label of `confirm` in its own order. Each set is
    mixed across labels (round-robin), so a truncated run is still balanced.
    """
    import json
    import random

    by_label: dict[str, list[dict[str, str]]] = {k: [] for k in FEVER_LABELS.values()}
    seen: set[str] = set()
    with fever_path().open("r", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    for item in sorted(rows, key=lambda r: str(r["id"])):
        label = FEVER_LABELS.get(item["label"])
        claim = (item.get("claim") or "").strip()
        key = normalize_for_hashing(claim)
        if label is None or not claim or key in seen:
            continue
        seen.add(key)
        by_label[label].append({"claim": claim, "label": label, "fever_id": str(item["id"])})
    rng = random.Random(SEED)
    for label in sorted(by_label):
        rng.shuffle(by_label[label])

    def deal(n: int, taken: dict[str, int]) -> list[dict[str, str]]:
        picked = {lab: by_label[lab][taken[lab]:taken[lab] + n] for lab in sorted(by_label)}
        for lab in picked:
            taken[lab] += n
        return [picked[lab][i] for i in range(n) for lab in sorted(picked)]

    taken = {lab: 0 for lab in by_label}
    select = deal(FEVER_SELECT_PER_CLASS, taken)
    confirm = deal(FEVER_CONFIRM_PER_CLASS, taken)
    sub = [c for i in range(FEVER_SUB_PER_CLASS) for c in confirm[3 * i:3 * i + 3]]
    # Protocol 2 (docs/live-fever-protocol-2.md): fresh claims dealt AFTER select and
    # confirm, so those two sets are byte-for-byte what they were and the fresh set is
    # disjoint from both. Round-robin over the labels until each is used up.
    fresh_pools = {lab: by_label[lab][taken[lab]:taken[lab] + n] for lab, n in FEVER_FRESH_COUNTS.items()}
    fresh = [fresh_pools[lab][i] for i in range(max(FEVER_FRESH_COUNTS.values()))
             for lab in sorted(fresh_pools) if i < len(fresh_pools[lab])]
    fresh_sub = []
    per_label: dict[str, int] = {}
    for c in fresh:
        if per_label.get(c["label"], 0) < FEVER_FRESH_SUB_PER_CLASS:
            per_label[c["label"]] = per_label.get(c["label"], 0) + 1
            fresh_sub.append(c)
    return {"select": select, "confirm": confirm, "confirm_sub": sub,
            "fresh": fresh, "fresh_sub": fresh_sub}


def _fever_rows(which: str) -> dict[str, list[Row]]:
    rows = []
    for i, item in enumerate(fever_samples()[which]):
        rows.append(Row(
            record=_make_record(
                dataset=f"fever_{which}", split="dev", index=i, lang="en", text=item["claim"],
                source_id=f"fever_dev:{item['fever_id']}", label=item["label"],
                label_set="verdict_5class"),
            text=item["claim"]))
    return {"dev": rows}


def fever_select_rows() -> dict[str, list[Row]]:
    return _fever_rows("select")


def fever_confirm_rows() -> dict[str, list[Row]]:
    return _fever_rows("confirm")


def fever_confirm_sub_rows() -> dict[str, list[Row]]:
    return _fever_rows("confirm_sub")


def fever_fresh_rows() -> dict[str, list[Row]]:
    return _fever_rows("fresh")


def fever_fresh_sub_rows() -> dict[str, list[Row]]:
    return _fever_rows("fresh_sub")


LOADERS = {
    "averitec": averitec_rows,
    "x_claim": xclaim_rows,
    "multiclaim": multiclaim_rows,
    "handtyped": handtyped_rows,
    "checkthat25_t2": checkthat_rows,
    "xclaim_cw": xclaim_checkworthy_rows,
    "averitec_stance": averitec_stance_rows,
    "x_claim_romanized": xclaim_romanized_rows,
    "fever_select": fever_select_rows,
    "fever_confirm": fever_confirm_rows,
    "fever_confirm_sub": fever_confirm_sub_rows,
    "fever_fresh": fever_fresh_rows,
    "fever_fresh_sub": fever_fresh_sub_rows,
}

# What each loader needs on disk. Used to skip a dataset whose source is not
# present rather than crash on it.
#
# This is not hypothetical tidiness: MultiClaim is access-restricted and cannot
# ever exist in CI, so the reproducibility job must be able to verify the
# datasets it CAN fetch and report the rest as unverifiable -- not fail, and not
# quietly pass either.
LOADER_SOURCES: dict[str, tuple[Path, ...]] = {
    "averitec": (RAW / "averitec" / "train.json", RAW / "averitec" / "dev.json"),
    "x_claim": (RAW / "x_claim" / "train-en.csv",),
    "multiclaim": (RAW / "multiclaim" / "posts.csv",
                   RAW / "multiclaim" / "fact_checks.csv",
                   RAW / "multiclaim" / "fact_check_post_mapping.csv"),
    # Collected by hand and never published: it contains people's own writing,
    # so like MultiClaim it can never exist on a CI runner.
    "handtyped": (RAW / "handtyped" / "forwards.csv",),
    # Derived from X-CLAIM's own CSVs, so it depends on exactly those files.
    "xclaim_cw": (RAW / "x_claim" / "train-en.csv",),
    # Derived from AVeriTeC's QA annotations; also reads the COMMITTED averitec
    # splits for membership, but those are not raw sources and do not belong here.
    "averitec_stance": (RAW / "averitec" / "train.json", RAW / "averitec" / "dev.json"),
    # X-CLAIM romanized by Dakshina's lexicon: both are sources. Dakshina is not
    # fetched in CI, so CI reports this one unverifiable, like MultiClaim.
    "x_claim_romanized": (RAW / "x_claim" / "dev-hi.csv", RAW / "x_claim" / "test-pa.csv",
                          RAW / "dakshina" / "extracted" / "hi" / "hi.translit.sampled.train.tsv",
                          RAW / "dakshina" / "extracted" / "pa" / "pa.translit.sampled.train.tsv"),
    # FEVER dev from the Hugging Face cache; the loader's own samples (seed 42).
    "fever_select": (fever_path(),),
    "fever_confirm": (fever_path(),),
    "fever_confirm_sub": (fever_path(),),
    "fever_fresh": (fever_path(),),
    "fever_fresh_sub": (fever_path(),),
    "checkthat25_t2": (RAW / "checkthat25_t2" / "train-eng.csv",
                       RAW / "checkthat25_t2" / "train-hi.csv",
                       RAW / "checkthat25_t2" / "train-pa.csv"),
}


def sources_available(dataset: str) -> bool:
    return all(p.is_file() for p in LOADER_SOURCES.get(dataset, ()))


def missing_sources(dataset: str) -> list[str]:
    return [p.as_posix() for p in LOADER_SOURCES.get(dataset, ()) if not p.is_file()]


def code_mixed_share(rows: list[Row], threshold: float = 0.9) -> float:
    """Share of rows whose dominant script covers less than `threshold`.

    Reported in docs/data-profile.md because code-mixing is the normal case
    for forwards, and a single `script` label hides it.
    """
    if not rows:
        return 0.0
    mixed = sum(1 for r in rows if script_purity(r.text) < threshold)
    return mixed / len(rows)
