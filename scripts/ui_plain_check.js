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
  + "\n;globalThis.__a={render,setS:(s)=>{S=s},setSTR:(x)=>{STR=x},setWords:(v)=>{WORDS=v},setB:(b)=>{BANDS=b},setLive:(v)=>{LIVE=v},setAns:(l)=>{ANSWER_LANG=l}};", ctx);
const api = ctx.__a;
const STR = {};
for (const l of ["en", "hi", "pa"]) STR[l] = JSON.parse(fs.readFileSync(`app/static/i18n/${l}.json`, "utf8"));
api.setSTR(STR); api.setB(data.version.confidence_bands); api.setLive(true); api.setWords(true);

// Two live cards (the "Look this up online" result), synthetic but shaped like the API's.
const liveBase = { claim: { claim_id: "c1", text: "Hyderabad is the capital of Telangana" }, path: "evidence", match: null,
  explanation: "x", explanation_source: "template", explanation_lang: "en", manipulation_flags: [],
  live_sources: ["wikipedia", "google_factcheck"], cited: ["e1"],
  passages: [{ passage_id: "e1", doc_id: "u1", url: "https://en.wikipedia.org/wiki/Hyderabad", title: "Hyderabad",
    text: "Hyderabad is the capital of Telangana.", premise: "Hyderabad is the capital of Telangana. It is a large city.",
    retrieval_score: 0.8, stance: "Supports", stance_prob: 0.97, source: "wikipedia" }] };
data.responses.push(
  { shows: "live_verdict", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
    results: [{ ...liveBase, verdict: "Supported", confidence: 0.89, abstained: false }] } },
  { shows: "live_none", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
    results: [{ ...liveBase, verdict: "NEI", confidence: 0.0, abstained: true }] } });

// A guess that came with a published fact-check scoring between tau_similar and tau_match.
data.responses.push({ shows: "similar", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ claim: { claim_id: "c1", text: "WhatsApp will start charging users from next month" }, path: "evidence", match: null,
    verdict: "Refuted", confidence: 0.7, abstained: false, explanation: "x", explanation_source: "template", explanation_lang: "en",
    cited: [], passages: [], live_sources: [], manipulation_flags: [],
    similar_match: { factcheck_id: "f1", score: 0.88, verdict: "Refuted", title: "Viral Messages Claiming WhatsApp Will Become Chargeable Are Fake",
      url: "https://www.boomlive.in/fact-check/whatsapp-chargeable", publisher: "boomlive.in", lang: "en" } }] } });

// The same, when the fact-check's own rating cannot be mapped to a verdict: no "rated it ...", still a link.
data.responses.push({ shows: "similar_unrated", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ claim: { claim_id: "c1", text: "Eating garlic cures COVID-19" }, path: "evidence", match: null,
    verdict: "Refuted", confidence: 0.7, abstained: false, explanation: "x", explanation_source: "template", explanation_lang: "en",
    cited: [], passages: [], live_sources: [], manipulation_flags: [],
    similar_match: { factcheck_id: "f2", score: 0.756, verdict: null, title: "Garlic COVID cure claim crushed by experts",
      url: "https://www.aap.com.au/factcheck/garlic", publisher: "aap.com.au", lang: "en" } }] } });

// A greeting the reader chose to check anyway: the claim gate said it is not a claim, so the "most messages like this
// are false" warning must not be used on it.
data.responses.push({ shows: "forced_greeting", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ claim: { claim_id: "c1", text: "Good morning, stay blessed" }, path: "evidence", match: null, _forced: true,
    verdict: "Refuted", confidence: 0.7, abstained: false, explanation: "x", explanation_source: "template", explanation_lang: "en",
    cited: [], passages: [], live_sources: [], manipulation_flags: [], similar_match: null }] } });

// A live look-up that still cannot decide, with a similar fact-check found earlier: the fact-check leads the card.
data.responses.push({ shows: "live_similar", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ ...liveBase, claim: { claim_id: "c1", text: "Pineapple juice 500 guna jyada asardar hai" },
    verdict: "NEI", confidence: 0.0, abstained: true,
    similar_match: { factcheck_id: "f3", score: 0.722, verdict: "Refuted", title: "Is pineapple juice 500% more effective than cough syrup?",
      url: "https://newsmeter.in/fact-check/pineapple", publisher: "newsmeter.in", lang: "en" } }] } });

// "Be careful" before a live look-up that finds nothing stays "Be careful" (the app sets _careful from the earlier card).
data.responses.push({ shows: "live_careful", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ ...liveBase, claim: { claim_id: "c1", text: "Kal se WhatsApp ke paise lagenge" }, _careful: true,
    verdict: "NEI", confidence: 0.0, abstained: true, similar_match: null }] } });

// A greeting: no "Check it anyway", and it says there is nothing to check.
data.responses.push({ shows: "greeting", body: { input: { lang: "en", script: "latn", original: "Good morning, stay blessed" },
  unchecked_claims: [], results: [{ claim: { claim_id: "c1", text: "Good morning, stay blessed" }, path: "none", match: null,
    verdict: "NotAClaim", confidence: 1, abstained: false, explanation: "x", explanation_source: "template", explanation_lang: "en",
    cited: [], passages: [], live_sources: [], manipulation_flags: [], gate_reason: "greeting" }] } });

// A live verdict with its judged premise: the "Which words mattered?" button is offered, and only here.
data.responses.push({ shows: "words_button", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ ...liveBase, claim_en: "Hyderabad is the capital of Telangana.", verdict: "Supported", confidence: 0.89, abstained: false,
    passages: [{ passage_id: "e1", doc_id: "u1", url: "https://en.wikipedia.org/wiki/Hyderabad", title: "Hyderabad",
      text: "Hyderabad is the capital of Telangana.", premise: "Hyderabad is the capital of Telangana. It is large.",
      retrieval_score: 0.8, stance: "Supports", stance_prob: 0.97, source: "wikipedia" }] }] } });

// A live look-up whose sources point opposite ways: says so, and is not the generic warning even if the offline lean was "false".
data.responses.push({ shows: "live_disagree", body: { input: { lang: "en", script: "latn" }, unchecked_claims: [],
  results: [{ ...liveBase, _careful: true, sources_disagree: true, verdict: "NEI", confidence: 0.0, abstained: true }] } });

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
    const isNone = r.shows === "not_a_claim" || r.shows === "greeting";
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
    // The offline evidence path is a guess, never an answer: "Hard to say", no verdict word, no "how sure",
    // the live button offered, the system's lean only inside Details.
    if (r.shows === "romanized_hindi" || r.shows === "claim_extraction") {
      if (!main.includes("card plain abstained")) problems.push("an offline guess is not shown as an abstained, hedged card");
      if (/Probably|quite sure|fairly sure|not very sure|I am .* sure/i.test(body.replace(/“[^”]*”/g, ""))) problems.push("an offline guess is worded like a verdict");
      if (lang === "en" && !/Be careful with this one/.test(body)) problems.push("a guess that leans false is not shown as a warning");
      if (!details.includes('class="note lean"')) problems.push("the system's lean is missing from Details");
      if (lang === "en" && !main.includes("live-btn")) problems.push("no 'look this up online' button on a guess");
    }
    if (r.shows === "not_a_claim" && !main.includes("act-force")) problems.push("no 'Check it anyway' button on the not-a-claim card");
    if (r.shows === "similar") {
      if (!main.includes("boomlive.in/fact-check/whatsapp-chargeable")) problems.push("similar: the fact-check link is missing");
      if (!main.includes("card plain abstained")) problems.push("similar: not shown as a hedged card");
      if (/Probably (TRUE|FALSE)|I am .* sure/i.test(body)) problems.push("similar: worded like a verdict");
      if (!/similar/i.test(body) && lang === "en") problems.push("similar: does not say it is only similar");
      const rating = {en: "False", hi: "झूठ", pa: "ਝੂਠ"}[lang];
      if (!body.includes(rating)) problems.push("similar: the publisher's rating is not shown in words");
      const reply = (main.match(/data-reply="([^"]*)"/) || [])[1] || "";
      if (!reply.includes("boomlive.in")) problems.push("similar: the reply has no link");
    }
    if (r.shows === "similar_unrated") {
      if (!main.includes("aap.com.au/factcheck/garlic")) problems.push("unrated similar: the fact-check link is missing");
      if (/rated it|\{rating\}|undefined/i.test(body)) problems.push("unrated similar: claims a rating it does not have");
      if (!/similar|मिलत|ਮਿਲਦ/.test(body)) problems.push("unrated similar: does not say it is only similar");
    }
    if (r.shows === "forced_greeting") {
      if (/Be careful/.test(body)) problems.push("forced greeting: shown the 'most messages like this are false' warning");
      if (lang === "en" && !/Hard to say/.test(body)) problems.push("forced greeting: not 'Hard to say'");
    }
    if (r.shows === "live_similar") {
      if (lang === "en" && !/looked at something similar/.test(body)) problems.push("live similar: the fact-check does not lead the card");
      if (/it is still hard to say/.test(body)) problems.push("live similar: still says hard to say");
      if ((main.match(/newsmeter\.in\/fact-check\/pineapple/g) || []).length > 1 + (main.includes('data-reply') ? 1 : 0))
        problems.push("live similar: the fact-check is listed twice");
    }
    if (r.shows === "live_verdict") {
      if (!main.includes("why-quote") || !main.includes("Hyderabad is the capital of Telangana.")) problems.push("live verdict: no quoted source sentence");
    } else if (r.shows !== "words_button" && /why-quote/.test(main)) problems.push("a quoted source sentence on a card that is not a live true/false answer");
    if (r.shows === "words_button") {
      if (!main.includes("words-btn") || !main.includes('data-premise="Hyderabad is the capital of Telangana. It is large."'))
        problems.push("words button: missing, or not carrying the judged premise");
    } else if (main.includes("words-btn")) problems.push("words button offered where there is no live verdict to explain");
    if (r.shows === "live_disagree") {
      if (lang === "en" && !/sources I found disagree/.test(body)) problems.push("live disagree: does not say the sources disagree");
      if (/Be careful/.test(body)) problems.push("live disagree: shown the generic warning");
    }
    if (r.shows === "greeting") {
      if (main.includes("act-force")) problems.push("greeting: offered 'Check it anyway'");
      if (!/greeting|अभिवादन|ਸਲਾਮ/.test(body)) problems.push("greeting: does not say it is a greeting");
    }
    if (r.shows === "live_careful") {
      if (lang === "en" && !/Be careful with this one/.test(body)) problems.push("live careful: lost the warning");
      if (lang === "en" && !/looked online too and still/.test(body)) problems.push("live careful: does not say it looked online");
      if (/it is still hard to say/.test(body)) problems.push("live careful: says hard to say");
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
// Which language a card answers in when the user has NOT used the language switch: the script of the
// message decides. Hindi or Punjabi typed in Latin letters is answered in English; Devanagari or
// Gurmukhi is answered in Hindi or Punjabi.
api.setAns(null); api.setS(STR.en);
const expectedLang = { fast_path: "en", romanized_hindi: "en", gurmukhi: "pa", claim_extraction: "en",
  not_a_claim: "en", abstained: "pa", live_verdict: "en", live_none: "en", similar: "en", similar_unrated: "en", forced_greeting: "en", live_similar: "en", live_careful: "en", greeting: "en", words_button: "en", live_disagree: "en" };
for (const r of data.responses) {
  const html = api.render(r.body);
  const got = (html.match(/<div class="card[^"]*" (?:id="[^"]*" )?lang="(\w+)"/) || [])[1];
  const ok = got === expectedLang[r.shows];
  console.log(`${ok ? "ok  " : "FAIL"} answers in ${got} (expected ${expectedLang[r.shows]}) for ${r.shows}: ${r.body.input.lang}/${r.body.input.script}`);
  if (!ok) bad++;
}
process.exit(bad ? 1 : 0);
