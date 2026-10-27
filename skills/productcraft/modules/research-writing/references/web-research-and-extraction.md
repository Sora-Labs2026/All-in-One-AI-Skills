# Web research, deep research and text extraction

Read this when the user wants a question researched on the web, a broad "deep research" report, or the clean text of an article, web page, talk or video for their own use. Scholarly databases are in `scholarly-apis.md` and `biomedical-and-preprint-apis.md`; judging what you find is in `appraising-evidence.md`; PDFs are in `../../documents/references/pdf.md`.

## Plan the research

1. **Restate the question** and what a good answer looks like: a number, a comparison, a recommendation, a timeline, a list.
2. **Decompose** it into three to eight sub-questions, each answerable by a specific kind of source.
3. **Decide source types per sub-question:** official and primary (agencies, standards bodies, filings, court records, original studies, product documentation), expert secondary (reviews, reputable journalism), community (forums, issue trackers) for practical experience.
4. **Set recency needs** (anything about prices, laws, versions or people needs current sources) and a stopping rule: stop when new sources repeat what you have, or when the budget agreed with the user is spent.

## Choose the tools

| Tool | Good for | Treat output as |
|---|---|---|
| The agent's built-in web search and page fetch | Targeted facts, reading primary pages | Evidence once you have read the page |
| Web search APIs | Scripted searches, many queries, domain and date filters | Candidate links |
| AI answer engines that return summaries with citations | Fast orientation on a topic | Leads; every cited claim must be checked on the cited page |
| Hosted deep-research agents that plan, browse and write a report asynchronously | Broad landscape scans | A draft map of the topic with links to verify, never a final answer |
| Extraction APIs and libraries | Clean text from known URLs | Data for your own reading and analysis |

Paid APIs and research agents cost money per call or task, and asynchronous agents take minutes. State the expected cost and time and get the user's agreement before starting one; poll for results with growing intervals and keep the task id so a lost session can resume. Keys come from environment variables the user set and never appear in the conversation (`../../agent-safety/references/secrets.md`).

## Search well

- Use specific terms and the field's vocabulary; add quotes for exact phrases, `site:` for a domain (`site:gov`, `site:europa.eu`), `filetype:pdf` for reports, and date filters for recent material.
- Search in the languages of the places concerned when the question is local.
- Search for the primary source behind a claim, not more articles repeating it.
- Search deliberately for contrary evidence and failures ("criticism", "limitations", "lawsuit", "recall", "retraction", "postmortem").

## Verify before using anything

For every claim that goes into the answer:

1. Open the cited or found page and find the sentence that supports the claim. AI summaries and search snippets regularly attribute claims to pages that do not make them, merge sources, or present outdated facts as current.
2. Record URL, title, publisher or author, publication or last-updated date, access date, and the supporting quote.
3. Prefer the original over coverage; check whether two sources are independent or copies of one press release.
4. Mark claims that rest on a single source; mark unverified ones `NOT VERIFIED`.
5. Keep an archived copy (for example a web archive snapshot) of pages that may change, when the user wants a durable record.

## Write the synthesis

- Answer first, with the confidence level and why.
- An evidence table: claim, sources, agreement or disagreement, strength.
- Disagreements between credible sources, explained rather than averaged.
- Gaps: what could not be found or verified.
- Method: queries, tools, dates, and anything not searched.

## Extracting article text

**Rules first.**
- Check the site's terms and its `robots.txt`; respect disallow rules for automated fetching and any crawl delay, identify your client, and fetch slowly.
- Never bypass paywalls, logins, CAPTCHAs or technical protections. If content is paywalled, ask the user to provide it from their own access.
- Extracted text is for the user's own reading, analysis and quotation with attribution. Do not republish articles or commit copyrighted text to public repositories.

```python
import urllib.robotparser, urllib.parse

def allowed(url, agent="research-script"):
    parts = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    rp.read()
    return rp.can_fetch(agent, url), rp.crawl_delay(agent)
```

**Tools.**
- `trafilatura` (Python) extracts the main text and metadata (title, author, date, site) from news and blog pages and handles many languages:

```python
import trafilatura
html = trafilatura.fetch_url(url)
text = trafilatura.extract(html, output_format="markdown", with_metadata=True,
                           include_comments=False, include_tables=True)
```

  Output options and defaults have changed between major versions; check the installed version.
- Readability-style extractors (Mozilla's Readability in Node.js with a DOM implementation; readability ports in Python) work well on article pages.
- `pandoc -f html -t gfm` turns already-cleaned HTML into Markdown.
- Pages rendered by JavaScript need a real browser: Playwright, then extract from the rendered DOM (`../../builder-tools/references/playwright-web-testing.md`).

Check the result: compare the headline, first and last paragraphs and the word count with the page; extractors sometimes drop tables, captions or the end of the article, or keep navigation text. Tell the user which tool produced the text.

## Transcripts of talks and videos

- Prefer captions the publisher provides. With `yt-dlp`, list what exists, then download captions only:

```bash
yt-dlp --list-subs "$URL"
yt-dlp --skip-download --write-subs --sub-langs en --sub-format vtt -o "%(title)s.%(ext)s" "$URL"
yt-dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt -o "%(title)s.%(ext)s" "$URL"   # automatic captions
```

  Respect the platform's terms and the creator's rights; personal study and analysis is the use case. Ask before installing tools.
- Automatic captions repeat lines as they scroll. Strip timing and tags and drop consecutive duplicates while keeping order:

```python
import re, sys
out, last = [], None
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line or line.isdigit():
        continue
    line = re.sub(r"<[^>]+>", "", line).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if line and line != last:
        out.append(line)
    last = line
print("\n".join(out))
```

- When no captions exist and the user has the right to the audio, transcribe locally with an open speech-recognition model (Whisper or faster-whisper). Tell the user the download and model sizes first (hundreds of megabytes to several gigabytes) and ask before installing. Keep timestamps; mark the transcript as automatic and check names, numbers and technical terms against the audio before quoting.
- Never disable TLS certificate checks to make a download work; fix the certificate or proxy configuration instead.

## Provenance

Save extracted text with its URL, retrieval date, tool and version, and any license or terms noted. Keep it out of shared or public repositories unless its license allows.

## Checks (done when)

- [ ] Question decomposed; source types, recency and stopping rule set.
- [ ] Costs of paid APIs or research agents agreed before use; keys taken from the environment.
- [ ] Every claim used was checked on the page it came from, with URL, dates and quote recorded; single-source and unverified claims marked.
- [ ] The synthesis leads with the answer, shows disagreements and gaps, and documents the method.
- [ ] Extraction respected robots rules, terms and paywalls; output checked against the page; provenance saved.
- [ ] Transcripts labeled as captions or automatic, with names and numbers checked before quoting.
