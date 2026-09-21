# Collecting hand-typed forwards (FR-26)

**Written for: friends and family helping collect messages.** Forward them this
file, or paste the "What to send" section into a chat.

Needed by **Day 11** (before the final tables). Phase 2 can start without it.

---

## Why this exists, in one paragraph

TruthLens checks forwarded WhatsApp messages in Hindi, Punjabi and English. The
hard case is when people type Hindi or Punjabi **in English letters** — "ye sach
hai kya" instead of "ये सच है क्या". A computer can *generate* romanized text
perfectly and consistently. Real people do not: they spell the same word three
different ways, drop vowels, mix in English, and add emoji. Measuring how much
worse the system does on real typing than on clean generated text is the actual
research finding of this project. That needs real typing, and there is no
dataset of it — which is why it has to be collected by hand.

---

## What to send

**~100 messages total.** Hindi or Punjabi, **typed in English letters.**

For each message, three things:

| | |
| --- | --- |
| 1. The message | Typed in English letters, as you would actually send it |
| 2. Language | Hindi / Punjabi / mixed |
| 3. What it claims | One line, any language. Or write "no claim" |

**Optional but doubles the value:** the same message written again in Devanagari
or Gurmukhi. That gives a matched pair — the identical claim in both scripts —
which is what makes the comparison exact rather than approximate.

### The single most important instruction

**Do not correct your spelling.** If you would type "sach", type "sach". If you
would type "sachh" or "sacch", type that. Inconsistent spelling is not a mistake
in this data — **it is the thing being measured.** A spellchecked set is useless.

Type it the way you would send it to your own family group. Emoji, ALL CAPS,
"forwarded many times" headers, missing punctuation — all wanted.

---

## The mix we need

Roughly this balance. It does not have to be exact.

| Kind | How many | Why |
| --- | --- | --- |
| Health and medicine claims | ~25 | The most common kind of real forward |
| Government schemes, money, free things | ~20 | The second most common |
| "Did you know" / science / history claims | ~15 | Checkable facts, low emotion |
| Long emotional messages with one fact buried inside | ~15 | Tests whether the system can find the claim |
| **Greetings, blessings, jokes, pure opinion** | **~15** | **Must contain no checkable fact** — tests that the system says "nothing to check" instead of inventing a verdict |
| Scam-style messages that also make a claim | ~10 | Realistic, and they mix a claim with a hook |

**Punjabi is the priority.** Every other dataset in this project is thin on
Punjabi — the largest one has 91 Punjabi messages in total. If someone can write
Punjabi, their messages are worth several times an equivalent Hindi one.

---

## Examples

Invented for illustration. None of these are true; the system's job is to check
them, not to be given correct ones.

**Health (Hindi, Roman)**
> Roz subah khali pet garam pani me nimbu aur haldi daal ke piyo, 3 din me sugar
> bilkul control ho jayega. Doctor log ye kabhi nahi batayenge 🙏

**Government scheme (Hindi, Roman)**
> Sarkar ne announce kiya hai ki har student ko 6000 rupaye scholarship milegi,
> form 31 tarikh tak bharna hai. Sabko forward karo

**Punjabi, Roman**
> Punjab sarkar ne kisana layi nawi scheme kaddi hai, har kisan nu saal de 6000
> rupaye milange. Sareyan nu dasso

**Punjabi, Roman**
> Haldi wala doodh peen naal saariyan bimariyan theek ho jandiyan ne, angrezi
> dawai di koi lod nahi

**"Did you know" (Hindi, Roman)**
> Mobile tower ki radiation ki wajah se pakshi mar rahe hai, isliye ab sheher me
> gauraiya dikhna band ho gayi hai

**Code-mixed question (very common)**
> Yaar ye true hai kya ki new traffic rule me helmet na pehno to 10,000 ka
> challan lagega?

**Long message, one fact buried in it**
> Bhaiyo behno, aaj kal ka mahaul dekh ke bahut dukh hota hai. Pehle log ek
> dusre ki izzat karte the, ab kisi ke paas time hi nahi hai. Waise aapko pata
> hai Delhi metro ki pehli line 2002 me shuru hui thi? Ab dekho kitna phail gaya
> hai par log kadar nahi karte. Jai Hind 🇮🇳

**No claim at all — we need these too**
> Suprabhat 🌺🙏 aaj ka din aapke liye mangalmay ho. Ye sandesh 11 logo ko
> bhejein, aapki manokamna puri hogi

**No claim at all (Punjabi)**
> Sat Sri Akal ji 🙏 Rabb sabnu khush rakhe. Ehna sandesh apne saare dostan nu
> bhejo

---

## Please do not send

- **Anyone's personal information.** No phone numbers, addresses, account
  numbers, or names of private individuals. Public figures in a factual claim
  are fine.
- **Messages attacking a religion, caste or community.** This project does not
  judge opinions or political positions, and there is no reason to build a
  collection of that material. A factual claim about a policy is fine; abuse is
  not.
- **Screenshots or images.** Text only — the system does not read images.
- **Messages only in English.** There is already plenty of English data.
- **Messages only in Devanagari or Gurmukhi.** There is already plenty of that
  too. The English-letters version is the scarce thing.

---

## How to send it

Whatever is easiest. A WhatsApp chat, a shared sheet, a text file — anything, as
long as the three fields stay together per message.

If a spreadsheet is convenient, these columns drop straight into the pipeline:

```csv
message,lang,claim_summary,native_script,source
"Roz subah khali pet garam pani...",hi,"Lemon and turmeric water cures diabetes in 3 days",,invented
"Sat Sri Akal ji 🙏 Rabb sabnu...",pa,"no claim",,real
```

| Column | Required | Notes |
| --- | --- | --- |
| `message` | yes | Roman script, uncorrected |
| `lang` | yes | `hi`, `pa`, or `mixed` |
| `claim_summary` | yes | One line, or `no claim` |
| `native_script` | no | The same message in Devanagari/Gurmukhi — worth a lot |
| `source` | no | `real` if actually received, `invented` if written for this |

Landing place in the repo: `data/raw/handtyped/forwards.csv` (gitignored, like
every other source file — nothing collected here gets committed or published).

---

## What happens to these messages

They are used **only** to evaluate this system, on one laptop, for one
university project. They are not published, not committed to the public repo,
not shared, and not used to train anything that leaves the machine. The repo
commits only anonymous identifiers and hashes — the same rule already applied to
every licensed dataset in the project.
