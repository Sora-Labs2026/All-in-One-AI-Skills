# Scientific talks and slides

Read this when preparing or reviewing a talk: a conference presentation, seminar, thesis defense, lab meeting, journal club, job talk or funding pitch. Building and editing `.pptx` files is in `../../documents/references/powerpoint-pptx.md`; rendering decks to images is in `../../documents/references/convert-and-render.md`; HTML slide decks as a web medium are covered by `../../creative-media/GUIDE.md`.

## Plan the talk before the slides

1. **Audience:** specialists, a mixed department, a hiring committee, funders, the public. This decides how much background and jargon.
2. **Slot:** total time and how much of it is questions. Plan for about 80 % of the speaking time; talks run long.
3. **One message:** the sentence people should repeat afterwards. Every slide serves it or goes to the backup section.
4. **Story:** the problem and why it matters, what was unknown, what you did, what you found (the bulk of the time), what it means and what comes next.

Rough shapes (adjust to the event's norms):

| Talk | Typical length | Shape |
|---|---|---|
| Lightning or flash talk | 3-5 min | Problem, one result, one takeaway; three to five slides |
| Conference talk | 10-20 min | Brief motivation, method in one or two slides, two or three key results, takeaway |
| Department seminar | 45-60 min | Broad motivation for non-specialists, two or three connected stories, future work |
| Thesis defense | 30-45 min plus questions | The whole contribution, each chapter's question and answer, limitations stated before they are asked |
| Job talk | 45-60 min | Research vision, one deep result, future program |
| Journal club | 20-45 min | The paper's question, methods, results, then a critical appraisal (`appraising-evidence.md`) |
| Funding pitch | 5-15 min | Need, approach, why this team, ask, milestones |

About one slide per minute is a common starting point; dense result slides take two or three minutes, transition slides seconds. Time a rehearsal rather than trusting the count.

## Design each slide

- **One idea per slide,** stated in the title as a full-sentence claim ("Knockout mice gained 30 % less weight on the high-fat diet") with the evidence below it, usually one figure. Topic titles ("Results") waste the most visible line.
- **Text that can be read from the back:** body text at least 24 pt in a large room, never below 18 pt; few words; no paragraphs. The audience reads or listens, not both.
- **Contrast and color:** at least 4.5:1 text contrast (WCAG AA), colorblind-safe palettes, and never color alone to distinguish lines; projectors wash out light colors.
- **Consistent layout:** same title position, fonts and colors on every slide; slide numbers so questions can point to a slide.
- **Builds** (revealing parts step by step) for complex figures and arguments, not for decoration.
- **Citations** in short form on the slide where the work is shown (Author, year, venue); full references at the end or in shared materials.

## Data on slides

- Redraw figures for the screen: larger fonts and markers, fewer panels, the key comparison highlighted, axis labels with units. A journal figure pasted at reduced size is unreadable.
- Show uncertainty (intervals, individual points) and the sample sizes.
- Keep the honest comparison: do not drop baselines, conditions or runs that make the result look weaker. If space forces a cut, say so on the slide and keep the full result in backup.
- Tables only for a few numbers; otherwise plot.
- Figure code and styling: `../../data-engineering/references/plotting.md`.

## Tools

| Tool | Choose when |
|---|---|
| PowerPoint, Keynote, Google Slides | The audience or co-presenters need to edit; institutional templates. Generate or edit `.pptx` with python-pptx through the documents module |
| LaTeX Beamer | Math-heavy talks, the paper is in LaTeX, reproducible builds |
| Quarto or reveal.js | Web-native decks with live code output, embedded interactive figures |
| Marp | Plain Markdown to PDF or PPTX quickly |

Do not generate whole slides as images: the text becomes uneditable and inaccessible, numbers and labels come out garbled, and every change means regenerating.

A minimal Beamer start:

```latex
\documentclass[aspectratio=169]{beamer}
\usetheme{default}
\setbeamertemplate{navigation symbols}{}
\setbeamertemplate{footline}[frame number]
\title{Diet-induced weight gain depends on Gene X}
\author{A. Author}
\date{Conference 2026}
\begin{document}
\frame{\titlepage}
\begin{frame}{Knockout mice gained 30\% less weight on a high-fat diet}
  \centering\includegraphics[width=0.8\linewidth]{fig/weight_gain.pdf}
\end{frame}
\end{document}
```

Use `\pause` or overlay specifications (`\only<2>{...}`) for builds, the `handout` class option for a printable version, and `latexmk -pdf` to build.

## Speaker notes and rehearsal

- Notes per slide: the point, the transition to the next slide, and any number you must say exactly.
- Rehearse aloud with a timer at least twice; when over time, cut slides rather than speaking faster.
- Prepare backup slides for the questions you expect (method details, extra controls, limitations); list likely questions with short answers.
- Know which slide to skip if time is cut, and which point to add if time is extended.

## Check the rendered deck

Export to PDF, render pages to images and look at every slide (`../../documents/references/convert-and-render.md`): text overflowing boxes or the slide edge, overlapping elements, unreadable font sizes, low contrast, misaligned elements, broken builds, missing fonts. Check the aspect ratio of the room's projector (16:9 is the usual default), embed fonts or export to PDF for the presentation machine, test any video on that machine, and keep an offline copy.

## Accessibility

- Unique slide titles; logical reading order in the slide software.
- Alternative text for meaningful images; captions for embedded video.
- Share the slides (or a text version) before or after the talk when the event allows it.
- Describe key visuals aloud as you present them.

## Reviewing someone's deck

Report by slide number with severity: must fix (unreadable, overflowing, wrong or unsupported claim, timing far off), should fix (inconsistent design, text-heavy slides, weak figure), optional (polish). Include what works.

## Checks (done when)

- [ ] Audience, slot, one message and story agreed; slide count fits a timed rehearsal.
- [ ] Every slide title states a claim; figures redrawn for the screen; comparisons kept honest.
- [ ] Rendered deck inspected slide by slide; no overflow, overlap or unreadable text; fonts embedded.
- [ ] Speaker notes, backup slides and expected questions prepared.
- [ ] Alt text, captions and contrast checked.
