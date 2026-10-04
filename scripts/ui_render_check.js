// Render real API responses with app.js in Node and check each demo card.
// Usage: see scripts/capture_responses.py. Exits 1 if a card misses what UI_UX.md
// says it must show, or prints undefined / NaN / an unfilled {placeholder}.
const fs = require("fs"), vm = require("vm");
const [appPath, respPath, enPath] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(respPath, "utf8"));
const en = JSON.parse(fs.readFileSync(enPath, "utf8"));
const stubEl = () => ({ addEventListener() {}, querySelectorAll: () => [], setAttribute() {}, appendChild() {}, classList: { add() {}, remove() {} } });
const ctx = { document: { getElementById: stubEl, addEventListener() {}, querySelectorAll: () => [], documentElement: {} },
              location: { search: "" }, navigator: { language: "en" }, fetch: async () => ({ ok: false }),
              URL, URLSearchParams, setTimeout, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(appPath, "utf8") + "\n;globalThis.__api = { render, setS: (s) => { S = s; }, setBands: (b) => { BANDS = b; } };", ctx);
const api = ctx.__api;
api.setS(en); api.setBands(data.version.confidence_bands);
const expect = {
  fast_path: ["📰", "Already checked by", "chip Refuted", "Fact-checkers say: FALSE"],
  romanized_hindi: ["typed in Roman script", "chip Refuted", "Explanation in English", "Be careful with this one"],
  gurmukhi: ["Punjabi, Gurmukhi script", "Explanation in English"],
  claim_extraction: ["Claim: “Nimbu paani", "class=\"flags\"", "See evidence"],
  not_a_claim: ["neutral-card", "find a claim to check", "Check it anyway"],
  abstained: ["card plain abstained", "Hard to say", "Leaning: Supported by evidence", "Not confident enough to judge"],
};
let bad = 0;
for (const r of data.responses) {
  const html = api.render(r.body);
  const missing = expect[r.shows].filter((s) => !html.includes(s));
  if (/undefined|NaN|\{[a-z_]+\}/.test(html.replace(/<[^>]+>/g, " "))) { missing.push("undefined/NaN/unfilled placeholder in text"); }
  console.log(`${missing.length ? "FAIL" : "ok  "} ${r.shows} ${missing.join(" | ")}`);
  if (missing.length) { bad++; fs.writeFileSync(`${respPath}.${r.shows}.html`, html); }
}
process.exit(bad ? 1 : 0);
