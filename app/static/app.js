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
let UI_LANG = "en";
let ANSWER_LANG = null; // set by the language switch; null = each card follows its message's language
const LANGS = ["en", "hi", "pa"];
const SPEECH = { en: "en-IN", hi: "hi-IN", pa: "pa-IN" };
let BANDS = null;       // from /version; no bands -> no band shown, never a guess
let LIVE = false;       // from /version: may this server search Wikipedia / Google live?
let lastText = "";
let cardSeq = 0;

const MAX_CHARS = 4000;  // FR-1, mirrored from the API so the error is instant

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

/* The language a card answers in. The language switch wins if the user used it. Otherwise the
 * answer follows the SCRIPT of the message: Hindi or Punjabi written in Devanagari or Gurmukhi
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
  if (forced) ANSWER_LANG = UI_LANG;      // ?lang= forces the answers too, for a demo
  document.documentElement.lang = S._lang || "en";
  applyStaticStrings();
  wireLanguageSwitch();

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
    })
    .catch(() => {});

  fetch("/static/samples.json").then((r) => r.json()).then(renderChips).catch(() => {});
}

function wireLanguageSwitch() {
  document.querySelectorAll("[data-lang]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.lang === UI_LANG));
    b.addEventListener("click", () => setLanguage(b.dataset.lang));
  });
}

/* The language switch changes the page AND every answer already on screen. */
function setLanguage(lang) {
  UI_LANG = ANSWER_LANG = lang;
  S = STR[lang] || S;
  document.documentElement.lang = lang;
  applyStaticStrings();
  document.querySelectorAll("[data-lang]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  document.querySelectorAll(".bubble.in").forEach((b) => { if (b._state) renderBubble(b); });
  const health = $("health-text");
  if (health && health.dataset.key) health.textContent = t(health.dataset.key);
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
  if (r.abstained) return { kind: "abstained", v: r.verdict, live };
  return { kind: "verdict", v: r.verdict, live };
}

function plainTitle(c, lang) {
  if (c.kind === "fast") return tl(lang, `plain.fast_title.${c.v}`);
  if (c.kind === "abstained") return tl(lang, "plain.title.abstained");
  return tl(lang, `plain.title.${c.v}`);
}

function plainReason(c, r, lang) {
  if (c.kind === "fast") return tl(lang, "plain.reason.fast", { publisher: r.match?.publisher || "" });
  if (c.kind === "abstained") {
    if (c.live) return tl(lang, "plain.reason.live_none");
    return tl(lang, c.v === "Supported" || c.v === "Refuted" ? `plain.reason.abstained_${c.v}`
      : "plain.reason.abstained_other");
  }
  if (c.live && (c.v === "Supported" || c.v === "Refuted")) return tl(lang, `plain.reason.live_${c.v}`);
  return tl(lang, `plain.reason.${c.v}`);
}

function plainAction(c, lang) {
  const v = c.kind === "abstained" ? null : c.v;
  return tl(lang, v === "Refuted" || v === "Supported" ? `plain.action.${v}` : "plain.action.check");
}

/* Up to three sources an ordinary reader can open: the matched fact-check, the cited
 * passages that point the same way as the verdict, or -- on a live card -- whatever was found. */
function plainSources(c, r) {
  const href = (p) => (p.url && /^https?:/.test(p.url) ? p.url : null);
  const row = (url, title) => ({ url, title, domain: domainOf(url) });
  if (c.kind === "fast") return r.match ? [row(r.match.url, r.match.title)] : [];
  const passages = (r.passages || []).filter((p) => href(p));
  if (c.live) return passages.slice(0, 3).map((p) => row(href(p), p.title || p.doc_id));
  if (c.kind === "verdict" && (c.v === "Supported" || c.v === "Refuted")) {
    const want = c.v === "Supported" ? "Supports" : "Refutes";
    const cited = new Set(r.cited || []);
    return passages.filter((p) => cited.has(p.passage_id) && p.stance === want)
      .slice(0, 2).map((p) => row(href(p), p.title || p.doc_id));
  }
  return [];
}

function plainFlags(r, lang) {
  const flags = r.manipulation_flags || [];
  if (!flags.length) return "";
  const list = flags.map((f) => tl(lang, `plain.technique.${f}`)).join(", ");
  return `<p class="plain-flags"><span aria-hidden="true">⚠</span> ${esc(tl(lang, "plain.flags", { list }))}</p>`;
}

function replyText(c, sources, lang) {
  const key = c.kind === "abstained" ? "check" : (c.v === "Refuted" || c.v === "Supported" ? c.v : "check");
  let text = tl(lang, `plain.reply.${key}`);
  if (sources.length) text += `\n${tl(lang, "plain.reply.source", { url: sources[0].url })}`;
  return text;
}

function plainCard(r, inp, idx) {
  const lang = cardLang(inp);
  const icons = S.icon || {};
  const c = plainCase(r);

  if (c.kind === "none") {
    return `<div class="card neutral-card plain" lang="${esc(lang)}">
      <p class="neutral-title"><span aria-hidden="true">${esc(icons.NotAClaim || "💬")}</span> ${esc(tl(lang, "plain.none_title"))}</p>
      <p class="reason">${esc(tl(lang, "plain.none_note"))}</p></div>`;
  }

  const id = `c${++cardSeq}`;
  const bandName = bandOf(r.confidence);
  const title = plainTitle(c, lang);
  const chipClass = c.kind === "abstained" ? "abstained" : (c.v === "Conflicting" || c.v === "NEI" || c.v === "Refuted"
    || c.v === "Supported" ? c.v : "NEI");
  const icon = c.kind === "abstained" ? icons.abstained : icons[c.v];
  const reason = plainReason(c, r, lang);
  const action = plainAction(c, lang);
  const sources = plainSources(c, r);
  // Only an offline, calibrated verdict says how sure it is; a live one is uncalibrated and says nothing.
  const sure = c.kind === "verdict" && !c.live && bandName ? tl(lang, `plain.sure.${bandName}`) : "";
  const speak = [title, reason, sure, action].filter(Boolean).join(" ");

  let html = `<div class="card plain${c.kind === "abstained" ? " abstained" : ""}" id="${id}" lang="${esc(lang)}">
    <p class="plain-head"><span class="chip big ${esc(chipClass)}" role="img"
      aria-label="${esc(t("verdict_aria", { label: title }))}"><span aria-hidden="true">${esc(icon || "")}</span>${esc(title)}</span></p>
    <p class="reason">${esc(reason)}${sure ? ` <span class="sure">${esc(sure)}</span>` : ""}</p>
    <p class="action">${esc(action)}</p>`;
  if (sources.length) {
    html += `<p class="src-label">${esc(tl(lang, c.live || c.kind === "abstained" ? "plain.found_label"
        : (c.kind === "fast" ? "plain.sources_label" : "plain.closest_label")))}</p>
      <ul class="plain-sources">${sources.map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>${
        x.domain ? ` <span class="domain">· ${esc(x.domain)}</span>` : ""}</li>`).join("")}</ul>`;
  }
  html += plainFlags(r, lang);
  if (r.claim && r.claim.text) {
    html += `<p class="claim-line">${esc(tl(lang, "plain.claim_label"))} “${esc(r.claim.text)}”</p>`;
  }
  html += `<div class="actions">
      <button type="button" class="act act-listen" data-speak="${esc(speak)}" data-card-lang="${esc(lang)}"
        aria-label="${esc(tl(lang, "plain.listen"))}"><span aria-hidden="true">🔊</span> ${esc(tl(lang, "plain.listen"))}</button>
      <button type="button" class="act act-copy" data-reply="${esc(replyText(c, sources, lang))}" data-card-lang="${esc(lang)}"
        aria-label="${esc(tl(lang, "plain.copy"))}"><span aria-hidden="true">📋</span> ${esc(tl(lang, "plain.copy"))}</button>
    </div><p class="note act-note" hidden></p>`;

  // Looking it up online: explicit, per claim, and it says exactly what it sends.
  const liveUsed = c.live;
  if (!liveUsed && LIVE && r.path !== "fast" && r.claim?.text && (r.abstained || bandName !== "High")) {
    html += `<button type="button" class="live-btn" data-card="${id}" data-claim="${esc(r.claim.text)}" data-idx="${idx}">
      <span aria-hidden="true">🌐</span> ${esc(tl(lang, "live_button"))}</button>
      <p class="note live-privacy">${esc(tl(lang, "live_privacy"))}</p>`;
  }
  html += `<p class="disclaimer">${esc(tl(lang, "disclaimer"))}</p>`;
  html += `<details class="more"><summary>${esc(tl(lang, "plain.details"))}</summary>${technicalCard(r, inp, id)}</details></div>`;
  return html;
}

function verdictCard(r, inp, idx = 0) {
  return plainCard(r, inp, idx);
}

/* The full technical card (verdict class, confidence band, explanation, evidence trail,
 * live notes, input note), inside "Details". It is the card the project measured. */
function technicalCard(r, inp, cardId) {
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
      head += `<span class="band" tabindex="0"
        title="${esc(t("band_title", { value: Number(r.confidence).toFixed(2) }))}">
        ${esc(t(`band.${band}`, {}, band))}</span>`;
    }
  }

  let html = `<div class="technical"><div class="card-head">${head}</div>`;
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
      aria-controls="${id}-trail">${liveUsed ? "▾" : "▸"} ${esc(t(liveUsed ? "hide_evidence" : "see_evidence", { n }))}</button>
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
      body: JSON.stringify({ text: btn.dataset.claim, include_trace: false, live_search: true }),
    });
    if (res.ok) body = await res.json();
  } catch (e) { /* handled below: the card keeps its answer */ }
  const result = body && body.results && body.results[0];
  if (!result || !(result.live_sources || []).length) {
    // A source was down, or the server refused: the earlier answer stays, visibly.
    btn.disabled = false;
    btn.textContent = `🌐 ${tl(lang, "live_button")}`;
    const note = btn.parentElement.querySelector(".live-privacy");
    if (note) note.textContent = tl(lang, "live_unavailable");
    return;
  }
  if (bubble && bubble._state) {
    bubble._state.live[idx] = { result, input: body.input || {} };
    renderBubble(bubble);
  }
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
    btn.innerHTML = `<span aria-hidden="true">✓</span> ${esc(tl(lang, "plain.copied"))}`;
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
  root.querySelectorAll(".act-listen").forEach((btn) => btn.addEventListener("click", () => speakCard(btn)));
  root.querySelectorAll(".act-copy").forEach((btn) => btn.addEventListener("click", () => copyReply(btn)));
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
  btn.textContent = `${open ? "▾" : "▸"} ${t(open ? "hide_evidence" : "see_evidence",
    { n: list.children.length })}`;
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
