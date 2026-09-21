# TruthLens — Product Requirements Document

| | |
| --- | --- |
| **Status** | Approved for build · v1.0 · 21 Sep 2026 |
| **Course** | CSE472 — Deep Learning for Natural Language Processing |
| **Timeline** | 14 days, Day 1 = first day of Phase 1 |
| **Owns** | *Why* and *for whom*: problem, users, goals, success metrics, scope priorities |
| **Does not own** | Testable requirements → `SRS.md` · architecture and contracts → `SYSTEM_DESIGN.md` · screens → `UI_UX.md` · rationale history → `../build-plan.md` |

---

## 1. Problem

Misinformation in India travels as forwarded chat messages, in Hindi, Punjabi and English, very often typed in Roman script ("ye sach hai kya"), mixed across languages, and wrapped in emotional framing. Existing fact-checking tools assume clean, native-script, single-claim English input. They fail on exactly the input people actually receive.

Professional fact-checkers do not verify every claim from scratch. They first check whether the claim has already been debunked. Automated systems usually skip that step and go straight to open-ended verification, which is slower and less reliable.

## 2. Users and scenarios

**Primary user for this release — the evaluator.** A professor, viva panel or interviewer who has five minutes and wants to see the system handle realistic input and explain itself. Every product decision in this release optimises for them understanding what the system did and why.

**Conceptual end user — the recipient of a forward.** Someone who receives a message in a family group and wants to know whether to believe it or pass it on. They type in whatever script is on their keyboard, usually Roman. They want an answer in their own language, and they need to see *why*, because an unexplained verdict from software is just another forward.

**Secondary — a fact-checker triaging volume.** Wants to know quickly whether an incoming claim matches something already checked. Not built for in this release, but the claim-matching track serves them directly and is worth naming in the report.

### Scenarios this release must handle

| # | Input | Expected behaviour |
| --- | --- | --- |
| S1 | English claim that matches a published fact-check | Fast path: shows the matched fact-check and its verdict |
| S2 | Romanized Hindi claim with no prior fact-check | Transliterates, retrieves evidence, gives a verdict with sources |
| S3 | A long emotional rant with one factual claim buried inside | Extracts the claim, verifies only that |
| S4 | Pure opinion or a greeting ("Good morning, stay blessed") | Says there is no checkable factual claim — no verdict |
| S5 | A claim with thin or contradictory evidence | Says so — NEI, Conflicting, or abstains — rather than guessing |
| S6 | Gurmukhi Punjabi claim | Verdict in Punjabi context; explanation may fall back to Hindi or English (cut list item 3) |

## 3. Goals and non-goals

### Goals

1. Accept realistic forwards in EN / HI / PA, native or romanized, and route them correctly.
2. Mirror how fact-checkers work: claim matching first, evidence verification second.
3. Never return a verdict without showing the evidence behind it.
4. Prefer declining to answer over answering wrongly, and make the decline visible.
5. Measure and report the romanization penalty across the pipeline — the project's research contribution.

### Non-goals (stated in the report as decisions, not omissions)

- Image, video, audio or link-content claims. Text only.
- Adjudicating political opinions, predictions or value judgements. These route to NotAClaim.
- A real WhatsApp bot. The UI is a WhatsApp-styled web demo (see `UI_UX.md`).
- Deployment readiness, multi-user serving, authentication, scaling.
- Redistributing any licensed dataset. The repo holds ID manifests only.

## 4. Product principles

These resolve design arguments. When two choices conflict, the higher principle wins.

1. **No verdict without evidence.** Zero evidence retrieved means NEI plus abstain, never a guess.
2. **Abstaining is a feature.** "I'm not confident enough" is a first-class answer, visibly distinct from NEI.
3. **Show the work.** Every verdict expands into its sources and supporting spans.
4. **Meet the input where it is.** Romanized input is the primary case, not an edge case.
5. **Honest numbers over good-looking numbers.** Macro-F1 beside baselines, never accuracy alone.

## 5. Scope and priority

Priorities map directly onto the cut list in `../build-plan.md`. P0 is never cut.

| Feature | Priority | Phase | Notes |
| --- | --- | --- | --- |
| Language ID, per-row script detection, transliteration | P0 | 2 | Script detection already exists: `src/data/script_id.py` |
| Check-worthiness filter → NotAClaim | P0 | 3 | |
| Claim span extraction and normalization | P0 | 3 | X-CLAIM, CheckThat! 2025 T2 |
| **Claim-matching fast path** | **P0** | 4 | Never cut. Blocked on MultiClaim approval |
| Evidence retrieval, hybrid BM25 + dense | P0 | 5 | |
| Stance detection per evidence passage | P0 | 5 | BiLSTM baseline, XLM-R-base model |
| 5-class verdict with calibrated confidence | P0 | 6 | |
| **Abstention** | **P0** | 6 | Never cut |
| Grounded explanation with citations | P0 | 6 | IndicBART; template fallback always available |
| Faithfulness check on explanations | P0 | 6 | NLI-based |
| **Native vs romanized evaluation** | **P0** | 2 onward | Never cut. The research contribution |
| WhatsApp-style UI with evidence trail | P0 | 7 | Plain HTML page from Phase 1 |
| Cross-lingual t-SNE plot | P1 | 2 | LaBSE, report figure only |
| Punjabi explanation generation | P1 | 6 | Cut item 3 — fallback: HI or EN explanation |
| Manipulation-technique flags | P2 | 6–7 | Cut item 1 — zero-shot plus rules, not a trained classifier |
| Live search for recent claims | P2 | 5 | Cut item 2 — static corpus, recency limitation reported |
| Streaming stage progress in UI | P2 | 7 | Nice to have |

## 6. Success metrics

All metrics are computed by `src/eval/evaluate.py` only, per language **and** per script, with the dumb baseline in the same table. Figures below come from `docs/data-profile.md` as it stands today.

| Area | Metric | Bar for "this is a result" |
| --- | --- | --- |
| Verdict | 5-class macro-F1 on AVeriTeC dev | Beats `stratified_random` and `majority_class` on macro-F1. Note: majority class already scores **61.0% accuracy** on dev, and macro-F1 is **structurally capped at 0.80** on AVeriTeC-only runs because NotAClaim has zero support there. |
| Abstention | Accuracy at 60% coverage vs at 100% | The coverage–accuracy curve rises monotonically. This is the headline figure. |
| Calibration | ECE on dev | Reported before and after temperature scaling |
| Claim matching | Success@10, MRR | Beats BM25 per language |
| Evidence retrieval | Recall@{1,5,10}, MRR | Dense beats BM25, or the failure is reported as a finding |
| Claim span | Token F1 on X-CLAIM | Beats `whole_post_span` per language |
| Explanations | NLI entailment rate vs retrieved evidence | Reported; unfaithful explanations fall back to template |
| **Research** | **Romanization gap** | Native vs romanized score for every stage that has both, with the stage where the gap is largest named |

No absolute target is set for any model metric. Targets set before seeing the data become things to tune toward, which is exactly what the harness exists to prevent.

## 7. Release plan

| Milestone | Day | Definition of done |
| --- | --- | --- |
| M1 Vertical slice | 1 | English claim in → verdict + sources out via `POST /verify`, numbers in `results/` |
| M2 Language layer | 2–3 | Native vs romanized table exists for retrieval |
| M3 Front of pipeline | 4 | NotAClaim short-circuit and claim extraction wired in |
| M4 Claim matching | 5–6 | Fast path live. If MultiClaim isn't approved by Day 5, swap with M5 |
| M5 Evidence + stance | 7–8 | Hybrid retrieval and stance model wired in |
| M6 Verdict + generation | 9–11 | Calibrated verdicts, abstention curve, grounded explanations |
| M7 Demo + report | 12–14 | **Code freeze end of Day 12.** Days 13–14 writing and demo polish only |

## 8. Dependencies and risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| MultiClaim approval delayed | P0 claim matching blocked | Request filed. M4 and M5 swap order if not approved by Day 5 |
| AVeriTeC knowledge store size | Phase 1 evidence blocked | Subset to the claims in dev + train; size checked before download |
| IndicXlit install on Windows / Python 3.11 | Transliteration blocked | Day 2 install spike first; rule-based fallback defined in `SYSTEM_DESIGN.md` |
| 6 GB VRAM | Larger models don't fit | Base-size models, LoRA, fp16, one training job at a time |
| Agent-written code nobody can explain | Viva failure | Read every diff; the project log records every decision and why |
| 14 days is tight | Scope slips | Cut list adopted from Day 1; cut further without guilt |

## 9. Open questions

- Which Wikipedia slice forms the demo evidence corpus for claims outside AVeriTeC? Proposed in `SYSTEM_DESIGN.md` §7; confirm on Day 5.
- Does the course rubric weight the seq2seq + attention architecture itself, or the quality of the output? Decides whether a prompted-LLM comparison is worth the Day 9–11 slack.
