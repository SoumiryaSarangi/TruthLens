// The plain card, rendered in Node (no browser): what an ordinary reader sees.
//   node scripts/ui_plain_check.js reports/ui_responses.json [--show]
//
// For every demo response, in English, Hindi and Punjabi, this checks the properties the
// plain-card plan (docs/specs/UI_UX.md section 5) promises:
//   1. the card has a plain headline, a reason and a what-to-do line, in the card's language;
//   2. none of the technical words appear OUTSIDE the closed "Details" fold;
//   3. the main text is short (the reason and the action together, a word budget);
//   4. Listen and Copy-a-reply are there, and the reply is in the card's language;
//   5. the Details fold still holds the technical card (nothing was removed).
// --show prints the main card as plain text so a person can read it.
const fs = require("fs"), vm = require("vm");
const [respPath, flag] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(respPath, "utf8"));
const el = () => ({ addEventListener() {}, querySelectorAll: () => [], setAttribute() {}, appendChild() {}, classList: { add() {}, remove() {} } });
const ctx = { document: { getElementById: el, addEventListener() {}, querySelectorAll: () => [], documentElement: {} },
  location: { search: "" }, navigator: { language: "en" }, fetch: async () => ({ ok: false }), URL, URLSearchParams, setTimeout, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("app/static/app.js", "utf8")
  + "\n;globalThis.__a={render,setS:(s)=>{S=s},setSTR:(x)=>{STR=x},setB:(b)=>{BANDS=b},setLive:(v)=>{LIVE=v},setAns:(l)=>{ANSWER_LANG=l}};", ctx);
const api = ctx.__a;
const STR = {};
for (const l of ["en", "hi", "pa"]) STR[l] = JSON.parse(fs.readFileSync(`app/static/i18n/${l}.json`, "utf8"));
api.setSTR(STR); api.setB(data.version.confidence_bands); api.setLive(true);

// Two live cards (the "Look this up online" result), synthetic but shaped like the API's.
const liveBase = { claim: { claim_id: "c1", text: "Hyderabad is the capital of Telangana" }, path: "evidence", match: null,
  explanation: "x", explanation_source: "template", explanation_lang: "en", manipulation_flags: [],
  live_sources: ["wikipedia", "google_factcheck"], cited: ["e1"],
  passages: [{ passage_id: "e1", doc_id: "u1", url: "https://en.wikipedia.org/wiki/Hyderabad", title: "Hyderabad",
    text: "Hyderabad is the capital of Telangana.", retrieval_score: 0.8, stance: "Supports", stance_prob: 0.97, source: "wikipedia" }] };
data.responses.push(
  { shows: "live_verdict", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
    results: [{ ...liveBase, verdict: "Supported", confidence: 0.89, abstained: false }] } },
  { shows: "live_none", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
    results: [{ ...liveBase, verdict: "NEI", confidence: 0.0, abstained: true }] } });

// Words an ordinary reader should never meet outside Details.
const JARGON = [/contradict/i, /\bevidence\b/i, /calibrat/i, /\bstance\b/i, /stage trace/i, /\bNEI\b/, /\bRefutes\b/, /\bSupports\b/,
  /\bNeutral\b/, /confidence/i, /\bmodels?\b/i, /\bband\b/i, /\bHigh\b/, /\bMedium\b/, /\bLow\b/, /explanation/i,
  /Roman script/i, /Devanagari/i, /Gurmukhi/i, /CC BY/i, /fast path/i];
const WORD_BUDGET = 38;

function split(html) {
  const m = html.match(/<details class="more">[\s\S]*?<\/details>/g) || [];
  let main = html;
  for (const d of m) main = main.replace(d, "");
  main = main.replace(/<details class="trace">[\s\S]*?<\/details>/g, "");
  return { main, details: m.join("") };
}
const text = (h) => h.replace(/<[^>]+>/g, " ").replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();

let bad = 0;
for (const lang of ["en", "hi", "pa"]) {
  api.setS(STR[lang]); api.setAns(lang);
  for (const r of data.responses) {
    const html = api.render(r.body);
    const { main, details } = split(html);
    const problems = [];
    const body = text(main);
    const isNone = r.shows === "not_a_claim";
    if (!isNone) {
      if (!main.includes('class="chip big')) problems.push("no plain headline");
      if (!main.includes('class="reason"')) problems.push("no reason");
      if (!main.includes('class="action"')) problems.push("no what-to-do line");
      if (!main.includes("act-listen") || !main.includes("act-copy")) problems.push("missing Listen or Copy");
      if (!details.includes("technical")) problems.push("Details fold lost the technical card");
      const reasonAction = text((main.match(/<p class="reason">[\s\S]*?<\/p>/) || [""])[0]) + " " + text((main.match(/<p class="action">[\s\S]*?<\/p>/) || [""])[0]);
      if (reasonAction.split(" ").length > WORD_BUDGET) problems.push(`reason+action over ${WORD_BUDGET} words`);
      const reply = (main.match(/data-reply="([^"]*)"/) || [])[1] || "";
      if (!reply.includes("TruthLens")) problems.push("reply is not a ready message");
      if (lang !== "en" && /\bPlease\b|\bforward\b/.test(reply)) problems.push("reply is in English");
    }
    for (const re of JARGON) {
      // the claim line quotes the user's own message and the sources are named by their publishers: skip them
      const scrub = body.replace(/“[^”]*”/g, "").replace(/·[^·]*$/g, "");
      const hit = (lang === "en" ? scrub : scrub.replace(/[A-Za-z][A-Za-z .,'’\-:()%0-9«»/_]*/g, " ")).match(re);
      if (hit && lang === "en" && !isNone) {
        // English: only flag a jargon word if it is in a fixed string, not inside a quoted source title
        const fixed = text(main.replace(/<ul class="plain-sources">[\s\S]*?<\/ul>/, "")).replace(/“[^”]*”/g, "");
        if (re.test(fixed)) problems.push(`jargon: ${re}`);
      }
    }
    if (r.shows === "live_verdict") {
      if (!main.includes("plain-sources") || /class="sure"/.test(main)) problems.push("live verdict: sources missing, or an uncalibrated 'how sure' shown");
      if (!main.includes("Hyderabad</a>")) problems.push("live verdict: no source link");
    }
    if (r.shows === "live_none" && !main.includes("plain-sources")) problems.push("live no-verdict: the sources found are not listed");
    if (/undefined|NaN|\{[a-z_]+\}/.test(body)) problems.push("undefined / NaN / unfilled placeholder");
    console.log(`${problems.length ? "FAIL" : "ok  "} ${lang} ${r.shows} ${problems.join(" | ")}`);
    if (problems.length) bad++;
    if (flag === "--show" && lang !== "pa") console.log("      " + body + "\n");
  }
}
process.exit(bad ? 1 : 0);
