# Third-party notices

TruthLens is MIT-licensed (`LICENSE`). It downloads and uses the models and datasets below, which are **not** covered by
that licence and keep their own. This file lists what the project uses. **A licence is stated here only where it was read
from the material itself on the development machine; everything else says "not verified here" and must be confirmed on
the model or dataset page before any redistribution or commercial use.**

## Models (downloaded from Hugging Face on first use; never committed)

| Model | Used for | Licence |
| --- | --- | --- |
| `BAAI/bge-m3` | claim matching and evidence retrieval; relevance in the live check | MIT (read from the cached model card) |
| `sentence-transformers/LaBSE` | bitext alignment and the t-SNE plot only | Apache-2.0 (read from the cached model card) |
| `google/muril-base-cased` | baseline encoder in span experiments | Apache-2.0 (read from the cached model card) |
| `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | live check: first of two NLI models; the polarity guard | not verified here |
| `facebook/bart-large-mnli` | live check: second NLI model that must agree | not verified here |
| `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | offline multilingual stance | not verified here |
| `facebook/nllb-200-distilled-600M` | claim translation to English for the live check | not verified here. The NLLB-200 family is, to the author's knowledge, published under a **non-commercial** licence (CC BY-NC); treat it as non-commercial until confirmed on the model page |
| `ai4bharat/IndicBART` | explanation generation | not verified here |
| `xlm-roberta-base` | token-classification baselines | not verified here |

## Datasets (downloaded locally; raw text is git-ignored and never redistributed)

| Dataset | Used for | Terms |
| --- | --- | --- |
| AVeriTeC | verdict training and evaluation (the verification backbone) | **CC BY-NC 4.0: non-commercial, academic use** (stated in `data/CLAUDE.md`) |
| MultiClaim / SemEval-2025 Task 7 | claim matching | **access-restricted; not redistributable**; supplied by request, kept in git-ignored `data/raw/` |
| X-CLAIM | claim span detection in EN/HI/PA | not verified here; see its repository and `data/CLAUDE.md`; not redistributed |
| CheckThat! 2025 Task 2 | claim normalization | not verified here; see `data/CLAUDE.md` |
| Hindi and Punjabi Wikipedia (dumps pinned to 2026-09-01) | the demo evidence corpus only | CC BY-SA 4.0 (stated in `data/CLAUDE.md`); every passage shown carries its article URL |
| Dakshina | transliteration lexicon | not verified here; see the dataset page |
| FEVER | live-check validation | not verified here; see the dataset page |

**Consequence for anyone reusing the models or measurements:** the verdict components were trained and evaluated on AVeriTeC,
which is non-commercial. Treat the trained artifacts as non-commercial unless you have checked that this does not apply.

`data/CLAUDE.md` is the authoritative provenance record for each dataset.

## Live sources

- **Wikipedia** text shown in a live card is available under CC BY-SA 4.0. The card keeps its link to the page.
- **Google Fact Check Tools API**: used under its terms with a user-supplied key. Fact-check headlines and ratings are shown
  as the publisher's own, with attribution and a link.

## Software

Python dependencies are pinned in `requirements*.txt` (hash-locked) and keep their own licences. The only built front-end
file, `app/static/vendor/rail-shader.js`, bundles these npm packages (see `package.json` and `package-lock.json`):

| Package | Licence |
| --- | --- |
| `@shadergradient/react` | MIT (stated in its package metadata) |
| `@react-three/fiber`, `three`, `react`, `react-dom` | MIT; see each package's own `LICENSE` in `node_modules/` |
| `esbuild` (build only) | MIT; see its package |

The favicon and home-screen icons were authored in this repository from the brand mark in `app/static/index.html`; no
third-party artwork is used.
