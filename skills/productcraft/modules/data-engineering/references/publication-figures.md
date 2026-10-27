# Publication-quality scientific figures

Read this when figures go into a paper, thesis, poster, grant or regulatory submission, or when a user asks for "publication quality". It adds venue requirements, typography, color and statistical display rules on top of `plotting.md`. Writing the manuscript itself is covered by `../../research-writing/GUIDE.md`.

## Start from the venue

Requirements differ by journal and change over time. Read the target venue's current author guidelines for figures and record what they say before making anything. Typical requirements in 2026, to be confirmed for each venue:

| Item | Typical requirement |
|---|---|
| Width | Single column about 85-90 mm; 1.5 columns about 114-140 mm; full width about 170-183 mm |
| Text size | 5-8 pt at final printed size for labels and ticks; panel letters 8-12 pt |
| Fonts | A common sans-serif (Arial, Helvetica, or a close substitute), embedded in the file |
| Line art and charts | Vector (PDF, EPS, SVG) preferred; otherwise at least 600-1200 dpi at final size |
| Photographs and micrographs | At least 300 dpi at final size, TIFF or PNG, never JPEG for data |
| Color | RGB for online publication; convert to CMYK only when the venue asks |
| Source data | Many journals require the numbers behind each plot as a supplementary file |

## Build at final size

Design each figure at the exact size it will be printed; scaling afterwards shrinks text below the minimum and changes line weights.

```python
import matplotlib as mpl
import matplotlib.pyplot as plt

MM = 1 / 25.4
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7,
    "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 6,
    "axes.linewidth": 0.6, "lines.linewidth": 1.0,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "ps.fonttype": 42,     # embed TrueType fonts, keep text editable
    "svg.fonttype": "none",                    # SVG text stays text
    "savefig.dpi": 600,
})

fig, axd = plt.subplot_mosaic("AB;CC", figsize=(180 * MM, 120 * MM), layout="constrained")
for label, ax in axd.items():
    ax.text(-0.12, 1.02, label.lower(), transform=ax.transAxes,
            fontsize=9, fontweight="bold", va="bottom", ha="right")
fig.savefig("figure2.pdf")
fig.savefig("figure2.png", dpi=600)
```

- Put these settings in a project `.mplstyle` file so every figure in the paper matches; seaborn figures inherit them (call `sns.set_theme(context="paper", rc=...)` or skip `set_theme` so it does not override the style).
- Fonts named in `font.sans-serif` must exist on the machine. If Arial is missing, matplotlib silently falls back to the next entry; check the embedded fonts after export (below).
- Align panels on a grid, share axes where comparison matters (`sharex`, `sharey`), and use `fig.align_labels()` for multi-row figures.
- Label panels consistently (lowercase or uppercase, bold or not, as the venue specifies), in the same corner of every panel.

## Color

- Qualitative: at most about eight distinguishable colors, from a colorblind-safe set (Okabe-Ito; Paul Tol's palettes; seaborn `"colorblind"`). Encode the same condition with the same color in every figure of the paper.
- Sequential data: perceptually uniform maps (viridis, cividis, magma). Diverging data: a diverging map centered on the meaningful midpoint, with `matplotlib.colors.TwoSlopeNorm(vcenter=0)` when the range is asymmetric. Never rainbow or `jet`.
- Redundant encoding: different markers or line styles as well as colors, and direct labels instead of a legend where space allows.
- Check the result in grayscale and with a color-vision-deficiency simulator before submitting.

## Showing data and statistics honestly

- With small samples (roughly under 20-30 per group), show every observation (strip or swarm points) over or beside the summary, instead of a bar with an error whisker. Bars suit counts and totals that start at zero, not means of continuous measurements.
- State in the legend or caption what every error bar and band is: standard deviation (spread of the data), standard error, or a confidence interval (with its level), and the n behind it, including what n counts (animals, cells, technical replicates).
- Name the statistical test, its sidedness and the multiple-comparison correction where significance is marked; define every symbol (`*`, `**`). Report exact p-values or intervals where the venue allows. The analysis itself belongs to `../../ml-engineering/references/statistical-inference.md`.
- Axis breaks, truncated axes and log scales must be visible and labeled.
- Never invent, smooth away or "tidy" data points, and never compute a statistic for the figure that was not computed in the analysis.

## Images

- Microscopy, gels and blots: include scale bars; apply brightness and contrast changes linearly to the whole image and to controls alike; never remove, add or move features; keep the unprocessed originals and state processing in the methods. Splices and crops are marked. Imaging pipelines are covered under `../../life-sciences/GUIDE.md`.
- Store images as lossless TIFF or PNG; JPEG artifacts can look like structure.
- Pseudo-colored channels: choose combinations readable by colorblind readers (magenta and green rather than red and green), or show channels separately in grayscale.

## Reproducibility

- Every figure is produced by one script or notebook from saved data, with a fixed random seed for any jitter, bootstrap or layout, and pinned library versions.
- Keep the plotted numbers as a CSV next to each figure; it doubles as the source data file journals ask for.
- Name outputs by figure and panel (`fig2_panels.pdf`) and regenerate all figures with one command before submission.

## Export and verify

- Vector output for charts (PDF or EPS as requested, SVG for later editing); raster output only for images or when required.
- Check the files, not the code:
  - `pdffonts figure2.pdf` lists embedded fonts (every font should show "yes" under `emb`, and no Type 3 fonts where the venue forbids them).
  - `pdfinfo figure2.pdf` shows page size in points (1 mm is about 2.835 pt); confirm the width matches the column size.
  - For raster files, check pixel dimensions divided by width in inches equals the required dpi.
  - View at 100% and print one page at actual size to judge text and line weights.
- Re-read the venue's checklist against the final files.

## Checks (done when)

- [ ] Venue requirements read and recorded; sizes, fonts, formats and resolution match them.
- [ ] Figures built at final size from a shared style; text at least the minimum size when printed.
- [ ] Colorblind-safe palettes, redundant encodings, and consistent colors across figures.
- [ ] Error bars, n, tests and symbols defined; small samples shown as individual points.
- [ ] Image processing disclosed and applied uniformly; originals kept.
- [ ] Every figure regenerates from data with one command; source data saved; fonts embedded and verified.
