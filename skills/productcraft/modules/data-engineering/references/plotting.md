# Plotting in Python: matplotlib, seaborn and Plotly

Read this when analysis code produces charts: notebooks, reports, EDA, monitoring snapshots, interactive HTML for colleagues. Charts inside a product's UI follow `../../data-and-product-surfaces.md` and the UI rules; figures for papers and theses add the requirements in `publication-figures.md`.

## Choose the form, then the library

Pick the chart from the question it answers, with the table in "Charts: pick the form from the question" in `../../data-and-product-surfaces.md` (time trend, ranking, share, distribution, relationship, density, target, funnel) and its honesty rules: bars start at zero, no dual y-axes, no 3D, color for meaning. Analysis adds a few forms worth knowing:

| Question during analysis | Form |
|---|---|
| How is one variable distributed, without choosing bins? | ECDF (`sns.ecdfplot`) |
| Does a variable follow a reference distribution? | Q-Q plot (`scipy.stats.probplot`, `statsmodels` `qqplot`) |
| How do many groups compare on the same measure? | Small multiples with shared axes (`col=`/`row=` facets) |
| How do several variables relate pairwise? | Pair plot on a sample (`sns.pairplot(df.sample(2000, random_state=0))`) |
| Where are millions of points concentrated? | Hexbin, 2-D histogram, or Datashader rasterization |

| Need | Library |
|---|---|
| Static figures, full control, publication output | matplotlib |
| Statistical plots from tidy data with grouping and faceting in a line or two | seaborn (draws with matplotlib, so matplotlib customizes it) |
| Interactive HTML (hover, zoom, toggling series) to share or embed; dashboards | Plotly (Dash for full apps) |
| Declarative grammar of graphics, small to medium data, Vega-Lite output | Altair |
| Very large point or line data | Datashader with HoloViews, or aggregate first |

## matplotlib

Versions 3.8 to 3.10 are common in 2026; check `matplotlib.__version__`. Some APIs were removed recently, for example `matplotlib.cm.get_cmap` (use `matplotlib.colormaps["viridis"]`).

```python
import matplotlib
matplotlib.use("Agg")                      # headless: scripts, CI, servers (or set MPLBACKEND=Agg)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
ax.plot(daily["day"], daily["revenue"], color="0.2", lw=1.5, label="Revenue")
ax.axhline(target, color="tab:red", ls="--", lw=1, label="Target")
ax.set(title="Daily revenue, March 2026", xlabel="Day", ylabel="Revenue (EUR)")
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
ax.legend(frameon=False)
fig.savefig("revenue.png", dpi=200)
plt.close(fig)                             # free memory; essential in loops
```

- **Use the object-oriented API** (`fig, ax = plt.subplots()` and `ax.` methods). The `plt.` state machine is fine for one quick plot and confusing with several axes.
- **Layout:** `layout="constrained"` handles labels, colorbars and legends; `fig.subplot_mosaic("AAB;CCB")` builds irregular grids by name. `bbox_inches="tight"` at save time trims margins but changes the final size; avoid it when exact dimensions matter.
- **Dates:** pass real datetimes, not strings; `ConciseDateFormatter` produces compact, unambiguous tick labels.
- **Dense data in vector files:** `ax.scatter(..., rasterized=True)` keeps axes and text as vectors but stores the many marks as an image, so PDFs stay small and fast.
- **Consistent style:** a project `.mplstyle` file or one `rcParams` block, applied once, beats per-plot tweaks. `plt.style.use("seaborn-v0_8-whitegrid")`-style names changed in 3.6; prefer your own style file.
- **Memory leaks:** every `plt.figure()` stays alive until closed. Generating hundreds of charts without `plt.close(fig)` exhausts memory.
- **Fonts and missing glyphs:** non-Latin text needs a font that has the glyphs (set `font.family`); check the rendered image, not the code.

## seaborn

Versions 0.12 and 0.13 (2022-2023) changed several parameters and defaults, so older examples mislead; check `seaborn.__version__`.

```python
import seaborn as sns
sns.set_theme(context="notebook", style="whitegrid", palette="colorblind")

g = sns.relplot(
    data=long_df, x="week", y="signups", hue="channel", col="region", col_wrap=3,
    kind="line", errorbar=("ci", 95), seed=0, height=3, aspect=1.4,
)
g.set_axis_labels("Week", "Signups per week").set_titles("{col_name}")
g.figure.savefig("signups.png", dpi=200)
```

- **Long-form data** (one row per observation, with columns for variables) is what seaborn wants. `df.melt(...)` converts wide tables.
- **Figure-level** functions (`relplot`, `displot`, `catplot`, `lmplot`, `pairplot`, `jointplot`) create their own figure and support `col=`/`row=` faceting; they return a grid object (`g.figure`, `g.axes`). **Axes-level** functions (`lineplot`, `histplot`, `boxplot` ...) draw into an `ax=` you provide, for combining with other panels.
- **Error bars must be explained.** Since 0.12 the `errorbar` parameter replaces `ci`: `("ci", 95)` is a bootstrap confidence interval of the estimate, `"sd"` the spread of the data, `"se"` the standard error, `("pi", 50)` a percentile interval. Say which one in the caption. Bootstrap intervals are random; set `seed=` for reproducible figures, and `errorbar=None` on large data to skip the bootstrap.
- **Aggregation is implicit.** `lineplot` and `barplot` average repeated x values by default (`estimator="mean"`); if the data already has one row per point, that is harmless, but when it does not, the chart shows means you did not intend. Aggregate explicitly when in doubt.
- `histplot(stat="density", common_norm=False)` compares shapes of groups with different sizes; the default normalizes over all groups together.
- The objects interface (`import seaborn.objects as so`) composes marks, stats and scales declaratively; useful for layered custom plots, still marked experimental in places.

## Plotly

Plotly 6 (2025) accepts pandas, Polars and PyArrow inputs directly through a dataframe-agnostic layer; check `plotly.__version__`.

```python
import plotly.express as px

fig = px.line(daily, x="day", y="revenue", color="channel",
              labels={"revenue": "Revenue (EUR)", "day": "Day"},
              title="Daily revenue by channel")
fig.update_traces(hovertemplate="%{x|%d %b}: %{y:,.0f} EUR<extra>%{fullData.name}</extra>")
fig.update_layout(template="simple_white", hovermode="x unified")
fig.write_html("revenue.html", include_plotlyjs="cdn")   # small file; needs internet to view
```

- **Plotly Express** (`px`) for almost everything from tidy data; **graph objects** (`go.Figure`, `go.Scatter`) when you need traces px cannot express, then customize with `update_traces`, `update_layout`, `update_xaxes`.
- **HTML output:** `include_plotlyjs="cdn"` writes a small file that loads the library from the internet; `include_plotlyjs=True` embeds it (several MB) for offline viewing. Pick based on where the file will be opened.
- **Static images** (`fig.write_image("chart.png", scale=2)`) need the Kaleido package; Kaleido 1.x drives a locally installed Chrome or Chromium rather than bundling one, so headless servers need a browser installed first.
- **Many points:** `px.scatter(..., render_mode="webgl")` (or `go.Scattergl`) above roughly ten thousand points; above about a million, aggregate or rasterize first.
- **Everything in the figure ships to the viewer.** An HTML chart embeds the full data of every trace, including columns used only in hover text. Aggregate or drop sensitive columns before sharing a file outside the team.
- For apps with filters and callbacks, Dash builds on the same figures; treat it as a web application (authentication, deployment) rather than a chart.

## Large data

Aggregate to what the chart can show before plotting: roughly one value per horizontal pixel for lines, binned counts for distributions and densities. Plotting a million raw points produces an unreadable blob, a slow notebook and a huge file. When the raw points matter (spatial patterns, rare outliers), rasterize them (Datashader, `hexbin`, `hist2d`).

## Honest, readable charts

- Title states what the chart shows; axis labels carry units; the source and date range appear in a caption or note.
- One message per chart; highlight the series that matters and mute the rest.
- Same category, same color across all figures in a report. Use colorblind-safe palettes (`"colorblind"` in seaborn, Okabe-Ito), and never color alone to distinguish lines: vary marker or line style too.
- Continuous color: a perceptually uniform sequential map (viridis, cividis) for magnitude, a diverging map centered on a meaningful value (zero, the target) for deviations. Avoid rainbow maps such as `jet`, which invent boundaries.
- Show uncertainty where it exists, and the number of observations behind each point or group.
- Logarithmic axes only when labeled and when the audience reads them.

## Verify every chart

- Open the saved file (PNG, PDF or HTML) and look at it at the size it will be used; for agents, read the image back or render it, rather than assuming the code did what was intended.
- Check two or three plotted values against the table they came from.
- Check that axes start where they should, labels are not clipped or overlapping, and the legend matches the series.

## Checks (done when)

- [ ] Chart form chosen from the question; honesty rules from `../../data-and-product-surfaces.md` respected.
- [ ] Units, labels, source and the meaning of any error bars stated.
- [ ] Colorblind-safe palette and redundant encoding where color distinguishes series.
- [ ] Output file opened and inspected; plotted values spot-checked against data.
- [ ] Shared interactive files contain only data meant for their audience.
