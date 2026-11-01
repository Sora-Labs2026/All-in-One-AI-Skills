# Energy procurement for commercial and industrial sites

Read this when the task is understanding an electricity or gas bill, comparing supply offers, planning a tender, reducing demand or capacity charges, or assessing a renewable power purchase agreement (PPA) or certificate purchase. Market rules differ by country and region (and within the US by wholesale market and state). **This is general information, not financial, trading or legal advice:** contracts that hedge price risk can be financial instruments, and long-term commitments need the owner's finance and legal sign-off.

## Ground rules

- **Start from interval meter data**, not the annual total. Fifteen- or thirty-minute data (depending on the market) shows the load shape, the peaks and which hours drive cost.
- **Separate what is competitive from what is regulated.** In liberalised markets only the energy (and sometimes capacity) component is bought from a supplier; network charges and many levies pass through whatever the supply contract says.
- **Quote prices with their date, source and tenor.** Forward prices move daily; a quote without a timestamp cannot be compared.
- **Present options and their risk, not a market call.** Nobody times the bottom reliably; say what each structure costs in a calm year and in a stress year.

## Read the bill first

| Component | How it is charged | What reduces it |
|---|---|---|
| Energy | Per kWh: flat, time-of-use bands, or indexed to wholesale prices | Procurement structure; shifting load to cheaper hours |
| Demand (peak) charge | The highest averaged interval in the billing period times a rate per kW or kVA | Avoiding simultaneous start-ups; peak shaving; power-factor correction where billed in kVA |
| Demand ratchet | Billed demand may not fall below a share of the highest peak over the prior months | Preventing one-off peaks (commissioning, tests); check the tariff before any change that could spike load |
| Capacity or coincident-peak charges | Your load during a few system peak hours sets next period's charge (for example a peak-load contribution or "tag") | Curtailing during the expected system peak hours |
| Transmission and distribution | Regulated tariffs: fixed, per-kW and per-kWh parts | Tariff selection; rarely avoided by on-site generation, since grid connection is still used |
| Levies, riders and taxes | Policy costs, set by regulators and governments | Exemptions where the site qualifies; track rate cases and policy changes |

Useful load metrics:

- **Load factor** = energy in the period / (peak demand x hours in the period). A flat profile (high load factor) suits baseload blocks; a peaky one makes demand charges and shaped products matter more.
- **Peak attribution:** list the top intervals each month and what was running. Peaks usually come from coincident start-ups or one process, not from total consumption.

A first pass over an interval export (columns `timestamp`, `kwh`, one row per 15-minute interval; check the meter's interval length and time zone first):

```python
import pandas as pd

df = pd.read_csv("intervals.csv", parse_dates=["timestamp"]).set_index("timestamp").sort_index()
interval_h = 0.25                                    # 15-minute data
df["kw"] = df["kwh"] / interval_h                    # average demand in each interval
for month, m in df.groupby(df.index.to_period("M")):
    peak_kw = m["kw"].max()
    load_factor = m["kwh"].sum() / (peak_kw * len(m) * interval_h)
    top = m["kw"].nlargest(5)
    print(month, f"peak {peak_kw:.0f} kW", f"load factor {load_factor:.2f}",
          "top intervals:", ", ".join(t.strftime("%d %H:%M") for t in top.index))
```

Check for gaps and daylight-saving duplicates before trusting the result; billing demand may also use a different interval length or kVA rather than kW, so reconcile one month against the actual bill.

## Supply structures

| Structure | You carry | Suits |
|---|---|---|
| Fixed price, full requirements | Little price risk; you pay the supplier's risk premium; volume tolerance bands may apply | Organisations that value budget certainty |
| Index (wholesale pass-through plus adder) | Full price risk, including extreme events | Organisations with risk tolerance, hedging capability and treasury oversight |
| Block and index | Fixed blocks for the predictable baseload; the rest floats | Sites with a stable base and variable top-up |
| Layered (tranche) buying | Prices averaged over several purchase dates | Most buyers who cannot or should not time the market |

Tender checklist: interval data (ideally several years), site and meter list, contract start and end dates, volume tolerances, product options requested, renewable content, credit terms, change-of-use and termination clauses, and how pass-through charges and change-in-law costs are treated. Assess supplier creditworthiness: a supplier failure mid-contract can drop sites onto default or fallback tariffs.

Stress test every structure: what happens to cost under a winter or summer extreme, a supply shock, a 20 % volume change, or a regulatory charge increase? Extreme scarcity pricing in some wholesale markets has turned unhedged index exposure into very large bills within days.

## Reducing demand and capacity costs

1. Rank interventions by stacked value: avoided demand charges + avoided capacity or coincident-peak charges + time-of-use savings + any demand-response payments, minus operating impact.
2. Low-cost first: staggered start-up sequences, interlocks on non-critical loads, scheduling batch processes and charging off-peak, fixing compressed-air leaks and controls.
3. Capital options (batteries, thermal storage, on-site generation) need a model with real interval data, degradation, maintenance, and the tariff and market rules as they stand, plus a sensitivity to rule changes. Present payback as a range.
4. Demand-response programmes pay for curtailment but carry obligations and penalties; make sure operations can actually curtail when called.

## Renewable sourcing and reporting

- **Physical PPA:** buy the output of a specific generator for a long term; you take shape risk (it produces when the weather allows), volume and curtailment risk, and often basis risk between the generator's location and your load.
- **Virtual (financial) PPA:** a contract for differences against a market price at a settlement point; your physical supply does not change. Settlements can be negative for long periods, and negative-price hours can create payments you owe under some terms. These contracts may need derivative accounting assessment and treasury approval.
- **Certificates:** renewable energy certificates (RECs) in North America, Guarantees of Origin in Europe, and other national schemes record the attribute of one MWh of renewable generation. Unbundled certificates are cheap but do little to add new generation; say so honestly in sustainability claims.
- **Greenhouse-gas reporting:** the GHG Protocol's Scope 2 Guidance (2015) requires dual reporting, location-based and market-based. The Protocol has been revising its Scope 2 standard (with proposals such as hourly matching and deliverability requirements); check which version your reporting framework requires before designing a procurement around a claim.
- Marketing claims built on energy purchases ("100 % renewable", "carbon neutral") are regulated in several markets; route them through the claims register in `../../legal-ready/references/honest-commerce.md`.

## PPA due diligence questions

- Strike price versus forward curves over the full term, under high and low price scenarios; not only at signing.
- Historical basis between the project's node or zone and the settlement point; who carries curtailment and negative-price hours.
- Volume: as-generated or a fixed shape; delivery shortfall remedies.
- Credit support required (letters of credit, guarantees) and its cost.
- Change in law, termination, and what happens if the project is late.

## Checks (done when)

- [ ] The bill is decomposed into components with the share of cost each represents, from actual bills and interval data.
- [ ] Every price quoted carries its date, source and tenor.
- [ ] Each supply option is shown with its cost in a normal year and in at least one stress scenario.
- [ ] Demand interventions are ranked by stacked value with the tariff clauses they depend on (ratchets, coincident peaks) cited.
- [ ] Long-term or financial commitments are flagged for finance, treasury and legal approval; no recommendation is presented as a trading call.
