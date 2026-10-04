"""Measure the live verdict on FEVER dev (docs/live-fever-protocol.md, pre-registered).

    python scripts/live_fever.py collect  --set select            # network + pipeline
    python scripts/live_fever.py collect  --set sub --lang hi     # round-trip Hindi check
    python scripts/live_fever.py score    --set select            # NLI models, one at a time
    python scripts/live_fever.py variants --set select            # preds + eval configs
    python scripts/live_fever.py select                           # the pre-fixed selection rule

Three phases, so the network is hit once per claim and two GPU-heavy things never share
the 6 GiB card:

  collect   the real `Orchestrator.verify(claim, live=True)` (what the UI button runs) and
            the offline answer; stores each judged passage with the premise the NLI read.
  score     DeBERTa-v3-large, BART-large-MNLI and mDeBERTa-xnli read the stored pairs,
            one model loaded at a time.
  variants  V1 (DeBERTa alone), V2 (DeBERTa and BART agree), V3 (DeBERTa and mDeBERTa
            agree) are computed from the stored probabilities; predictions and eval
            configs are written. Metrics come from `make eval`, never from here.

A prediction is what the user would be shown: the verdict if not abstained, else NEI.
Resumable: `collect` skips claims already done; `--rerun-degraded` redoes only claims
where a source failed (HTTP 429 and the like), once, as the protocol allows.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "reports" / "live_fever"
DATASETS = {"select": "fever_select", "confirm": "fever_confirm", "sub": "fever_confirm_sub"}
MODELS = {"deberta": "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",
          "bart": "facebook/bart-large-mnli",
          "mdeberta": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"}
VARIANTS = ("v0", "v1", "v2", "v3", "nei")
TAU = 0.3835                                   # the served tau_abstain
SHOWN = {"Supported", "Refuted"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def stem(args) -> str:
    return f"{args.set}_{args.lang}"


def claims_of(set_name: str) -> list[dict]:
    dataset = DATASETS[set_name]
    split = read_jsonl(ROOT / "data" / "splits" / dataset / "dev.jsonl")
    text = {r["uid"]: r["text"] for r in read_jsonl(ROOT / "data" / "interim" / dataset / "dev.jsonl")}
    return [{"uid": r["uid"], "label": r["label"], "text": text[r["uid"]]} for r in split]


def shown(res) -> tuple[str, float]:
    """(prediction, confidence) the user would see for one ClaimResult."""
    if res is None or res.verdict == "NotAClaim" or res.abstained:
        return "NEI", float(getattr(res, "confidence", 0.0) or 0.0)
    return res.verdict, float(res.confidence)


# ------------------------------------------------------------------------ collect --


def cmd_collect(args) -> int:
    from pipeline.orchestrator import Orchestrator, PipelineConfig, _translator_device
    from preprocess.translate import NllbTranslator

    claims = claims_of(args.set)
    if args.lang != "en" and args.set != "sub":
        raise SystemExit("--lang hi/pa is only defined for --set sub (the 60-claim round-trip subset)")
    path = OUT / f"{stem(args)}.collect.jsonl"
    done = {r["uid"]: r for r in read_jsonl(path)}
    todo = [c for c in claims if c["uid"] not in done
            or (args.rerun_degraded and done[c["uid"]]["degraded"] and not done[c["uid"]].get("rerun"))]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{stem(args)}: {len(claims)} claims, {len(done)} done, {len(todo)} to run", flush=True)
    if not todo:
        return 0

    cfg = PipelineConfig.load(ROOT / "configs/pipeline/dev.yaml")
    cfg.stages["generation"] = "template"          # the verdict does not depend on the explainer
    cfg.live_search = cfg.live_verdict = cfg.live_translate = True
    orch = Orchestrator(cfg)
    translator = NllbTranslator(device=_translator_device())
    orch._translator = translator
    orch.verify("warm-up")
    for n, claim in enumerate(todo, 1):
        text = claim["text"]
        if args.lang != "en":
            text = translator.translate(text, "en", args.lang)
        t0 = time.perf_counter()
        offline = orch.verify(text)
        orch._live_capture = []
        trace = orch.verify(text, live=True)
        capture, orch._live_capture = orch._live_capture, None
        results = trace.results
        live_pred, live_conf = shown(results[0] if results else None)
        off_pred, off_conf = shown(offline.results[0] if offline.results else None)
        notes = [e.note for e in trace.events if e.stage == "live" and e.note]
        rec = {
            "uid": claim["uid"], "label": claim["label"], "text": text, "lang": args.lang,
            "offline": {"pred": off_pred, "confidence": off_conf},
            "live": {"pred": live_pred, "confidence": live_conf,
                     "path": results[0].path if results else None,
                     "verdict": results[0].verdict if results else None,
                     "abstained": bool(results[0].abstained) if results else None,
                     "sources": results[0].live_sources if results else []},
            "n_results": len(results), "capture": capture,
            "degraded": any(n.startswith("degraded") for n in notes), "notes": notes,
            "seconds": round(time.perf_counter() - t0, 2),
            "rerun": bool(args.rerun_degraded and claim["uid"] in done),
        }
        done[claim["uid"]] = rec
        write_jsonl(path, [done[c["uid"]] for c in claims if c["uid"] in done])
        print(f"{n:4}/{len(todo)} {claim['label']:9} live={live_pred:9} offline={off_pred:9} "
              f"{'DEGRADED ' if rec['degraded'] else ''}{rec['seconds']}s", flush=True)
        time.sleep(args.pause)
    return 0


# -------------------------------------------------------------------------- score --


def cmd_score(args) -> int:
    import gc

    import torch

    from stance.nli import NLIStance

    rows = read_jsonl(OUT / f"{stem(args)}.collect.jsonl")
    pairs: list[tuple[int, int, str, str]] = []
    for ri, rec in enumerate(rows):
        if rec["n_results"] != 1 or len(rec["capture"]) != 1:
            continue
        cap = rec["capture"][0]
        for pi, p in enumerate(cap["judged"]):
            if not p["rating_stance"]:
                pairs.append((ri, pi, p["premise"], cap["hypothesis"]))
    print(f"{stem(args)}: {len(pairs)} (premise, claim) pairs", flush=True)
    for rec in rows:
        rec["probs"] = {}
    for key, model_id in MODELS.items():
        nli = NLIStance(model_id=model_id, max_length=256, batch_size=8)
        scored = nli.score_pairs([(prem, hyp) for _, _, prem, hyp in pairs])
        for rec in rows:
            rec["probs"][key] = [None] * len(rec["capture"][0]["judged"]) if rec["capture"] else []
        for (ri, pi, _, _), s in zip(pairs, scored, strict=True):
            rows[ri]["probs"][key][pi] = s.probs
        print(f"  scored with {key}", flush=True)
        del nli
        NLIStance._LOADED.clear()
        gc.collect()
        torch.cuda.empty_cache()
    write_jsonl(OUT / f"{stem(args)}.scored.jsonl", rows)
    return 0


# ----------------------------------------------------------------------- variants --


def verdict_of(rec: dict, key: str) -> tuple[str, float] | None:
    """The live verdict from one model's stored probabilities, or None if no pairs."""
    from pipeline.live import live_verdict

    if rec["n_results"] != 1 or len(rec["capture"]) != 1:
        return None
    judged = rec["capture"][0]["judged"]
    idx = [i for i, p in enumerate(judged) if not p["rating_stance"]]
    if not idx:
        return None
    verdict, conf, _ = live_verdict([rec["probs"][key][i] for i in idx],
                                    [judged[i]["cosine"] for i in idx])
    return verdict, conf


def shown_pair(verdict: str, conf: float) -> tuple[str, float]:
    return ("NEI", conf) if conf < TAU or verdict not in ("Supported", "Refuted", "Conflicting", "NEI") \
        else (verdict, conf)


def variant_predictions(rec: dict) -> dict[str, tuple[str, float]]:
    out = {"v0": (rec["offline"]["pred"], rec["offline"]["confidence"]), "nei": ("NEI", 1.0)}
    base = (rec["live"]["pred"], rec["live"]["confidence"])
    d = verdict_of(rec, "deberta")
    if d is None:                                  # nothing to judge: every variant is the card
        out.update({"v1": base, "v2": base, "v3": base})
        return out
    out["v1"] = shown_pair(*d)
    for name, other in (("v2", "bart"), ("v3", "mdeberta")):
        o = verdict_of(rec, other)
        if o is not None and d[0] == o[0] and d[0] in SHOWN:
            out[name] = shown_pair(d[0], min(d[1], o[1]))
        else:
            out[name] = ("NEI", min(d[1], o[1]) if o else 0.0)
    return out


def cmd_variants(args) -> int:
    rows = read_jsonl(OUT / f"{stem(args)}.scored.jsonl")
    if not rows:
        raise SystemExit("run `score` first")
    dataset = DATASETS[args.set]
    preds: dict[str, list[dict]] = {v: [] for v in VARIANTS}
    mismatches, degraded = [], []
    for rec in rows:
        vp = variant_predictions(rec)
        for v in VARIANTS:
            pred, conf = vp[v]
            preds[v].append({"uid": rec["uid"], "pred": pred, "confidence": round(float(conf), 6)})
        if vp["v1"][0] != rec["live"]["pred"]:
            mismatches.append({"uid": rec["uid"], "stored": vp["v1"], "card": rec["live"]["pred"]})
        if rec["degraded"]:
            degraded.append(rec["uid"])
    (ROOT / "results" / "preds").mkdir(parents=True, exist_ok=True)
    (ROOT / "configs").mkdir(exist_ok=True)
    for v in VARIANTS:
        name = f"p8_fever_{stem(args)}_{v}"
        write_jsonl(ROOT / "results" / "preds" / f"{name}.jsonl", preds[v])
        (ROOT / "configs" / f"{name}.yaml").write_text(
            f"# Live verdict on FEVER (docs/live-fever-protocol.md, pre-registered). Variant {v}.\n"
            f"experiment: {name}\ntask: classification\n"
            f"split: data/splits/{dataset}/dev.jsonl\n"
            f"predictions: results/preds/{name}.jsonl\n"
            "label_set: verdict_5class\nbaseline: stratified_random\n"
            "false_label: Supported\nbreakdown: [lang]\nsanity_ceiling: 1.0\n"
            "calibration:\n  tau: 0.3835\n"
            "notes: >\n  Scored predictions are what the user would be shown (abstained -> NEI)."
            f" Variant {v} of the FEVER live-verdict measurement; see the protocol.\n",
            encoding="utf-8")
    summary = {"set": args.set, "lang": args.lang, "n": len(rows), "degraded": degraded,
               "v1_vs_card_mismatches": mismatches,
               "multi_claim": [r["uid"] for r in rows if r["n_results"] != 1],
               "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2]}
    (OUT / f"{stem(args)}.summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"wrote {len(VARIANTS)} prediction files and configs; degraded={len(degraded)} "
          f"v1-vs-card mismatches={len(mismatches)} multi-claim={len(summary['multi_claim'])}")
    return 0


# ----------------------------------------------------------------------- select --


def cmd_select(_args) -> int:
    """The protocol's selection rule, applied to the harness's own results on `select`."""
    chosen = None
    table = []
    for v in ("v1", "v2", "v3"):
        res = find_result(f"p8_fever_select_en_{v}")
        o = res["metrics"]["overall"]
        fl = o["false_label_rate"]
        pc = o["confusion"]
        answered = sum(pc[t].get(p, 0) for t in pc for p in ("Supported", "Refuted"))
        correct = pc.get("Supported", {}).get("Supported", 0) + pc.get("Refuted", {}).get("Refuted", 0)
        table.append((v, int(fl["k"]), correct / answered if answered else 0.0, answered))
    order = {"v1": 0, "v2": 1, "v3": 2}
    table.sort(key=lambda t: (t[1], -round(t[2], 6), order[t[0]]))
    chosen = table[0][0]
    for v, k, acc, n in table:
        print(f"{v}: false-Supported={k}  accuracy-on-answered={acc:.3f}  answered={n}")
    print("CHOSEN:", chosen)
    return 0


def find_result(experiment: str) -> dict:
    best = None
    for p in (ROOT / "results").glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("experiment") == experiment and (best is None or p.stat().st_mtime > best[0]):
            best = (p.stat().st_mtime, data)
    if best is None:
        raise SystemExit(f"no results/*.json for {experiment}; run make eval first")
    return best[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("collect", "score", "variants"):
        p = sub.add_parser(name)
        p.add_argument("--set", choices=sorted(DATASETS), required=True)
        p.add_argument("--lang", choices=("en", "hi", "pa"), default="en")
        if name == "collect":
            p.add_argument("--pause", type=float, default=6.0, help="seconds between claims (rate limits)")
            p.add_argument("--limit", type=int, default=None)
            p.add_argument("--rerun-degraded", action="store_true")
    sub.add_parser("select")
    args = ap.parse_args(argv)
    return {"collect": cmd_collect, "score": cmd_score, "variants": cmd_variants,
            "select": cmd_select}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
