"""The demo page, checked without a browser (FR-23, NFR-12, UI_UX.md §7-§9).

CI has no browser, so these are the properties of the static files that can be
proven by reading them: WCAG AA contrast for every text/background token pair
in light AND dark, every string the script asks for exists in every locale, and
no confidence cut point is hard-coded in JavaScript.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

STATIC = Path("app/static")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
JS = (STATIC / "app.js").read_text(encoding="utf-8")

# Every pair the stylesheet actually puts text on. A new pair in styles.css
# belongs here too -- that is the point of listing them.
PAIRS = [
    ("text", "app-bg"), ("text", "bubble-in"), ("text", "bubble-out"),
    ("text", "abstained-bg"), ("text", "mark-bg"),
    ("muted", "app-bg"), ("muted", "bubble-in"), ("muted", "bubble-out"),
    ("muted", "abstained-bg"),
    ("bar-fg", "bar-bg"),
    ("link", "bubble-in"), ("link", "abstained-bg"),
    ("err", "app-bg"), ("err", "bubble-in"),
    ("supported-fg", "supported-bg"), ("refuted-fg", "refuted-bg"),
    ("conflicting-fg", "conflicting-bg"), ("nei-fg", "nei-bg"),
    ("conflicting-fg", "bubble-in"), ("conflicting-fg", "abstained-bg"),
    ("abstained-fg", "abstained-bg"),
    ("chip-fg", "chip-bg"),
]


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _themes() -> dict[str, dict[str, str]]:
    light = CSS.split("@media (prefers-color-scheme: dark)")[0]
    dark = CSS.split("@media (prefers-color-scheme: dark)")[1].split("\n}\n")[0]
    base = _tokens(light)
    return {"light": base, "dark": {**base, **_tokens(dark)}}


def _luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_helper_matches_the_wcag_reference_points():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("fg, bg", PAIRS)
def test_every_text_pair_meets_wcag_aa(theme, fg, bg):
    tokens = _themes()[theme]
    ratio = contrast(tokens[fg], tokens[bg])
    assert ratio >= 4.5, f"{theme}: --{fg} on --{bg} is {ratio:.2f}:1, below AA 4.5:1"


def test_dark_mode_redefines_every_colour():
    themes = _themes()
    assert set(themes["light"]) == set(_tokens(CSS.split("@media (prefers-color-scheme: dark)")[1]
                                               .split("\n}\n")[0]))


def _locale(name: str) -> dict:
    return json.loads((STATIC / "i18n" / f"{name}.json").read_text(encoding="utf-8"))


def _leaves(d: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for k, v in d.items():
        if k.startswith("_"):
            continue
        out |= _leaves(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


@pytest.mark.parametrize("locale", ["hi", "pa"])
def test_every_locale_has_every_english_key(locale):
    assert _leaves(_locale(locale)) == _leaves(_locale("en"))


@pytest.mark.parametrize("locale", ["hi", "pa"])
def test_unreviewed_locales_still_say_so(locale):
    """UI_UX.md §6: until a native speaker has reviewed them, the files say so."""
    comment = _locale(locale).get("_comment", "")
    assert "UNVERIFIED" in comment or "reviewed by" in comment.lower()


def test_every_string_the_script_asks_for_exists():
    keys = set(re.findall(r'\bt\("([\w.]+)"', JS))
    missing = sorted(keys - _leaves(_locale("en")))
    assert not missing, f"app.js asks for strings en.json does not have: {missing}"


def test_no_confidence_cut_point_is_hard_coded():
    """UI_UX.md §7: the bands come from /version, never from the script."""
    assert not re.search(r"(high|medium)\s*:\s*0?\.\d", JS)


def test_samples_cover_the_six_demo_paths():
    samples = json.loads((STATIC / "samples.json").read_text(encoding="utf-8"))
    chips = samples["chips"]
    assert len(chips) == 6
    assert {c["shows"] for c in chips} == {
        "fast_path", "romanized_hindi", "gurmukhi", "claim_extraction",
        "not_a_claim", "abstained"}
    assert all(c["text"].strip() for c in chips)
