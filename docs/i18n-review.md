# Hindi and Punjabi UI strings: native-language review

Reviewed: 2026-10-02, by the project owner.

**Applied on 2026-10-02.** Every correction below is now in
`app/static/i18n/hi.json` and `pa.json`, exactly as given: 18 Hindi strings and
23 Punjabi strings. Every `{placeholder}` was checked to survive. Both files
record this review in `_comment`.

One consequence was carried into English. The review notes that "Alarming
language" changes the meaning of *Loaded language*, and the corrected Hindi and
Punjabi now say "inciting language" and "emotional language". So
`technique.Loaded_Language` in `en.json` is now "Emotionally loaded language",
and the three languages agree.

---

Every row was checked for meaning, grammatical naturalness, and a plain WhatsApp-style UI tone. The correction column is filled only where I would change the displayed wording.

Important: placeholders in `{braces}` are preserved.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| abstained_label | Not confident enough to judge | भरोसे से फ़ैसला नहीं कर सकते | ਭਰੋਸੇ ਨਾਲ ਫ਼ੈਸਲਾ ਨਹੀਂ ਕਰ ਸਕਦੇ | Hindi: फ़ैसला करने के लिए इतना भरोसा नहीं है \| Punjabi: ਫ਼ੈਸਲਾ ਕਰਨ ਲਈ ਕਾਫ਼ੀ ਭਰੋਸਾ ਨਹੀਂ ਹੈ |
| already_checked | Already checked by {publisher} | {publisher} पहले ही जाँच चुका है | {publisher} ਪਹਿਲਾਂ ਹੀ ਜਾਂਚ ਚੁੱਕਾ ਹੈ | Hindi: इसकी जाँच पहले ही {publisher} ने कर ली है \| Punjabi: ਇਸ ਦੀ ਜਾਂਚ ਪਹਿਲਾਂ ਹੀ {publisher} ਨੇ ਕਰ ਲਈ ਹੈ |
| band.High | High | ऊँचा | ਉੱਚਾ | Hindi: उच्च \| Punjabi: ਉੱਚ |
| band.Low | Low | कम | ਘੱਟ |  |
| band.Medium | Medium | मध्यम | ਦਰਮਿਆਨਾ |  |
| band_title | Confidence {value}, calibrated on the development set | भरोसा {value}, डेवलपमेंट सेट पर कैलिब्रेट किया गया | ਭਰੋਸਾ {value}, ਡਿਵੈਲਪਮੈਂਟ ਸੈੱਟ ਉੱਤੇ ਕੈਲੀਬ੍ਰੇਟ ਕੀਤਾ | Hindi: भरोसे का स्तर: {value}, डेवलपमेंट सेट पर कैलिब्रेट किया गया \| Punjabi: ਭਰੋਸੇ ਦਾ ਪੱਧਰ: {value}, ਡਿਵੈਲਪਮੈਂਟ ਸੈੱਟ 'ਤੇ ਕੈਲੀਬ੍ਰੇਟ ਕੀਤਾ ਗਿਆ |
| checking | Checking… | जाँच हो रही है… | ਜਾਂਚ ਹੋ ਰਹੀ ਹੈ… |  |
| cite_aria | Show source {n} | स्रोत {n} दिखाएँ | ਸਰੋਤ {n} ਵਿਖਾਓ | Punjabi: ਸਰੋਤ {n} ਵੇਖੋ |
| claim | Claim | दावा | ਦਾਅਵਾ |  |
| degraded | Some models are not loaded | कुछ मॉडल लोड नहीं हुए | ਕੁਝ ਮਾਡਲ ਲੋਡ ਨਹੀਂ ਹੋਏ |  |
| disclaimer | TruthLens can be wrong. Check the sources. | TruthLens ग़लत हो सकता है। स्रोत ज़रूर देखें। | TruthLens ਗ਼ਲਤ ਹੋ ਸਕਦਾ ਹੈ। ਸਰੋਤ ਜ਼ਰੂਰ ਵੇਖੋ। |  |
| empty | Message is empty | संदेश ख़ाली है | ਸੁਨੇਹਾ ਖ਼ਾਲੀ ਹੈ |  |
| error_server | TruthLens could not finish checking this message. | TruthLens इस संदेश की जाँच पूरी नहीं कर सका। | TruthLens ਇਸ ਸੁਨੇਹੇ ਦੀ ਜਾਂਚ ਪੂਰੀ ਨਹੀਂ ਕਰ ਸਕਿਆ। |  |
| explanation_fallback | Explanation in English — {lang} explanations aren't available yet. | व्याख्या अंग्रेज़ी में है — {lang} में व्याख्या अभी उपलब्ध नहीं है। | ਵਿਆਖਿਆ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਹੈ — {lang} ਵਿੱਚ ਵਿਆਖਿਆ ਅਜੇ ਉਪਲਬਧ ਨਹੀਂ। |  |
| forwarded | Forwarded | फ़ॉरवर्ड किया गया | ਅੱਗੇ ਭੇਜਿਆ |  |
| hide_evidence | Hide evidence ({n}) | सबूत छिपाएँ ({n}) | ਸਬੂਤ ਲੁਕਾਓ ({n}) |  |
| input_detected | {lang}, {script} script | {lang}, {script} लिपि | {lang}, {script} ਲਿਪੀ |  |
| input_translit | {lang}, typed in Roman script → converted to {script} | {lang}, रोमन लिपि में टाइप किया गया → {script} में बदला गया | {lang}, ਰੋਮਨ ਲਿਪੀ ਵਿੱਚ ਟਾਈਪ ਕੀਤਾ → {script} ਵਿੱਚ ਬਦਲਿਆ | Punjabi: {lang}, ਰੋਮਨ ਲਿਪੀ ਵਿੱਚ ਟਾਈਪ ਕੀਤਾ ਗਿਆ → {script} ਵਿੱਚ ਬਦਲਿਆ ਗਿਆ |
| intro | Paste a forwarded message. TruthLens checks it and shows you the sources. | कोई फ़ॉरवर्ड किया हुआ संदेश यहाँ चिपकाएँ। TruthLens उसे जाँचकर स्रोत दिखाएगा। | ਕੋਈ ਅੱਗੇ ਭੇਜਿਆ ਸੁਨੇਹਾ ਇੱਥੇ ਪਾਓ। TruthLens ਉਸਦੀ ਜਾਂਚ ਕਰਕੇ ਸਰੋਤ ਵਿਖਾਏਗਾ। | Hindi: फ़ॉरवर्ड किया हुआ संदेश यहाँ पेस्ट करें। TruthLens इसकी जाँच करके स्रोत दिखाएगा। \| Punjabi: ਫਾਰਵਰਡ ਕੀਤਾ ਸੁਨੇਹਾ ਇੱਥੇ ਪੇਸਟ ਕਰੋ। TruthLens ਇਸ ਦੀ ਜਾਂਚ ਕਰਕੇ ਸਰੋਤ ਦਿਖਾਏਗਾ। |
| lang_name.en | English | अंग्रेज़ी | ਅੰਗਰੇਜ਼ੀ |  |
| lang_name.hi | Hindi | हिंदी | ਹਿੰਦੀ |  |
| lang_name.pa | Punjabi | पंजाबी | ਪੰਜਾਬੀ |  |
| leaning | Leaning: {label} | झुकाव: {label} | ਝੁਕਾਅ: {label} | Hindi: रुझान: {label} \| Punjabi: ਰੁਝਾਨ: {label} |
| manipulation_title | Persuasion techniques spotted in the message. They never change the verdict. | संदेश में बहकाने के तरीक़े दिखे। इनसे फ़ैसला नहीं बदलता। | ਸੁਨੇਹੇ ਵਿੱਚ ਭਰਮਾਉਣ ਦੇ ਤਰੀਕੇ ਦਿਸੇ। ਇਹ ਫ਼ੈਸਲਾ ਨਹੀਂ ਬਦਲਦੇ। | Hindi: संदेश में मनाने के कुछ तरीके दिखे। इनसे फ़ैसला नहीं बदलता। \| Punjabi: ਸੁਨੇਹੇ ਵਿੱਚ ਮਨਾਉਣ ਦੇ ਕੁਝ ਤਰੀਕੇ ਦਿਸੇ। ਇਹ ਫ਼ੈਸਲਾ ਨਹੀਂ ਬਦਲਦੇ। |
| models_ready | Models ready | मॉडल तैयार हैं | ਮਾਡਲ ਤਿਆਰ ਹਨ |  |
| notaclaim_note | TruthLens only checks factual claims. Greetings, opinions and predictions have nothing to verify. | TruthLens केवल तथ्यात्मक दावों की जाँच करता है। शुभकामनाओं, राय और भविष्यवाणियों में जाँचने को कुछ नहीं होता। | TruthLens ਸਿਰਫ਼ ਤੱਥਾਂ ਵਾਲੇ ਦਾਅਵਿਆਂ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੈ। ਸ਼ੁਭਕਾਮਨਾਵਾਂ, ਰਾਏ ਅਤੇ ਭਵਿੱਖਬਾਣੀਆਂ ਵਿੱਚ ਜਾਂਚਣ ਲਈ ਕੁਝ ਨਹੀਂ ਹੁੰਦਾ। | Hindi: TruthLens केवल तथ्यात्मक दावों की जाँच करता है। अभिवादन, राय और भविष्यवाणियों की जाँच नहीं की जाती। \| Punjabi: TruthLens ਸਿਰਫ਼ ਤੱਥਾਂ ਵਾਲੇ ਦਾਅਵਿਆਂ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੈ। ਸਲਾਮ-ਦੁਆ, ਰਾਏ ਅਤੇ ਭਵਿੱਖਬਾਣੀਆਂ ਦੀ ਜਾਂਚ ਨਹੀਂ ਕੀਤੀ ਜਾਂਦੀ। |
| path_evidence | Checked against evidence | सबूतों से जाँचा गया | ਸਬੂਤਾਂ ਨਾਲ ਜਾਂਚਿਆ | Hindi: सबूतों के आधार पर जाँचा गया \| Punjabi: ਸਬੂਤਾਂ ਦੇ ਆਧਾਰ 'ਤੇ ਜਾਂਚਿਆ ਗਿਆ |
| path_factcheck | Already checked by {publisher} | {publisher} पहले ही जाँच चुका है | {publisher} ਪਹਿਲਾਂ ਹੀ ਜਾਂਚ ਚੁੱਕਾ ਹੈ | Hindi: इसकी जाँच पहले ही {publisher} ने कर ली है \| Punjabi: ਇਸ ਦੀ ਜਾਂਚ ਪਹਿਲਾਂ ਹੀ {publisher} ਨੇ ਕਰ ਲਈ ਹੈ |
| placeholder | Paste a forwarded message… | फ़ॉरवर्ड किया हुआ संदेश… | ਅੱਗੇ ਭੇਜਿਆ ਸੁਨੇਹਾ… |  |
| retry | Retry | फिर से कोशिश करें | ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ |  |
| samples_label | Try an example | कोई उदाहरण आज़माएँ | ਕੋਈ ਉਦਾਹਰਨ ਅਜ਼ਮਾਓ |  |
| script_name.deva | Devanagari | देवनागरी | ਦੇਵਨਾਗਰੀ |  |
| script_name.guru | Gurmukhi | गुरमुखी | ਗੁਰਮੁਖੀ |  |
| script_name.latn | Latin | रोमन | ਰੋਮਨ |  |
| see_evidence | See evidence ({n}) | सबूत देखें ({n}) | ਸਬੂਤ ਵੇਖੋ ({n}) | Punjabi: ਸਬੂਤ ਵੇਖੋ ({n}) |
| send | Send | भेजें | ਭੇਜੋ |  |
| stage_trace | Stage trace | चरण विवरण | ਪੜਾਅ ਵੇਰਵਾ | Hindi: चरणों का विवरण \| Punjabi: ਪੜਾਵਾਂ ਦਾ ਵੇਰਵਾ |
| stance.Neutral | Neutral | तटस्थ | ਨਿਰਪੱਖ |  |
| stance.Refutes | Refutes | खंडन | ਖੰਡਨ |  |
| stance.Supports | Supports | समर्थन | ਹਮਾਇਤ | Punjabi: ਸਮਰਥਨ |
| technique.Appeal_to_Authority | Appeal to authority | अधिकार का हवाला | ਅਧਿਕਾਰੀ ਦਾ ਹਵਾਲਾ | Hindi: किसी विशेषज्ञ या अधिकारी का हवाला \| Punjabi: ਕਿਸੇ ਮਾਹਿਰ ਜਾਂ ਅਧਿਕਾਰੀ ਦਾ ਹਵਾਲਾ |
| technique.Appeal_to_Fear-Prejudice | Fear appeal | डर दिखाना | ਡਰ ਵਿਖਾਉਣਾ |  |
| technique.Appeal_to_Popularity | "Everyone says so" | "सब यही कहते हैं" | "ਸਾਰੇ ਇਹੀ ਕਹਿੰਦੇ ਹਨ" |  |
| technique.Appeal_to_Time | Pressure to act fast | जल्दबाज़ी का दबाव | ਕਾਹਲੀ ਦਾ ਦਬਾਅ | Hindi: जल्दी करने का दबाव \| Punjabi: ਜਲਦੀ ਕਰਨ ਦਾ ਦਬਾਅ |
| technique.Exaggeration-Minimisation | Exaggeration | अतिशयोक्ति | ਵਧਾ-ਚੜ੍ਹਾ ਕੇ ਕਹਿਣਾ | Hindi: बढ़ा-चढ़ाकर कहना |
| technique.Loaded_Language | Alarming language | डराने वाली भाषा | ਡਰਾਉਣੀ ਭਾਸ਼ਾ | Hindi: उकसाने वाली भाषा \| Punjabi: ਭਾਵਨਾਤਮਕ ਭਾਸ਼ਾ |
| technique.Repetition | Repetition | दोहराव | ਦੁਹਰਾਅ |  |
| template_note | Couldn't generate an explanation that the sources back up, so this one lists them directly. | स्रोतों से पुष्ट होने वाली व्याख्या नहीं बन सकी, इसलिए यहाँ सीधे स्रोत दिए गए हैं। | ਸਰੋਤਾਂ ਨਾਲ ਪੁਸ਼ਟ ਹੋਣ ਵਾਲੀ ਵਿਆਖਿਆ ਨਹੀਂ ਬਣ ਸਕੀ, ਇਸ ਲਈ ਇੱਥੇ ਸਿੱਧੇ ਸਰੋਤ ਦਿੱਤੇ ਹਨ। | Hindi: स्रोतों के आधार पर व्याख्या तैयार नहीं हो सकी, इसलिए यहाँ सीधे स्रोत दिए गए हैं। \| Punjabi: ਸਰੋਤਾਂ ਦੇ ਆਧਾਰ 'ਤੇ ਵਿਆਖਿਆ ਨਹੀਂ ਬਣ ਸਕੀ, ਇਸ ਲਈ ਇੱਥੇ ਸਿੱਧੇ ਸਰੋਤ ਦਿੱਤੇ ਹਨ। |
| title | TruthLens | TruthLens | TruthLens |  |
| too_long | Message is too long (4,000 characters at most) | संदेश बहुत लंबा है (अधिकतम 4,000 अक्षर) | ਸੁਨੇਹਾ ਬਹੁਤ ਲੰਮਾ ਹੈ (ਵੱਧ ਤੋਂ ਵੱਧ 4,000 ਅੱਖਰ) |  |
| unchecked | {n} more claims in this message were not checked | इस संदेश के {n} और दावे नहीं जाँचे गए | ਇਸ ਸੁਨੇਹੇ ਦੇ {n} ਹੋਰ ਦਾਅਵੇ ਨਹੀਂ ਜਾਂਚੇ ਗਏ |  |
| unchecked_one | 1 more claim in this message was not checked | इस संदेश का 1 और दावा नहीं जाँचा गया | ਇਸ ਸੁਨੇਹੇ ਦਾ 1 ਹੋਰ ਦਾਅਵਾ ਨਹੀਂ ਜਾਂਚਿਆ ਗਿਆ |  |
| unreachable | API unreachable | API से संपर्क नहीं हो पा रहा | API ਨਾਲ ਸੰਪਰਕ ਨਹੀਂ ਹੋ ਰਿਹਾ |  |
| unsupported | TruthLens works with English, Hindi and Punjabi. | TruthLens अंग्रेज़ी, हिंदी और पंजाबी में काम करता है। | TruthLens ਅੰਗਰੇਜ਼ੀ, ਹਿੰਦੀ ਅਤੇ ਪੰਜਾਬੀ ਵਿੱਚ ਕੰਮ ਕਰਦਾ ਹੈ। |  |
| verdict.Conflicting | Evidence disagrees | सबूत आपस में टकराते हैं | ਸਬੂਤ ਆਪਸ ਵਿੱਚ ਟਕਰਾਉਂਦੇ ਹਨ |  |
| verdict.NEI | Not enough evidence | पर्याप्त सबूत नहीं | ਲੋੜੀਂਦੇ ਸਬੂਤ ਨਹੀਂ | Punjabi: ਕਾਫ਼ੀ ਸਬੂਤ ਨਹੀਂ |
| verdict.NotAClaim | Nothing here to fact-check | इसमें जाँचने लायक कोई दावा नहीं है | ਇਸ ਵਿੱਚ ਜਾਂਚਣ ਯੋਗ ਕੋਈ ਦਾਅਵਾ ਨਹੀਂ | Punjabi: ਇੱਥੇ ਤੱਥ-ਜਾਂਚ ਕਰਨ ਲਈ ਕੋਈ ਦਾਅਵਾ ਨਹੀਂ |
| verdict.Refuted | Contradicted by evidence | सबूतों से खंडित | ਸਬੂਤਾਂ ਨਾਲ ਖੰਡਿਤ | Hindi: सबूत इसका खंडन करते हैं \| Punjabi: ਸਬੂਤ ਇਸ ਦਾ ਖੰਡਨ ਕਰਦੇ ਹਨ |
| verdict.Supported | Supported by evidence | सबूतों से पुष्ट | ਸਬੂਤਾਂ ਨਾਲ ਪੁਸ਼ਟ | Hindi: सबूत इसका समर्थन करते हैं \| Punjabi: ਸਬੂਤ ਇਸ ਦਾ ਸਮਰਥਨ ਕਰਦੇ ਹਨ |
| verdict_aria | Verdict: {label} | फ़ैसला: {label} | ਫ਼ੈਸਲਾ: {label} |  |

## Main review findings

Most strings are already understandable and usable. The clearest fixes are:

- Remove gender assumptions around `{publisher}` by using neutral constructions.
- Prefer everyday UI wording such as “रुझान”, “पेस्ट करें”, and “सबूत इसका समर्थन/खंडन करते हैं”.
- Avoid wording that changes the meaning of a technique, especially “Loaded language” → “डराने वाली भाषा”.
- In Punjabi, use more natural forms such as “ਵੇਖੋ”, “ਫਾਰਵਰਡ ਕੀਤਾ”, “ਕਾਫ਼ੀ ਸਬੂਤ ਨਹੀਂ”, and “ਪੜਾਵਾਂ ਦਾ ਵੇਰਵਾ”.
- Keep the evidence-focused framing: the interface should describe what the evidence shows rather than imply an absolute true/false judgment.

---

## Live search strings: REVIEWED and applied (added and reviewed 2026-10-04)

Machine-drafted, then reviewed by the owner on 2026-10-04: 3 strings corrected
(`live_checking`, `live_used` Punjabi, `live_uncalibrated`), the other 7 kept as
written. The table shows the drafts; the corrected text is in
`app/static/i18n/hi.json` and `pa.json`. `{sources}` is filled in by the app.
Reason for the third: the English says "calibrated", and "जाँचा-परखा / ਪਰਖਿਆ"
would change that technical meaning to "tested".

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `live_button` | Search Wikipedia & fact-checkers | विकिपीडिया और फ़ैक्ट-चेकर्स में खोजें | ਵਿਕੀਪੀਡੀਆ ਅਤੇ ਫ਼ੈਕਟ-ਚੈਕਰਾਂ ਵਿੱਚ ਖੋਜੋ | |
| `live_privacy` | This sends the claim to Wikipedia and Google Fact Check. | यह दावा विकिपीडिया और Google Fact Check को भेजा जाएगा। | ਇਹ ਦਾਅਵਾ ਵਿਕੀਪੀਡੀਆ ਅਤੇ Google Fact Check ਨੂੰ ਭੇਜਿਆ ਜਾਵੇਗਾ। | |
| `live_checking` | Searching online… | ऑनलाइन खोजा जा रहा है… | ਆਨਲਾਈਨ ਖੋਜ ਹੋ ਰਹੀ ਹੈ… | |
| `live_used` | Checked online against: {sources} | ऑनलाइन स्रोतों से जाँचा गया: {sources} | ਆਨਲਾਈਨ ਸਰੋਤਾਂ ਤੋਂ ਜਾਂਚਿਆ ਗਿਆ: {sources} | |
| `live_unavailable` | Online search isn't available right now, so the earlier answer stays. | ऑनलाइन खोज अभी उपलब्ध नहीं है, इसलिए पहले वाला नतीजा ही दिख रहा है। | ਆਨਲਾਈਨ ਖੋਜ ਹੁਣ ਉਪਲਬਧ ਨਹੀਂ, ਇਸ ਲਈ ਪਹਿਲਾਂ ਵਾਲਾ ਨਤੀਜਾ ਹੀ ਦਿਖ ਰਿਹਾ ਹੈ। | |
| `live_attribution` | Wikipedia text is available under CC BY-SA 4.0. | विकिपीडिया का पाठ CC BY-SA 4.0 लाइसेंस के तहत उपलब्ध है। | ਵਿਕੀਪੀਡੀਆ ਦਾ ਪਾਠ CC BY-SA 4.0 ਲਾਇਸੈਂਸ ਅਧੀਨ ਉਪਲਬਧ ਹੈ। | |
| `live_uncalibrated` | Confidence for online results has not been calibrated. | ऑनलाइन नतीजों के लिए भरोसे का स्तर जाँचा-परखा नहीं गया है। | ਆਨਲਾਈਨ ਨਤੀਜਿਆਂ ਲਈ ਭਰੋਸੇ ਦਾ ਪੱਧਰ ਪਰਖਿਆ ਨਹੀਂ ਗਿਆ। | |
| `source_name.wikipedia` | Wikipedia | विकिपीडिया | ਵਿਕੀਪੀਡੀਆ | |
| `source_name.factcheck_live` | Fact-check (live) | फ़ैक्ट-चेक (ऑनलाइन) | ਫ਼ੈਕਟ-ਚੈਕ (ਆਨਲਾਈਨ) | |
| `source_name.google_factcheck` | Google Fact Check | Google Fact Check | Google Fact Check | |

---

## Live verdict strings: REVIEWED and applied (added and reviewed 2026-10-05)

Machine-drafted, then reviewed by the owner on 2026-10-05: **all 3 corrected**, none kept. The
table shows the drafts; the corrected text is in `app/static/i18n/hi.json` and `pa.json`. The
numbers in `live_validated` (350 claims, 94%, 3 in 10) come from the pre-registered test in
`docs/live-fever-protocol-2.md` and must change together with it. Reasons given: "से निकला /
ਤੋਂ ਆਇਆ" read as literal and "जिनका सहमत होना / ਜਿਨ੍ਹਾਂ ਦਾ ਸਹਿਮਤ ਹੋਣਾ" as unnatural (now "पर आधारित /
'ਤੇ ਆਧਾਰਿਤ" and "दोनों का सहमत होना / ਦੋਵਾਂ ਦੀ ਸਹਿਮਤੀ"); "जब यह नतीजा देता था / ਜਦੋਂ ਇਹ ਨਤੀਜਾ ਦਿੰਦਾ
ਸੀ" read as machine-like (the conditional is now explicit, figures unchanged); "उन्हें / ਉਨ੍ਹਾਂ ਨੂੰ"
added so "were not sure enough" is explicit.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `live_verdict_basis` | This verdict comes from Wikipedia text, read by two models that had to agree. | यह नतीजा विकिपीडिया के पाठ से निकला है, जिसे दो मॉडलों ने पढ़ा और जिनका सहमत होना ज़रूरी था। | ਇਹ ਨਤੀਜਾ ਵਿਕੀਪੀਡੀਆ ਦੇ ਪਾਠ ਤੋਂ ਆਇਆ ਹੈ, ਜਿਸਨੂੰ ਦੋ ਮਾਡਲਾਂ ਨੇ ਪੜ੍ਹਿਆ ਅਤੇ ਜਿਨ੍ਹਾਂ ਦਾ ਸਹਿਮਤ ਹੋਣਾ ਲਾਜ਼ਮੀ ਸੀ। | |
| `live_validated` | In a test on 350 claims it was right 94% of the time when it gave a verdict, and it gave one for only about 3 claims in 10. | 350 दावों के परीक्षण में, जब यह नतीजा देता था तो लगभग 94% बार सही था, और यह करीब 10 में से 3 दावों पर ही नतीजा देता था। | 350 ਦਾਅਵਿਆਂ ਦੇ ਟੈਸਟ ਵਿੱਚ, ਜਦੋਂ ਇਹ ਨਤੀਜਾ ਦਿੰਦਾ ਸੀ ਤਾਂ ਲਗਭਗ 94% ਵਾਰ ਸਹੀ ਸੀ, ਅਤੇ ਇਹ ਲਗਭਗ 10 ਵਿੱਚੋਂ 3 ਦਾਅਵਿਆਂ ਉੱਤੇ ਹੀ ਨਤੀਜਾ ਦਿੰਦਾ ਸੀ। | |
| `live_no_verdict` | The two models did not agree, or were not sure enough, so there is no verdict. Read the sources. | दोनों मॉडल सहमत नहीं हुए या पर्याप्त भरोसा नहीं था, इसलिए कोई नतीजा नहीं दिया गया। स्रोत पढ़ें। | ਦੋਵੇਂ ਮਾਡਲ ਸਹਿਮਤ ਨਹੀਂ ਹੋਏ ਜਾਂ ਕਾਫ਼ੀ ਭਰੋਸਾ ਨਹੀਂ ਸੀ, ਇਸ ਲਈ ਕੋਈ ਨਤੀਜਾ ਨਹੀਂ ਦਿੱਤਾ ਗਿਆ। ਸਰੋਤ ਵੇਖੋ। | |

---

## Plain-language card strings: REVIEWED and applied (added and reviewed 2026-10-05)

**Reviewed by the owner on 2026-10-05, and every open point decided the same day.** The table below shows
the machine drafts; the corrected text is in `app/static/i18n/hi.json` and `pa.json`. Decisions:

1. **`plain.flags` is kept as drafted** ("यह संदेश {list} की कोशिश करता है।" / "ਇਹ ਸੁਨੇਹਾ {list} ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰਦਾ
   ਹੈ।"): the approved `plain.technique.*` phrases are infinitives and fit exactly this pattern.
2. **Punjabi `plain.sure.Medium` is "ਮੈਨੂੰ ਠੀਕ-ਠਾਕ ਭਰੋਸਾ ਹੈ।"**, distinct from High ("ਮੈਨੂੰ ਕਾਫ਼ੀ ਭਰੋਸਾ ਹੈ।") and Low,
   so there are three clear levels.
3. **The helper is gender-neutral.** The masculine forms ("कह सकता", "कर पाया", "ਕਹਿ ਸਕਦਾ", "ਕਰ ਸਕਿਆ") were
   replaced in `plain.reason.abstained_Supported`, `plain.reason.abstained_Refuted` and `plain.reply.check`
   ("इसे पक्का कहने लायक भरोसा नहीं है", "इसकी पुष्टि नहीं हो पाई", "ਇਸ ਦੀ ਪੁਸ਼ਟੀ ਨਹੀਂ ਹੋ ਸਕੀ").

**Answer language (decided 2026-10-05).** The card answers in Hindi or Punjabi only when the message
is written in Devanagari or Gurmukhi. Hindi or Punjabi typed in Latin letters ("Kal se WhatsApp ke paise
lagenge") is answered in English. There are no language buttons on the page (removed at the owner's request): the page follows the
browser's language, and an answer never depends on anything the reader pressed.

The card ordinary readers see (docs/specs/UI_UX.md section 5) is written in plain words and in the
reader's own language, so these strings matter more than any other in the app: they are what a
parent or grandparent reads. Machine-drafted by the assistant; please correct anything that is not
how a native speaker would say it.

**How to read the sheet.** The card speaks as "I" (a helper), says "probably" and "the sources I
found" (it reports what sources say, never the truth), and always ends with what to do. Keep that:
`{publisher}`, `{url}`, `{lang}` and `{list}` are filled in by the app. `plain.flags` is
completed by `plain.technique.*`: "This message tries to *scare you, make you hurry*": the technique
phrases are infinitives that fit after "tries to" (Hindi "की कोशिश करता है", Punjabi "ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰਦਾ ਹੈ"),
so keep that grammar. First-person verbs should stay gender-neutral. Prefer everyday words
(सबूत, स्रोत, जाँच; ਸਬੂਤ, ਸਰੋਤ, ਜਾਂਚ) over formal ones.

Four existing strings were also reworded to be simpler (`intro`, `live_button`, `live_privacy`,
`stage_trace`). The older reviewed wording of those is in the sections above.

After you correct, apply the corrections to `app/static/i18n/hi.json` and `pa.json` and remove the
"PLAIN-LANGUAGE CARD ... NOT YET REVIEWED" sentence from their `_comment`.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `intro` | Paste a message someone forwarded to you, then press the arrow. You will see whether it looks true or false, and why. | जो संदेश आपको किसी ने भेजा है, उसे यहाँ पेस्ट करें और तीर दबाएँ। आपको दिखेगा कि वह सच लगता है या झूठ, और क्यों। | ਜੋ ਸੁਨੇਹਾ ਤੁਹਾਨੂੰ ਕਿਸੇ ਨੇ ਭੇਜਿਆ ਹੈ, ਉਹ ਇੱਥੇ ਪੇਸਟ ਕਰੋ ਅਤੇ ਤੀਰ ਦਬਾਓ। ਤੁਹਾਨੂੰ ਦਿਖੇਗਾ ਕਿ ਉਹ ਸੱਚ ਲੱਗਦਾ ਹੈ ਜਾਂ ਝੂਠ, ਅਤੇ ਕਿਉਂ। | |
| `live_button` | Look this up online | इसे ऑनलाइन देखें | ਇਸਨੂੰ ਆਨਲਾਈਨ ਵੇਖੋ | |
| `live_privacy` | This sends only this claim to Wikipedia and Google. | इससे सिर्फ़ यही दावा विकिपीडिया और Google को भेजा जाएगा। | ਇਸ ਨਾਲ ਸਿਰਫ਼ ਇਹੀ ਦਾਅਵਾ ਵਿਕੀਪੀਡੀਆ ਅਤੇ Google ਨੂੰ ਭੇਜਿਆ ਜਾਵੇਗਾ। | |
| `stage_trace` | Technical trace (for engineers) | तकनीकी ब्योरा (इंजीनियरों के लिए) | ਤਕਨੀਕੀ ਵੇਰਵਾ (ਇੰਜੀਨੀਅਰਾਂ ਲਈ) | |
| `plain.title.Refuted` | Probably FALSE | संभवतः झूठ | ਸ਼ਾਇਦ ਝੂਠ | |
| `plain.title.Supported` | Probably TRUE | संभवतः सच | ਸ਼ਾਇਦ ਸੱਚ | |
| `plain.title.Conflicting` | The sources disagree | स्रोत आपस में सहमत नहीं | ਸਰੋਤ ਆਪਸ ਵਿੱਚ ਸਹਿਮਤ ਨਹੀਂ | |
| `plain.title.NEI` | Not enough to decide | फ़ैसला करने लायक सबूत नहीं | ਫ਼ੈਸਲਾ ਕਰਨ ਜੋਗੇ ਸਬੂਤ ਨਹੀਂ | |
| `plain.title.abstained` | Hard to say | पक्का कहना मुश्किल है | ਪੱਕਾ ਕਹਿਣਾ ਔਖਾ ਹੈ | |
| `plain.fast_title.Refuted` | Fact-checkers say: FALSE | फ़ैक्ट-चेकर कहते हैं: झूठ | ਫ਼ੈਕਟ-ਚੈਕਰ ਕਹਿੰਦੇ ਹਨ: ਝੂਠ | |
| `plain.fast_title.Supported` | Fact-checkers say: TRUE | फ़ैक्ट-चेकर कहते हैं: सच | ਫ਼ੈਕਟ-ਚੈਕਰ ਕਹਿੰਦੇ ਹਨ: ਸੱਚ | |
| `plain.fast_title.Conflicting` | Fact-checkers say: partly true or misleading | फ़ैक्ट-चेकर कहते हैं: आंशिक सच या भ्रामक | ਫ਼ੈਕਟ-ਚੈਕਰ ਕਹਿੰਦੇ ਹਨ: ਅੱਧਾ ਸੱਚ ਜਾਂ ਭਰਮਾਉਣ ਵਾਲਾ | |
| `plain.fast_title.NEI` | Fact-checkers could not settle it | फ़ैक्ट-चेकर भी तय नहीं कर पाए | ਫ਼ੈਕਟ-ਚੈਕਰ ਵੀ ਤੈਅ ਨਹੀਂ ਕਰ ਸਕੇ | |
| `plain.reason.fast` | {publisher} has already checked this message. | {publisher} इस संदेश की जाँच पहले ही कर चुका है। | {publisher} ਨੇ ਇਹ ਸੁਨੇਹਾ ਪਹਿਲਾਂ ਹੀ ਜਾਂਚ ਲਿਆ ਹੈ। | |
| `plain.reason.Refuted` | The sources I found say this is not right. | मुझे जो स्रोत मिले, वे कहते हैं कि यह बात सही नहीं है। | ਮੈਨੂੰ ਜੋ ਸਰੋਤ ਮਿਲੇ, ਉਹ ਕਹਿੰਦੇ ਹਨ ਕਿ ਇਹ ਗੱਲ ਠੀਕ ਨਹੀਂ ਹੈ। | |
| `plain.reason.Supported` | The sources I found agree with this. | मुझे जो स्रोत मिले, वे इस बात से सहमत हैं। | ਮੈਨੂੰ ਜੋ ਸਰੋਤ ਮਿਲੇ, ਉਹ ਇਸ ਗੱਲ ਨਾਲ ਸਹਿਮਤ ਹਨ। | |
| `plain.reason.Conflicting` | The sources I found do not agree with each other. | मुझे जो स्रोत मिले, वे आपस में सहमत नहीं हैं। | ਮੈਨੂੰ ਜੋ ਸਰੋਤ ਮਿਲੇ, ਉਹ ਆਪਸ ਵਿੱਚ ਸਹਿਮਤ ਨਹੀਂ ਹਨ। | |
| `plain.reason.NEI` | I could not find enough to decide. | फ़ैसला करने के लिए मुझे पर्याप्त जानकारी नहीं मिली। | ਫ਼ੈਸਲਾ ਕਰਨ ਲਈ ਮੈਨੂੰ ਕਾਫ਼ੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ। | |
| `plain.reason.abstained_Supported` | It looks true, but I am not sure. | यह सच लगता है, लेकिन मैं पक्का नहीं हूँ। | ਇਹ ਸੱਚ ਲੱਗਦਾ ਹੈ, ਪਰ ਮੈਨੂੰ ਪੱਕਾ ਨਹੀਂ ਪਤਾ। | |
| `plain.reason.abstained_Refuted` | It looks false, but I am not sure. | यह झूठ लगता है, लेकिन मैं पक्का नहीं हूँ। | ਇਹ ਝੂਠ ਲੱਗਦਾ ਹੈ, ਪਰ ਮੈਨੂੰ ਪੱਕਾ ਨਹੀਂ ਪਤਾ। | |
| `plain.reason.abstained_other` | I could not find enough to be sure. | पक्का कहने के लिए मुझे पर्याप्त जानकारी नहीं मिली। | ਪੱਕਾ ਕਹਿਣ ਲਈ ਮੈਨੂੰ ਕਾਫ਼ੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ। | |
| `plain.reason.live_none` | I looked online too, and it is still hard to say. Here is what I found. | मैंने ऑनलाइन भी देखा, फिर भी पक्का कहना मुश्किल है। जो मिला, वह नीचे है। | ਮੈਂ ਆਨਲਾਈਨ ਵੀ ਵੇਖਿਆ, ਫਿਰ ਵੀ ਪੱਕਾ ਕਹਿਣਾ ਔਖਾ ਹੈ। ਜੋ ਮਿਲਿਆ, ਉਹ ਹੇਠਾਂ ਹੈ। | |
| `plain.reason.live_Supported` | I looked it up online and the sources agree with this. | मैंने ऑनलाइन देखा और स्रोत इस बात से सहमत हैं। | ਮੈਂ ਆਨਲਾਈਨ ਵੇਖਿਆ ਅਤੇ ਸਰੋਤ ਇਸ ਗੱਲ ਨਾਲ ਸਹਿਮਤ ਹਨ। | |
| `plain.reason.live_Refuted` | I looked it up online and the sources say this is not right. | मैंने ऑनलाइन देखा और स्रोत कहते हैं कि यह बात सही नहीं है। | ਮੈਂ ਆਨਲਾਈਨ ਵੇਖਿਆ ਅਤੇ ਸਰੋਤ ਕਹਿੰਦੇ ਹਨ ਕਿ ਇਹ ਗੱਲ ਠੀਕ ਨਹੀਂ ਹੈ। | |
| `plain.action.Refuted` | Please don't forward it. | कृपया इसे आगे न भेजें। | ਕਿਰਪਾ ਕਰਕੇ ਇਸਨੂੰ ਅੱਗੇ ਨਾ ਭੇਜੋ। | |
| `plain.action.Supported` | It looks true, but check the source before you forward it. | यह सच लगता है, पर आगे भेजने से पहले स्रोत देख लें। | ਇਹ ਸੱਚ ਲੱਗਦਾ ਹੈ, ਪਰ ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਸਰੋਤ ਵੇਖ ਲਵੋ। | |
| `plain.action.check` | Please check before you forward it. | आगे भेजने से पहले कृपया जाँच लें। | ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਰਪਾ ਕਰਕੇ ਜਾਂਚ ਲਵੋ। | |
| `plain.sure.High` | I am quite sure. | मुझे काफ़ी भरोसा है। | ਮੈਨੂੰ ਕਾਫ਼ੀ ਭਰੋਸਾ ਹੈ। | |
| `plain.sure.Medium` | I am fairly sure. | मुझे ठीक-ठाक भरोसा है। | ਮੈਨੂੰ ਠੀਕ-ਠਾਕ ਭਰੋਸਾ ਹੈ। | |
| `plain.sure.Low` | I am not very sure. | मुझे ज़्यादा भरोसा नहीं है। | ਮੈਨੂੰ ਬਹੁਤਾ ਭਰੋਸਾ ਨਹੀਂ ਹੈ। | |
| `plain.none_title` | Nothing to check here | यहाँ जाँचने लायक कुछ नहीं है | ਇੱਥੇ ਜਾਂਚਣ ਵਾਲਾ ਕੁਝ ਨਹੀਂ | |
| `plain.none_note` | This looks like a greeting or an opinion, not something that can be checked. | यह नमस्ते जैसा संदेश या कोई राय लगती है, ऐसी बात नहीं जिसकी जाँच हो सके। | ਇਹ ਨਮਸਕਾਰ ਵਰਗਾ ਸੁਨੇਹਾ ਜਾਂ ਕੋਈ ਰਾਇ ਲੱਗਦੀ ਹੈ, ਅਜਿਹੀ ਗੱਲ ਨਹੀਂ ਜਿਸਦੀ ਜਾਂਚ ਹੋ ਸਕੇ। | |
| `plain.claim_label` | I checked this claim: | मैंने यह दावा जाँचा: | ਮੈਂ ਇਹ ਦਾਅਵਾ ਜਾਂਚਿਆ: | |
| `plain.sources_label` | Where this comes from: | यह जानकारी यहाँ से आई है: | ਇਹ ਜਾਣਕਾਰੀ ਇੱਥੋਂ ਆਈ ਹੈ: | |
| `plain.found_label` | What I found: | जो मुझे मिला: | ਜੋ ਮੈਨੂੰ ਮਿਲਿਆ: | |
| `plain.listen` | Listen | सुनें | ਸੁਣੋ | |
| `plain.listen_stop` | Stop | रोकें | ਰੋਕੋ | |
| `plain.listen_none` | This device has no {lang} voice. | इस डिवाइस में {lang} आवाज़ नहीं है। | ਇਸ ਡਿਵਾਈਸ ਵਿੱਚ {lang} ਆਵਾਜ਼ ਨਹੀਂ ਹੈ। | |
| `plain.copy` | Copy a reply | जवाब कॉपी करें | ਜਵਾਬ ਕਾਪੀ ਕਰੋ | |
| `plain.copied` | Copied | कॉपी हो गया | ਕਾਪੀ ਹੋ ਗਿਆ | |
| `plain.copy_failed` | Could not copy. Please select the text yourself. | कॉपी नहीं हो सका। कृपया लिखा हुआ ख़ुद चुनकर कॉपी करें। | ਕਾਪੀ ਨਹੀਂ ਹੋ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਲਿਖਿਆ ਹੋਇਆ ਆਪ ਚੁਣ ਕੇ ਕਾਪੀ ਕਰੋ। | |
| `plain.details` | Details | ब्योरा | ਵੇਰਵਾ | |
| `plain.flags` | This message tries to {list}. | यह संदेश {list} की कोशिश करता है। | ਇਹ ਸੁਨੇਹਾ {list} ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰਦਾ ਹੈ। | |
| `plain.reply.Refuted` | I checked this message with TruthLens: it looks FALSE. Please don't forward it. | मैंने यह संदेश TruthLens से जाँचा: यह झूठ लगता है। कृपया इसे आगे न भेजें। | ਮੈਂ ਇਹ ਸੁਨੇਹਾ TruthLens ਨਾਲ ਜਾਂਚਿਆ: ਇਹ ਝੂਠ ਲੱਗਦਾ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਇਸਨੂੰ ਅੱਗੇ ਨਾ ਭੇਜੋ। | |
| `plain.reply.Supported` | I checked this message with TruthLens: it looks true. Please check the source before you forward it. | मैंने यह संदेश TruthLens से जाँचा: यह सच लगता है। आगे भेजने से पहले स्रोत देख लें। | ਮੈਂ ਇਹ ਸੁਨੇਹਾ TruthLens ਨਾਲ ਜਾਂਚਿਆ: ਇਹ ਸੱਚ ਲੱਗਦਾ ਹੈ। ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਸਰੋਤ ਵੇਖ ਲਵੋ। | |
| `plain.reply.check` | I checked this message with TruthLens: I could not confirm it. Please check before you forward it. | मैंने यह संदेश TruthLens से जाँचा: मैं इसकी पुष्टि नहीं कर सका। आगे भेजने से पहले कृपया जाँच लें। | ਮੈਂ ਇਹ ਸੁਨੇਹਾ TruthLens ਨਾਲ ਜਾਂਚਿਆ: ਮੈਂ ਇਸਦੀ ਪੁਸ਼ਟੀ ਨਹੀਂ ਕਰ ਸਕਿਆ। ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਰਪਾ ਕਰਕੇ ਜਾਂਚ ਲਵੋ। | |
| `plain.reply.source` | More: {url} | और जानकारी: {url} | ਹੋਰ ਜਾਣਕਾਰੀ: {url} | |
| `plain.technique.Appeal_to_Time` | make you hurry | जल्दबाज़ी करवाने | ਕਾਹਲੀ ਕਰਵਾਉਣ | |
| `plain.technique.Appeal_to_Authority` | say an important person or group agrees | किसी बड़े व्यक्ति या संस्था का नाम लेकर मनवाने | ਵੱਡੇ ਨਾਮ ਦੇ ਸਹਾਰੇ ਮਨਵਾਉਣ | |
| `plain.technique.Appeal_to_Popularity` | say everyone believes it | 'सब यही मानते हैं' कहकर मनवाने | 'ਸਭ ਇਹੀ ਮੰਨਦੇ ਹਨ' ਕਹਿ ਕੇ ਮਨਵਾਉਣ | |
| `plain.technique.Loaded_Language` | stir up strong feelings | भावनाएँ भड़काने | ਜਜ਼ਬਾਤ ਭੜਕਾਉਣ | |
| `plain.technique.Repetition` | repeat itself to push you | बार-बार दोहराकर दबाव डालने | ਵਾਰ-ਵਾਰ ਦੁਹਰਾ ਕੇ ਦਬਾਅ ਪਾਉਣ | |
| `plain.technique.Appeal_to_Fear-Prejudice` | scare you | डराने | ਡਰਾਉਣ | |
| `plain.technique.Exaggeration-Minimisation` | exaggerate or play things down | बढ़ा-चढ़ाकर बताने | ਵਧਾ-ਚੜ੍ਹਾ ਕੇ ਦੱਸਣ | |
| `plain.closest_label` | Closest sources I found: | सबसे क़रीबी स्रोत जो मुझे मिले: | ਸਭ ਤੋਂ ਨੇੜਲੇ ਸਰੋਤ ਜੋ ਮੈਨੂੰ ਮਿਲੇ: | |

---

## Honest-card strings: NOT YET REVIEWED (added 2026-10-05)

Added when the offline evidence-path guess stopped being shown as a verdict (docs/specs/UI_UX.md section 5):
the card now says it could not find a source that checks the exact claim, and a message the claim gate refuses
gets "I didn't find a claim to check" with a "Check it anyway" button. Machine-drafted; same tone and rules as
above (plain words, gender-neutral helper, placeholders kept). `plain.none_title` and `plain.none_note` replace
the earlier greeting wording. After you correct them, apply the corrections to `hi.json` and `pa.json` and remove
the "NOT YET REVIEWED (added 2026-10-05...)" sentence from their `_comment`.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `lean_note` | The system's own lean, which is NOT reliable for free text: {label}. | सिस्टम का अपना झुकाव, जो खुले पाठ के लिए भरोसेमंद नहीं है: {label}। | ਸਿਸਟਮ ਦਾ ਆਪਣਾ ਝੁਕਾਅ, ਜੋ ਖੁੱਲ੍ਹੇ ਪਾਠ ਲਈ ਭਰੋਸੇਯੋਗ ਨਹੀਂ ਹੈ: {label}। | |
| `plain.none_title` | I didn't find a claim to check | मुझे जाँचने लायक दावा नहीं मिला | ਮੈਨੂੰ ਜਾਂਚਣ ਲਈ ਦਾਅਵਾ ਨਹੀਂ ਮਿਲਿਆ | |
| `plain.none_note` | I couldn't find a full claim to check here. If you meant a claim, write it as a full sentence, for example “The exam paper was leaked.” | यहाँ मुझे जाँचने लायक पूरा दावा नहीं मिला। अगर यह कोई दावा है, तो इसे पूरे वाक्य में लिखें, जैसे “परीक्षा का पेपर लीक हुआ।” | ਇੱਥੇ ਮੈਨੂੰ ਜਾਂਚਣ ਲਈ ਪੂਰਾ ਦਾਅਵਾ ਨਹੀਂ ਮਿਲਿਆ। ਜੇ ਇਹ ਕੋਈ ਦਾਅਵਾ ਹੈ, ਤਾਂ ਇਸਨੂੰ ਪੂਰੇ ਵਾਕ ਵਿੱਚ ਲਿਖੋ, ਜਿਵੇਂ “ਪੇਪਰ ਲੀਕ ਹੋ ਗਿਆ।” | |
| `plain.check_anyway` | Check it anyway | फिर भी जाँचें | ਫਿਰ ਵੀ ਜਾਂਚੋ | |
| `plain.no_exact` | I couldn't find a source that checks this exact claim. | मुझे ऐसा कोई स्रोत नहीं मिला जो ठीक इसी दावे की जाँच करता हो। | ਮੈਨੂੰ ਅਜਿਹਾ ਕੋਈ ਸਰੋਤ ਨਹੀਂ ਮਿਲਿਆ ਜੋ ਠੀਕ ਇਸੇ ਦਾਅਵੇ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੋਵੇ। | |
| `plain.related_label` | The closest things I found (they may not be about this claim): | जो सबसे क़रीबी चीज़ें मिलीं (हो सकता है वे इस दावे के बारे में न हों): | ਜੋ ਸਭ ਤੋਂ ਨੇੜਲੀਆਂ ਚੀਜ਼ਾਂ ਮਿਲੀਆਂ (ਹੋ ਸਕਦਾ ਹੈ ਉਹ ਇਸ ਦਾਅਵੇ ਬਾਰੇ ਨਾ ਹੋਣ): | |
| `plain.try_online` | To get a real answer, look it up online. | सही जवाब पाने के लिए इसे ऑनलाइन खोजें। | ਸਹੀ ਜਵਾਬ ਲੈਣ ਲਈ ਇਸਨੂੰ ਆਨਲਾਈਨ ਖੋਜੋ। | |

---

## Similar-fact-check strings: NOT YET REVIEWED (added 2026-10-05)

For the card that says "a fact-checker looked at something similar" (docs/similar-factcheck-protocol.md). Machine-drafted;
same rules as above (plain words, gender-neutral helper, placeholders `{publisher}`, `{rating}` kept). The
`plain.similar.rating.*` words are inserted into `plain.similar.reason` and `plain.reply.similar`, so they must fit
the sentence ("... ने उसे झूठ बताया"). After you correct them, apply to `hi.json` and `pa.json` and remove the "NOT YET
REVIEWED (added 2026-10-05...): the 'similar fact-check' strings" sentence from their `_comment`.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `plain.title.similar` | A similar claim was fact-checked | मिलते-जुलते दावे की जाँच हो चुकी है | ਮਿਲਦੇ-ਜੁਲਦੇ ਦਾਅਵੇ ਦੀ ਜਾਂਚ ਹੋ ਚੁੱਕੀ ਹੈ | |
| `plain.similar.reason` | {publisher} looked at something similar and rated it {rating}. This may not be the same message. | {publisher} ने इससे मिलती-जुलती बात की जाँच की और उसे {rating} बताया। हो सकता है यह वही संदेश न हो। | {publisher} ਨੇ ਇਸ ਨਾਲ ਮਿਲਦੀ-ਜੁਲਦੀ ਗੱਲ ਦੀ ਜਾਂਚ ਕੀਤੀ ਅਤੇ ਉਸਨੂੰ {rating} ਦੱਸਿਆ। ਹੋ ਸਕਦਾ ਹੈ ਇਹ ਉਹੀ ਸੁਨੇਹਾ ਨਾ ਹੋਵੇ। | |
| `plain.similar.action` | Please read it before you forward this. | इसे आगे भेजने से पहले कृपया पढ़ लें। | ਇਸਨੂੰ ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਰਪਾ ਕਰਕੇ ਪੜ੍ਹ ਲਵੋ। | |
| `plain.similar.label` | The fact-check: | वह फ़ैक्ट-चेक: | ਉਹ ਫ਼ੈਕਟ-ਚੈਕ: | |
| `plain.similar.rating.Refuted` | False | झूठ | ਝੂਠ | |
| `plain.similar.rating.Supported` | True | सच | ਸੱਚ | |
| `plain.similar.rating.Conflicting` | partly true or misleading | आंशिक सच या भ्रामक | ਅੱਧਾ ਸੱਚ ਜਾਂ ਭਰਮਾਉਣ ਵਾਲਾ | |
| `plain.similar.rating.NEI` | not settled | अनिर्णीत | ਤੈਅ ਨਹੀਂ | |
| `plain.reply.similar` | I checked this message with TruthLens: a fact-checker looked at something similar and rated it {rating}. Please read it before you forward this. | मैंने इस संदेश की TruthLens से जाँच की: एक फ़ैक्ट-चेकर ने इससे मिलती-जुलती बात की जाँच की और उसे {rating} बताया। आगे भेजने से पहले कृपया इसे पढ़ लें। | ਮੈਂ ਇਸ ਸੁਨੇਹੇ ਦੀ TruthLens ਨਾਲ ਜਾਂਚ ਕੀਤੀ: ਇੱਕ ਫ਼ੈਕਟ-ਚੈਕਰ ਨੇ ਇਸ ਨਾਲ ਮਿਲਦੀ-ਜੁਲਦੀ ਗੱਲ ਦੀ ਜਾਂਚ ਕੀਤੀ ਅਤੇ ਉਸਨੂੰ {rating} ਦੱਸਿਆ। ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਰਪਾ ਕਰਕੇ ਇਸਨੂੰ ਪੜ੍ਹ ਲਵੋ। | |

---

## "Be careful" and unrated-suggestion strings: NOT YET REVIEWED (added 2026-10-05)

`plain.title.careful` and `plain.reason.careful` replace "Hard to say" for the case where the offline guess leaned false: they
say the system could not confirm the claim and that most messages like this turn out to be false. `plain.similar.reason_unrated`
and `plain.reply.similar_unrated` are for a similar fact-check whose rating cannot be mapped. Machine-drafted; same rules as
above. Apply your corrections to `hi.json` and `pa.json` and remove the matching "NOT YET REVIEWED (added 2026-10-05..." sentences
from their `_comment`.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `plain.title.careful` | Be careful with this one | इस संदेश से सावधान रहें | ਇਸ ਸੁਨੇਹੇ ਤੋਂ ਸਾਵਧਾਨ ਰਹੋ | |
| `plain.reason.careful` | I couldn't find a source that checks this exact claim. Most messages like this turn out to be false. | मुझे ऐसा कोई स्रोत नहीं मिला जो ठीक इसी दावे की जाँच करता हो। इस तरह के ज़्यादातर संदेश झूठे निकलते हैं। | ਮੈਨੂੰ ਅਜਿਹਾ ਕੋਈ ਸਰੋਤ ਨਹੀਂ ਮਿਲਿਆ ਜੋ ਠੀਕ ਇਸੇ ਦਾਅਵੇ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੋਵੇ। ਇਸ ਤਰ੍ਹਾਂ ਦੇ ਜ਼ਿਆਦਾਤਰ ਸੁਨੇਹੇ ਝੂਠੇ ਨਿਕਲਦੇ ਹਨ। | |
| `plain.similar.reason_unrated` | {publisher} looked at something similar. This may not be the same message. | {publisher} ने इससे मिलती-जुलती बात की जाँच की है। हो सकता है यह वही संदेश न हो। | {publisher} ਨੇ ਇਸ ਨਾਲ ਮਿਲਦੀ-ਜੁਲਦੀ ਗੱਲ ਦੀ ਜਾਂਚ ਕੀਤੀ ਹੈ। ਹੋ ਸਕਦਾ ਹੈ ਇਹ ਉਹੀ ਸੁਨੇਹਾ ਨਾ ਹੋਵੇ। | |
| `plain.reply.similar_unrated` | I checked this message with TruthLens: a fact-checker looked at something similar. Please read it before you forward this. | मैंने इस संदेश की TruthLens से जाँच की: एक फ़ैक्ट-चेकर ने इससे मिलती-जुलती बात की जाँच की है। आगे भेजने से पहले कृपया इसे पढ़ लें। | ਮੈਂ ਇਸ ਸੁਨੇਹੇ ਦੀ TruthLens ਨਾਲ ਜਾਂਚ ਕੀਤੀ: ਇੱਕ ਫ਼ੈਕਟ-ਚੈਕਰ ਨੇ ਇਸ ਨਾਲ ਮਿਲਦੀ-ਜੁਲਦੀ ਗੱਲ ਦੀ ਜਾਂਚ ਕੀਤੀ ਹੈ। ਅੱਗੇ ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਰਪਾ ਕਰਕੇ ਇਸਨੂੰ ਪੜ੍ਹ ਲਵੋ। | |
| `plain.reason.careful_live` | I looked online too and still couldn't find a source that checks this exact claim. Most messages like this turn out to be false. | मैंने ऑनलाइन भी देखा, फिर भी मुझे ऐसा कोई स्रोत नहीं मिला जो ठीक इसी दावे की जाँच करता हो। इस तरह के ज़्यादातर संदेश झूठे निकलते हैं। | ਮੈਂ ਆਨਲਾਈਨ ਵੀ ਵੇਖਿਆ, ਫਿਰ ਵੀ ਮੈਨੂੰ ਅਜਿਹਾ ਕੋਈ ਸਰੋਤ ਨਹੀਂ ਮਿਲਿਆ ਜੋ ਠੀਕ ਇਸੇ ਦਾਅਵੇ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੋਵੇ। ਇਸ ਤਰ੍ਹਾਂ ਦੇ ਜ਼ਿਆਦਾਤਰ ਸੁਨੇਹੇ ਝੂਠੇ ਨਿਕਲਦੇ ਹਨ। | |
| `plain.greeting_title` | Just a greeting | यह सिर्फ़ एक अभिवादन है | ਇਹ ਸਿਰਫ਼ ਇੱਕ ਨਮਸਕਾਰ ਹੈ | |
| `plain.greeting_note` | This looks like a greeting or a good wish. There's nothing here to check. | यह एक अभिवादन या शुभकामना लगती है। इसमें जाँचने लायक कुछ नहीं है। | ਇਹ ਇੱਕ ਨਮਸਕਾਰ ਜਾਂ ਸ਼ੁਭਕਾਮਨਾ ਲੱਗਦੀ ਹੈ। ਇਸ ਵਿੱਚ ਜਾਂਚਣ ਲਾਇਕ ਕੋਈ ਗੱਲ ਨਹੀਂ ਹੈ। | |
| `plain.words.button` | Which words mattered? | कौन-से शब्द मायने रखते थे? | ਕਿਹੜੇ ਸ਼ਬਦ ਅਹਿਮ ਸਨ? | |
| `plain.words.title` | These words pushed the answer the most: | इन शब्दों ने जवाब पर सबसे ज़्यादा असर डाला: | ਇਨ੍ਹਾਂ ਸ਼ਬਦਾਂ ਨੇ ਜਵਾਬ ਉੱਤੇ ਸਭ ਤੋਂ ਵੱਧ ਅਸਰ ਪਾਇਆ: | |
| `plain.words.hint` | The marked words are the ones that changed the answer most. | निशान वाले शब्द हटाने पर जवाब सबसे ज़्यादा बदलता है। | ਨਿਸ਼ਾਨ ਵਾਲੇ ਸ਼ਬਦ ਹਟਾਉਣ ਨਾਲ ਜਵਾਬ ਸਭ ਤੋਂ ਵੱਧ ਬਦਲਦਾ ਹੈ। | |
| `plain.words.note_english` | These are the words of the English version of your message. | ये आपके संदेश के अंग्रेज़ी रूप के शब्द हैं। | ਇਹ ਤੁਹਾਡੇ ਸੁਨੇਹੇ ਦੇ ਅੰਗਰੇਜ਼ੀ ਰੂਪ ਦੇ ਸ਼ਬਦ ਹਨ। | |
| `plain.words.source` | This sentence in the source mattered most: | स्रोत का यह वाक्य सबसे ज़्यादा मायने रखता था: | ਸਰੋਤ ਦਾ ਇਹ ਵਾਕ ਸਭ ਤੋਂ ਅਹਿਮ ਸੀ: | |
| `plain.words.none` | No single word stood out. | कोई एक शब्द अलग से ख़ास नहीं निकला। | ਕੋਈ ਇੱਕ ਸ਼ਬਦ ਵੱਖਰਾ ਖ਼ਾਸ ਨਹੀਂ ਨਿਕਲਿਆ। | |
| `plain.words.unavailable` | I couldn't show this right now. | अभी यह नहीं दिखाया जा सका। | ਇਹ ਹੁਣੇ ਨਹੀਂ ਦਿਖਾਇਆ ਜਾ ਸਕਿਆ। | |
| `plain.words.loading` | One moment… | थोड़ा रुकिए… | ਥੋੜ੍ਹਾ ਰੁਕੋ… | |
| `plain.why.label` | Why: this is what the source says | क्यों: स्रोत में यह लिखा है | ਕਿਉਂ: ਸਰੋਤ ਵਿੱਚ ਇਹ ਲਿਖਿਆ ਹੈ | |
| `plain.why.english` | The source is in English. | यह स्रोत अंग्रेज़ी में है। | ਇਹ ਸਰੋਤ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਹੈ। | |
| `plain.reason.sources_disagree` | The sources I found disagree with each other on this one. Here is what I found. | मुझे जो स्रोत मिले, वे इस बारे में एक-दूसरे से सहमत नहीं हैं। जो मिला, वह नीचे है। | ਮੈਨੂੰ ਜੋ ਸਰੋਤ ਮਿਲੇ, ਉਹ ਇਸ ਬਾਰੇ ਇੱਕ-ਦੂਜੇ ਨਾਲ ਸਹਿਮਤ ਨਹੀਂ ਹਨ। ਜੋ ਮਿਲਿਆ, ਉਹ ਹੇਠਾਂ ਹੈ। | |

---

## Outcome of the review of the 2026-10-05 strings (owner, 2026-10-05)

33 strings reviewed; **12 corrected as given and applied** (lean_note; plain.none_title pa; plain.related_label; plain.similar.label; plain.similar.rating.NEI hi;
plain.similar.reason pa; plain.greeting_title pa; plain.greeting_note pa; plain.words.hint; plain.words.none; plain.words.unavailable; plain.words.loading); the rest kept as drafted.
All placeholders ({label}, {publisher}, {rating}) were preserved and the helper stays gender-neutral. **Still NOT YET REVIEWED:** `plain.why.label`, `plain.why.english` and
`plain.reason.sources_disagree` (added after the sheet was sent), which keep their notes in the `_comment` of hi.json and pa.json.

---

## "What this is for" strings: NOT YET REVIEWED (added 2026-10-05)

Machine-drafted hi/pa; same rules as above (first person gender-neutral, placeholders none). Apply corrections to `hi.json` and `pa.json` and remove the matching `_comment` sentence.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `scope.title` | What this is for | यह किसके लिए है | ਇਹ ਕਿਸ ਲਈ ਹੈ | |
| `scope.built_for_title` | Built for | इनके लिए बना है | ਇਨ੍ਹਾਂ ਲਈ ਬਣਿਆ ਹੈ | |
| `scope.built_for_1` | Short claims people forward: health cures, money schemes, “WhatsApp will start charging”. | फ़ॉरवर्ड किए जाने वाले छोटे दावे: सेहत के नुस्ख़े, पैसों की योजनाएँ, “WhatsApp पर अब पैसे लगेंगे”। | ਅੱਗੇ ਭੇਜੇ ਜਾਂਦੇ ਛੋਟੇ ਦਾਅਵੇ: ਸਿਹਤ ਦੇ ਨੁਸਖ਼ੇ, ਪੈਸਿਆਂ ਦੀਆਂ ਸਕੀਮਾਂ, “WhatsApp ਹੁਣ ਪੈਸੇ ਲਵੇਗਾ”। | |
| `scope.built_for_2` | English, Hindi and Punjabi, including typed in Roman letters. | अंग्रेज़ी, हिंदी और पंजाबी, रोमन अक्षरों में लिखे हुए भी। | ਅੰਗਰੇਜ਼ੀ, ਹਿੰਦੀ ਅਤੇ ਪੰਜਾਬੀ, ਰੋਮਨ ਅੱਖਰਾਂ ਵਿੱਚ ਲਿਖੇ ਹੋਏ ਵੀ। | |
| `scope.built_for_3` | Claims a fact-checker has already looked at. | ऐसे दावे जिन्हें किसी फ़ैक्ट-चेकर ने पहले देखा हो। | ਅਜਿਹੇ ਦਾਅਵੇ ਜਿਨ੍ਹਾਂ ਨੂੰ ਕਿਸੇ ਫ਼ੈਕਟ-ਚੈਕਰ ਨੇ ਪਹਿਲਾਂ ਵੇਖਿਆ ਹੋਵੇ। | |
| `scope.built_for_4` | Plain facts that Wikipedia can settle. | सीधे तथ्य, जिन्हें Wikipedia से तय किया जा सके। | ਸਿੱਧੇ ਤੱਥ, ਜਿਨ੍ਹਾਂ ਨੂੰ Wikipedia ਨਾਲ ਤੈਅ ਕੀਤਾ ਜਾ ਸਕੇ। | |
| `scope.not_for_title` | Not built for | इनके लिए नहीं बना | ਇਨ੍ਹਾਂ ਲਈ ਨਹੀਂ ਬਣਿਆ | |
| `scope.not_for_1` | Recent events (an exam or a news story from this month): the sources used are out of date. | हाल की घटनाएँ (इसी महीने की कोई परीक्षा या ख़बर): जाँच के स्रोत पुराने हैं। | ਹਾਲੀਆ ਘਟਨਾਵਾਂ (ਇਸੇ ਮਹੀਨੇ ਦੀ ਕੋਈ ਪ੍ਰੀਖਿਆ ਜਾਂ ਖ਼ਬਰ): ਜਾਂਚ ਦੇ ਸਰੋਤ ਪੁਰਾਣੇ ਹਨ। | |
| `scope.not_for_2` | Private or local events: there is no public source for them. | निजी या स्थानीय घटनाएँ: इनका कोई सार्वजनिक स्रोत नहीं होता। | ਨਿੱਜੀ ਜਾਂ ਸਥਾਨਕ ਘਟਨਾਵਾਂ: ਇਨ੍ਹਾਂ ਦਾ ਕੋਈ ਜਨਤਕ ਸਰੋਤ ਨਹੀਂ ਹੁੰਦਾ। | |
| `scope.not_for_3` | Opinions and predictions: there is nothing to check. | राय और भविष्यवाणियाँ: इनमें जाँचने लायक कुछ नहीं होता। | ਰਾਇ ਅਤੇ ਭਵਿੱਖਬਾਣੀਆਂ: ਇਨ੍ਹਾਂ ਵਿੱਚ ਜਾਂਚਣ ਵਾਲੀ ਕੋਈ ਗੱਲ ਨਹੀਂ ਹੁੰਦੀ। | |
| `scope.not_for_4` | Very short fragments: write them as a full sentence. | बहुत छोटे टुकड़े: इन्हें पूरे वाक्य में लिखें। | ਬਹੁਤ ਛੋਟੇ ਟੁਕੜੇ: ਇਨ੍ਹਾਂ ਨੂੰ ਪੂਰੇ ਵਾਕ ਵਿੱਚ ਲਿਖੋ। | |
| `scope.not_for_5` | Anything with no source to be found: the answer is “Hard to say”, not a guess. | जिसका कोई स्रोत न मिले: जवाब “पक्का कहना मुश्किल है” होगा, अंदाज़ा नहीं लगाया जाएगा। | ਜਿਸ ਦਾ ਕੋਈ ਸਰੋਤ ਨਾ ਮਿਲੇ: ਜਵਾਬ “ਪੱਕਾ ਕਹਿਣਾ ਔਖਾ ਹੈ” ਹੋਵੇਗਾ, ਅੰਦਾਜ਼ਾ ਨਹੀਂ ਲਗਾਇਆ ਜਾਵੇਗਾ। | |
