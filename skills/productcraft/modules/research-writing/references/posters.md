# Research posters

Read this when making, converting or reviewing a conference poster or e-poster. Figures for the poster are made with `../../data-engineering/references/publication-figures.md`; schematics with `diagrams-and-mermaid.md`; editing a poster delivered as `.pptx` goes through `../../documents/references/powerpoint-pptx.md`. Layout grids, type scale, print sizes and export checks for the poster as a designed page are in `../../creative-media/references/posters-and-canvas.md`; data graphics in `../../creative-media/references/infographics.md`.

## Start from the venue

Record before designing: exact size and orientation (A0 is 841 x 1189 mm; 36 x 48 in and 48 x 36 in are common in North America; some boards are smaller), print or screen (e-posters have pixel dimensions and sometimes a slide-like format), file format and size limits, printing deadline and printer requirements (bleed, margins, color profile), and any template or logo rules from the organizers or the institution.

## Content: less than you think

- **Title as the finding,** short enough to read from several meters ("Gene X deletion halves diet-induced weight gain in mice"), with authors, affiliations and contact.
- **300 to 800 words in total.** A poster is a visual abstract and a conversation starter, not the paper.
- **Sections:** question or motivation, approach (a schematic beats a paragraph), key results (the largest area), takeaways (two or three bullets), and a few references in short form. Acknowledge funding.
- **One hero figure** that carries the main result, readable at a distance.
- **A QR code** to the paper, preprint, code or data, using a stable URL or DOI. Test it from the printed proof with two phones.
- Keep comparisons honest: show the baselines and conditions that matter, even when space is tight.

## Layout

- Portrait: two to four columns; landscape: three to five. Reading order runs down each column, left to right; make the order obvious with numbered sections or clear column breaks.
- A grid with aligned edges and consistent gutters; generous white space; the same block style throughout.
- Visual hierarchy by size and position: title, then hero figure and takeaways, then supporting detail.
- Put the takeaway where people stand: upper middle for a first glance, and again at the end of the reading order.

## Type sizes for distance (A0; scale proportionally for smaller posters)

| Element | Size | Should be readable from |
|---|---|---|
| Title | 72-120 pt | 5 m or more |
| Section headings | 40-60 pt | 3 m |
| Body text and figure labels | 24-32 pt, never below 20 pt | 1.5-2 m |
| References, small print | 16-20 pt | Close up |

Use one or two sans-serif families, left-aligned text, and lines of 40 to 70 characters.

## Color and accessibility

- Text contrast at least 4.5:1; dark text on a light background is the safest under poor lighting.
- Colorblind-safe palettes; never color alone to separate lines or groups.
- Plain-language summary for mixed audiences.
- For e-posters, a tagged PDF or a text version with alternative text for figures.

## Tools

| Tool | Choose when | Notes |
|---|---|---|
| LaTeX `tikzposter`, `beamerposter`, `baposter`, or `tcolorbox` poster layouts | The paper is in LaTeX; math; reproducible builds | Fonts match the paper; layout tweaks need LaTeX skill |
| PowerPoint or other slide software with a custom page size | Co-authors edit in slide software; institutional templates | PowerPoint's maximum slide size is 56 in (about 142 cm); for larger posters design at half size and print at 200 % with vector content |
| HTML and CSS with print styles | Web-first teams, programmatic layouts | Set `@page { size: 841mm 1189mm; margin: 0 }` and print to PDF with a headless browser |
| Inkscape, Scribus, other layout tools | Fine-grained visual design | Keep the editable source |

A minimal `tikzposter` start:

```latex
\documentclass[25pt, a0paper, portrait]{tikzposter}
\title{Gene X deletion halves diet-induced weight gain in mice}
\author{A. Author, B. Author} \institute{Example University}
\usetheme{Simple}
\begin{document}
\maketitle
\begin{columns}
  \column{0.5}
  \block{Question}{Does Gene X drive weight gain on a high-fat diet?}
  \block{Approach}{\includegraphics[width=0.95\linewidth]{fig/design.pdf}}
  \column{0.5}
  \block{Key result}{\includegraphics[width=0.95\linewidth]{fig/weight.pdf}}
  \block{Takeaways}{\begin{itemize}\item ... \item ...\end{itemize}}
\end{columns}
\end{document}
```

For an HTML poster, the headless print step can be done with Playwright (`page.pdf(width="841mm", height="1189mm", print_background=True)`; setup in `../../builder-tools/references/playwright-web-testing.md`).

## Images and resolution

- Plots and schematics as vector graphics (PDF or SVG), so they stay sharp at any size.
- Photos and micrographs: at least 150 dpi at printed size, 300 dpi for fine detail. A photo spanning the full A0 width (33.1 in) at 150 dpi needs about 4,970 pixels across. Do not upscale small images and call them high resolution.
- Logos from official vector files, used per the owner's rules.

## Print and delivery checks

```bash
pdfinfo poster.pdf    # page size: A0 portrait is about 2384 x 3370 pts
pdffonts poster.pdf   # every font should show "yes" under emb
```

- View the PDF at 100 % to check detail and at 25 % for the overall impression.
- Print a proof on A4 or Letter: body text that is readable on a quarter-scale print is readable on the poster.
- Check the printer's requirements on margins, bleed and color; ask before converting to CMYK yourself.
- Keep the file within the venue's size limit; compress photos rather than vector content.
- Bring or upload a PDF copy; for e-posters, test on the actual display format if possible.

## Checks (done when)

- [ ] Size, orientation, format, deadline and printer requirements recorded from the venue.
- [ ] Title states the finding; 300 to 800 words; one hero figure; QR code tested.
- [ ] Type sizes meet the distance table; contrast and colorblind safety checked.
- [ ] PDF page size and embedded fonts verified; quarter-scale proof legible.
- [ ] No comparison removed to flatter the result.
