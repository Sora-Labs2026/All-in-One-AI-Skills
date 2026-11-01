# Freight carriers, routing guides and shipment exceptions

Read this when the task is choosing or reviewing freight carriers, running a freight bid, building a routing guide or scorecard, or handling a delayed, damaged, short, lost or refused shipment and its claim. Customs holds are in `customs-and-trade-compliance.md`; returns from consumers in `returns-and-reverse-logistics.md`. Liability rules below are general information, not legal advice; the contract of carriage and the governing law decide.

## Ground rules

- **The shipper's own data sets the targets.** Benchmarks for on-time rates, acceptance or claims ratios vary by mode, lane, region and season. Derive thresholds from the company's last 12 months of shipments and agree them with the owner; do not import someone else's numbers as targets.
- **Compare total landed cost, not the line-haul rate.** Rate, fuel surcharge, accessorials, minimum charges and the cost of service failures together decide which carrier is cheaper.
- **Verify identity through the regulator, not the paperwork.** Carrier fraud (identity theft of real carriers, double brokering) relies on forged certificates and look-alike email domains.
- **Claims have hard deadlines.** Record the deadline for every open exception on day one.
- **Never commit volume, sign a rate confirmation or file a claim on the owner's behalf** without their approval of the exact document.

## Carrier relationships

### Price the components separately

| Component | What to pin down | Pitfall |
|---|---|---|
| Line-haul | Per-mile, per-load or (less-than-truckload) discount off the carrier's tariff, by lane | A blanket "x % off everything" hides lanes that are far above market |
| Fuel surcharge | The whole table: the index it follows (for example a national diesel average), the base price at which the surcharge is zero, the step size and how often it updates | A low line-haul paired with an aggressive table. Model total cost at three or more fuel prices before comparing bids |
| Accessorials | Detention (free time and hourly rate), liftgate, residential, appointment, inside delivery, reweigh and reclassification fees | Detention is the most common invoice dispute; long dwell at your own docks is often the cause |
| Minimums | Minimum charge per shipment or per short-haul load | Short lanes priced on per-mile rates |

### Vetting a new carrier or broker (US example)

1. Look up operating authority, insurance filings and safety data on the regulator's public register (FMCSA in the US) using the identifier the carrier gave you, then check that the phone number and email domain match the register, not only the documents sent to you.
2. Confirm insurance with the insurer or through the register's filings, not only the certificate. Federal minimum liability cover for general freight is lower than most shippers require; set your own contract minimum with your insurer.
3. For brokers, check the surety bond or trust filing and whether they carry contingent cargo cover.
4. Record the check with its date and repeat it on a schedule and before large tenders.

Other countries have their own licensing registers (for example operator licences for road haulage in the UK and EU). The principle is the same: verify against the authority, not against what the carrier supplies.

### Routing guide and allocation

- For each lane with regular volume, keep a ranked list: primary, backup and a ceiling option (often a broker or the spot market). Electronic tendering follows the order; record every rejection.
- Give each carrier enough volume on a lane to matter to them, and avoid depending on one carrier for a critical lane. Decide the concentration limit with the owner.
- Contract rates buy predictability; spot rates follow the market. A rising share of spot freight on a contract lane usually means the contract rate is below market or the carrier is rejecting tenders.
- A carrier that accepts tenders but picks up late is soft-rejecting; measure tender-to-pickup time, not only acceptance.

### Scorecards

Track a few metrics the carrier can act on, measured the same way for everyone:

| Metric | Definition to agree | Note |
|---|---|---|
| On-time pickup and on-time delivery | Within the agreed window, measured separately | Good pickup with poor delivery points at line-haul or terminals |
| Tender acceptance | Accepted tenders / tenders offered, primary lanes only | Falling acceptance on one lane signals a rate problem there |
| Claims ratio | Claim value / freight spend; also claim count | Many small claims indicate a handling problem; one large one may not |
| Invoice accuracy | Invoices matching contracted rates without correction | Chronic small overbilling costs audit time |

Share scorecards with carriers on a fixed cadence, lead reviews with the data, and put a corrective plan with dates in writing before reallocating volume.

### Freight bids (RFPs)

1. Pull 12 months of shipments: lanes, volumes, weights, equipment, special handling, current cost and service.
2. Bid lane by lane with volume ranges, transit expectations, accessorial schedule, payment terms, insurance minimums and the evaluation weights stated up front.
3. Score cost, service history, capacity commitment and operational fit separately; do not award on price alone.
4. Award in waves, give carriers time to set up, run old and new guides in parallel briefly, then cut over.
5. Keep market-rate benchmarks (lane-rate services, public freight indices) as context with their dates; none is exact.

## Shipment exceptions

### Classify, then act

| Exception | First actions |
|---|---|
| Delay | Get a new ETA from the carrier; tell the customer what you know, what you are doing and the new date |
| Visible damage | Note it on the delivery receipt before signing, photograph packaging and goods, keep everything |
| Concealed damage | Notify the carrier in writing as soon as found (many carriers set a short inspection window); keep packaging for inspection |
| Shortage or overage | Count at the tailgate; never sign clean when the count is off; an overage usually means someone else is short |
| Temperature excursion | Download the continuous logger data, not a single reading; quarantine and involve quality before any release |
| Refused or misdelivered | Establish why; storage and return charges usually follow fault |
| Lost (no scan activity) | Call origin and destination terminals for a physical location before declaring loss; then open a formal trace |

Severity is the highest of three axes: product value and expedite cost, customer impact (contract penalties, a stopped production line) and time sensitivity. Safety and regulated products (pharmaceuticals, hazardous materials) always come first.

### Claim deadlines by regime (check the contract and current law)

| Regime | Notice | Time bar | Liability limit |
|---|---|---|---|
| US domestic surface carriage (Carmack, 49 U.S.C. 14706) | Written claim within the period in the carrier's terms, which may not be shorter than 9 months from delivery | Suit at least 2 years from the carrier's written declination | Actual loss unless validly limited (released rates) |
| International road in Europe (CMR) | Apparent damage at delivery; non-apparent within 7 days (excluding Sundays and public holidays); delay within 21 days | 1 year (3 years for wilful misconduct) | 8.33 SDR per kg gross weight |
| International air (Montreal Convention 1999) | Damage within 14 days of receipt; delay within 21 days | 2 years | Per-kg SDR limit, revised every five years (26 SDR per kg from December 2024) |
| Ocean (Hague-Visby; US COGSA) | At delivery, or within 3 days if not apparent | 1 year | Hague-Visby: 666.67 SDR per package or 2 SDR per kg, whichever is higher; COGSA: USD 500 per package unless value declared |

Parcel carriers apply their own tariff limits unless declared value or insurance was bought at shipping. US carriers under the Carmack framework must acknowledge a claim within 30 days and pay or decline within 120 days (49 CFR Part 370).

### The claim file

- Bill of lading showing clean tender, delivery receipt with the exception noted, commercial invoice proving value, photographs, inspection or survey report, repair or replacement quotes, packaging specification and the correspondence timeline.
- Wait until split deliveries against one bill of lading are reconciled before claiming a shortage.
- Whether to absorb a small loss or claim it depends on the admin cost and the pattern. Log every absorbed loss against the carrier's scorecard anyway: repeated small losses are a performance issue.

### Fraud signals

The truck or driver does not match the carrier on the tender, the driver cannot name their dispatcher, insurance documents name a different company, a pickup is redirected after dispatch, or the same small shortage recurs across shipments. Do not release freight to a mismatched truck; verify through the carrier's registered contact details and involve security.

## Communication

- To carriers: reference numbers (bill of lading, pro number), what happened, what you need and by when. Escalate with the timeline of earlier contacts and the contract clause, not adjectives.
- To customers: lead with what you are doing and the revised date; do not blame a named carrier; follow up before the customer has to ask.

## Checks (done when)

- [ ] Targets and thresholds come from the company's own history and are agreed with the owner.
- [ ] Bids compared on total cost with fuel modeled across a range of prices.
- [ ] New carriers verified against the regulator's register, with contact details cross-checked and the date recorded.
- [ ] Every open exception has a classification, an owner, evidence collected and the claim deadline for its regime.
- [ ] Nothing committed, signed or filed without the owner's approval of the exact document.
