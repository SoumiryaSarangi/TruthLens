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

**Reviewed by the owner on 2026-10-05: 54 of the 55 strings corrected and applied exactly as given.**
The table below shows the machine drafts; the corrected text is in `app/static/i18n/hi.json` and
`pa.json`. One string was NOT applied and one result needs a decision:

1. **`plain.flags` (kept as drafted).** The reviewed sentence is "आपको {list} करने के लिए उकसाने की कोशिश
   करता है" / "ਤੁਹਾਨੂੰ {list} ਕਰਨ ਲਈ ਉਕਸਾਉਣ ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰਦਾ ਹੈ", which puts "करने के लिए / ਕਰਨ ਲਈ" after
   `{list}`. The reviewed `plain.technique.*` phrases are infinitives ("डराने", "भावनाएँ भड़काने",
   "ਡਰਾਉਣ"), and the two do not fit: it would read "आपको डराने करने के लिए ...". The previous sentence
   ("यह संदेश {list} की कोशिश करता है") fits the reviewed phrases, so it stays. **Decision needed:** keep it, or
   send phrases that fit the new sentence (for example nouns: "डराना", "जल्दबाज़ी").
2. **Punjabi `plain.sure.High` and `plain.sure.Medium` are now the same sentence** ("ਮੈਨੂੰ ਕਾਫ਼ੀ ਭਰੋਸਾ
   ਹੈ"), so a reader cannot tell "quite sure" from "fairly sure". Applied as given; please send a different
   Punjabi sentence for one of them (the earlier draft for Medium was "ਮੈਨੂੰ ਠੀਕ-ਠਾਕ ਭਰੋਸਾ ਹੈ").
3. Several reviewed first-person sentences use masculine forms ("कह सकता", "कर पाया", "ਕਹਿ ਸਕਦਾ", "ਕਰ ਸਕਿਆ").
   Applied as given; if the helper should be gender-neutral, say so and I will reword them.

**Answer language (decided 2026-10-05).** The card answers in Hindi or Punjabi only when the message
is written in Devanagari or Gurmukhi. Hindi or Punjabi typed in Latin letters ("Kal se WhatsApp ke paise
lagenge") is answered in English. The EN / हिं / ਪੰ switch, if pressed, overrides this.

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
