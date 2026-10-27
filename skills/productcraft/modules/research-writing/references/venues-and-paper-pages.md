# Venue templates, submission and paper web pages

Read this when formatting a manuscript for a specific journal or conference, preparing a submission or a preprint upload, anonymizing for double-blind review, or turning a paper into a project web page. Writing the content is in `scientific-writing.md`; grant formats are in `grant-proposals.md`; Word files go through `../../documents/references/word-docx.md`.

## Read the current author instructions

Requirements change every year, sometimes between submission cycles of the same conference. From the venue's own pages (not a template found elsewhere, not memory), record:

- Article type, word or page limits, and what counts toward them (references, appendices, figures, supplementary material).
- The template or class file and its year; required options (review mode, line numbers, anonymous).
- Abstract length and structure; keyword, highlight or significance-statement requirements.
- Reference style and any limit on the number of references.
- Figure and table specifications (`../../data-engineering/references/publication-figures.md`).
- Anonymization rules, supplementary material rules, dual-submission and preprint policies.
- Required statements: data and code availability, ethics, competing interests, funding, author contributions (often CRediT roles), AI-use disclosure, and reporting checklists (`study-checklists-and-registration.md`).

Keep this list in the project as a checklist and check it again on the final PDF.

## Use the official template

- LaTeX classes in wide use: `acmart` (ACM; formats such as `sigconf` or `acmsmall`, options such as `review` and `anonymous`), `IEEEtran`, `elsarticle` (Elsevier), the Springer Nature journal template and `llncs` for Lecture Notes in Computer Science, `revtex4-2` (APS, AIP), `aastex` (AAS); machine-learning and NLP conferences publish a style file per year (NeurIPS, ICML, ICLR, ACL). Get them from the publisher or conference site, or the publisher's official template gallery.
- Many journals accept or require Word; use their template and keep their styles.
- Do not change margins, fonts, line spacing or float spacing to fit the page limit. Reviewers and editors notice, and some venues desk-reject for it. Cut text instead.

## Anonymize for double-blind review

- Remove names, affiliations, acknowledgments and funding from the PDF (most templates have an anonymous option).
- Cite your own work in the third person ("Smith et al. showed"), not "our previous work [3]"; follow the venue's rule on anonymous self-citation.
- Replace repository links with anonymized mirrors or upload code as supplementary material.
- Clean metadata: PDF author fields, document properties, figure files with names, comments in the LaTeX source if source is uploaded, and screenshots showing user names or paths.
- Check figures and supplementary files for lab names, logos and URLs.

## Build hygiene for LaTeX

```bash
latexmk -pdf main.tex                 # or -lualatex / -xelatex as the template requires
grep -nE "Warning|undefined|Overfull" main.log | head -40
chktex -q main.tex                    # style lint; review, do not auto-fix
pdfinfo main.pdf                      # page count and page size
pdffonts main.pdf                     # all fonts embedded; some venues reject Type 3 fonts
```

Resolve undefined references and citations, large overfull boxes and missing figures before submission. Run `scripts/bib_check.py refs.bib --cited-in main.tex` on the bibliography. Compile from a clean checkout to make sure every file is in the repository.

## Preprint servers (arXiv as the main example)

- Upload LaTeX source when possible; arXiv compiles it with its own TeX distribution.
- arXiv does not run BibTeX or biber on your `.bib`; include the generated `.bbl`, built with the same bibliography package version arXiv uses (for biblatex, mismatched versions fail).
- Comments in the source become public. Remove them, along with unused files, before upload (tools exist that clean a LaTeX project for arXiv; review their output).
- Choose the license deliberately (arXiv's default license or a Creative Commons license) and check it against the target journal's preprint policy.
- Pick categories carefully; expect moderation, not peer review. Post updates as new versions, with a note on what changed.

## Journal submission package

Cover letter (what, why this venue, confirmation of originality and no dual submission, suggested and excluded reviewers if asked, with no conflicts), the manuscript, figures in the required formats, supplementary material, the completed reporting checklist, author information including ORCID iDs, statements, and permissions for any reused figures. Check the system's generated PDF before approving it.

## Turning a paper into a web page

A project page helps readers find the key result, the paper, code and data in one place.

**Content:** title, authors with links, venue and year; one-paragraph summary in plain language; the key figure with a caption; links to the paper (DOI or preprint), code, data, slides, poster and video; a BibTeX block copied from the verified entry (`citations-and-reference-managers.md`); a contact.

**Rights first:**
- Check the publishing agreement before posting the full text. Most publishers allow the preprint or accepted manuscript on a personal or institutional page, often with conditions; fewer allow the publisher's formatted PDF. Open-access articles under CC BY can be reposted with attribution. Check the journal's policy (open policy databases such as Sherpa list them) and record it.
- Figures in the published version may belong to the publisher; use the authors' own versions where the agreement allows.

**Building it:**
- A single static page (HTML and CSS) or a static site generator (Jekyll, Hugo, Quarto, Astro) hosted on GitHub Pages, GitLab Pages or the institution's server.
- For the full paper as HTML, convert the source with pandoc (with MathJax or KaTeX for equations) or LaTeXML, or link to arXiv's HTML rendering when it exists. Check equations, tables and cross-references after conversion; they are where converters fail.
- Accessibility: one `h1`, ordered headings, alternative text for figures, sufficient contrast, keyboard-usable media controls, captions for video (`../../responsive-accessibility.md`).
- Performance: compressed images, video loaded on demand rather than autoplaying large files.
- No analytics or third-party trackers without the user's decision and the consent the law requires (`../../legal-ready/GUIDE.md`).

**Video summaries:** narrated by the authors, or with a synthetic voice that is clearly disclosed; never a synthetic likeness or cloned voice of a real person without their explicit consent; captions included. Video production and synthetic media rules are covered by `../../creative-media/GUIDE.md`.

## Checks (done when)

- [ ] Current author instructions recorded and checked against the final PDF.
- [ ] Official template used without layout hacks; page limits met by cutting text.
- [ ] Anonymization complete in PDF, metadata, figures, links and supplementary files (double-blind venues).
- [ ] Clean build: no undefined references or citations, fonts embedded, `bib_check.py` clean.
- [ ] Preprint upload includes the `.bbl`, has comments removed and a deliberately chosen license.
- [ ] Project page respects the publishing agreement, works without trackers, and passes accessibility checks.
