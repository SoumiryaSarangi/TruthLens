// Render an evidence-only live result in en/hi/pa: sources open, no stance tags, each source tagged.
//   node scripts/ui_evidence_check.js
const fs = require("fs"), vm = require("vm");
const el = () => ({ addEventListener() {}, querySelectorAll: () => [], setAttribute() {}, appendChild() {}, classList: { add() {}, remove() {} } });
const ctx = { document: { getElementById: el, addEventListener() {}, querySelectorAll: () => [], documentElement: {} }, location: { search: "" }, navigator: { language: "en" }, fetch: async () => ({ ok: false }), URL, URLSearchParams, setTimeout, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("app/static/app.js", "utf8") + "\n;globalThis.__a={render,setS:(s)=>{S=s},setB:(b)=>{BANDS=b}};", ctx);
for (const loc of ["en", "hi", "pa"]) {
  ctx.__a.setS(JSON.parse(fs.readFileSync(`app/static/i18n/${loc}.json`, "utf8"))); ctx.__a.setB({ high: 0.6, medium: 0.4 });
  const r = { claim: { claim_id: "c1", text: "x claim" }, path: "evidence", match: null, verdict: "NEI", confidence: 0, abstained: true,
    explanation: "TruthLens found these online sources: [1] A; [2] B. Read them.", explanation_source: "template", explanation_lang: "en", cited: ["e1", "e2"],
    live_sources: ["wikipedia", "google_factcheck"], manipulation_flags: [],
    passages: [{ passage_id: "e1", doc_id: "u1", url: "https://en.wikipedia.org/wiki/A", title: "A", text: "Lead of A.", retrieval_score: 0.7, stance: null, source: "wikipedia" },
               { passage_id: "e2", doc_id: "u2", url: "https://fc.example/b", title: "AajTak", text: "Headline — AajTak rating: False", retrieval_score: 0.7, stance: null, source: "factcheck_live" }] };
  const out = ctx.__a.render({ input: { lang: "hi", script: "deva" }, results: [r], unchecked_claims: [] });
  const open = out.includes('aria-expanded="true"') && !/<ol class="trail"[^>]*hidden/.test(out);
  const noStance = !/class="stance /.test(out);
  const tagged = (out.match(/class="src-tag"/g) || []).length === 2;
  console.log(loc, open && noStance && tagged ? "ok  " : "FAIL", { open, noStance, tagged });
}
