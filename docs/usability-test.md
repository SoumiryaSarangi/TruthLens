# Usability test: can an ordinary reader understand the answer?

TruthLens is for people who receive WhatsApp forwards, not for engineers. This is a small test
with the owner's relatives (parents, grandparents, other family) of whether they understand the
plain card (`docs/specs/UI_UX.md` section 5). **The questions and the pass bars below are fixed
before anyone is tested.** The results go in `docs/usability-results.md` and report section 6,
whatever they are, including a failed bar.

With 3 to 5 people this is an indication, not a statistic. It is meant to find confusing wording,
and the report says so.

## Who and how

- 3 to 5 people who regularly get forwards. At least one who reads Hindi or Punjabi more easily
  than English, and (if possible) one older than 60.
- The owner sits beside them and does **not** explain the screen. Say only: "Please read this and
  tell me what you think it says."
- Use the owner's laptop or phone with the app open, with the page open (its language follows
  the browser, or add `?lang=hi` or `?lang=pa` to the address for a Hindi or Punjabi page; the answers
  follow each message's own language and script).
- Use only the app's own example messages, or the Hindi sentence given for task B (no personal messages, no names). Record only the
  answers below, the language, an age band and the device; no names.
- Ask for consent in one sentence: "I'm testing an app, not you; you can stop any time."

## The tasks

Open the "Try an example" fold and press each example, then press send. Do the tasks in this order.

| Task | Example | What the card says | Expected understanding |
| --- | --- | --- | --- |
| A | EN, fact-checked (pineapple juice) | Fact-checkers say: FALSE | It is false; do not forward it |
| B | For a Hindi reader paste "नींबू पानी पीने से कैंसर ठीक हो जाता है"; for others Roman Hindi ("Kal se WhatsApp ke paise lagenge", answered in English because it is typed in Latin letters) or the Long forward | "Be careful with this one: I couldn't find a source that checks this exact claim. Most messages like this turn out to be false.", a warning in words if the message tries to scare, and a "Look this up online" button | The app could not confirm it; be careful and check before forwarding |
| C | Thin evidence (Lahore, in Punjabi) | Hard to say, it looks true | Not sure; check before forwarding |
| D | Greeting ("Good morning, stay blessed") | "I didn't find a claim to check", with a "Check it anyway" button | It is not a claim |
| E | Type "Hyderabad is the capital of Telangana", press send, then "Look this up online" (needs the network and the key in `.env`; press it once beforehand so the answer is cached) | Probably TRUE, with a line saying how it was found and how it was tested | It looks true; still check the source |

After each card, ask these four questions and write down the answer in the person's own words:

1. **"In your own words, what is this telling you?"**  Scored *correct* if they say the message is
   false / probably true / the app is not sure, as the card says for that task (A: false; B and C: the
   app cannot tell; E: probably true).
2. **"Would you forward this message to the family group? Why?"**  Scored *correct* if it matches
   the "what to do" line (do not forward A; check first for B, C and E; D has no action).
3. **"How sure do you think the app is?"**  Scored *correct* for C if they say it is not sure.
4. **"Was anything in the answer confusing?"**  Free text; this is the most useful question.

Then two extra tasks and one rating:

5. **"Please make the app read the answer out loud."**  Pass if they find and press **Listen**
   without help. (If the device has no voice for their language, the card says so; record that.)
6. **"Please make a reply you could send to the family group."**  Pass if they press **Copy a reply**
   and can paste it somewhere (Notes or WhatsApp).
7. **"On a scale of 1 to 5, how easy was it to understand? (1 = very hard, 5 = very easy)"**

## Pass bars (fixed before testing)

All four must hold across the people tested:

1. At least **80%** of Question 1 answers (person x task, tasks A, B, C and E) are correct.
2. At least **80%** of Question 2 answers (tasks A, B, C and E) match the expected action.
3. **Nobody** fails to say what to do for a false message (task A) or for "Hard to say" (tasks B and C).
4. The mean ease rating is at least **4 out of 5**, and at least **3 of 5** (or all, if fewer than
   5 are tested) find Listen or Copy a reply without help.

## If a bar fails

Fix the wording the confusing answers point at (the notes from Question 4 are the guide), say what
was changed, and test **two new people**. Report both rounds in `docs/usability-results.md`; the
first round is never dropped.

## Results sheet (copy into `docs/usability-results.md`)

| Person | Language | Age band | Device | A Q1/Q2/Q3 | B Q1/Q2/Q3 | C Q1/Q2/Q3 | D Q1 | Listen | Copy | Ease 1-5 | Confusing (Q4) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | | | | |
| 2 | | | | | | | | | | | |
| 3 | | | | | | | | | | | |
