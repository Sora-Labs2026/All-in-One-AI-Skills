# Glycosylation sites and glycoengineering

Read this when you scan a protein sequence for glycosylation sites, plan mutations that add or remove them, interpret glycan composition data, or reason about glycosylation in a therapeutic protein. Protein sequence handling is in `biopython.md`; glycopeptide mass spectrometry in `mass-spectrometry.md`.

## The biology that drives the code

- **N-linked glycosylation** attaches glycans to asparagine in the sequon **N-X-S/T**, where X is any residue except proline. A second, rarer sequon N-X-C exists. The sequon is necessary, not sufficient: occupancy depends on accessibility, folding kinetics, the cell type and the expression system. N-X-T is generally occupied more efficiently than N-X-S.
- **O-linked glycosylation** (most commonly O-GalNAc on serine or threonine) has no strict consensus. Sites cluster in serine- and threonine-rich, often proline-rich regions; proline immediately after the residue disfavors initiation by some transferases. Prediction is statistical; treat computed sites as low-confidence hypotheses.
- **The host decides the glycans.** The same sequence expressed in CHO cells, HEK cells, yeast, insect cells, plants or bacteria (which normally do not N-glycosylate) yields different structures. Non-human epitopes from non-human hosts are an immunogenicity concern for therapeutics.
- **Glycans affect** folding, stability, protease resistance, clearance rate, effector function and immunogenicity; this is why they are engineered at all.

## Finding N-glycosylation sequons

```python
import re

SEQUON = re.compile(r"N[^P][ST]")

def n_sequons(seq: str):
    """Yield 1-based asparagine positions of N-X-S/T sequons, including overlapping matches."""
    s = seq.upper()
    for m in re.finditer(r"(?=(N[^P][ST]))", s):      # lookahead: NNTS has sequons at 1 and 2
        pos = m.start() + 1
        yield {"position": pos, "motif": m.group(1),
               "type": "NXT" if m.group(1)[2] == "T" else "NXS",
               "context": s[max(0, pos - 6): pos + 5]}
```

- Scan with a lookahead so overlapping sequons are not missed; a plain `finditer` on `N[^P][ST]` skips the second site in `NNTT`.
- Validate the input: only the 20 standard amino-acid letters (plus known ambiguity codes you decide to handle); reject nucleotide sequences passed by mistake.
- Report positions in the numbering the user cares about (mature protein against precursor with signal peptide). State which, every time; this is the most common source of confusion in site tables.

## Mutating sites

- **Remove a site:** N to Q is the usual conservative substitution (similar size, not glycosylated); mutating S/T at position +2 or putting proline at +1 also abolishes it, but changes the backbone more.
- **Add a site:** introduce N and make sure position +1 is not proline and position +2 is S or T. An added sequon is often poorly occupied, or not occupied at all, especially in structured regions; surface loops work best.
- Check the structural context before proposing mutations: a buried asparagine, a disulfide partner or a functional residue must not be touched. Any mutation changes more than glycosylation.
- State clearly that predicted changes need experimental confirmation (site occupancy by glycopeptide mass spectrometry, activity assays, stability and, for therapeutics, immunogenicity assessment).

## Scoring O-glycosylation regions

A defensible heuristic, when no trained predictor is available, flags serine and threonine residues inside locally serine- and threonine-rich stretches, and skips residues followed by proline:

```python
def st_density_sites(seq: str, window: int = 11, min_fraction: float = 0.4):
    """Candidate O-glycosylation residues by local S/T density. A weak heuristic, not a predictor."""
    s = seq.upper()
    half = window // 2
    for i, aa in enumerate(s):
        if aa not in "ST":
            continue
        if i + 1 < len(s) and s[i + 1] == "P":        # proline at +1 disfavors initiation
            continue
        segment = s[max(0, i - half): i + half + 1]
        fraction = sum(c in "ST" for c in segment) / len(segment)
        if fraction >= min_fraction:
            yield {"position": i + 1, "residue": aa, "st_fraction": round(fraction, 3)}
```

Report it as what it is: a density-based shortlist of regions worth examining, far weaker than a trained predictor and much weaker than mass spectrometry. Mucin-like domains will light up almost entirely, which is expected and not informative on its own.

## Therapeutic antibodies, in short

The conserved N-glycan at the asparagine in the IgG Fc CH2 domain (Asn297 in EU numbering) shapes effector function:

| Change | Reported effect | Notes |
|---|---|---|
| Removing core fucose | Substantially stronger FcgammaRIIIa binding and antibody-dependent cellular cytotoxicity | The basis of several approved afucosylated antibodies |
| Removing the glycan entirely (for example N297 substitutions) | Loss of Fcgamma receptor binding and complement activation | Used deliberately for "effector-silent" formats |
| High-mannose glycans | Faster clearance in reported studies | A product-quality attribute to control |
| Terminal sialylation | Associated with anti-inflammatory activity in some settings | Context-dependent; contested in detail |
| Non-human epitopes (for example alpha-Gal, N-glycolylneuraminic acid from some hosts) | Immunogenicity risk | Host-cell choice matters |

Numbering schemes differ (EU against Kabat against sequential); always say which you are using. Treat the table as orientation: product decisions need the primary literature, analytical data and regulatory input, not a summary.

## Notation and data

- Monosaccharide shorthand: Glc, Gal, Man (hexoses), GlcNAc, GalNAc (N-acetylhexosamines), Fuc (deoxyhexose), Neu5Ac (sialic acid; Neu5Gc is its non-human variant).
- Compositions are written as counts (for example HexNAc(4)Hex(5)Fuc(1)NeuAc(1)); a composition does not define a structure, since isomers share a mass. Say "composition" when that is what the data supports.
- Machine-readable structure formats exist (GlycoCT, WURCS) and public repositories assign stable glycan identifiers; use those identifiers when exchanging structures. The public databases section of `../GUIDE.md` covers access.

## Prediction servers

Several widely used site-prediction servers are academic web services with terms that restrict commercial use and that discourage automated scraping. Before using one: read its terms, respect submission limits, prefer a downloadable version if offered, and never submit confidential sequences without permission. Label every server result as a prediction with the tool name and version.

## Analytical confirmation

- Released-glycan profiling (labeled glycans by chromatography or capillary electrophoresis with mass detection) gives the glycan distribution.
- Glycopeptide mass spectrometry gives site-specific occupancy and composition; see `mass-spectrometry.md` for FDR and confidence-level rules.
- Report occupancy per site with the method, and do not extrapolate from one expression batch to another.

## Checks (done when)

- [ ] Sequence validated as protein; numbering scheme (precursor or mature, EU or sequential) stated.
- [ ] Sequon search handles overlaps and the proline exclusion; counts of NXT and NXS reported.
- [ ] Predicted sites labeled as predictions, with structural context considered for any proposed mutation.
- [ ] Expression host named wherever glycan structures are discussed.
- [ ] Server terms checked, and no confidential sequence submitted without permission.
