# Market research reports

Read this when the user wants a market sizing, competitive landscape, industry overview, customer segmentation or opportunity assessment, for a business plan, product decision, grant impact section or investor memo. Pulling official statistics and company filings is in `../../data-engineering/references/economic-statistics-apis.md` and `../../data-engineering/references/filings-and-market-data.md`; web research method in `web-research-and-extraction.md`. This is analysis, never investment advice.

## Start from the decision

- **Decision:** what will the user decide with this (enter a market, price a product, prioritize a segment, size a grant's impact)? The decision sets the depth; a go/no-go needs ranges, not a 60-page report.
- **Market definition:** product or service category, customer type, geography, channel and time frame. Most disagreements between market-size estimates come from different definitions; write yours down before searching.
- **Questions:** the five to ten questions the report must answer, agreed with the user.

## Sources, strongest first

| Source | Use | Watch for |
|---|---|---|
| Official statistics (national statistics offices, census and business surveys, trade data, central banks) | Counts of firms, households, spending, prices, trade flows | Definitions and classification codes; revisions; release dates |
| Regulatory filings and annual reports | Revenue by segment, customer counts, guidance, risk factors | Segment definitions change between years; fiscal years differ |
| Industry associations and public registries | Installed base, members, shipments | Membership bias; methodology often thin |
| Peer-reviewed and institutional research | Adoption, willingness to pay, behavior | Sample and setting may not match |
| Analyst and consultancy reports | Estimates and forecasts | Usually paywalled; figures quoted in press releases are marketing; methods unstated |
| Company websites, pricing pages, job postings | Offerings, prices, strategy signals | Change without notice; archive what you cite |
| Your own primary research (interviews, surveys) | The user's specific customers and questions | Sampling and question bias |

Many websites publish "market size" figures for nearly any category, with wildly different numbers and no method. Do not pick the one you like: show the spread, the definitions behind each, and explain why your estimate differs. Cite a paywalled estimate as what it is ("estimate by firm X, published in a press release of date Y; method not disclosed").

Respect terms of service and law: no deception or pretexting to obtain competitor information, no scraping behind logins, no use of confidential information the user should not have.

## Size the market two ways

- **TAM** (total addressable market): everyone who could buy this kind of product in the defined scope.
- **SAM** (serviceable available market): the part your offering can reach with its product, channel and geography.
- **SOM** (serviceable obtainable market): the part you can realistically win in the time frame, given competition and capacity.

Estimate top-down (a total from statistics or filings, narrowed by filters) and bottom-up (number of customers times adoption times price), then reconcile. A large gap means an assumption is wrong; find it.

```python
# Bottom-up sizing with explicit, sourced assumptions and a sensitivity range
assumptions = {   # value, low, high, source
    "target_firms":    (42_000, 38_000, 46_000, "national business register, 2025, firms with 10-249 staff in sector C"),
    "adoption_share":  (0.12, 0.06, 0.20, "user's 2026 survey, n=210; 95% CI"),
    "annual_price":    (4_800, 3_600, 6_000, "price list of three competitors, archived 2026-10-01"),
}

def size(a):
    return a["target_firms"] * a["adoption_share"] * a["annual_price"]

base = {k: v[0] for k, v in assumptions.items()}
print(f"SAM base: {size(base):,.0f} per year")
for k, (_, lo, hi, _) in assumptions.items():           # one-at-a-time sensitivity
    print(f"{k:15s} {size({**base, k: lo}):>14,.0f} .. {size({**base, k: hi}):>14,.0f}")
```

State currency, price year (nominal or inflation-adjusted) and exchange rates with their dates. Present a range with the assumptions that drive it, not a single number with false precision.

## Growth

```python
def cagr(start_value, end_value, years):
    return (end_value / start_value) ** (1 / years) - 1

print(f"{cagr(1.20e9, 1.85e9, 2025 - 2020):.1%}")   # 5 intervals between 2020 and 2025
```

Count intervals, not calendar years (2020 to 2025 is five). Distinguish historical growth from forecasts, name who made each forecast and when, and do not extend a past growth rate far into the future without a reason.

## Competitive landscape

- **The set:** direct competitors, indirect ones solving the same job differently, substitutes (spreadsheets, agencies, in-house builds) and doing nothing.
- **Comparison table** on the attributes customers use to choose (price and pricing model, key capabilities, target segment, integrations, support, compliance), each cell with a source and date. Archive the pages you cite.
- **Positioning:** where competitors cluster and where there is room; back it with customer evidence, not only a 2 by 2 chart.
- Facts about named companies must be sourced and fair.

## Frameworks: use only what changes the conclusion

Five forces (rivalry, buyers, suppliers, entrants, substitutes), PESTLE (political, economic, social, technological, legal, environmental), SWOT, value chain and jobs-to-be-done are checklists for not missing something. Include one only when it produces a specific implication ("buyer power is high because three distributors control 70 % of the channel, so margins below X are likely"). A SWOT that does not lead to an action is decoration.

## Customer evidence

- Interviews: recruit beyond friendly customers, ask about past behavior rather than hypothetical purchases, record and code answers.
- Surveys: define the population and sampling, avoid leading questions, report response rates and margins of error; willingness-to-pay questions overstate real payment.
- Reviews and forums: useful for themes, not for proportions; respect the sites' terms.

## Report shape (length follows the decision)

1. Answer first: the recommendation or the sized opportunity, with its range and confidence.
2. Market definition and scope.
3. Size and growth, with both methods, assumptions and sensitivity.
4. Customers and segments.
5. Competition.
6. Risks and uncertainties, including regulatory ones.
7. Implications and options for the decision.
8. Appendix: methods, sources with dates, assumption register, data tables.

Charts are built from the data with code (`../../data-engineering/references/plotting.md`); every chart has a source line.

## Guardrails

- Label every number as reported, estimated or forecast, with its source and date. Never invent companies, customers, quotes or figures.
- Projections are scenarios with stated assumptions, not predictions (`scenarios-and-panels.md`).
- No investment, trading or securities recommendations; financial figures are context for the user's own decision.

## Checks (done when)

- [ ] Decision, market definition and questions agreed and written down.
- [ ] Every figure sourced and dated; estimates labeled; spreads between sources shown and explained.
- [ ] Top-down and bottom-up sizing reconciled, with a sensitivity range in code.
- [ ] Competitor comparisons sourced, dated and archived; no information obtained improperly.
- [ ] Frameworks used only where they yield an implication; the report leads with the answer.
