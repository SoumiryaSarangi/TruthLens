/* TruthLens demo page. Vanilla JS, no framework, no build step (UI_UX.md §2).
 *
 * It calls POST /verify and renders the JSON. It never recomputes anything:
 * the verdict, the stances, the highlight spans and the confidence all come
 * from the response, because a browser deriving its own numbers is how a demo
 * starts disagreeing with the evaluation.
 */

const $ = (id) => document.getElementById(id);

let S = {};             // strings for the interface language
let STR = {};           // all three string tables, so a card can speak its OWN language
let UI_LANG = "en";   // the page language: the browser's, or ?lang=hi|pa for a demo
let ANSWER_LANG = null; // never set by the page: it is a hook for tests. The answer follows the message.
const LANGS = ["en", "hi", "pa"];
const SPEECH = { en: "en-IN", hi: "hi-IN", pa: "pa-IN" };
let BANDS = null;       // from /version; no bands -> no band shown, never a guess
let WORDS = false;      // from /version: is the on-demand "which words mattered" view enabled?
let LIVE = false;       // from /version: may this server search Wikipedia / Google live?
let lastText = "";
let cardSeq = 0;

const MAX_CHARS = 4000;  // FR-1, mirrored from the API so the error is instant

/* ----------------------------------------------------------------- icons
 * Drawn once, one stroke weight (UI_UX.md §6: every verdict has an icon AND a word). Decorative: each is
 * aria-hidden and the word beside it carries the meaning, so the glyph strings in i18n are not used for the
 * plain card. */
const ICONS = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  conflict: '<path d="M4 8h13m-3-3 3 3-3 3M20 16H7m3-3-3 3 3 3"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1.1.9-1.1 1.7M12 17h.01"/>',
  abstained: '<circle cx="12" cy="12" r="8.5" stroke-dasharray="3 3"/>',
  alert: '<path d="M12 4 3 19h18L12 4z"/><path d="M12 10v4M12 17h.01"/>',
  similar: '<path d="M5 9c2-2 4-2 7 0s5 2 7 0M5 15c2-2 4-2 7 0s5 2 7 0"/>',
  chat: '<path d="M5 6h14v9h-8.5L7 18v-3H5z"/>',
  speaker: '<path d="M4 10v4h3l5 4V6L7 10H4z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
  copy: '<rect x="9" y="9" width="10" height="10" rx="2"/><path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4-4"/>',
  warn: '<path d="M12 4 3 19h18L12 4z"/><path d="M12 10v4M12 17h.01"/>',
};

function ico(name) {
  return `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] || ""}</svg>`;
}

/* The icon of a plain card's banner, from the same facts that choose its title. */
function bannerIcon(c, sim) {
  if (showsSim(c, sim)) return "similar";
  if (isCareful(c)) return "alert";
  if (c.kind === "abstained" || c.kind === "lean") return "abstained";
  return { Supported: "check", Refuted: "x", Conflicting: "conflict" }[c.v] || "help";
}

/* ---------------------------------------------------------------- strings */

async function loadStrings(lang) {
  for (const candidate of [lang, "en"]) {
    try {
      const r = await fetch(`/static/i18n/${candidate}.json`);
      if (r.ok) return await r.json();
    } catch (e) { /* fall through to the next candidate */ }
  }
  return {};
}

function lookup(table, key) {
  const v = key.split(".").reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), table);
  return typeof v === "string" ? v : undefined;
}

function fill(s, vars) {
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : `{${k}}`));
}

/* t("unchecked", {n: 2}) -> the string with {n} filled in, or the fallback. */
function t(key, vars = {}, fallback = "") {
  const s = lookup(S, key);
  return fill(s === undefined ? (fallback || key) : s, vars);
}

/* tl(lang, key): the same, in a given language (a card's own), falling back to the
 * interface language and then English, so a missing string never shows a bare key. */
function tl(lang, key, vars = {}) {
  for (const table of [STR[lang], S, STR.en]) {
    const s = table && lookup(table, key);
    if (s !== undefined) return fill(s, vars);
  }
  return key;
}

/* The language a card answers in: it follows the SCRIPT of the message: Hindi or Punjabi written in Devanagari or Gurmukhi
 * is answered in Hindi or Punjabi, but Hindi or Punjabi typed in Latin letters ("Kal se WhatsApp
 * ke paise lagenge") is answered in English: the sender chose Latin letters, and English is what
 * they can read in that script. English is answered in English. */
function cardLang(inp) {
  if (ANSWER_LANG) return ANSWER_LANG;
  const lang = inp && inp.lang;
  if (lang === "hi" || lang === "pa") return inp.script === "latn" ? "en" : lang;
  return lang === "en" ? "en" : UI_LANG;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function applyStaticStrings() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n, {}, el.textContent);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder, {}, el.placeholder);
  });
  $("send").setAttribute("aria-label", t("send", {}, "Send"));
}

/* ------------------------------------------------------------------- boot */

async function boot() {
  // ?lang=hi|pa forces the interface language for a demo; otherwise the browser's.
  const forced = new URLSearchParams(location.search).get("lang");
  const wanted = forced || (navigator.language || "en").slice(0, 2);
  UI_LANG = LANGS.includes(wanted) ? wanted : "en";
  for (const l of LANGS) STR[l] = await loadStrings(l);
  S = STR[UI_LANG];
  document.documentElement.lang = S._lang || "en";
  applyStaticStrings();

  fetch("/health").then((r) => r.json()).then((h) => {
    const ok = h.status === "ok";
    $("health").className = `health ${ok ? "ok" : "degraded"}`;
    $("health-text").dataset.key = ok ? "models_ready" : "degraded";
    $("health-text").textContent = t(ok ? "models_ready" : "degraded");
  }).catch(() => {
    $("health").className = "health down";
    $("health-text").dataset.key = "unreachable";
    $("health-text").textContent = t("unreachable");
  });

  /* UI_UX.md §7: the band cut points come from /version and are never
   * hard-coded here. Without them the card shows no band rather than one
   * computed from stale numbers. */
  fetch("/version").then((r) => r.json())
    .then((v) => {
      if (v.confidence_bands) BANDS = v.confidence_bands;
      LIVE = Boolean(v.config && v.config.live_search);
      WORDS = Boolean(v.config && v.config.word_view);
    })
    .catch(() => {});

  fetch("/static/samples.json").then((r) => r.json()).then(renderChips).catch(() => {});
}

function renderChips(samples) {
  const box = $("chips");
  for (const s of samples.chips || []) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "sample";
    b.textContent = s.label;
    b.title = s.shows || "";
    // UI_UX.md §3: a chip FILLS the composer; the presenter still presses send.
    b.addEventListener("click", () => { $("text").value = s.text; $("text").focus(); });
    box.appendChild(b);
  }
}

/* ------------------------------------------------------------------- send */

function showComposerError(msg) {
  const el = $("composer-error");
  el.textContent = msg;
  el.hidden = !msg;
}

function bubble(cls, html) {
  const div = document.createElement("div");
  div.className = `bubble ${cls}`;
  div.innerHTML = html;
  const intro = $("intro");
  if (intro) intro.remove();
  $("chat").appendChild(div);
  div.scrollIntoView({ block: "end" });
  return div;
}

async function send(text, { echo = true } = {}) {
  showComposerError("");
  if (!text.trim()) { showComposerError(t("empty")); return; }
  if (text.length > MAX_CHARS) { showComposerError(t("too_long")); return; }

  lastText = text;
  if (echo) {
    bubble("out", `<div class="fwd">↪ ${esc(t("forwarded"))}</div><div class="body">${esc(text)}</div>`);
    $("text").value = "";
  }
  const pending = bubble("in",
    `<span class="checking"><span class="spinner" aria-hidden="true"></span>${esc(t("checking"))}</span>`);
  $("send").disabled = true;

  let res, body;
  try {
    res = await fetch("/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, include_trace: true }),
    });
    body = await res.json().catch(() => ({}));
  } catch (e) {
    res = null;
  } finally {
    $("send").disabled = false;
  }

  if (res && res.status === 422) {
    // UI_UX.md §4: validation errors go under the composer, not into the chat.
    pending.remove();
    showComposerError(text.length > MAX_CHARS ? t("too_long") : t("empty"));
    return;
  }
  if (!res || !res.ok) {
    pending.className = "bubble in error";
    pending.innerHTML = `<p>${esc(t("error_server"))}</p>
      <button type="button" class="retry">${esc(t("retry"))}</button>`;
    pending.querySelector(".retry").addEventListener("click", () => {
      pending.remove();
      send(lastText, { echo: false });
    });
    return;
  }
  pending._state = { body, live: {} };
  renderBubble(pending);
  pending.scrollIntoView({ block: "start" });
}

/* ----------------------------------------------------------------- render */

function bandOf(confidence) {
  if (!BANDS) return null;
  if (confidence >= BANDS.high) return "High";
  if (confidence >= BANDS.medium) return "Medium";
  return "Low";
}

function langName(code) { return t(`lang_name.${code}`, {}, code); }
function scriptName(code) { return t(`script_name.${code}`, {}, code); }

function inputNote(inp, explanationLang) {
  const parts = [];
  if (inp.transliterated) {
    const target = inp.lang === "pa" ? "guru" : "deva";
    parts.push(t("input_translit", { lang: langName(inp.lang), script: scriptName(target) }));
  } else if (inp.lang && inp.lang !== "other") {
    parts.push(t("input_detected", { lang: langName(inp.lang), script: scriptName(inp.script) }));
  }
  // FR-17 is cut to English explanations (cut-list item 3); UI_UX.md §8 says
  // the card must say so rather than leave a Hindi reader to wonder.
  if (inp.lang && inp.lang !== "en" && inp.lang !== "other" && explanationLang === "en") {
    parts.push(t("explanation_fallback", { lang: langName(inp.lang) }));
  }
  return parts.map((p) => `<p class="note">${esc(p)}</p>`).join("");
}

function domainOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return ""; }
}

/* The passage with its `highlight` span marked; a long passage is cut to a
 * window around the highlight, never re-scored. */
function passageHtml(p) {
  const text = p.text || "";
  const h = Array.isArray(p.highlight) ? p.highlight : null;
  const WINDOW = 420;
  if (!h || h[1] <= h[0]) {
    return esc(text.length > WINDOW ? text.slice(0, WINDOW) + "…" : text);
  }
  const start = Math.max(0, h[0] - 120);
  const end = Math.min(text.length, Math.max(h[1] + 120, start + WINDOW));
  return (start > 0 ? "…" : "") + esc(text.slice(start, h[0]))
    + `<mark>${esc(text.slice(h[0], h[1]))}</mark>`
    + esc(text.slice(h[1], end)) + (end < text.length ? "…" : "");
}

function explanationHtml(text, cardId, nPassages) {
  // `[n]` markers become buttons that open the trail and jump to row n.
  return esc(text).replace(/\[(\d+)\]/g, (m, n) => {
    const i = Number(n);
    if (i < 1 || i > nPassages) return m;
    return `<button type="button" class="cite" data-target="${cardId}-ev-${i}"
      aria-label="${esc(t("cite_aria", { n: i }))}">[${i}]</button>`;
  });
}

/* ------------------------------------------------------- the plain card
 *
 * What an ordinary reader sees (docs/specs/UI_UX.md §5): one plain verdict in their
 * language, one sentence of why, what to do, where it comes from, and two buttons.
 * Everything technical stays one tap away in "Details". It is built from fields the
 * API already returns; nothing is recomputed here, so no number can disagree with
 * the evaluation. The wording says "probably" and "the sources I found": it reports
 * what the sources say, never the truth.
 */

function plainCase(r) {
  if (r.verdict === "NotAClaim") return { kind: "none" };
  const live = (r.live_sources || []).length > 0;
  if (r.path === "fast" && r.match && !r.abstained) return { kind: "fast", v: r.verdict, live };
  if (r.abstained) return { kind: "abstained", v: r.verdict, live, careful: !!r._careful, conflict: !!r.sources_disagree };
  // The offline evidence path is NOT presented as an answer. On free text it says "Refuted" to almost
  // everything (122 of 125 TRUE claims in the pre-registered test; Paris is the capital of France too),
  // because it mostly reflects "forwarded claims are usually false". A verdict is shown only when it is
  // earned: a matched published fact-check (fast) or a live check that passed its test.
  if (!live) return { kind: "lean", v: r.verdict, live, forced: !!r._forced };
  return { kind: "verdict", v: r.verdict, live };
}

/* A published fact-check that scored below the fast-path bar but above tau_similar: offered to READ, never
 * believed. Shown on a guess or an abstained card, never over a live verdict. */
function similarOf(c, r) {
  return (c.kind === "lean" || c.kind === "abstained") && r.similar_match && r.similar_match.url ? r.similar_match : null;
}

function similarRating(sim, lang) {
  return sim.verdict ? tl(lang, `plain.similar.rating.${sim.verdict}`) : "";
}

/* The offline guess leaned "false" (it does for almost everything: most forwards ARE false). That is
 * not a finding about THIS message, so it is shown as a warning, not as a verdict. */
function isCareful(c) {
  // Not for a message the claim gate refused and the reader checked anyway ("Good morning"): the
  // "most messages like this are false" reasoning is about forwarded claims, not about a greeting.
  if (c.kind === "abstained") return !!(c.live && c.careful && !c.conflict);   // a live look-up that found nothing keeps the warning
  return c.kind === "lean" && c.v === "Refuted" && !c.forced;
}

/* The similar fact-check leads the card when there is no verdict of any kind: before a live look-up,
 * and after a live look-up that still could not decide (it is the best thing we have found). */
function showsSim(c, sim) {
  return !!sim && (!c.live || c.kind === "abstained");
}

function plainTitle(c, lang, sim) {
  if (showsSim(c, sim)) return tl(lang, "plain.title.similar");
  if (isCareful(c)) return tl(lang, "plain.title.careful");
  if (c.kind === "fast") return tl(lang, `plain.fast_title.${c.v}`);
  if (c.kind === "abstained" || c.kind === "lean") return tl(lang, "plain.title.abstained");
  return tl(lang, `plain.title.${c.v}`);
}

function plainReason(c, r, lang, sim) {
  if (showsSim(c, sim)) {
    // A fact-check whose rating cannot be mapped is still offered, without "rated it ...".
    return sim.verdict
      ? tl(lang, "plain.similar.reason", { publisher: sim.publisher || "", rating: similarRating(sim, lang) })
      : tl(lang, "plain.similar.reason_unrated", { publisher: sim.publisher || "" });
  }
  if (c.kind === "fast") return tl(lang, "plain.reason.fast", { publisher: r.match?.publisher || "" });
  if (isCareful(c)) return tl(lang, c.live ? "plain.reason.careful_live" : "plain.reason.careful");
  if (c.kind === "lean") return tl(lang, "plain.no_exact");
  if (c.kind === "abstained") {
    if (c.live) return tl(lang, c.conflict ? "plain.reason.sources_disagree" : "plain.reason.live_none");
    return tl(lang, c.v === "Supported" || c.v === "Refuted" ? `plain.reason.abstained_${c.v}`
      : "plain.reason.abstained_other");
  }
  if (c.live && (c.v === "Supported" || c.v === "Refuted")) return tl(lang, `plain.reason.live_${c.v}`);
  return tl(lang, `plain.reason.${c.v}`);
}

function plainAction(c, lang, sim) {
  if (showsSim(c, sim)) return tl(lang, "plain.similar.action");
  const v = c.kind === "abstained" || c.kind === "lean" ? null : c.v;
  return tl(lang, v === "Refuted" || v === "Supported" ? `plain.action.${v}` : "plain.action.check");
}

/* Up to three sources an ordinary reader can open: the matched fact-check, the cited
 * passages that point the same way as the verdict, or -- on a live card -- whatever was found. */
function plainSources(c, r) {
  const href = (p) => (p.url && /^https?:/.test(p.url) ? p.url : null);
  const row = (url, title) => ({ url, title, domain: domainOf(url) });
  if (c.kind === "fast") return r.match ? [row(r.match.url, r.match.title)] : [];
  const passages = (r.passages || []).filter((p) => href(p));
  if (c.live || c.kind === "lean") return passages.slice(0, 3).map((p) => row(href(p), p.title || p.doc_id));
  if (c.kind === "verdict" && (c.v === "Supported" || c.v === "Refuted")) {
    const want = c.v === "Supported" ? "Supports" : "Refutes";
    const cited = new Set(r.cited || []);
    return passages.filter((p) => cited.has(p.passage_id) && p.stance === want)
      .slice(0, 2).map((p) => row(href(p), p.title || p.doc_id));
  }
  return [];
}

/* "Why": for a live TRUE or FALSE answer, the sentence of the source that the answer rests on, quoted as the
 * source wrote it (extractive: nothing is generated, so nothing can be invented). The source is the passage that
 * points the same way as the verdict with the highest stance score; its sentence is the one that shares the most
 * words with the claim. A fast-path answer has no such text on file (only the fact-check's headline, which the
 * card already shows), so it gets none. Frontend only; nothing is recomputed on the server. */
const QUOTE_STOP = new Set(["the", "a", "an", "of", "in", "on", "is", "are", "was", "were", "to", "and", "or", "that", "this",
  "it", "for", "by", "with", "as", "at", "from", "be", "has", "have", "had", "than", "but", "not", "can", "will"]);
const QUOTE_MAX = 240;

function wordsOf(text) {
  return (String(text || "").toLowerCase().match(/[\p{L}\p{N}]+/gu) || []).filter((w) => !QUOTE_STOP.has(w));
}

function sourceQuote(c, r) {
  if (c.kind !== "verdict" || !c.live || (c.v !== "Supported" && c.v !== "Refuted")) return null;
  const want = c.v === "Supported" ? "Supports" : "Refutes";
  const best = (r.passages || []).filter((p) => p.premise && p.stance === want && /^https?:/.test(p.url || ""))
    .sort((a, b) => (b.stance_prob || 0) - (a.stance_prob || 0))[0];
  if (!best) return null;
  const claim = new Set(wordsOf(r.claim_en || (r.claim && r.claim.text)));
  const sentences = best.premise.split(/(?<=[.!?।])\s+/).map((s) => s.trim()).filter(Boolean);
  if (!sentences.length) return null;
  let pick = sentences[0], top = -1;
  for (const s of sentences) {
    const shared = wordsOf(s).filter((w) => claim.has(w)).length;
    if (shared > top) { top = shared; pick = s; }
  }
  if (pick.length > QUOTE_MAX) pick = pick.slice(0, QUOTE_MAX).replace(/\s+\S*$/, "") + "…";
  return { text: pick, title: best.title || domainOf(best.url), url: best.url };
}

/* The one live verdict the word view can explain: a Supported or Refuted live result and the source passage
 * that points the same way with the highest stance, read exactly as the models read it. */
function wordsSource(c, r) {
  if (!WORDS || c.kind !== "verdict" || !c.live || !r.claim_en) return null;
  if (c.v !== "Supported" && c.v !== "Refuted") return null;
  const want = c.v === "Supported" ? "Supports" : "Refutes";
  const best = (r.passages || []).filter((p) => p.premise && p.stance === want)
    .sort((a, b) => (b.stance_prob || 0) - (a.stance_prob || 0))[0];
  return best ? { claim: r.claim_en, premise: best.premise, verdict: c.v } : null;
}

/* The claim with the words that pushed the answer most marked: a mark AND a glyph, never colour alone. */
function wordsHtml(out, lang, shownText) {
  const top = new Set(out.top || []);
  let html = "";
  if (!top.size) {
    html += `<p class="reason">${esc(tl(lang, "plain.words.none"))}</p>`;
  } else {
    html += `<p class="src-label">${esc(tl(lang, "plain.words.title"))}</p><p class="words-claim">${
      (out.words || []).map((w, i) => (top.has(i)
        ? `<mark class="word-key"><span aria-hidden="true">▲</span>${esc(w.word)}</mark>` : esc(w.word))).join(" ")}</p>
      <p class="note">${esc(tl(lang, "plain.words.hint"))}</p>`;
    if (shownText && out.claim && shownText.trim() !== out.claim.trim()) {
      html += `<p class="note">${esc(tl(lang, "plain.words.note_english"))}</p>`;
    }
  }
  const marked = (out.sentences || []).find((s) => s.marked);
  if (marked) {
    html += `<p class="src-label">${esc(tl(lang, "plain.words.source"))}</p><p class="words-source">${esc(marked.text)}</p>`;
  }
  return html;
}

async function showWords(btn) {
  const lang = btn.dataset.cardLang;
  const view = btn.parentElement.querySelector(".words-view");
  if (!view) return;
  if (!view.hidden) { view.hidden = true; return; }       // a second tap folds it away
  if (view.dataset.done) { view.hidden = false; return; }
  btn.disabled = true;
  view.hidden = false;
  view.textContent = tl(lang, "plain.words.loading");
  let out = null;
  try {
    const res = await fetch("/explain_words", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim: btn.dataset.claim, premise: btn.dataset.premise, verdict: btn.dataset.verdict }),
    });
    if (res.ok) out = await res.json();
  } catch (e) { /* shown below */ }
  btn.disabled = false;
  if (!out) { view.innerHTML = `<p class="note">${esc(tl(lang, "plain.words.unavailable"))}</p>`; return; }
  view.innerHTML = wordsHtml(out, lang, btn.dataset.shown);
  view.dataset.done = "1";
}

function plainFlags(r, lang) {
  const flags = r.manipulation_flags || [];
  if (!flags.length) return "";
  const list = flags.map((f) => tl(lang, `plain.technique.${f}`)).join(", ");
  return `<p class="plain-flags">${ico("warn")}<span>${esc(tl(lang, "plain.flags", { list }))}</span></p>`;
}

function replyText(c, sources, lang, sim) {
  if (showsSim(c, sim)) {
    let text = sim.verdict ? tl(lang, "plain.reply.similar", { rating: similarRating(sim, lang) })
      : tl(lang, "plain.reply.similar_unrated");
    text += `\n${tl(lang, "plain.reply.source", { url: sim.url })}`;
    return text;
  }
  const key = c.kind === "abstained" || c.kind === "lean" ? "check" : (c.v === "Refuted" || c.v === "Supported" ? c.v : "check");
  let text = tl(lang, `plain.reply.${key}`);
  if (sources.length) text += `\n${tl(lang, "plain.reply.source", { url: sources[0].url })}`;
  return text;
}

function plainCard(r, inp, idx) {
  const lang = cardLang(inp);
  const icons = S.icon || {};
  const c = plainCase(r);

  if (c.kind === "none") {
    // The claim gate refuses short fragments ("JEE paper leaked"), so the reader can overrule it.
    const original = (inp && inp.original) || (r.claim && r.claim.text) || "";
    // A greeting has nothing to look up, so it is not offered a check (the server would refuse it anyway).
    if (r.gate_reason === "greeting") {
      return `<div class="card neutral-card plain" lang="${esc(lang)}">
      <p class="neutral-title">${ico("chat")}<span>${esc(tl(lang, "plain.greeting_title"))}</span></p>
      <p class="reason">${esc(tl(lang, "plain.greeting_note"))}</p></div>`;
    }
    return `<div class="card neutral-card plain" lang="${esc(lang)}">
      <p class="neutral-title">${ico("chat")}<span>${esc(tl(lang, "plain.none_title"))}</span></p>
      <p class="reason">${esc(tl(lang, "plain.none_note"))}</p>
      ${original ? `<div class="actions"><button type="button" class="act act-force" data-text="${esc(original)}"
        data-idx="${idx}" data-card-lang="${esc(lang)}">${esc(tl(lang, "plain.check_anyway"))}</button></div>
        <p class="note act-note" hidden></p>` : ""}</div>`;
  }

  const id = `c${++cardSeq}`;
  const bandName = bandOf(r.confidence);
  const sim = similarOf(c, r);
  const title = plainTitle(c, lang, sim);
  const chipClass = isCareful(c) ? "Conflicting" : c.kind === "abstained" || c.kind === "lean" ? "abstained" : (c.v === "Conflicting" || c.v === "NEI" || c.v === "Refuted"
    || c.v === "Supported" ? c.v : "NEI");
  const icon = bannerIcon(c, sim);
  const reason = plainReason(c, r, lang, sim);
  const action = plainAction(c, lang, sim);
  const sources = showsSim(c, sim) && c.kind === "lean" ? []
    : plainSources(c, r).filter((x) => !(showsSim(c, sim) && sim.url === x.url));   // the fact-check IS the source
  const simHtml = sim ? `<p class="src-label">${esc(tl(lang, "plain.similar.label"))}</p>
      <ul class="plain-sources"><li><a href="${esc(sim.url)}" target="_blank" rel="noopener">${esc(sim.title)}</a>${
    domainOf(sim.url) ? ` <span class="domain">· ${esc(domainOf(sim.url))}</span>` : ""}</li></ul>` : "";
  // Only an offline, calibrated verdict says how sure it is; a live one is uncalibrated and says nothing.
  const sure = c.kind === "verdict" && !c.live && bandName ? tl(lang, `plain.sure.${bandName}`) : "";
  const speak = [title, reason, sure, action].filter(Boolean).join(" ");

  let html = `<div class="card plain${c.kind === "abstained" || c.kind === "lean" ? " abstained" : ""}" id="${id}" lang="${esc(lang)}">
    <p class="plain-head"><span class="chip big ${esc(chipClass)}" role="img"
      aria-label="${esc(t("verdict_aria", { label: title }))}"><span aria-hidden="true">${ico(icon)}</span><span>${esc(title)}</span></span></p>
    <p class="reason">${esc(reason)}${sure ? ` <span class="sure">${esc(sure)}</span>` : ""}</p>
    <p class="action">${esc(action)}</p>`;
  const quote = sourceQuote(c, r);
  if (quote) {
    html += `<p class="src-label">${esc(tl(lang, "plain.why.label"))}</p>
      <blockquote class="why-quote" lang="en">“${esc(quote.text)}”
        <cite><a href="${esc(quote.url)}" target="_blank" rel="noopener">${esc(quote.title)}</a> <span class="domain">· ${
    esc(domainOf(quote.url))}</span></cite></blockquote>${lang !== "en" ? `<p class="note">${esc(tl(lang, "plain.why.english"))}</p>` : ""}`;
  }
  html += simHtml;
  if (sources.length) {
    html += `<p class="src-label">${esc(tl(lang, c.kind === "lean" ? "plain.related_label"
        : (c.live || c.kind === "abstained" ? "plain.found_label"
          : (c.kind === "fast" ? "plain.sources_label" : "plain.closest_label"))))}</p>
      <ul class="plain-sources">${sources.map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>${
        x.domain ? ` <span class="domain">· ${esc(x.domain)}</span>` : ""}</li>`).join("")}</ul>`;
  }
  html += plainFlags(r, lang);
  if (r.claim && r.claim.text) {
    html += `<p class="claim-line">${esc(tl(lang, "plain.claim_label"))} “${esc(r.claim.text)}”</p>`;
  }
  html += `<div class="actions">
      <button type="button" class="act act-listen" data-speak="${esc(speak)}" data-card-lang="${esc(lang)}"
        aria-label="${esc(tl(lang, "plain.listen"))}">${ico("speaker")}${esc(tl(lang, "plain.listen"))}</button>
      <button type="button" class="act act-copy" data-reply="${esc(replyText(c, sources, lang, sim))}" data-card-lang="${esc(lang)}"
        aria-label="${esc(tl(lang, "plain.copy"))}">${ico("copy")}${esc(tl(lang, "plain.copy"))}</button>
    </div><p class="note act-note" hidden></p>`;

  const ws = wordsSource(c, r);
  if (ws) {
    html += `<div class="words-box"><button type="button" class="act words-btn" data-card-lang="${esc(lang)}"
      data-claim="${esc(ws.claim)}" data-premise="${esc(ws.premise)}" data-verdict="${esc(ws.verdict)}"
      data-shown="${esc((r.claim && r.claim.text) || "")}">${ico("search")}${esc(tl(lang, "plain.words.button"))}</button>
      <div class="words-view" hidden></div></div>`;
  }

  // Looking it up online: explicit, per claim, and it says exactly what it sends.
  const liveUsed = c.live;
  if (!liveUsed && LIVE && r.path !== "fast" && r.claim?.text
      && (c.kind === "lean" || r.abstained || bandName !== "High")) {
    if (c.kind === "lean") html += `<p class="action">${esc(tl(lang, "plain.try_online"))}</p>`;
    html += `<button type="button" class="live-btn" data-card="${id}" data-claim="${esc(r.claim.text)}" data-idx="${idx}"${r._forced ? ' data-forced="1"' : ""}>
      ${ico("globe")}${esc(tl(lang, "live_button"))}</button>
      <p class="note live-privacy">${esc(tl(lang, "live_privacy"))}</p>`;
  }
  html += `<p class="disclaimer">${esc(tl(lang, "disclaimer"))}</p>`;
  html += `<details class="more"><summary>${esc(tl(lang, "plain.details"))}</summary>${technicalCard(r, inp, id, c.kind === "lean")}</details></div>`;
  return html;
}

function verdictCard(r, inp, idx = 0) {
  return plainCard(r, inp, idx);
}

/* The full technical card (verdict class, confidence band, explanation, evidence trail,
 * live notes, input note), inside "Details". It is the card the project measured. */
function technicalCard(r, inp, cardId, lean = false) {
  const id = cardId;
  const label = t(`verdict.${r.verdict}`, {}, r.verdict);
  const icons = S.icon || {};

  const liveUsed = (r.live_sources || []).length > 0;
  const bandName = bandOf(r.confidence);
  let head;
  if (r.abstained) {
    // UI_UX.md §6: abstained is not NEI. The would-be verdict is shown small
    // and greyed -- the system has an opinion and chose not to commit to it.
    const a = t("abstained_label");
    head = `<span class="chip abstained" role="img" aria-label="${esc(t("verdict_aria", { label: a }))}">
        <span aria-hidden="true">${esc(icons.abstained || "◌")}</span>${esc(a)}</span>`;
  } else {
    head = `<span class="chip ${esc(r.verdict)}" role="img" aria-label="${esc(t("verdict_aria", { label }))}">
        <span aria-hidden="true">${esc(icons[r.verdict] || "")}</span>${esc(label)}</span>`;
    const band = liveUsed ? null : bandName;     // live confidence is uncalibrated: no band
    if (band) {
      // A band, not a percentage (UI_UX.md §7); the exact value is one hover away.
      head += `<span class="band" data-band="${esc(band)}" tabindex="0"
        title="${esc(t("band_title", { value: Number(r.confidence).toFixed(2) }))}">
        ${esc(t(`band.${band}`, {}, band))}</span>`;
    }
  }

  let html = `<div class="technical">${lean ? `<p class="note lean">${esc(t("lean_note", { label }))}</p>` : ""}<div class="card-head">${head}</div>`;
  if (r.abstained) {
    html += `<p class="leaning">${esc(t("leaning", { label }))}</p>`;
  }
  html += `<p class="claim">${esc(t("claim"))}: “${esc(r.claim?.text)}”</p>`;

  const fast = r.path === "fast";
  if (r.path !== "none") {
    html += `<p class="path"><span aria-hidden="true">${fast ? "📰" : "🔎"}</span> ${esc(fast
      ? t("path_factcheck", { publisher: r.match?.publisher || "" })
      : t("path_evidence"))}</p>`;
  }

  const n = (r.passages || []).length;
  // A fast-path card IS the publisher's fact-check: the "Already checked by" line below
  // says it, so the explanation (which repeats it) and the "couldn't generate" note
  // (which is about generated text, and nothing was generated) are left out.
  if (!(fast && r.match)) {
    html += `<p class="explanation" lang="${esc(r.explanation_lang || "en")}">${
      explanationHtml(r.explanation || "", id, n)}</p>`;
    if (r.explanation_source === "template" && !r.abstained) {
      html += `<p class="note">${esc(t("template_note"))}</p>`;
    }
  }

  if (liveUsed) {
    // Live results say so, never present an uncalibrated confidence as a band, and
    // carry Wikipedia's CC BY-SA attribution.
    const names = r.live_sources.map((x) => t(`source_name.${x}`, {}, x)).join(", ");
    // A live verdict stands on two NLI models agreeing (docs/live-fever-protocol-2.md); with
    // no agreement there is no verdict and the card says why, then points at the sources.
    html += `<p class="live-note"><span aria-hidden="true">🌐</span> ${esc(t("live_used", { sources: names }))}</p>
      <p class="note">${esc(t(r.abstained ? "live_no_verdict" : "live_verdict_basis"))}</p>
      <p class="note">${esc(t("live_validated"))}</p>
      <p class="note">${esc(t("live_uncalibrated"))}</p>`;
    if (r.live_sources.includes("wikipedia")) html += `<p class="note">${esc(t("live_attribution"))}</p>`;
  }

  if (fast && r.match) {
    html += `<p class="src">${esc(t("already_checked", { publisher: r.match.publisher }))}:
      <a href="${esc(r.match.url)}" target="_blank" rel="noopener">${esc(r.match.title)}</a></p>`;
  }
  if (n) {
    // Live sources ARE the answer, so they start open; offline evidence starts collapsed.
    html += `<button type="button" class="trail-toggle" aria-expanded="${liveUsed}"
      aria-controls="${id}-trail"><span class="chev" aria-hidden="true"></span><span>${esc(t(liveUsed ? "hide_evidence" : "see_evidence", { n }))}</span></button>
      <ol class="trail" id="${id}-trail"${liveUsed ? "" : " hidden"}>`;
    (r.passages || []).forEach((p, k) => {
      const stance = p.stance;           // null on live evidence, which is listed, not judged
      const title = p.title || p.doc_id;
      const href = p.url && /^https?:/.test(p.url) ? p.url : null;
      html += `<li id="${id}-ev-${k + 1}" tabindex="-1">
        ${stance ? `<span class="stance ${esc(stance)}">${esc(t(`stance.${stance}`, {}, stance))}</span>` : ""}
        ${p.source ? `<span class="src-tag">${esc(t(`source_name.${p.source}`, {}, p.source))}</span>` : ""}
        <span class="src">[${k + 1}] ${href
          ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(title)}</a>`
          : esc(title)}</span>
        ${href ? `<span class="domain">· ${esc(domainOf(href))}</span>` : ""}
        <span class="passage">${passageHtml(p)}</span></li>`;
    });
    html += `</ol>`;
  }

  const flags = r.manipulation_flags || [];
  if (flags.length) {
    html += `<p class="flags" title="${esc(t("manipulation_title"))}">
      <span aria-hidden="true">⚠</span> ${flags.map((f) => esc(t(`technique.${f}`, {}, f))).join(" · ")}</p>`;
  }
  html += inputNote(inp, r.explanation_lang);
  html += `<p class="disclaimer">${esc(t("disclaimer"))}</p></div>`;
  return html;
}

/* `live` maps a result's index to the card it was upgraded to by "Look this up online". */
function render(b, live = {}) {
  const inp = b.input || {};
  if (inp.lang === "other" || !b.results || !b.results.length) {
    return `<p>${esc(t("unsupported"))}</p>`;
  }
  let html = b.results.map((r, i) => (live[i]
    ? verdictCard(live[i].result, live[i].input || inp, i) : verdictCard(r, inp, i))).join("");
  const more = (b.unchecked_claims || []).length;
  if (more) {
    html += `<p class="footnote">${esc(more === 1 ? t("unchecked_one") : t("unchecked", { n: more }))}</p>`;
  }
  if (b.trace && b.trace.events) {
    html += `<details class="trace"><summary>${esc(t("stage_trace"))}</summary><ul>`;
    for (const e of b.trace.events) {
      html += `<li>${esc(e.stage)} (${esc(e.impl)}) ${Number(e.ms).toFixed(0)} ms${
        e.note ? ` — <em>${esc(e.note)}</em>` : ""}</li>`;
    }
    html += `</ul></details>`;
  }
  return html;
}

/* A reply is drawn from its state, so the language switch and the live upgrade just redraw it. */
function renderBubble(bubble) {
  bubble.className = "bubble in";
  bubble.innerHTML = render(bubble._state.body, bubble._state.live);
  wire(bubble);
}

/* Expander and citation markers, after the HTML is in the page. */
async function searchLive(btn) {
  const bubble = btn.closest(".bubble");
  const idx = Number(btn.dataset.idx || 0);
  const lang = btn.closest(".card") ? btn.closest(".card").getAttribute("lang") : UI_LANG;
  btn.disabled = true;
  btn.textContent = tl(lang, "live_checking");
  let body = null;
  try {
    const res = await fetch("/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: btn.dataset.claim, include_trace: false, live_search: true,
        ...(btn.dataset.forced ? { force_claim: true } : {}) }),
    });
    if (res.ok) body = await res.json();
  } catch (e) { /* handled below: the card keeps its answer */ }
  const result = body && body.results && body.results[0];
  if (!result || !(result.live_sources || []).length) {
    // A source was down, or the server refused: the earlier answer stays, visibly.
    btn.disabled = false;
    btn.innerHTML = `${ico("globe")}${esc(tl(lang, "live_button"))}`;
    const note = btn.parentElement.querySelector(".live-privacy");
    if (note) note.textContent = tl(lang, "live_unavailable");
    return;
  }
  if (btn.dataset.forced) result._forced = true;
  if (bubble && bubble._state) {
    // "Be careful" before the look-up must not turn into "Hard to say" because the look-up found nothing:
    // it is the same finding (nothing checks this exact claim), now with "I looked online too".
    const before = (bubble._state.live[idx] || {}).result || (bubble._state.body.results || [])[idx];
    if (before && isCareful(plainCase(before))) result._careful = true;
    bubble._state.live[idx] = { result, input: body.input || {} };
    renderBubble(bubble);
  }
}

/* "Check it anyway": the reader overrules the claim gate for this one message. */
async function checkAnyway(btn) {
  const bubble = btn.closest(".bubble");
  const idx = Number(btn.dataset.idx || 0);
  const lang = btn.dataset.cardLang;
  btn.disabled = true;
  btn.textContent = t("checking");
  let body = null;
  try {
    const res = await fetch("/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: btn.dataset.text, include_trace: false, force_claim: true }),
    });
    if (res.ok) body = await res.json();
  } catch (e) { /* the card stays as it was */ }
  const result = body && body.results && body.results[0];
  if (!result) {
    btn.disabled = false;
    btn.textContent = tl(lang, "plain.check_anyway");
    const note = btn.parentElement.nextElementSibling;
    if (note) { note.textContent = t("error_server"); note.hidden = false; }
    return;
  }
  result._forced = true;
  bubble._state.live[idx] = { result, input: body.input || {} };
  renderBubble(bubble);
}

/* "Listen": the browser's own speech, in the card's language. If this device has no voice for
 * it, say so instead of reading Hindi in an English voice. */
function speakCard(btn) {
  const lang = btn.dataset.cardLang;
  const note = btn.parentElement.nextElementSibling;
  const synth = globalThis.speechSynthesis;
  const showNote = (msg) => { if (note) { note.textContent = msg; note.hidden = !msg; } };
  if (!synth || typeof SpeechSynthesisUtterance === "undefined") {
    showNote(tl(lang, "plain.listen_none", { lang: tl(lang, `lang_name.${lang}`) }));
    return;
  }
  if (synth.speaking) { synth.cancel(); btn.classList.remove("on"); return; }
  const voices = synth.getVoices ? synth.getVoices() : [];
  const base = SPEECH[lang].slice(0, 2);
  if (voices.length && !voices.some((v) => (v.lang || "").toLowerCase().startsWith(base))) {
    showNote(tl(lang, "plain.listen_none", { lang: tl(lang, `lang_name.${lang}`) }));
    return;
  }
  showNote("");
  const u = new SpeechSynthesisUtterance(btn.dataset.speak);
  u.lang = SPEECH[lang];
  u.onend = u.onerror = () => btn.classList.remove("on");
  btn.classList.add("on");
  synth.speak(u);
}

/* "Copy a reply": a ready message to send back to the family group. Nothing is sent to us. */
async function copyReply(btn) {
  const lang = btn.dataset.cardLang;
  const text = btn.dataset.reply;
  const note = btn.parentElement.nextElementSibling;
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (e) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      ok = document.execCommand("copy");
      ta.remove();
    } catch (e2) { ok = false; }
  }
  if (ok) {
    const label = btn.innerHTML;
    btn.innerHTML = `${ico("check")}${esc(tl(lang, "plain.copied"))}`;
    setTimeout(() => { btn.innerHTML = label; }, 2000);
    if (note) note.hidden = true;
  } else if (note) {
    note.textContent = tl(lang, "plain.copy_failed");
    note.hidden = false;
  }
}

function wire(root) {
  root.querySelectorAll(".live-btn").forEach((btn) => {
    btn.addEventListener("click", () => searchLive(btn));
  });
  root.querySelectorAll(".act-force").forEach((btn) => btn.addEventListener("click", () => checkAnyway(btn)));
  root.querySelectorAll(".act-listen").forEach((btn) => btn.addEventListener("click", () => speakCard(btn)));
  root.querySelectorAll(".act-copy").forEach((btn) => btn.addEventListener("click", () => copyReply(btn)));
  root.querySelectorAll(".words-btn").forEach((btn) => btn.addEventListener("click", () => showWords(btn)));
  root.querySelectorAll(".trail-toggle").forEach((btn) => {
    btn.addEventListener("click", () => toggleTrail(btn));
  });
  root.querySelectorAll(".cite").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = document.getElementById(btn.dataset.target);
      if (!row) return;
      const list = row.closest(".trail");
      const toggle = root.querySelector(`[aria-controls="${list.id}"]`);
      if (list.hidden && toggle) toggleTrail(toggle);
      row.scrollIntoView({ block: "center" });
      row.focus({ preventScroll: true });
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 1500);
    });
  });
}

function toggleTrail(btn) {
  const list = document.getElementById(btn.getAttribute("aria-controls"));
  const open = list.hidden;
  list.hidden = !open;
  btn.setAttribute("aria-expanded", String(open));
  btn.querySelector("span:not(.chev)").textContent = t(open ? "hide_evidence" : "see_evidence",
    { n: list.children.length });
}

/* --------------------------------------------------------------- keyboard */

document.addEventListener("DOMContentLoaded", () => {
  $("composer").addEventListener("submit", (e) => { e.preventDefault(); send($("text").value); });
  // UI_UX.md §9: Enter sends, Shift+Enter is a new line.
  $("text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send($("text").value);
    }
  });
  boot();
});
