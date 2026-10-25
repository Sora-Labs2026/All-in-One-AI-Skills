# Laws and standards map

General guidance, not legal advice; have a qualified lawyer review. This is a map for scoping the 20 items and writing questions for counsel. It is not a summary of any law. Laws change, and thresholds, dates and national variations matter, so check the current official text before relying on any detail here.

## How to use this map

1. Ask the owner which markets the product serves and who its users are (consumers or businesses, adults or children).
2. Pick the rows that match. A rule usually depends on where users are, not where the company is.
3. Mark each of the 20 items in scope or `NOT_APPLICABLE` with a reason, and copy the "check with counsel" points into the report's question list.

## Privacy and electronic communications

| Framework | Where | What it generally means for the build | Items |
|---|---|---|---|
| GDPR (EU) and UK GDPR with the Data Protection Act 2018 | EU/EEA and UK users | A legal basis per purpose, transparent notices, valid consent where consent is the basis, data minimisation, processor contracts, transfer mechanisms, data subject rights within one month, children's consent ages | 1, 5, 6, 7, 8, 17, 20 |
| ePrivacy Directive (2002/58/EC) and national laws, including PECR in the UK | EU/EEA and UK | Prior consent to store or read information on a device unless strictly necessary; consent for most electronic marketing to individuals, with a narrow soft opt-in | 4, 5, 6, 18 |
| CCPA as amended by CPRA | California residents, for businesses above its thresholds | Privacy policy and notice at collection, rights to know, delete and correct, opt-out of sale and sharing (honour GPC), limits on sensitive data, 45-day responses | 1, 5, 6, 8, 20 |
| Other US state comprehensive privacy laws (for example Virginia, Colorado, Connecticut, Texas, Oregon) | Residents of each state, above each law's thresholds | Notices, opt-outs of targeted advertising and sale, opt-in for sensitive data, universal opt-out signals in several states, appeal processes | 1, 5, 6, 20 |
| Washington My Health My Data Act | Consumer health data linked to Washington | Separate consent and a dedicated policy for consumer health data | 6, 7 |
| COPPA (with the FTC's 2025 amendments) | US, children under 13 | Notice to parents, verifiable parental consent before collection, parental rights, retention and security duties, separate consent for third-party disclosure | 17, 20 |
| UK Age Appropriate Design Code | UK services likely to be used by under-18s | High-privacy defaults, no nudging, location off, child-focused data protection impact assessment | 17 |
| CAN-SPAM Act | US commercial email | Honest headers and subjects, ad identification, postal address, working opt-out honoured within 10 business days | 16, 18 |
| TCPA | US calls and texts | Prior express written consent for most marketing texts and calls | 6 |

## Consumer protection, pricing, reviews and claims

| Framework | Where | What it generally means for the build | Items |
|---|---|---|---|
| Unfair Commercial Practices Directive (2005/29/EC), as amended by the Omnibus Directive ((EU) 2019/2161) | EU consumers | No misleading or aggressive practices, no fake reviews, disclosure of how reviews are checked, 30-day lowest-price reference for announced reductions | 9, 10, 11, 12 |
| Consumer Rights Directive (2011/83/EU), as amended including by Directive (EU) 2023/2673 | EU consumers | Pre-contract information, clear order button, 14-day withdrawal and model form, refunds within 14 days, digital-content waiver rules, an online withdrawal function from June 2026 | 2, 3, 10, 16 |
| Price Indication Directive (98/6/EC) | EU consumers | Selling price including taxes; unit prices where required | 10 |
| Unfair Contract Terms Directive (93/13/EEC) | EU consumers | Plain, fair terms; unfair terms do not bind | 2, 3 |
| Directive (EU) 2024/825 on empowering consumers for the green transition | EU, from September 2026 | No generic environmental claims without recognised excellent performance; no climate-neutral claims based on offsetting | 12 |
| Digital Services Act | EU intermediaries and online platforms | Contact points, moderation terms, no deceptive interface design on platforms, trader traceability for marketplaces | 2, 9, 16 |
| E-Commerce Directive (2000/31/EC) | EU information society services | Name, geographic address, email, register, VAT and regulator details easily accessible | 16 |
| EU AI Act, Article 50 | EU, phased in | Tell people when they deal with an AI system; label synthetic content | 12 |
| DMCC Act 2024, Consumer Contracts Regulations 2013, Consumer Rights Act 2015 | UK consumers | Banned unfair practices (including fake reviews and drip pricing) with direct fines, cancellation and withdrawal rights, fair terms, subscription rules being phased in | 2, 3, 9, 10, 11, 12 |
| UK Electronic Commerce Regulations 2002 and Companies Act 2006 trading disclosures | UK | Business identity and registered details on the website | 16 |
| FTC Act Section 5 | US | No unfair or deceptive practices; a reasonable basis for objective claims; competent and reliable scientific evidence for health claims | 9, 10, 11, 12 |
| FTC Rule on the Use of Consumer Reviews and Testimonials (16 CFR Part 465) | US | No fake, bought, insider-undisclosed or suppressed reviews; no fake social-media indicators | 11 |
| FTC Endorsement Guides (16 CFR Part 255) | US | Disclose material connections; testimonials reflect typical results or disclose them | 11, 12 |
| FTC Rule on Unfair or Deceptive Fees | US live-event tickets and short-term lodging | Total price including mandatory fees shown prominently | 10 |
| FTC Guides Against Deceptive Pricing (16 CFR Part 233) | US | Genuine former prices and comparisons | 10 |
| ROSCA and state automatic-renewal laws (California's among the strictest) | US subscriptions | Clear terms before billing, express consent, simple online cancellation, reminders where required | 3, 9 |
| State all-in pricing laws (for example California SB 478) | Those states | Advertised prices include mandatory fees | 10 |

## Accessibility

| Framework | Where | What it generally means for the build | Items |
|---|---|---|---|
| ADA Title III | US businesses open to the public | Accessible websites and apps; claims usually measured against WCAG 2.x AA | 13, 14, 15 |
| European Accessibility Act (Directive (EU) 2019/882) with EN 301 549 | EU, from 28 June 2025, for listed products and services; service microenterprises exempt | Accessible e-commerce and other listed services, and published accessibility information | 13, 14, 15 |
| UK Equality Act 2010 | UK service providers | Reasonable adjustments, including for digital services | 13, 14, 15 |
| WCAG 2.2 level AA | Technical standard | The build target: text alternatives, contrast, keyboard, focus, target size, accessible authentication | 13, 14, 15 |

## Technical standards and specifications

| Standard | Used for | Items |
|---|---|---|
| RFC 2369 (`List-Unsubscribe`) and RFC 8058 (one-click unsubscribe with `List-Unsubscribe-Post`) | Mail-client unsubscribe | 18 |
| SPF, DKIM and DMARC | Sender authentication; DKIM must cover the unsubscribe headers | 18 |
| Global Privacy Control (`Sec-GPC` header, `navigator.globalPrivacyControl`) | Browser opt-out signal | 5 |
| WCAG 2.2, EN 301 549 | Accessibility conformance | 13-15 |
| SPDX licence identifiers | Naming licences in the asset inventory | 19 |

## Check the current text before relying on

- Applicability thresholds of CCPA/CPRA and each other US state law (revenue, number of consumers, share of revenue from selling data). Some are adjusted for inflation.
- National consent-age choices under GDPR Article 8, and whether a UK cookie-consent exemption covers your analytics.
- Dates on which phased-in rules apply: the EU withdrawal function, the EU green-claims rules, AI Act Article 50, UK subscription-contract rules, and US state laws taking effect after this guide was written.
- Which state laws require honouring universal opt-out signals, and how.
- The current COPPA Rule text and the accepted consent methods.
- Whether a court has changed the status of a federal rule. The FTC's 2024 click-to-cancel amendments, for example, were set aside in 2025.

## Standard questions for the lawyer

1. Which of these frameworks apply to us, given our markets, users and size?
2. What legal basis do we rely on for each purpose in the data map?
3. Are our consent banner and form wording acceptable in each market, and how long should consent and refusals be remembered?
4. Do our ad pixels or data flows count as "sale" or "sharing", and what opt-out wording do we need?
5. Are our refund, cancellation, withdrawal and renewal terms right for each market?
6. Is our audience classification for children's rules correct, and which consent method should we use?
7. Which claims in the claims register need stronger evidence or rewording?
8. Which records must we keep after deletion, and for how long?
