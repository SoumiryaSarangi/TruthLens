/* TruthLens demo page. Vanilla JS, no framework, no build step (UI_UX.md §2).
 *
 * It calls POST /verify and renders the JSON. It never recomputes anything:
 * the verdict, the stances, the highlight spans and the confidence all come
 * from the response, because a browser deriving its own numbers is how a demo
 * starts disagreeing with the evaluation.
 */

const $ = (id) => document.getElementById(id);

let S = {};             // strings for the interface language
let BANDS = null;       // from /version; no bands -> no band shown, never a guess
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

/* t("unchecked", {n: 2}) -> the string with {n} filled in, or the fallback. */
function t(key, vars = {}, fallback = "") {
  let s = key.split(".").reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), S);
  if (typeof s !== "string") s = fallback || key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : `{${k}}`));
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
  const lang = forced || (navigator.language || "en").slice(0, 2);
  S = await loadStrings(lang);
  document.documentElement.lang = S._lang || "en";
  applyStaticStrings();

  fetch("/health").then((r) => r.json()).then((h) => {
    const ok = h.status === "ok";
    $("health").className = `health ${ok ? "ok" : "degraded"}`;
    $("health-text").textContent = ok ? t("models_ready") : t("degraded");
  }).catch(() => {
    $("health").className = "health down";
    $("health-text").textContent = t("unreachable");
  });

  /* UI_UX.md §7: the band cut points come from /version and are never
   * hard-coded here. Without them the card shows no band rather than one
   * computed from stale numbers. */
  fetch("/version").then((r) => r.json())
    .then((v) => { if (v.confidence_bands) BANDS = v.confidence_bands; })
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
  pending.innerHTML = render(body);
  wire(pending);
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

function verdictCard(r, inp) {
  const id = `c${++cardSeq}`;
  const label = t(`verdict.${r.verdict}`, {}, r.verdict);
  const icons = S.icon || {};

  if (r.verdict === "NotAClaim") {
    // UI_UX.md §4-§5: a neutral card, not a verdict card -- no chip, no band.
    return `<div class="card neutral-card">
      <p class="neutral-title"><span aria-hidden="true">${esc(icons.NotAClaim || "💬")}</span> ${esc(label)}</p>
      <p class="note">${esc(t("notaclaim_note"))}</p></div>`;
  }

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
    const band = bandOf(r.confidence);
    if (band) {
      // A band, not a percentage (UI_UX.md §7); the exact value is one hover away.
      head += `<span class="band" tabindex="0"
        title="${esc(t("band_title", { value: Number(r.confidence).toFixed(2) }))}">
        ${esc(t(`band.${band}`, {}, band))}</span>`;
    }
  }

  let html = `<div class="card${r.abstained ? " abstained" : ""}" id="${id}">
    <div class="card-head">${head}</div>`;
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
  html += `<p class="explanation" lang="${esc(r.explanation_lang || "en")}">${
    explanationHtml(r.explanation || "", id, n)}</p>`;
  if (r.explanation_source === "template" && !r.abstained) {
    html += `<p class="note">${esc(t("template_note"))}</p>`;
  }

  if (fast && r.match) {
    html += `<p class="src">${esc(t("already_checked", { publisher: r.match.publisher }))}:
      <a href="${esc(r.match.url)}" target="_blank" rel="noopener">${esc(r.match.title)}</a></p>`;
  }
  if (n) {
    html += `<button type="button" class="trail-toggle" aria-expanded="false"
      aria-controls="${id}-trail">▸ ${esc(t("see_evidence", { n }))}</button>
      <ol class="trail" id="${id}-trail" hidden>`;
    (r.passages || []).forEach((p, k) => {
      const stance = p.stance || "Neutral";
      const title = p.title || p.doc_id;
      const href = p.url && /^https?:/.test(p.url) ? p.url : null;
      html += `<li id="${id}-ev-${k + 1}" tabindex="-1">
        <span class="stance ${esc(stance)}">${esc(t(`stance.${stance}`, {}, stance))}</span>
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

function render(b) {
  const inp = b.input || {};
  if (inp.lang === "other" || !b.results || !b.results.length) {
    return `<p>${esc(t("unsupported"))}</p>`;
  }
  let html = b.results.map((r) => verdictCard(r, inp)).join("");
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

/* Expander and citation markers, after the HTML is in the page. */
function wire(root) {
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
