# Investor materials and outreach

Read this when the task is a pitch deck, one-pager, investor memo, financial model, use-of-funds table, accelerator application, investor update, or emails to investors. Market sizing is in `../../research-writing/references/market-research.md`; slides and talk mechanics in `../../research-writing/references/slides-and-talks.md` and `../../documents/references/powerpoint-pptx.md`; stress-testing a plan in `../../research-writing/references/stress-tests.md`. **Nothing here is investment, securities or legal advice.** Fundraising is regulated; the company's counsel decides how an offering may be promoted.

## Ground rules

- **One source of truth.** Every number, title and date in every asset comes from a single fact sheet the founder confirms. When two documents disagree, stop and resolve it before drafting.
- **Never invent traction, customers, quotes, logos, team credentials or commitments.** Missing facts get a visible placeholder (`[[FACT: ARR at 2026-10-31]]`).
- **Label the status of each figure:** actual (with date and source), committed (signed), pipeline, or projection.
- **Projections are scenarios with stated assumptions**, not predictions; say so on the page.
- **Securities rules decide who may receive what.** In the US, a Regulation D Rule 506(b) offering may not use general solicitation, while 506(c) allows it but requires verifying that every purchaser is accredited; in the UK, communicating an invitation to invest generally needs approval by an authorised firm unless an exemption applies; the EU and other countries have their own regimes. Ask the founder which route counsel has chosen before any public post, mass email or website page mentions the raise.
- **Outreach is personal and permission-respecting.** No bulk scraping of investor contacts, no automated messaging sequences, an easy way to say no, and a stop when someone says it.

## The fact sheet

Keep it in the repository or a shared document, with an owner and an "as of" date:

| Area | Facts |
|---|---|
| Company | Legal name, one-sentence description, founding date, locations, headcount |
| Traction | Revenue measure and definition, customers, retention, growth, usage, each with date and source |
| Business model | Pricing, unit economics, sales motion |
| Round | Amount, instrument (equity, SAFE, convertible note), key terms the founder is willing to share, lead status |
| Use of funds | Categories that sum to the round, milestones they buy, months of runway |
| Team | Names, titles, relevant prior roles, as the people themselves approve them |
| Risks | The ones an investor will ask about anyway |

## Assets

### Deck

A common order: what the company does and for whom; the problem with evidence; the solution and product (a demo or real screenshots); why now; market (sized two ways, from the market-research reference); business model; traction; competition and differentiation (honest, see `competitive-analysis.md`); team; the ask, use of funds and milestones; appendix. Each slide makes one claim in its title, supported by the content. Keep a source note for every figure.

### One-pager and memo

Lead with the one-sentence description and the strongest proof, then the ask. A memo can carry the reasoning a deck cannot: assumptions, risks and how the team will know it is working.

### Financial model

- Separate inputs (assumptions with sources), calculations and outputs on different sheets; no hard-coded numbers inside formulas.
- Build revenue from drivers (customers x price x retention, or volume x conversion x price), not from a growth rate typed into a cell.
- Show a base case and at least a downside case, plus a sensitivity table on the two or three assumptions that move the outcome most.
- Check that the use of funds sums to the round, that headcount drives salary costs, that cash never goes negative without a financing event, and that the model ties to the deck. Spreadsheet mechanics are in `../../documents/references/excel-xlsx.md`.

### Applications (accelerators, grants, competitions)

Answer exactly the question asked, within the limit, using the fact sheet. Grant proposals have their own reference (`../../research-writing/references/grant-proposals.md`).

## Researching investors

Research firms and their public statements, not people's private lives: fund focus, stage, typical cheque size, relevant portfolio companies, published thesis or talks, and whether a portfolio company competes with yours. Record each fact with its source and date. Do not compile profiles of individuals beyond their professional role and public statements, and do not use leaked or paywalled data the user is not entitled to.

## Outreach

- **Warm introductions first.** Make the connector's job easy: why this investor fits, and a forwardable blurb of a few sentences that stands on its own.
- **Cold email:** a specific subject line; one sentence on why this investor (a real link to their focus or portfolio); what the company does and the strongest proof; one concrete ask (a call, a deck review). If no genuine reason for fit exists, say the draft is not ready rather than inventing one.
- **Follow-ups:** a small number, each adding something new (a milestone, a customer), then stop. Respect any "not now" and record it.
- **Investor updates** (to existing investors and those who asked to follow): the same structure every time: highlights, key metrics with definitions, lowlights, asks, cash and runway. Consistency builds trust.
- **Privacy and email law:** investor contact data is personal data under the GDPR and similar laws; keep a record of where each contact came from, include the sender's identity and a way to opt out, and honour opt-outs. Individual messages written to one person differ from bulk marketing, but anti-spam rules (CAN-SPAM in the US; PECR in the UK) still require honest headers and subject lines. Details in `../../legal-ready/references/business-children-email-assets-rights.md` (item 18).
- **Send only after the founder approves each message;** draft by default (`email-and-messaging-ops.md`).

An update template that stays the same every month:

```markdown
Subject: [Company] update, [Month Year]

Highlights:   2-3 facts with numbers (and the date they were measured)
Metrics:      [metric]: [value] ([definition]; previous: [value])
Lowlights:    what went wrong and what you are doing about it
Asks:         specific introductions, hires or advice
Cash:         [cash at month end], [net burn], [runway in months]
Next month:   the 1-3 things you will report on
```

## Words to cut

Superlatives without evidence ("revolutionary", "massive"), vague founder adjectives, praise for an investor's thesis with no connection to the company, and soft closings when a direct ask is clearer. Replace each with a fact or delete it.

## Checks (done when)

- [ ] Every figure in every asset traces to the dated fact sheet; all assets agree.
- [ ] Projections are labelled as scenarios with assumptions and a downside case.
- [ ] Use of funds sums to the round; the model's outputs match the deck.
- [ ] The promotion route was confirmed with the founder (and their counsel) before anything public mentions the raise.
- [ ] Each outreach draft has a genuine, sourced reason for fit, one ask, and an opt-out path; nothing was sent without approval.
