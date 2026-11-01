# Text processing and NLP for low-resource languages (worked example: Bengali)

Read this when building search, classification, extraction, chat, translation or evaluation for a language with few tools and little labeled data, or when cleaning a corpus written in a non-Latin script. Bengali (Bangla, script range U+0980 to U+09FF) is the worked example; most points carry over to other Brahmic scripts (Devanagari, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, Sinhala) and many others, and the last section lists what to check for a new language. Model training is in `../../ml-engineering/references/fine-tuning.md` and `../../ml-engineering/references/transformers.md`; LLM evaluation method in `../../ml-engineering/references/llm-evaluation.md`; UI string catalogs in `../../engineering-practices/references/i18n-catalog-sync.md`.

## Ground rules

- **Native speakers decide.** Anything shipped to users (normalization rules, stop-word lists, prompts, evaluation labels, generated text) is reviewed by fluent speakers of the variety you serve. Bengali differs between Bangladesh and West Bengal, and between the formal literary register (sadhu bhasha) and the standard colloquial one (cholito bhasha).
- **Data rights.** Web-crawled corpora carry licenses and terms; social-media text contains personal data that needs a lawful basis and minimization. Record the source and license of every corpus.
- **Script is not language.** Bengali script also writes Assamese and other languages; Bengali is also typed in Latin letters ("Banglish"). Detect both, never assume one from the other.
- **Store the original.** Keep raw text untouched and write normalized text to a separate field, so a later fix to the rules can be replayed.

## Unicode facts that cause real bugs

| Fact | Consequence | What to do |
|---|---|---|
| A visible letter cluster can be several code points: consonant + virama (hasanta, U+09CD) + consonant forms a conjunct, so `ক্ষ` is U+0995 U+09CD U+09B7 | Slicing, length limits and cursor logic by code point cut conjuncts in half | Count and cut by extended grapheme clusters |
| Grapheme rules for conjuncts are new: Unicode 15.1 (2023) added a rule that keeps Indic conjuncts together | Older ICU and regex releases split `ক্ষ` into two clusters; newer ones (for example Node 22 with ICU 77) return one | Test segmentation on your runtime with a few conjuncts before relying on it |
| Vowel signs (U+09BE to U+09CC) are combining marks, not letters | Python `re` `\w+` splits `রহিম` into `রহ` and `ম`; JavaScript `\w` is ASCII-only | Python: the `regex` module with `\p{Bengali}` or `[\p{L}\p{M}]+`; JavaScript: `/[\p{L}\p{M}\p{Nd}]+/u` |
| Two-part vowel signs have precomposed forms: `ো` (U+09CB) equals U+09C7 + U+09BE | The same word compares unequal across sources | Normalize to NFC at every boundary (input, storage, index, query) |
| `ড়`, `ঢ়` and `য়` (U+09DC, U+09DD, U+09DF) are composition exclusions: NFC turns them into base letter + nukta (U+09BC) and never back | A dictionary or regex typed with the precomposed letters stops matching NFC text | Normalize dictionaries, patterns and test fixtures with the same NFC function as the data |
| Khanda ta `ৎ` (U+09CE) was written as `ত` + virama + ZWJ before Unicode 4.1 | Old text and some keyboards produce the legacy sequence; NFC does not convert it | Map the sequence to U+09CE explicitly |
| Some typists produce visually identical but non-equivalent sequences, such as `অ` + `া` for `আ` | NFC leaves them unequal | A reviewed, language-specific normalization table, applied to a separate field |
| ZWNJ (U+200C) and ZWJ (U+200D) change how conjuncts and ligatures render | Stripping all "zero-width" characters changes spelling | Remove ZWSP (U+200B), BOM (U+FEFF), soft hyphen and word joiner; keep ZWNJ and ZWJ unless a reviewed rule says otherwise |
| Sentence enders `।` and `॥` (U+0964, U+0965) live in the Devanagari block and are shared | Sentence splitters that test for the Bengali block miss them | Include them explicitly |
| Bengali digits `০` to `৯` (U+09E6 to U+09EF) | `int("১২৩")` is 123 in Python, but `str.isdigit()` also accepts superscripts and other scripts' digits | Validate with an explicit class (`[0-9০-৯]`) or `str.isdecimal()`; store the original and a normalized numeric value |

Other encoding problems seen in Bengali corpora: UTF-8 text decoded as Latin-1 or Windows-1252 shows runs like `à¦`, which can usually be repaired by re-encoding (`s.encode("latin-1").decode("utf-8")`) after checking a sample; and documents in legacy non-Unicode font encodings, where Latin code points are drawn as Bengali glyphs by a special font, look like gibberish Latin without that font and need a dedicated converter, not normalization.

## Cleaning pipeline (order matters)

1. Decode bytes as UTF-8 in strict mode; route failures and mojibake to repair or review.
2. Remove BOM, ZWSP, soft hyphens and control characters; turn no-break spaces into spaces; collapse whitespace.
3. Unicode NFC.
4. Language-specific rules (khanda ta, reviewed equivalence table, digit policy) into the normalized field.
5. Script and language identification per sentence or segment; keep code-mixed and romanized text labeled rather than dropping it.
6. Deduplicate: exact matches after normalization, then near-duplicates (MinHash or similar). Web corpora in smaller languages are heavily duplicated and mirrored.
7. Quality filters (script ratio, length, boilerplate, encoding errors), with counts of what each filter removed.
8. Personal-data scrubbing where the use requires it.

A standard-library audit to run before and after cleaning; it reports counts only, never the text:

```python
import collections, unicodedata

DROP = {"​": "ZWSP", "﻿": "BOM", "­": "SOFT_HYPHEN", "⁠": "WORD_JOINER"}
KEEP = {"‌": "ZWNJ", "‍": "ZWJ"}
LEGACY_KHANDA_TA = "ত্‍"

def audit(text: str) -> dict:
    c = collections.Counter(not_nfc=int(unicodedata.normalize("NFC", text) != text),
                            legacy_khanda_ta=text.count(LEGACY_KHANDA_TA),
                            mojibake_hint=text.count("à¦"))
    for ch in text:
        if ch in DROP or ch in KEEP:
            c[DROP.get(ch) or KEEP[ch]] += 1
        elif "ঀ" <= ch <= "৿":
            c["bengali"] += 1
        elif ch.isascii() and ch.isalpha():
            c["latin"] += 1
        elif unicodedata.category(ch) == "Cc" and ch not in "\n\r\t":
            c["control"] += 1
    return {k: v for k, v in sorted(c.items()) if v}

def clean(text: str) -> str:
    text = "".join(ch for ch in text if ch not in DROP).replace(" ", " ")
    return unicodedata.normalize("NFC", text).replace(LEGACY_KHANDA_TA, "ৎ")
```

## Tokenization

- **Baseline:** split on whitespace and punctuation, including `।` and `॥`. It is a fine start for search and counting.
- **Morphology:** case markers and postpositions attach to words (`-এর`, `-র` possessive; `-কে` objective; `-তে`, `-য়` locative; plural `-রা`, `-গুলো`, `-গুলি`). Light rule-based stemming helps recall in search; measure precision before adopting it, and keep negation words (`না`, `নয়`, `নেই`) out of stop-word lists for sentiment or intent tasks.
- **Subword tokenizers and cost:** measure the fertility of each candidate model's tokenizer on a sample of your text (tokens per word and per character, and the share of byte-fallback tokens). English-centric tokenizers often split Bengali into several times more tokens than comparable English, which raises cost, shortens the effective context and often lowers quality.
- **Training your own tokenizer:** SentencePiece (unigram or BPE) on normalized text with `character_coverage=1.0` for an alphabetic script like Bengali. SentencePiece applies NFKC-based normalization by default (`nmt_nfkc`); make training-time and inference-time normalization identical to your pipeline.
- **Romanized and code-mixed input:** transliterate to Bengali script with a model or rules where needed, keep the original, and evaluate on real mixed text.

## Search

- Normalize documents and queries with the same function; fold digits to one script for matching; decide stemming by measurement.
- Character n-gram indexing (for example trigrams) tolerates spelling variation well in small corpora.
- Elasticsearch and OpenSearch ship a `bengali` analyzer (normalization plus a light stemmer); test it on your queries before trusting it.
- Common spelling variation (`ি`/`ী`, `ু`/`ূ`, `শ`/`ষ`/`স`, `ন`/`ণ`, `জ`/`য`) can be folded for fuzzy matching only, never in stored text.
- Sort with ICU collation for `bn` (PyICU, `Intl.Collator("bn")`, or an ICU collation in PostgreSQL); code-point order is not dictionary order.
- Reject empty or whitespace-only queries before matching; an empty string is a substring of everything.

## Models and LLMs

- Candidates: multilingual encoders (XLM-R and similar), monolingual encoders trained by research groups for the language, and multilingual LLMs. Choose by results on your own task data in the language, not by English benchmarks or translated test sets.
- Translate-then-process pipelines (translate to English, run an English model, translate back) lose nuance and names; compare them against native processing on the same test set.
- Prompts: keep user text in its own message as data; state the output language and script explicitly (Bengali script, not romanized); check that the model does not drift into English mid-answer.
- Scarce training data: back-translation and careful synthetic data can help, but never evaluate on machine-translated test data; translated text ("translationese") inflates scores.

## Evaluation

- Test sets written by native speakers, covering the dialects, registers and code-mixing your users produce, frozen and versioned.
- Metrics: chrF (character n-gram F-score) is more stable than BLEU for morphologically rich languages; if BLEU is reported, use sacreBLEU and publish its signature; character error rate rather than word error rate for speech; macro-F1 for imbalanced classification. Report the normalization applied before scoring, since it changes scores.
- Public resources such as FLORES-200 (translation) include Bengali; check each benchmark's license and whether it may already be in a model's training data.
- Human evaluation by native speakers with a rubric (adequacy, fluency, correct script, register), with inter-rater agreement reported.

## Storage and display

- UTF-8 everywhere. Bengali code points are three bytes in UTF-8 and fit MySQL's legacy `utf8` (utf8mb3), but use `utf8mb4` anyway so emoji in the same text do not fail. Size byte-limited columns and indexes for three bytes per code point and several code points per visible letter.
- Mark Bengali content with `lang="bn"` (or `bn-BD`, `bn-IN`) in HTML for fonts, screen readers and hyphenation; include a Bengali-capable font in the stack (Noto Sans Bengali or Noto Serif Bengali).
- Rendering needs complex text shaping (HarfBuzz or the platform's engine). Many plotting, image and PDF libraries draw Indic scripts wrongly without it, so inspect rendered output; for images, Pillow built with libraqm supports shaping.
- Truncate display text by grapheme cluster and line-break with ICU rules, not by code point or byte.

## Adapting to another low-resource language

| Check | Examples of what changes |
|---|---|
| Script and normalization quirks | Composition exclusions, legacy encodings (Burmese text in a legacy font encoding is a well-known case), visually confusable sequences |
| Word boundaries | Thai, Lao, Khmer and Burmese use no spaces between words, so use ICU word break iterators or a trained segmenter |
| Direction | Right-to-left scripts need the Unicode bidirectional algorithm and isolation marks around mixed-direction runs |
| Digits, punctuation, calendars | Script-specific digits and sentence marks; local calendars in dates |
| Locale data | Whether CLDR and ICU have collation and formatting data for the language |
| Resources and licenses | Corpora, treebanks, benchmarks, tokenizer fertility of available models |
| People | Native-speaker reviewers for each variety and register you serve |

## Done when

- [ ] Raw and normalized text are stored separately; the normalization function is shared by data, dictionaries, patterns and queries.
- [ ] The audit shows no unexpected invisible characters, controls, mojibake or legacy sequences after cleaning, with removal counts recorded.
- [ ] Grapheme segmentation, regex classes and sentence splitting were tested on conjuncts, vowel signs and `।` on the target runtime.
- [ ] Tokenizer fertility was measured for candidate models; evaluation uses native-written, frozen test sets with chrF or task metrics and stated normalization.
- [ ] Native speakers reviewed rules, prompts and outputs; corpus licenses and personal-data handling are recorded.
