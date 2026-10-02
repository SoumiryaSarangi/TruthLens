#!/usr/bin/env bash
# The one test-split run, exactly as docs/test-protocol.md pre-registers it.
#
#   bash scripts/run_test_protocol.sh            # from the repo root, Git Bash
#
# Runs every prediction command (each proven on dev to reproduce its dev twin
# byte for byte), writes the three configs that pair against a run produced
# earlier in this script, and scores every config ONCE. Run it on the
# `code-freeze` commit. It sets TRUTHLENS_ALLOW_TEST=1 for itself only -- this
# is the final run, and nothing on test feeds back into any choice.
#
# Takes ~1.5 h, most of it the explainer (#7). Each step writes before the next
# starts, so a crash can be resumed by commenting out the finished steps -- a
# re-run is allowed only for a crash, a refusal or a non-metric bug, and is
# logged with its cause (protocol, rule 2).
set -euo pipefail

export TRUTHLENS_ALLOW_TEST=1 PYTHONIOENCODING=utf-8 PYTHONPATH=src
PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=.venv/bin/python
B="$PY -m pipeline.batch"
EVAL="$PY -m eval.evaluate --config"
AV=data/splits/averitec/test.jsonl
EVIDENCE="--impl hybrid --depth 200 --fusion rrf --k 10"
LOG=reports/test_run.log
mkdir -p reports
exec > >(tee -a "$LOG") 2>&1
echo "== test run on $(git rev-parse --short HEAD) $(git describe --tags --always) at $(date -u +%FT%TZ)"
[ -z "$(git status --porcelain -- src configs scripts)" ] || { echo "REFUSED: code or configs are dirty"; exit 2; }

hash_of() {  # the config_hash a scored config just wrote, read from its results file
  "$PY" - "$1" <<'EOF'
import json, sys, glob, os
exp = sys.argv[1]
docs = [json.load(open(p, encoding="utf-8")) for p in glob.glob("results/*.json")]
docs = [d for d in docs if d.get("experiment") == exp]
print(max(docs, key=lambda d: d["created_utc"])["config_hash"])
EOF
}

runtime_config() {  # name, dev twin, predictions, baseline hash, extra yaml lines
  local name=$1 twin=$2 preds=$3 base=$4 extra=${5:-}
  "$PY" - "$name" "$twin" "$preds" "$base" "$extra" <<'EOF'
import sys, yaml
name, twin, preds, base, extra = sys.argv[1:6]
cfg = yaml.safe_load(open(f"configs/{twin}.yaml", encoding="utf-8"))
cfg.update({"experiment": name, "predictions": preds, "baseline": base,
            "split": cfg["split"].replace("dev.jsonl", "test.jsonl")})
if "gold" in cfg:
    cfg["gold"] = cfg["gold"].replace("_dev_", "_test_")
if extra:
    for k, v in yaml.safe_load(extra).items():
        cfg[k] = v if not isinstance(v, dict) else {**cfg.get(k, {}), **v}
cfg["notes"] = (f"FINAL TEST RUN (docs/test-protocol.md), scored once with "
                f"TRUTHLENS_ALLOW_TEST=1. Written at run time from {twin}; only "
                f"split, predictions, gold and the baseline hash differ.")
head = (f"# Test protocol: written by scripts/run_test_protocol.sh from {twin}.yaml.\n"
        f"# Baseline {base} is the test run this one pairs against.\n")
open(f"configs/{name}.yaml", "w", encoding="utf-8", newline="\n").write(
    head + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print(f"wrote configs/{name}.yaml (baseline {base})")
EOF
}

echo "== #1 control, #2-4 served, #5 served at T=1 (AVeriTeC test, evidence path)"
$B --split $AV --stage verdict $EVIDENCE --stance-impl xlmr_claimonly --aggregate-impl learned \
   --aggregator data/interim/models/aggregator_xlmr_claimonly/model.joblib \
   --out-verdict results/preds/p7_test_verdict_control.jsonl
$B --split $AV --stage verdict $EVIDENCE --stance-impl xlmr_nli --aggregate-impl learned \
   --aggregator data/interim/models/aggregator_xlmr_nli_prior/model.joblib \
   --out-verdict results/preds/p7_test_verdict_served.jsonl
$B --split $AV --stage verdict $EVIDENCE --stance-impl xlmr_nli --aggregate-impl learned \
   --aggregator data/interim/models/aggregator_xlmr_nli_prior/model.joblib --temperature 1.0 \
   --out-verdict results/preds/p7_test_verdict_served_t1.jsonl
$EVAL configs/p7_test_verdict_control.yaml
CONTROL=$(hash_of p7_test_verdict_control)
runtime_config p7_test_verdict_served p6_verdict_served results/preds/p7_test_verdict_served.jsonl \
   "$CONTROL" "{calibration: {coverage_target: 0.6, tau: 0.3835}}"
$EVAL configs/p7_test_verdict_served.yaml
SERVED=$(hash_of p7_test_verdict_served)
$EVAL configs/p7_test_verdict_served_majority.yaml
runtime_config p7_test_calibration_served_t1 p6_calibration_served_t1 \
   results/preds/p7_test_verdict_served_t1.jsonl "$SERVED" "{calibration: {coverage_target: 0.6, tau: 0.3835}}"
$EVAL configs/p7_test_calibration_served_t1.yaml

echo "== #6 evidence retrieval"
$B --split $AV --stage retrieval --impl bm25 --stance-impl always_neutral \
   --out results/preds/p7_test_retrieval_bm25.jsonl
$B --split $AV --stage retrieval $EVIDENCE --stance-impl always_neutral \
   --out results/preds/p7_test_retrieval_hybrid.jsonl
$EVAL configs/p7_test_retrieval_bm25.yaml
BM25=$(hash_of p7_test_retrieval_bm25)
runtime_config p7_test_retrieval_hybrid p5_retrieval_hybrid_rrf_n200 \
   results/preds/p7_test_retrieval_hybrid.jsonl "$BM25"
$EVAL configs/p7_test_retrieval_hybrid.yaml

echo "== #8-11 claim spans (X-CLAIM test, romanized test)"
$B --split data/splits/x_claim/test.jsonl --stage span --claims-impl xlmr \
   --out results/preds/p7_test_span_joint.jsonl
$B --split data/splits/x_claim/test.jsonl --stage span --claims-impl heuristic_span \
   --out results/preds/p7_test_span_served.jsonl
$B --split data/splits/x_claim_romanized/test.jsonl --stage span --claims-impl xlmr \
   --out results/preds/p7_test_span_romanized_joint.jsonl
for c in p7_test_span_joint p7_test_span_served p7_test_span_romanized_joint \
         p7_test_span_native_matched_joint; do $EVAL configs/$c.yaml; done

echo "== #12-13 claim matching and the fast path (MultiClaim test)"
$B --split data/splits/multiclaim/test.jsonl --stage match --encoder bge_m3 \
   --out results/preds/p7_test_match_bge_m3.jsonl
$B --split data/splits/multiclaim/test.jsonl --stage match --impl bm25_factcheck \
   --out results/preds/p7_test_match_bm25.jsonl
for c in p7_test_match_bge_m3 p7_test_match_bm25 p7_test_fastpath_bge_m3; do $EVAL configs/$c.yaml; done

echo "== #14 normalization, #15 language ID"
$B --split data/splits/checkthat25_t2/test.jsonl --stage normalize --preprocess-impl hybrid \
   --claims-impl xlmr --out results/preds/p7_test_normalize_extractive.jsonl
$B --split data/splits/multiclaim/test.jsonl --stage lang --preprocess-impl hybrid \
   --out results/preds/p7_test_lid_hybrid.jsonl
$EVAL configs/p7_test_normalize_extractive.yaml
$EVAL configs/p7_test_lid_hybrid.yaml

echo "== #7 explanations (longest: ~1 h)"
$B --split $AV --stage explain --evidence retrieved --decoding beam $EVIDENCE \
   --stance-impl nli --aggregate-impl learned --out results/preds/p7_test_explain_beam.jsonl
$EVAL configs/p7_test_faithfulness_beam.yaml

echo "== done $(date -u +%FT%TZ). Results: results/*.json for experiments p7_test_*; log: $LOG"
