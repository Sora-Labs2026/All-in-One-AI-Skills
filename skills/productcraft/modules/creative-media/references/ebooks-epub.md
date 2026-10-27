# Markdown to EPUB

Read this to turn Markdown (notes, a report, documentation, a manuscript, a set of articles) into an EPUB 3 ebook that opens on common readers and passes validation. pandoc does the conversion; EPUBCheck and Ace by DAISY verify it. Versions: pandoc 3.x, EPUBCheck 5.x (2024-2026). Check what is installed with `pandoc --version` and `java -version`. Converting other documents to Markdown first is covered in `../../documents/references/convert-and-render.md`.

Contents: decide the shape · prepare the Markdown · metadata · build with pandoc · styling · images, covers and fonts · accessibility · building programmatically · validate and look · Kindle and stores · done when.

## Decide the shape

- **Reflowable** (the default, and right for text): the reader chooses font, size and margins, and text reflows. Design for that; do not fight it.
- **Fixed layout** is for picture books, comics and designed pages where position matters. It is a different build and reads badly on phones; avoid it for text.
- One EPUB per book. A collection of articles becomes one book with a chapter per article.

## Prepare the Markdown

- **One level-1 heading per chapter.** pandoc splits files at that level (`--split-level=1`), and the table of contents follows the heading hierarchy, so headings must not skip levels (no `#` straight to `###`).
- **Put the book title in metadata**, not as a top `#` heading, or it appears twice.
- Several files are joined in the order given: `pandoc front.md ch01.md ch02.md back.md`. Name them so a sorted list is the reading order.
- Links between chapters use heading identifiers (`[see Setup](#setup)`); pandoc rewrites them across the split files. Check them after the build.
- Footnotes become EPUB notes; tables stay tables but wide ones overflow small screens, so keep tables narrow or turn long ones into lists.
- Code blocks keep their language for syntax highlighting; keep lines short, since small screens wrap or scroll them.
- Math: `--mathml` gives real, accessible math where the reader supports MathML; otherwise render equations as images with alt text.

## Metadata

`meta.yaml`:

```yaml
title: Field Notes on Reliable Releases
subtitle: A practical guide
creator:
  - role: aut                  # MARC relator code: aut author, edt editor, trl translator
    text: Dana Okafor
lang: en-GB                    # required; BCP 47 language tag
identifier:
  - scheme: URN
    text: "urn:uuid:5f0c7a3e-2b1d-4c8e-9a61-0d2f4b7c9e13"   # generate once, keep for this edition;
                                                           # a published book uses its ISBN (scheme: ISBN-13)
date: 2026-03-01
publisher: Example Press
rights: © 2026 Dana Okafor. All rights reserved.
description: How small teams ship changes safely.
subject: [Software engineering, Release management]
cover-image: images/cover.jpg
```

- The identifier must stay the same for every rebuild of the same edition; readers and stores use it to recognize the book. A new random UUID on each build makes every update look like a new book.
- Never invent an ISBN. Use the one the publisher assigned, or a UUID (`urn:uuid:`) for unpublished books.
- Fill author, rights and dates from the user; leave clearly marked placeholders where facts are missing.

## Build with pandoc

```bash
pandoc meta.yaml front.md ch*.md back.md \
  --output=out/book.epub \
  --toc --toc-depth=2 \
  --split-level=1 \
  --css=epub.css \
  --resource-path=.:images \
  --mathml
```

- pandoc 3.0 renamed `--epub-chapter-level` to `--split-level`; older guides use the old name.
- `--epub-embed-font=fonts/*.woff2` (or `.ttf`, `.otf`) embeds fonts; see licensing below.
- `--epub-title-page=false` drops pandoc's generated title page when the book has its own.
- Put the command in a script or Makefile next to the sources, so the book rebuilds identically.

## Styling

Keep the stylesheet small and respect the reader's settings:

```css
body { margin: 0; line-height: 1.5; }                 /* no font-size or font-family on body */
h1 { break-before: page; page-break-before: always; margin-top: 2em; }
h1, h2, h3 { line-height: 1.2; hyphens: none; }
p { margin: 0; text-indent: 1.2em; orphans: 2; widows: 2; }
h1 + p, h2 + p, h3 + p { text-indent: 0; }
pre, code { font-family: monospace; font-size: 0.9em; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; } th, td { padding: 0.25em 0.5em; border: 1px solid currentColor; }
```

- Use relative units (`em`, `%`). Fixed pixel sizes, absolute positioning and floats behave unpredictably across readers.
- Do not set background colors or light text colors: readers have night and sepia modes that invert or tint, and hard-coded colors produce unreadable combinations. Use `currentColor` for borders.
- Many readers ignore or override parts of the CSS. Test on real readers rather than trusting the stylesheet.

## Images, covers and fonts

- **Images:** JPEG for photos, PNG for screenshots and diagrams, SVG with care (support varies). About 1600-2000 px on the long edge is plenty; large files bloat the book and some stores cap total size. Every meaningful image has alt text (`![A dashboard showing error rates dropping after the release](images/errors.png)`); decorative images get empty alt text.
- **Cover:** a JPEG at 1600 x 2560 px (a 1:1.6 ratio) suits most stores; check the store's current specification. The title on the cover must be readable as a small thumbnail. Cover art needs the same rights as any image (`posters-and-canvas.md`).
- **Fonts:** embedding is redistribution. SIL Open Font License fonts may be embedded; commercial fonts need an ebook-embedding license, which is often separate from desktop and web licenses. Most readers let the reader override the font anyway, so embed only when the design needs it (a display face for headings, a script the reader devices may lack).

## Accessibility

Accessible ebooks are a legal requirement in many markets: in the EU, the European Accessibility Act covers ebooks placed on the market from 28 June 2025 (with an exemption for microenterprises).
- Language set in metadata; headings in order; alt text on images; tables with header cells; reading order that matches the visual order; no text inside images.
- Add accessibility metadata to the package document: access modes (`textual`, plus `visual` if images carry information), sufficient access modes, features (for example `tableOfContents`, `readingOrder`, `alternativeText`, `structuralNavigation`), hazards (`none` or the specific ones) and a short summary. Recent pandoc releases accept these in the YAML metadata (see the EPUB section of the manual for your version); otherwise add the `meta` elements to the `.opf` file after the build and validate again.
- If the book has a print edition, a page list mapping to print page numbers helps readers who cite it.

## Building programmatically

When an application must generate EPUBs (for example, exporting user content), the choices are:
- **pandoc as a subprocess:** most complete output; pandoc is GPL-licensed, which is fine for running it as a separate program.
- **EbookLib** (Python): convenient API, but licensed under the AGPL v3. Bundling it in a product or offering it in a network service can trigger the AGPL's source-sharing terms; check with the project owner before adopting it.
- **Writing the package yourself:** an EPUB is a ZIP with a fixed layout. The `mimetype` file must be the first entry and stored uncompressed:

```bash
cd build && zip -X0 ../out/book.epub mimetype && zip -Xr9D ../out/book.epub META-INF OEBPS
```

Content from users is untrusted: escape it into XHTML properly, strip scripts and remote resources, and cap sizes (`../../launchguard/references/security-baseline.md`).

## Validate and look

1. **EPUBCheck** (the W3C-maintained validator): `java -jar epubcheck.jar out/book.epub`. Zero errors is the bar; read every warning and fix or explain it. Stores run the same checks.
2. **Ace by DAISY** for accessibility: `npx @daisy/ace -o out/ace-report out/book.epub`, then read the report's violations.
3. **Open it in at least two readers** of different kinds, for example Thorium Reader or the Calibre viewer on a desktop and Apple Books or a phone reading app. Check: the table of contents works and matches the chapters; chapter breaks fall where expected; internal links and footnotes jump correctly and back; images show with sensible size; code and tables are readable on a phone-width screen; night mode does not produce unreadable text; the cover appears in the library view.
4. Read the first and last pages of every chapter for stray Markdown, broken emphasis or missing text.

## Kindle and stores

- Kindle devices and apps receive EPUB through Amazon's Send to Kindle service, which converts it; the old MOBI format is no longer accepted there. Kindle Direct Publishing accepts EPUB uploads. Use the store's previewer before publishing.
- Each store has its own cover, metadata and content rules, and some require an ISBN. Check the current requirements; publishing, pricing and rights decisions stay with the author.
- Calibre can convert EPUB to other formats (for example AZW3) for personal use; validate the EPUB first, since conversion carries errors along.

## Done when

- EPUBCheck reports no errors, warnings are resolved or explained, and the Ace report has no serious violations.
- The book opened in two different readers, with a working table of contents, links, images, cover and readable code and tables at phone width.
- Metadata is complete and true: title, author, language, a stable identifier (a real ISBN or a UUID), rights; accessibility metadata is present.
- Fonts and images are licensed for embedding and distribution; the build command is saved with the sources.
