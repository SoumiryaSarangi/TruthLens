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
    ("paper-ink", "chip-bg"), ("paper-muted", "chip-bg"),
    ("bar-fg", "rail-a"), ("bar-fg", "rail-b"), ("bar-fg", "rail-c"),     # the rail's CSS gradient, light and dark
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
    keys |= set(re.findall(r'\btl\([^,()]+,\s*"([\w.]+)"', JS))      # tl(lang, "plain.listen")
    missing = sorted(keys - _leaves(_locale("en")))
    assert not missing, f"app.js asks for strings en.json does not have: {missing}"


# -- the plain card (docs/specs/UI_UX.md section 5) ---------------------------------------

VERDICTS = ["Refuted", "Supported", "Conflicting", "NEI"]


def _plain_keys() -> set[str]:
    """Every plain.* string the card can ask for: its families are built from the verdict
    (and a few fixed cases), so a typo would otherwise show a bare key to a reader."""
    keys = {f"plain.title.{v}" for v in VERDICTS} | {"plain.title.abstained"}
    keys |= {f"plain.fast_title.{v}" for v in VERDICTS}
    keys |= {"plain.reason.fast", "plain.reason.abstained_Supported", "plain.reason.abstained_Refuted",
             "plain.reason.abstained_other", "plain.reason.live_none", "plain.reason.live_Supported",
             "plain.reason.live_Refuted"} | {f"plain.reason.{v}" for v in VERDICTS}
    keys |= {"plain.action.Refuted", "plain.action.Supported", "plain.action.check"}
    keys |= {f"plain.sure.{b}" for b in ("High", "Medium", "Low")}
    keys |= {f"plain.reply.{k}" for k in ("Refuted", "Supported", "check", "source", "similar")}
    keys |= {"plain.title.similar", "plain.similar.reason", "plain.similar.action", "plain.similar.label"}
    keys |= {"plain.title.careful", "plain.reason.careful", "icon.careful"}
    keys |= {"plain.similar.reason_unrated", "plain.reply.similar_unrated", "plain.reason.careful_live",
             "plain.greeting_title", "plain.greeting_note"}
    keys |= {"plain.why.label", "plain.why.english", "plain.reason.sources_disagree"}
    keys |= {f"plain.words.{k}" for k in ("button", "title", "hint", "note_english", "source", "none", "unavailable", "loading")}
    keys |= {f"plain.similar.rating.{v}" for v in VERDICTS} | {"icon.similar"}
    keys |= {f"plain.{k}" for k in ("none_title", "none_note", "claim_label", "sources_label", "closest_label",
                                    "found_label", "listen", "listen_stop", "listen_none", "copy", "copied",
                                    "copy_failed", "details", "flags", "check_anyway", "no_exact",
                                    "related_label", "try_online")}
    return keys


@pytest.mark.parametrize("locale", ["en", "hi", "pa"])
def test_every_plain_card_string_exists_in_every_language(locale):
    missing = sorted(_plain_keys() - _leaves(_locale(locale)))
    assert not missing, f"{locale}.json lacks plain-card strings: {missing}"


@pytest.mark.parametrize("locale", ["en", "hi", "pa"])
def test_every_persuasion_technique_has_a_plain_phrase(locale):
    assert set(_locale("en")["technique"]) == set(_locale(locale)["plain"]["technique"])


@pytest.mark.parametrize("locale", ["hi", "pa"])
def test_plain_strings_keep_their_placeholders(locale):
    def flat(d, prefix=""):
        for k, v in d.items():
            if not k.startswith("_"):
                yield from flat(v, f"{prefix}{k}.") if isinstance(v, dict) else [(prefix + k, v)]

    en, other = dict(flat(_locale("en"))), dict(flat(_locale(locale)))
    for key, text in en.items():
        assert sorted(re.findall(r"\{\w+\}", text)) == sorted(re.findall(r"\{\w+\}", other[key])), key


def test_the_main_card_has_no_technical_words_in_its_fixed_english_strings():
    """What a grandparent reads first. The technical words belong in Details."""
    plain = json.dumps(_locale("en")["plain"]).lower()
    for word in ("contradict", "calibrat", "stance", "confidence", "model", "nli", "band", "explanation"):
        assert not re.search(rf"{word}", plain), f"jargon {word!r} in the plain card strings"   # : "online" is fine


def test_the_examples_fold_exists_and_there_are_no_language_buttons():
    """The owner did not want a language switch on the page: the page follows the browser's language
    (or ?lang=), and each answer follows its message's own script."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<details class="examples">' in html
    assert "data-lang" not in html and "langs" not in html


def test_the_action_buttons_are_not_tiny():
    """Listen and Copy a reply stay comfortably pressable (at least 2 rem, about 32 px)."""
    block = re.search(r"\.act\s*\{[^}]*min-height:\s*([\d.]+)rem", CSS)
    assert block and float(block.group(1)) >= 2.0


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



# -- the responsive proof desk and the living rail (docs/specs/UI_UX.md, 2026-10-12) -------------------------------------------------

HTML = (STATIC / "index.html").read_text(encoding="utf-8")


def test_one_design_at_every_width_the_whatsapp_world_is_retired():
    """Narrowing a window used to drop the page into a WhatsApp-styled column. The base rules are the phone, and min-width tiers layer the rest."""
    for token in ("#075e54", "#efeae2", "#d9fdd3", "phone-teal", "max-width: 440px", "max-width: 460px"):
        assert token not in CSS, f"the retired WhatsApp layout is back: {token}"
    for width in ("760px", "1100px", "1360px"):
        assert f"@media (min-width: {width})" in CSS
    assert not re.search(r"@media \(max-width: (?!759)", CSS.replace("@media (max-width: 759.98px)", ""))    # mobile-first: no desktop-first cuts


def test_there_are_no_per_width_colour_overrides_so_the_pair_tests_cover_every_width():
    """The desktop token overrides used to sit after the first light/dark pair and escaped tests/test_ui_static.py; colours now live only in those two blocks."""
    outside = CSS.split("/* ------------------------------------------------------------------ base */")[1]
    outside = re.sub(r"@media \(prefers-contrast: more\) \{.*?\n\}\n", "", outside, flags=re.S)    # the high-contrast preference may set its own line colours
    assert not re.search(r"--[\w-]+:\s*#[0-9a-fA-F]{6}", outside), "a colour token is defined outside the first light and dark blocks"


def test_the_head_serves_a_phone_a_favicon_a_manifest_and_a_theme_colour():
    assert "viewport-fit=cover" in HTML and "interactive-widget=resizes-content" in HTML
    assert HTML.count('name="theme-color"') == 2 and 'prefers-color-scheme: dark' in HTML
    for href in ("/static/favicon.svg", "/static/favicon.ico", "/static/apple-touch-icon.png", "/static/manifest.webmanifest"):
        assert f'href="{href}"' in HTML, href
        assert (STATIC / href.removeprefix("/static/")).is_file(), href


def test_the_icons_and_the_manifest_are_real_files_of_the_right_size():
    from PIL import Image

    assert Image.open(STATIC / "apple-touch-icon.png").size == (180, 180)
    assert Image.open(STATIC / "icon-192.png").size == (192, 192) and Image.open(STATIC / "icon-512.png").size == (512, 512)
    assert {s for s in Image.open(STATIC / "favicon.ico").info.get("sizes", set())} >= {(16, 16), (32, 32), (48, 48)}
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "TruthLens" and manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        assert (STATIC / icon["src"].removeprefix("/static/")).is_file(), icon["src"]


def test_the_shader_is_local_motion_gated_and_never_fetches_anything():
    src = Path("ui-src/rail-shader.jsx").read_text(encoding="utf-8")
    assert 'lightType="3d"' in src and 'control="props"' in src          # "env" lights fetch HDR files from a third-party host; "query" ignores props
    bundle = STATIC / "vendor" / "rail-shader.js"
    assert bundle.is_file() and bundle.stat().st_size > 100_000
    mount = JS[JS.index("The living rail"):JS.index("function scheduleRailShader")]
    assert "http://" not in mount and "https://" not in mount and 'import("/static/vendor/rail-shader.js")' in mount
    for guard in ("prefers-reduced-motion: no-preference", "prefers-contrast: more", "forced-colors: active", "min-width: 760px", "webglAvailable()"):
        assert guard in mount, guard
    assert "requestIdleCallback" in JS                                      # after first paint, never blocking typing
    assert "rail-drift" in CSS and ".rail-bg:not(.live)::before { animation" in CSS
    assert ".rail-shader::after" in CSS                                     # the legibility scrim measured in UI_UX.md
    assert 'frameloop="demand"' in src and "FPS" in src and "setBusy" in src          # throttled: on a real GPU the unthrottled canvas slowed answers 2.4x
    assert "railHandle.setBusy" in JS and JS.count("checking(true)") >= 3 and JS.count("checking(false)") >= 3


def test_the_rail_keeps_a_flat_colour_for_high_contrast_and_forced_colours():
    assert re.search(r"prefers-contrast: more\)[^@]*\.rail-bg \{ background: var\(--rail-a\); \}", CSS, re.S)
    assert re.search(r"forced-colors: active\)[^@]*\.rail-shader \{ display: none; \}", CSS, re.S)


def test_the_audit_fixes_are_in():
    assert "scroll-padding-top: 4.75rem" in CSS and "padding: 4.75rem 2rem 3rem" in CSS            # the corner link never overlaps the first answer
    assert ".scope-pop:popover-open { display: block; opacity: 1; transform: none; }" in CSS and "@starting-style" in CSS
    at = CSS.index(".chat { scroll-behavior: smooth; }")
    assert "prefers-reduced-motion: no-preference" in CSS[CSS.rindex("@media", 0, at):at]                  # smooth scroll, gated by reduced motion
    assert 'id="announce"' in HTML and 'role="status"' in HTML and "announce.textContent" in JS     # the copy confirmation is announced
    assert "ease-out .1" not in CSS and "ease-out .2" not in CSS                                    # entrances use the one token, not the keyword
    assert "previousElementSibling" in JS                                                           # the forward and its answer scroll in as one unit
