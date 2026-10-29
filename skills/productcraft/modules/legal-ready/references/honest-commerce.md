# Honest commerce and marketing (items 9-12)

General guidance, not legal advice; have a qualified lawyer review. Design guidance for honest persuasion is in [`../../ethical-persuasion.md`](../../ethical-persuasion.md); this file adds the legal angle, the code and the records to keep.

## 9. Remove dark patterns

- **What it is:** removing interface designs that steer people into choices they would not otherwise make. Common forms: obstruction (hard to cancel or delete), sneaking (items added to the basket, costs revealed late), interference (confirmshaming, a faint "no" next to a loud "yes", trick wording), forced action, nagging, fake urgency or scarcity, and ads disguised as content.
- **When it applies:** any funnel, checkout, upgrade, cancellation, consent, settings or notification prompt.
  - EU: the Unfair Commercial Practices Directive (2005/29/EC) covers misleading and aggressive practices. The Digital Services Act (Article 25) bars online platforms from deceptive or manipulative interface design. GDPR consent obtained this way is not valid.
  - US: CPRA states that agreement obtained through dark patterns is not consent. The FTC acts against such designs under Section 5 of the FTC Act and ROSCA.
  - UK: the DMCC Act 2024 lets the regulator fine directly for unfair commercial practices.
- **Implement:**
  - List the flows: signup, checkout, upgrade, cancel, consent, account deletion, unsubscribe, notification and permission prompts. For each, count the steps and note the labels.
  - Symmetric choices: accept and decline have the same weight. Decline labels are neutral ("No thanks", "Not now"), never shaming.
  - The basket holds only what the user added. Paid add-ons, insurance, donations and upgrades start unselected.
  - Urgency only when real: a countdown renders from a server-side `offers.ends_at` and survives a reload (`ENG-09`); stock and "people viewing" counts come from live data or are not shown.
  - Ads, sponsored placements and affiliate links are labelled ("Ad", "Sponsored", "We earn a commission").
  - Respect a "no": store `prompt_dismissals(user_id, prompt_key, dismissed_at, snooze_until)` and do not show the same prompt again before `snooze_until`.
  - Cancellation, deletion and unsubscribe take no more steps than signup and are reachable from account settings.
- **Verify:** a table of step counts per flow (signup vs cancel vs delete vs unsubscribe) in the report; screenshot review of each flow against the list above; a test that the basket total equals the items the user added; a test that reloading does not reset a countdown.
- **Common mistakes:** a retention maze; repeated "Are you sure you want to lose your benefits?" screens; a pre-selected "protect my order"; invented "3 people are looking at this"; countdowns that restart on reload; a tiny, low-contrast close button; a "continue without" link styled as body text.

## 10. No hidden fees

- **What it is:** the first price people see includes every mandatory charge. Nothing compulsory is added later ("drip pricing").
- **When it applies:** wherever a price appears, including ads, cards, pricing pages and app store listings.
  - EU: the Price Indication Directive (98/6/EC) and the Consumer Rights Directive require the total price including taxes, plus delivery charges or the fact that they apply. Consumer prices include VAT. Under the Omnibus Directive ((EU) 2019/2161), an announced price reduction must show the lowest price of the previous 30 days as the reference.
  - UK: the DMCC Act 2024 treats drip pricing as misleading.
  - US: the FTC's Rule on Unfair or Deceptive Fees requires total prices including mandatory fees for live-event tickets and short-term lodging. California (SB 478) and some other states apply all-in pricing to most goods and services, with exceptions such as government taxes or shipping in some laws. The FTC's Guides Against Deceptive Pricing (16 CFR Part 233) require a "was" price to be a genuine former price.
- **Implement:**
  - One server endpoint computes prices, for example `GET /api/quote?sku=pro&region=DE`:

    ```json
    {"currency": "EUR", "base_minor": 1000,
     "mandatory_fees": [{"code": "service", "label": "Service fee", "amount_minor": 150}],
     "tax": {"included": true, "amount_minor": 184},
     "shipping_minor": null, "total_minor": 1150,
     "recurring": {"interval": "month", "amount_minor": 1150, "first_charge_date": "2026-11-24"}}
    ```

  - Every surface renders `total_minor` as the headline price, with the breakdown available. The client never adds a mandatory fee itself.
  - Data model: `prices(sku, region, currency, amount_minor, tax_inclusive, interval)`, `fees(code, mandatory, amount_minor or percent, applies_to)`, and optional extras with `default_selected = false`.
  - Recurring prices state the billed amount and interval ("€120 billed yearly", optionally with "€10 a month equivalent"), the trial length, and the price and date of the first charge.
  - Reductions: keep `price_history(sku, region, amount_minor, valid_from)`, compute the 30-day lowest price for EU displays, and show a struck-through price only when it is genuine.
  - Always show the currency, and label converted amounts as estimates.
- **Verify:** an end-to-end test for fixture products in each region asserts listing price = checkout total = amount sent to the payment provider (in its sandbox). A unit test asserts every `mandatory` fee is in the headline. A unit test checks the 30-day lowest price on a fixture history. Snapshot the pricing page.
- **Common mistakes:** "+ service fee" at the last step; "from $9" when nothing sells at $9; a per-month price for an annual plan without the billed total; VAT added at checkout for EU consumers; a "free" trial that converts without stating the price; an ad price that differs from the site.

## 11. No fake reviews or testimonials

- **What it is:** every review, rating, testimonial, customer logo, endorsement and count comes from a real, identifiable source, is shown fairly, and discloses incentives and relationships.
- **When it applies:** any review system, testimonial section, logo wall, star rating, "used by" count or influencer content.
  - US: the FTC's Rule on the Use of Consumer Reviews and Testimonials (16 CFR Part 465, in force since October 2024) bans fake reviews (including generated reviews attributed to people who do not exist or did not use the product), buying reviews conditioned on their sentiment, undisclosed insider reviews, company-run "independent" review sites, suppressing reviews by threats or false accusations, and buying fake followers or views. The FTC Endorsement Guides (16 CFR Part 255) require clear disclosure of material connections, and testimonials must reflect typical results or state what people can generally expect.
  - EU: the UCPD as amended by the Omnibus Directive bans presenting reviews as genuine without reasonable steps to check them and bans fake or commissioned reviews. Traders must explain whether and how they verify reviews.
  - UK: the DMCC Act 2024 bans fake reviews and concealed incentivised reviews.
- **Implement:**
  - `reviews(id, product_id, user_id, order_id, rating, body, created_at, status, rejection_reason_code, verified_purchase, incentive, relationship, source, source_url)` where `incentive` is `none`, `discount`, `free_product` or `prize_entry`, and `relationship` is `customer`, `employee`, `affiliate` or `partner`.
  - `verified_purchase` is set by the server only when `order_id` belongs to the reviewer. Incentivised and insider reviews carry a visible label, or insider reviews are excluded.
  - Average ratings are computed from all published reviews and never filtered by star. Rejection only for reasons in the published policy (spam, abuse, off-topic), recorded as a reason code.
  - A `/reviews-policy` page explains how reviews are collected, verified and moderated.
  - `testimonials(person_name, quote, consent_ref, consent_at, material_connection, results_typical, typical_results_note, source)`. Quotes are approved by the person. Customer logos need written permission (`[[LEGAL: logo permission on file]]`). Counts ("2,000 teams") are computed from data or supplied by the owner with a source.
  - Structured rating data in page markup is generated from the real aggregate, never hard-coded.

  - Search engines add their own rules for rating markup (genuine reviews visible on the page, no self-serving reviews of the business itself) and can withdraw rich results or take manual action: `../../search-visibility/references/structured-data-and-social-cards.md`.
  - Generated or demo testimonials are removed before launch or replaced with `[[LEGAL: real testimonial needed]]`.
- **Verify:** every item in the scanner's `REVIEWS_TESTIMONIALS` list and every testimonial, logo and count on screen maps to a record with source and permission. A test computes the average from fixtures that include one-star reviews. Incentive labels render. No rating literal remains in markup.
- **Common mistakes:** generated landing-page testimonials ("Sarah J., CEO") left in; stock photos with invented names; logo walls of companies that are not customers; incentives tied to five-star reviews; hiding one- and two-star reviews; a "verified" badge with no verification; asking only happy customers for public reviews, which skews the overall picture.

## 12. No unsupported claims

- **What it is:** every objective claim (speed, savings, accuracy, health effects, security, AI capability, environmental benefit, rankings, user counts) has evidence before it is published, and its wording does not go beyond that evidence.
- **When it applies:** all marketing and product copy, app store text, ads, emails and onboarding.
  - US: under Section 5 of the FTC Act, advertisers need a reasonable basis before making objective claims, and health claims need competent and reliable scientific evidence. The FTC has brought cases over exaggerated AI capability claims.
  - EU: the UCPD covers misleading claims. Directive (EU) 2024/825, applying from September 2026, bans generic environmental claims such as "eco-friendly" without recognised excellent environmental performance, and bans "climate neutral" claims based on offsetting. The AI Act (Article 50) adds transparency duties, such as telling people they are dealing with an AI system and labelling synthetic content. They are being phased in, so check which apply on the launch date.
  - UK: the DMCC Act 2024 covers misleading claims.
  - Everywhere: software that claims to diagnose, treat or prevent a condition may be regulated as a medical device. Claims of compliance or certification ("GDPR compliant", "SOC 2 certified") must be literally true and current.
- **Implement:**
  - A claims register, for example `docs/legal/claims.yaml`:

    ```yaml
    - id: import-speed
      text: "Import 1,000 rows in under a minute"
      where: [locales/en.json#hero.subtitle]
      type: performance
      evidence: "[[LEGAL: link to benchmark report]]"
      method: "Median of 50 imports of a 1,000-row file on the standard plan, measured 2026-09"
      owner: product
      review_by: 2027-03-01
    ```

  - Rewrite or remove any claim without evidence. Qualify what remains ("in our tests on…"), date benchmarks, and state the baseline and typical result for savings.
  - AI features: describe what the feature does and its limits, take accuracy figures only from a documented evaluation (dataset, date, metric), label AI chat ("You are chatting with an AI assistant") and generated media, and never say it replaces a professional.
  - Security copy describes measures ("data encrypted in transit and at rest"), not guarantees ("unhackable", "100% secure", "bank-level").
  - Keep copy in locale or content files where review and the scanner can see it.
- **Verify:** every `CLAIMS_TO_SUBSTANTIATE` hit is removed, rewritten, or present in the register with evidence. Every register `where` still exists and no `review_by` date has passed. AI disclosures appear in screenshots.
- **Common mistakes:** generated copy with invented statistics; "trusted by 10,000+" with 200 users; a "GDPR compliant" badge; "AI-powered" on a rules engine; accuracy from hand-picked examples; "clinically proven" based on another product's study; "carbon neutral" through offsets; an old benchmark kept after the product changed.
