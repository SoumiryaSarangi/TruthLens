// Render the live-search states of the card with app.js in Node (no browser needed).
//   node scripts/ui_live_check.js app/static/app.js app/static/i18n/en.json
// Checks UI_UX.md's promises for live results: the button exists only where it
// should and says what it sends; a live result is badged, attributed, tagged per
// source, and NEVER shown with a calibrated confidence band.
const fs = require("fs"), vm = require("vm");
const [appPath, locPath] = process.argv.slice(2);
const el = () => ({ addEventListener() {}, querySelectorAll: () => [], setAttribute() {}, appendChild() {}, classList: { add() {}, remove() {} } });
const ctx = { document: { getElementById: el, addEventListener() {}, querySelectorAll: () => [], documentElement: {} }, location: { search: "" }, navigator: { language: "en" }, fetch: async () => ({ ok: false }), URL, URLSearchParams, setTimeout, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(appPath, "utf8") + "\n;globalThis.__a={render,setS:(s)=>{S=s},setB:(b)=>{BANDS=b},setL:(v)=>{LIVE=v}};", ctx);
const api = ctx.__a;
const L = JSON.parse(fs.readFileSync(locPath, "utf8"));
api.setS(L);
const names = `${L.source_name.wikipedia}, ${L.source_name.google_factcheck}`;
api.setB({ high: 0.6, medium: 0.4 });

const claim = { claim_id: "c1", text: "Narendra Modi was Gujarat's chief minister" };
const base = { claim, path: "evidence", match: null, passages: [], verdict: "NEI", confidence: 0.32, abstained: true,
  explanation: "x", explanation_source: "template", explanation_lang: "en", cited: [], live_sources: [], manipulation_flags: [] };
const wiki = { passage_id: "e1", doc_id: "u", url: "https://en.wikipedia.org/wiki/Narendra_Modi", title: "Narendra Modi",
  text: "Modi was the chief minister of Gujarat.", retrieval_score: 0.7, stance: "Supports", stance_prob: 0.99, source: "wikipedia" };
const body = (r) => ({ input: { lang: "en", script: "latn" }, results: [r], unchecked_claims: [] });
const html = (r, live) => { api.setL(live); return api.render(body(r)); };

const cases = [
  ["button shown on an abstained card", html(base, true), ["live-btn", "live-privacy", L.live_privacy], []],
  ["button hidden when the server cannot go live", html(base, false), [], ["live-btn"]],
  ["button hidden on a High-band card", html({ ...base, abstained: false, verdict: "Refuted", confidence: 0.7 }, true), [], ["live-btn"]],
  ["button shown on a Medium-band card", html({ ...base, abstained: false, verdict: "Refuted", confidence: 0.57 }, true), ["live-btn"], []],
  ["button hidden on a fast-path card", html({ ...base, path: "fast", abstained: false, verdict: "Refuted", confidence: 0.92,
      match: { publisher: "FC", title: "t", url: "https://fc.example/x" } }, true), [], ["live-btn"]],
  ["live result: badge, attribution, source tag, no band", html({ ...base, abstained: false, verdict: "Supported", confidence: 0.99,
      passages: [wiki], live_sources: ["wikipedia", "google_factcheck"] }, true),
      ["live-note", L.live_used.replace("{sources}", names), "CC BY-SA 4.0", L.live_uncalibrated, "src-tag",
       L.live_verdict_basis, L.live_validated],
      ["class=\"band\"", "live-btn", L.live_no_verdict]],
  // the two models did not agree: an abstained live card says so and points at the sources
  ["live result, no agreement: abstained, says why", html({ ...base, abstained: true, verdict: "NEI", confidence: 0.2,
      passages: [wiki], live_sources: ["wikipedia"] }, true),
      ["live-note", L.live_no_verdict, L.live_validated, L.live_uncalibrated, "abstained"],
      ["class=\"band\"", L.live_verdict_basis]],
];
let bad = 0;
for (const [name, out, want, notWant] of cases) {
  const missing = want.filter((s) => !out.includes(s)), present = notWant.filter((s) => out.includes(s));
  const text = out.replace(/<[^>]+>/g, " ");
  const junk = text.match(/undefined|NaN|\{[a-z_]+\}/g);
  const problems = [...missing.map((m) => `missing ${m}`), ...present.map((p) => `unexpected ${p}`), ...(junk ? [`junk ${junk}`] : [])];
  console.log(`${problems.length ? "FAIL" : "ok  "} ${name} ${problems.join(" | ")}`);
  if (problems.length) bad++;
}
process.exit(bad ? 1 : 0);
