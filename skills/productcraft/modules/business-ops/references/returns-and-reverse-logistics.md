# Returns, warranty claims and reverse logistics

Read this when the task is a returns policy or workflow, grading returned goods, choosing a disposition channel, recovering cost from vendors, handling warranty claims, or spotting return abuse. The customer-facing refund and cancellation pages, statutory withdrawal rights and their implementation are in `../../legal-ready/references/policies-and-consent.md` (item 3); the payment-side refund mechanics are in `../../integrations/references/payments-stripe.md` and `billing-operations.md`. Consumer law here is general information, not legal advice.

## Ground rules

- **Statutory rights come before policy.** A store policy can be more generous than the law, never less. In the EU, most distance sales carry a 14-day right of withdrawal with a refund due within 14 days of withdrawal (the trader may wait until the goods are back or proof of return is supplied); the trader may deduct only for diminished value caused by handling beyond what is needed to establish the nature of the goods, not charge a general restocking fee. EU law also gives at least a two-year legal guarantee of conformity for goods. The UK's Consumer Rights Act 2015 gives a 30-day short-term right to reject faulty goods. US rules come mostly from state law, card-network rules and the retailer's posted policy. Ask the owner which markets apply.
- **A recall is not a return.** Products under a safety recall follow the recall programme and its reporting, never the normal returns flow.
- **Abuse detection supports human decisions.** Scores and flags route a return to review; a person decides. Automated refusals that significantly affect someone raise duties under the GDPR (Article 22) and similar laws, and false accusations harm good customers.
- **Do not tell a customer they are suspected of fraud.** Say the return needs more time to process and give a date; keep the evidence internal.

## Policy design

Write the policy as data the systems can apply, with an owner for exceptions:

| Element | Decide |
|---|---|
| Window | Per category, starting from delivery; how holiday purchases are treated |
| Condition | What "unused" means per category (opened packaging is normal unboxing; worn or damaged is not); hygiene and sealed-goods rules |
| Proof of purchase | Order lookup by account, card or loyalty ID; gift receipts give exchange or credit at the price paid |
| Refund method and amount | To the original payment method at the price actually paid, not the current shelf price |
| Fees | Only where lawful and disclosed before purchase; waived for faulty goods and fulfilment errors |
| Cross-channel | Buy online, return in store: the refund matches the original price; the item either re-enters store stock or is routed to a returns centre |
| Low-value items | "Returnless refund" when return shipping and handling cost more than the recoverable value, with abuse limits |
| Exceptions | A short written order of questions: is the product faulty? is the request reasonable to a neutral observer? can the item be resold? does granting it set a public precedent? |

## Receiving and grading

Use a written grading rubric per category with photographs of each grade, and audit inspectors' agreement on a sample. A typical scale:

| Grade | Condition | Usual route |
|---|---|---|
| A | As new, complete, passes functional test | Restock as new where the law and the brand allow, or as open-box |
| B | Minor cosmetic wear or damaged packaging, complete, functional | Open-box or renewed channel after repackaging |
| C | Visible wear, minor damage or missing low-value parts, functional | Outlet, marketplace or liquidation; refurbish if the numbers work |
| D | Not functional or missing critical parts | Parts recovery, recycling or certified destruction |

- Electronics need a functional test and a data-wipe step with a record; check serial numbers against the order to catch swapped items.
- Selling a used or refurbished item as new is misleading; label condition truthfully.
- Opened cosmetics, personal-care products, medicines and some food are usually not resaleable; follow product-safety and hygiene rules.

## Disposition economics

For each grade and category, compare the net recovery of each channel: expected price minus processing (inspection, repackaging, refurbishment, testing), storage, shipping and channel fees, and the time to sell. Write the rule as a table the system applies, review it quarterly against actual recoveries, and keep these constraints:

- Hazardous returns (lithium batteries, aerosols, chemicals) need dangerous-goods packaging and carriers that accept them; do not send them through the normal parcel return label.
- Mixed-category liquidation lots tend to sell at the lowest category's price; sort before selling.
- Donations need product-safety compliance and brand rules; tax treatment is a question for the owner's tax adviser.
- Destruction needs a certificate for compliance and tax records. Since 19 July 2026, large companies in the EU may not destroy unsold apparel and footwear, which includes items returned under the right of withdrawal, under the Ecodesign for Sustainable Products Regulation (EU) 2024/1781, with narrow exceptions; check the current scope and dates for your size and products.

## Vendor recovery and warranty

- Return-to-vendor claims have windows set by the vendor agreement; track the deadline per unit from the day it is received, and batch shipments to meet vendor minimums without missing windows.
- Defect claims need evidence aggregated by item: counts, defect codes, photos and customer complaint data, measured against the defect allowance in the agreement.
- Keep three things apart in systems and communication: the retailer's return window, the manufacturer's warranty, and any extended warranty or protection plan sold by a third party (whose administrator handles claims).
- Warranty decisions on modified or misused products depend on the warranty terms and consumer law (a modification does not void cover for an unrelated defect in many jurisdictions); document what was inspected.

## Abuse and fraud patterns

| Pattern | Signals | Proportionate response |
|---|---|---|
| Item swap | Serial or weight mismatch, counterfeit or older unit in the box | Inspect before refund for high-value items; serial capture at sale |
| Wear and return | Odour, cosmetics, stretched fabric, removed tags | Condition rules stated in the policy; tags that must stay attached |
| Price arbitrage | Refund requested at a higher price than paid | Refund tied to the actual transaction |
| Receipt fraud | No-receipt returns for cash | Refund to original payment; limits on no-receipt returns |
| Serial returning | High return rate; but many are bracket shoppers (several sizes) | Judge on net value and condition, not rate alone; improve fit information first |
| Organised retail crime | Many identities, one address; high-theft categories | Escalate to loss prevention; outside normal returns handling |

Keep the data used for abuse detection to what the purpose needs, state it in the privacy notice, and set a retention period.

## Metrics worth tracking

Processing time from receipt to refund, grading agreement on audits, recovery rate by channel, vendor recovery against eligible amounts, refund disputes, and reasons for return by item (which feed product, sizing and content fixes upstream). Set targets from your own baseline.

## Checks (done when)

- [ ] The policy states statutory rights for each market and never undercuts them.
- [ ] Grading rubric with photos per category; inspector agreement audited.
- [ ] Disposition rules show the net-recovery calculation and respect hazardous-goods, product-safety and destruction rules.
- [ ] Vendor and warranty deadlines are tracked per unit.
- [ ] Abuse flags route to human review; customer messages are neutral; recalled products are diverted to the recall process.
