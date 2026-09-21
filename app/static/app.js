/* TruthLens demo page. Vanilla JS, no framework, no build step (UI_UX.md §2).
 *
 * It calls POST /verify and renders the JSON. It never recomputes anything:
 * the evidence trail, the stances and the confidence all come from the
 * response, because a browser deriving its own numbers is how a demo starts
 * disagreeing with the evaluation.
 */

const $ = (id) => document.getElementById(id);

let STRINGS = {};
let BANDS = { high: 0.75, medium: 0.5 };

/* Copy lives in app/static/i18n/*.json so Phase 7 can translate the interface
 * without touching this file. Falls back to English if a locale is missing. */
async function loadStrings(lang) {
  for (const candidate of [lang, "en"]) {
    try {
      const r = await fetch(`/static/i18n/${candidate}.json`);
      if (r.ok) return await r.json();
    } catch (e) { /* fall through to the next candidate */ }
  }
  return {};
}

/* UI_UX.md §7: the band cut points come from /version and are never hard-coded
 * here. They are chosen from the calibration curve on dev, so a copy in
 * JavaScript would silently go stale the moment calibration is rerun. */
async function boot() {
  STRINGS = await loadStrings(navigator.language?.slice(0, 2) || "en");

  fetch("/health").then((r) => r.json())
    .then((h) => {
      $("health").textContent = h.status === "ok"
        ? (STRINGS.models_ready || "· models ready")
        : (STRINGS.degraded || "· degraded");
    })
    .catch(() => { $("health").textContent = STRINGS.unreachable || "· API unreachable"; });

  fetch("/version").then((r) => r.json())
    .then((v) => { if (v.confidence_bands) BANDS = v.confidence_bands; })
    .catch(() => { /* keep the defaults; the page still works */ });
}

function band(confidence) {
  if (confidence >= BANDS.high) return "High";
  if (confidence >= BANDS.medium) return "Medium";
  return "Low";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function verdictLabel(v) {
  return (STRINGS.verdict && STRINGS.verdict[v]) || v;
}

function verdictIcon(v, abstained) {
  const icons = STRINGS.icon || {};
  return abstained ? (icons.abstained || "◌") : (icons[v] || "");
}

async function check() {
  const text = $("text").value;
  const idx = $("idx").value;
  $("out").innerHTML = `<p class="muted">${esc(STRINGS.checking || "Checking…")}</p>`;

  const url = "/verify" + (idx !== "" ? `?claim_idx=${encodeURIComponent(idx)}` : "");
  let res, body;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, include_trace: true }),
    });
    body = await res.json();
  } catch (e) {
    $("out").innerHTML = `<p class="err">Request failed: ${esc(e)}</p>`;
    return;
  }
  if (!res.ok) {
    const detail = body && body.detail ? body.detail : res.statusText;
    $("out").innerHTML = `<p class="err">${res.status}: ${esc(JSON.stringify(detail))}</p>`;
    return;
  }
  $("out").innerHTML = render(body);
}

function render(b) {
  const inp = b.input || {};
  let html = `<p class="muted">Detected ${esc(inp.lang)} / ${esc(inp.script)}
    (script purity ${Number(inp.script_purity ?? 0).toFixed(2)})</p>`;

  if (!b.results || !b.results.length) {
    return html + `<div class="card"><p>${esc(STRINGS.unsupported
      || "TruthLens works with English, Hindi and Punjabi.")}</p></div>`;
  }

  for (const r of b.results) {
    html += `<div class="card${r.abstained ? " abstained" : ""}">`;

    /* UI_UX.md §6: abstained is visibly different from NEI. NEI says the
     * evidence is missing; abstained says the system does not trust its own
     * answer, so the would-be verdict is shown small rather than asserted. */
    html += r.abstained
      ? `<p class="verdict">${verdictIcon(r.verdict, true)}
         ${esc(STRINGS.not_confident || "Not confident enough to judge — leaning:")}
         ${esc(verdictLabel(r.verdict))}</p>`
      : `<p class="verdict">${verdictIcon(r.verdict, false)}
         ${esc(verdictLabel(r.verdict))}</p>`;

    /* A band, not a percentage (UI_UX.md §7) — "73%" invites false precision.
     * The exact value is in the title attribute for whoever asks. */
    html += `<p class="muted" title="calibrated on the development set">
      confidence ${esc(band(r.confidence))}
      · path ${esc(r.path)}
      · explanation ${esc(r.explanation_source)}</p>`;
    html += `<p lang="${esc(r.explanation_lang || "en")}">${esc(r.explanation)}</p>`;

    if (r.passages && r.passages.length) {
      const label = STRINGS.see_evidence || "See evidence";
      html += `<details><summary>${esc(label)} (${r.passages.length})</summary><ol>`;
      for (const p of r.passages) {
        html += `<li><strong>${esc(p.stance ?? "—")}</strong>
          <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.doc_id)}</a>
          <br><span class="muted">${esc((p.text || "").slice(0, 300))}</span></li>`;
      }
      html += `</ol></details>`;
    }
    html += `<p class="muted">${esc(STRINGS.disclaimer
      || "TruthLens can be wrong. Check the sources.")}</p></div>`;
  }

  if (b.trace && b.trace.events) {
    html += `<details><summary>${esc(STRINGS.stage_trace || "Stage trace")}</summary><ul>`;
    for (const e of b.trace.events) {
      html += `<li>${esc(e.stage)} (${esc(e.impl)}) ${Number(e.ms).toFixed(1)} ms
        ${e.note ? `— <em>${esc(e.note)}</em>` : ""}</li>`;
    }
    html += `</ul></details>`;
  }
  return html;
}

document.addEventListener("DOMContentLoaded", () => {
  $("go").onclick = check;
  boot();
});
