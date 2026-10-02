# Hindi and Punjabi UI strings: native-speaker review

**For:** a native Hindi speaker and a native Punjabi speaker, before any demo.
**Why:** every Hindi and Punjabi string in the TruthLens interface was drafted by
machine and has never been checked by a person. UI_UX.md §6: wrong Punjabi in a
Punjabi demo is worse than English.

**How to review.** Read each row. If the Hindi or Punjabi is wrong, unnatural, or
not how a WhatsApp user would say it, write your version in the last column.
Leave it empty if it is fine. Text in `{braces}` is filled in by the app (a
number, a language name, a publisher) — keep the braces where they are.

Tone, from UI_UX.md §8: plain words, never "true" or "false" (the app judges
*evidence*, not truth), no exclamation marks, no alarm language.

Once reviewed, the corrections go into `app/static/i18n/hi.json` and `pa.json`,
and the `_comment` line saying "UNVERIFIED" is changed to name the reviewer and
the date.

| key | English | Hindi | Punjabi | correction |
| --- | --- | --- | --- | --- |
| `abstained_label` | Not confident enough to judge | भरोसे से फ़ैसला नहीं कर सकते | ਭਰੋਸੇ ਨਾਲ ਫ਼ੈਸਲਾ ਨਹੀਂ ਕਰ ਸਕਦੇ | |
| `already_checked` | Already checked by {publisher} | {publisher} पहले ही जाँच चुका है | {publisher} ਪਹਿਲਾਂ ਹੀ ਜਾਂਚ ਚੁੱਕਾ ਹੈ | |
| `band.High` | High | ऊँचा | ਉੱਚਾ | |
| `band.Low` | Low | कम | ਘੱਟ | |
| `band.Medium` | Medium | मध्यम | ਦਰਮਿਆਨਾ | |
| `band_title` | Confidence {value}, calibrated on the development set | भरोसा {value}, डेवलपमेंट सेट पर कैलिब्रेट किया गया | ਭਰੋਸਾ {value}, ਡਿਵੈਲਪਮੈਂਟ ਸੈੱਟ ਉੱਤੇ ਕੈਲੀਬ੍ਰੇਟ ਕੀਤਾ | |
| `checking` | Checking… | जाँच हो रही है… | ਜਾਂਚ ਹੋ ਰਹੀ ਹੈ… | |
| `cite_aria` | Show source {n} | स्रोत {n} दिखाएँ | ਸਰੋਤ {n} ਵਿਖਾਓ | |
| `claim` | Claim | दावा | ਦਾਅਵਾ | |
| `degraded` | Some models are not loaded | कुछ मॉडल लोड नहीं हुए | ਕੁਝ ਮਾਡਲ ਲੋਡ ਨਹੀਂ ਹੋਏ | |
| `disclaimer` | TruthLens can be wrong. Check the sources. | TruthLens ग़लत हो सकता है। स्रोत ज़रूर देखें। | TruthLens ਗ਼ਲਤ ਹੋ ਸਕਦਾ ਹੈ। ਸਰੋਤ ਜ਼ਰੂਰ ਵੇਖੋ। | |
| `empty` | Message is empty | संदेश ख़ाली है | ਸੁਨੇਹਾ ਖ਼ਾਲੀ ਹੈ | |
| `error_server` | TruthLens could not finish checking this message. | TruthLens इस संदेश की जाँच पूरी नहीं कर सका। | TruthLens ਇਸ ਸੁਨੇਹੇ ਦੀ ਜਾਂਚ ਪੂਰੀ ਨਹੀਂ ਕਰ ਸਕਿਆ। | |
| `explanation_fallback` | Explanation in English — {lang} explanations aren't available yet. | व्याख्या अंग्रेज़ी में है — {lang} में व्याख्या अभी उपलब्ध नहीं है। | ਵਿਆਖਿਆ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਹੈ — {lang} ਵਿੱਚ ਵਿਆਖਿਆ ਅਜੇ ਉਪਲਬਧ ਨਹੀਂ। | |
| `forwarded` | Forwarded | फ़ॉरवर्ड किया गया | ਅੱਗੇ ਭੇਜਿਆ | |
| `hide_evidence` | Hide evidence ({n}) | सबूत छिपाएँ ({n}) | ਸਬੂਤ ਲੁਕਾਓ ({n}) | |
| `input_detected` | {lang}, {script} script | {lang}, {script} लिपि | {lang}, {script} ਲਿਪੀ | |
| `input_translit` | {lang}, typed in Roman script → converted to {script} | {lang}, रोमन लिपि में टाइप किया गया → {script} में बदला गया | {lang}, ਰੋਮਨ ਲਿਪੀ ਵਿੱਚ ਟਾਈਪ ਕੀਤਾ → {script} ਵਿੱਚ ਬਦਲਿਆ | |
| `intro` | Paste a forwarded message. TruthLens checks it and shows you the sources. | कोई फ़ॉरवर्ड किया हुआ संदेश यहाँ चिपकाएँ। TruthLens उसे जाँचकर स्रोत दिखाएगा। | ਕੋਈ ਅੱਗੇ ਭੇਜਿਆ ਸੁਨੇਹਾ ਇੱਥੇ ਪਾਓ। TruthLens ਉਸਦੀ ਜਾਂਚ ਕਰਕੇ ਸਰੋਤ ਵਿਖਾਏਗਾ। | |
| `lang_name.en` | English | अंग्रेज़ी | ਅੰਗਰੇਜ਼ੀ | |
| `lang_name.hi` | Hindi | हिंदी | ਹਿੰਦੀ | |
| `lang_name.pa` | Punjabi | पंजाबी | ਪੰਜਾਬੀ | |
| `leaning` | Leaning: {label} | झुकाव: {label} | ਝੁਕਾਅ: {label} | |
| `manipulation_title` | Persuasion techniques spotted in the message. They never change the verdict. | संदेश में बहकाने के तरीक़े दिखे। इनसे फ़ैसला नहीं बदलता। | ਸੁਨੇਹੇ ਵਿੱਚ ਭਰਮਾਉਣ ਦੇ ਤਰੀਕੇ ਦਿਸੇ। ਇਹ ਫ਼ੈਸਲਾ ਨਹੀਂ ਬਦਲਦੇ। | |
| `models_ready` | Models ready | मॉडल तैयार हैं | ਮਾਡਲ ਤਿਆਰ ਹਨ | |
| `notaclaim_note` | TruthLens only checks factual claims. Greetings, opinions and predictions have nothing to verify. | TruthLens केवल तथ्यात्मक दावों की जाँच करता है। शुभकामनाओं, राय और भविष्यवाणियों में जाँचने को कुछ नहीं होता। | TruthLens ਸਿਰਫ਼ ਤੱਥਾਂ ਵਾਲੇ ਦਾਅਵਿਆਂ ਦੀ ਜਾਂਚ ਕਰਦਾ ਹੈ। ਸ਼ੁਭਕਾਮਨਾਵਾਂ, ਰਾਏ ਅਤੇ ਭਵਿੱਖਬਾਣੀਆਂ ਵਿੱਚ ਜਾਂਚਣ ਲਈ ਕੁਝ ਨਹੀਂ ਹੁੰਦਾ। | |
| `path_evidence` | Checked against evidence | सबूतों से जाँचा गया | ਸਬੂਤਾਂ ਨਾਲ ਜਾਂਚਿਆ | |
| `path_factcheck` | Already checked by {publisher} | {publisher} पहले ही जाँच चुका है | {publisher} ਪਹਿਲਾਂ ਹੀ ਜਾਂਚ ਚੁੱਕਾ ਹੈ | |
| `placeholder` | Paste a forwarded message… | फ़ॉरवर्ड किया हुआ संदेश… | ਅੱਗੇ ਭੇਜਿਆ ਸੁਨੇਹਾ… | |
| `retry` | Retry | फिर से कोशिश करें | ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ | |
| `samples_label` | Try an example | कोई उदाहरण आज़माएँ | ਕੋਈ ਉਦਾਹਰਨ ਅਜ਼ਮਾਓ | |
| `script_name.deva` | Devanagari | देवनागरी | ਦੇਵਨਾਗਰੀ | |
| `script_name.guru` | Gurmukhi | गुरमुखी | ਗੁਰਮੁਖੀ | |
| `script_name.latn` | Latin | रोमन | ਰੋਮਨ | |
| `see_evidence` | See evidence ({n}) | सबूत देखें ({n}) | ਸਬੂਤ ਵੇਖੋ ({n}) | |
| `send` | Send | भेजें | ਭੇਜੋ | |
| `stage_trace` | Stage trace | चरण विवरण | ਪੜਾਅ ਵੇਰਵਾ | |
| `stance.Neutral` | Neutral | तटस्थ | ਨਿਰਪੱਖ | |
| `stance.Refutes` | Refutes | खंडन | ਖੰਡਨ | |
| `stance.Supports` | Supports | समर्थन | ਹਮਾਇਤ | |
| `technique.Appeal_to_Authority` | Appeal to authority | अधिकार का हवाला | ਅਧਿਕਾਰੀ ਦਾ ਹਵਾਲਾ | |
| `technique.Appeal_to_Fear-Prejudice` | Fear appeal | डर दिखाना | ਡਰ ਵਿਖਾਉਣਾ | |
| `technique.Appeal_to_Popularity` | "Everyone says so" | "सब यही कहते हैं" | "ਸਾਰੇ ਇਹੀ ਕਹਿੰਦੇ ਹਨ" | |
| `technique.Appeal_to_Time` | Pressure to act fast | जल्दबाज़ी का दबाव | ਕਾਹਲੀ ਦਾ ਦਬਾਅ | |
| `technique.Exaggeration-Minimisation` | Exaggeration | अतिशयोक्ति | ਵਧਾ-ਚੜ੍ਹਾ ਕੇ ਕਹਿਣਾ | |
| `technique.Loaded_Language` | Alarming language | डराने वाली भाषा | ਡਰਾਉਣੀ ਭਾਸ਼ਾ | |
| `technique.Repetition` | Repetition | दोहराव | ਦੁਹਰਾਅ | |
| `template_note` | Couldn't generate an explanation that the sources back up, so this one lists them directly. | स्रोतों से पुष्ट होने वाली व्याख्या नहीं बन सकी, इसलिए यहाँ सीधे स्रोत दिए गए हैं। | ਸਰੋਤਾਂ ਨਾਲ ਪੁਸ਼ਟ ਹੋਣ ਵਾਲੀ ਵਿਆਖਿਆ ਨਹੀਂ ਬਣ ਸਕੀ, ਇਸ ਲਈ ਇੱਥੇ ਸਿੱਧੇ ਸਰੋਤ ਦਿੱਤੇ ਹਨ। | |
| `title` | TruthLens | TruthLens | TruthLens | |
| `too_long` | Message is too long (4,000 characters at most) | संदेश बहुत लंबा है (अधिकतम 4,000 अक्षर) | ਸੁਨੇਹਾ ਬਹੁਤ ਲੰਮਾ ਹੈ (ਵੱਧ ਤੋਂ ਵੱਧ 4,000 ਅੱਖਰ) | |
| `unchecked` | {n} more claims in this message were not checked | इस संदेश के {n} और दावे नहीं जाँचे गए | ਇਸ ਸੁਨੇਹੇ ਦੇ {n} ਹੋਰ ਦਾਅਵੇ ਨਹੀਂ ਜਾਂਚੇ ਗਏ | |
| `unchecked_one` | 1 more claim in this message was not checked | इस संदेश का 1 और दावा नहीं जाँचा गया | ਇਸ ਸੁਨੇਹੇ ਦਾ 1 ਹੋਰ ਦਾਅਵਾ ਨਹੀਂ ਜਾਂਚਿਆ ਗਿਆ | |
| `unreachable` | API unreachable | API से संपर्क नहीं हो पा रहा | API ਨਾਲ ਸੰਪਰਕ ਨਹੀਂ ਹੋ ਰਿਹਾ | |
| `unsupported` | TruthLens works with English, Hindi and Punjabi. | TruthLens अंग्रेज़ी, हिंदी और पंजाबी में काम करता है। | TruthLens ਅੰਗਰੇਜ਼ੀ, ਹਿੰਦੀ ਅਤੇ ਪੰਜਾਬੀ ਵਿੱਚ ਕੰਮ ਕਰਦਾ ਹੈ। | |
| `verdict.Conflicting` | Evidence disagrees | सबूत आपस में टकराते हैं | ਸਬੂਤ ਆਪਸ ਵਿੱਚ ਟਕਰਾਉਂਦੇ ਹਨ | |
| `verdict.NEI` | Not enough evidence | पर्याप्त सबूत नहीं | ਲੋੜੀਂਦੇ ਸਬੂਤ ਨਹੀਂ | |
| `verdict.NotAClaim` | Nothing here to fact-check | इसमें जाँचने लायक कोई दावा नहीं है | ਇਸ ਵਿੱਚ ਜਾਂਚਣ ਯੋਗ ਕੋਈ ਦਾਅਵਾ ਨਹੀਂ | |
| `verdict.Refuted` | Contradicted by evidence | सबूतों से खंडित | ਸਬੂਤਾਂ ਨਾਲ ਖੰਡਿਤ | |
| `verdict.Supported` | Supported by evidence | सबूतों से पुष्ट | ਸਬੂਤਾਂ ਨਾਲ ਪੁਸ਼ਟ | |
| `verdict_aria` | Verdict: {label} | फ़ैसला: {label} | ਫ਼ੈਸਲਾ: {label} | |
