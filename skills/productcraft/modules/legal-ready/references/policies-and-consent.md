# Policies and consent (items 1-6)

General guidance, not legal advice; have a qualified lawyer review. Every legal fact below marked `[[LEGAL: ...]]` comes from the owner, never from the agent.

Shared building blocks used by several items:

- **Policy versions.** Keep every published version: `policy_versions(id, kind, version, published_at, content_hash, url)` where `kind` is `privacy`, `terms`, `cookies` or `refund`. Pages show "Last updated" and keep old versions reachable (for example `/terms/v/2026-03-01`).
- **One consent registry.** A single file (for example `consent/registry.json`) lists consent categories and every cookie, storage key, pixel and SDK with its category. The banner, the script loader and the cookie policy page all read it, so they cannot drift apart.

## 1. Privacy policy

- **What it is:** the public notice that says what personal data the product collects, why, on what legal basis, who receives it, how long it is kept, what rights people have and how to use them.
- **When it applies:** whenever personal data is processed, which includes IP addresses in logs, analytics identifiers and email addresses. GDPR and UK GDPR (Articles 13 and 14) set the content for people in the EU and UK. CCPA/CPRA requires a privacy policy and a notice at collection, and other US state privacy laws require similar notices once their thresholds are met. COPPA adds a children's notice. The major app stores require a privacy policy link for apps.
- **Implement:**
  - A `/privacy` route, a link in every page footer and in the app's settings screen, and a short notice with a link next to every form that collects data ("We use your email to send receipts. See our Privacy policy.").
  - Write it from the data map, section by section: who we are and how to contact us (`[[LEGAL: legal entity, address, privacy contact]]`, DPO or EU/UK representative if required); a table of data categories with source, purpose, legal basis and retention; recipients and processors by category; international transfers and their safeguards (`[[LEGAL: transfer mechanism]]`); people's rights and exactly how to use them (link to account settings and the request form from item 20); cookies (link to item 4); children; automated decisions, if any; how changes are announced; the right to complain to a data protection authority.
  - For US readers, add the categories collected in the past 12 months, whether data is sold or shared for cross-context advertising, sensitive data uses, retention per category and the opt-out links from item 5.
  - Render from a source file in the repository (or the CMS) and record each published version in `policy_versions`.
- **Verify:** an end-to-end test or link crawl confirms the footer link resolves on every template and app screen. Check every row of the data map and every vendor in the item 8 inventory against the policy. The scanner's `PRIVACY_POLICY` and `UNRESOLVED_PLACEHOLDERS` checks are clean. The store listing links to the same page. California expects a review at least every 12 months, so set a reminder.
- **Common mistakes:** a copied template that lists data you do not collect and misses what you do (analytics, session replay, AI prompts); "we never share your data" while ad pixels run; no legal basis per purpose; retention "as long as necessary" with no criteria; a policy on the marketing site but not reachable in the app; a hosted policy on a generator's domain that later expires; silent edits with no version.

## 2. Terms of service

- **What it is:** the contract with users: the service, accounts, acceptable use, fees and billing, user content and licences, intellectual property, suspension and termination, warranties and liability within what consumer law allows, disputes, changes, and governing law (`[[LEGAL: governing law and venue]]`).
- **When it applies:** accounts, paid features, user-generated content, APIs or any ongoing relationship. In the EU and UK, unfair terms do not bind consumers (Unfair Contract Terms Directive 93/13/EEC; UK Consumer Rights Act 2015), and a choice-of-law clause cannot remove a consumer's home-country mandatory protections. Services that host user content also have Digital Services Act duties, such as explaining content moderation in the terms.
- **Implement:**
  - A `/terms` route with versions.
  - Clickwrap at signup and checkout: an unticked checkbox "I agree to the [Terms of Service] and have read the [Privacy Policy]", or a statement directly beside the button ("By creating an account you agree to the Terms"), with both links. The server rejects signup without the acceptance flag and sets the version itself, never trusting a version sent by the client.
  - `terms_acceptances(user_id, terms_version, accepted_at, method, context)` where `method` is `checkbox` or `button_statement` and `context` is `signup`, `checkout` or `reaccept`.
  - Material changes: notify by email and in the product ahead of the effective date (`[[LEGAL: notice period]]`), then show a re-accept step on next sign-in. Minor edits get a new version without re-acceptance.
- **Verify:** tests show signup fails without acceptance, writes a row with the current version, serves older versions, and gates the next sign-in after a material version bump.
- **Common mistakes:** a footer link as the only notice for a paid contract; a pre-ticked acceptance box; terms that remove statutory refund or warranty rights; unilateral change clauses with no notice; terms written for a different business model; terms that contradict the refund policy; no record of which version a user accepted.

## 3. Refund and cancellation policy

- **What it is:** how people cancel, when they get money back, how long it takes, who processes it, and the statutory rights that apply.
- **When it applies:** anything sold, including subscriptions, trials, digital content and in-app purchases.
  - EU: the Consumer Rights Directive (2011/83/EU) gives a 14-day right of withdrawal for most distance contracts, requires pre-contract information and a model withdrawal form, and sets a refund deadline of 14 days after withdrawal. For digital content, the right ends only once the consumer has expressly asked for immediate access, acknowledged losing the right, and received confirmation on a durable medium. If consumers are not told about the right, the withdrawal period is extended by up to 12 months. Rules adopted in 2023 (Directive (EU) 2023/2673) add an online withdrawal function for contracts made through a website or app, applying from June 2026; confirm the details with counsel.
  - UK: the Consumer Contracts Regulations 2013 are similar, and the DMCC Act 2024 adds subscription-contract rules that are being phased in.
  - US: ROSCA requires clear disclosure of material terms before billing, express informed consent and a simple way to stop recurring charges. State automatic-renewal laws, California's among the strictest, add consent, reminder and online-cancellation duties. The FTC's 2024 "click-to-cancel" amendments were set aside by a federal appeals court in 2025, but these other rules still apply. Germany requires a cancellation button for consumer subscriptions sold online.
- **Implement:**
  - A `/refunds` page. At checkout, beside the pay button: price, billing interval, next charge date, trial length and the price after it, how to cancel, and the refund window.
  - `/account/billing` with a visible "Cancel subscription" button, available online if signup was online. Allow at most one skippable retention offer, then a confirmation and an email stating the effective date. The endpoint `POST /api/billing/cancel` is idempotent and sets `cancel_at_period_end`. The UI shows *pending* until the payment provider confirms, following ProductCraft's verified-over-optimistic rule.
  - EU digital content with immediate access: an unticked box "I want access now and understand I lose my 14-day right of withdrawal". Store `withdrawal_waiver_at` and send the confirmation email.
  - The withdrawal function where required: `/account/orders/:id/withdraw` with a clearly labelled button, a confirmation step and an acknowledgement email.
  - Reminders before a trial converts or an annual plan renews where a law in scope requires them (`[[LEGAL: reminder rules for our markets]]`).
  - In-app purchases: say that refunds go through the app store, link to its refund request page and deep-link to the platform's subscription settings.
  - Data model: `subscriptions(status, current_period_end, cancel_at_period_end, canceled_at)`, `refunds(order_id, amount_minor, currency, reason, requested_at, processed_at, provider_ref)`.
- **Verify:** an end-to-end test cancels from the account page in no more steps than signup took; the cancel endpoint is idempotent; the confirmation email arrives in the local mail catcher; checkout screenshots show recurring terms above the pay button; refunds are processed inside the stated window in a sandbox.
- **Common mistakes:** "email support to cancel"; phone-only cancellation; several retention screens; a "no refunds" line that overrides statutory withdrawal; not telling EU consumers about the right; promising refunds for purchases only the app store can refund.

## 4. Cookie policy

- **What it is:** a list of every cookie, local or session storage key, pixel and SDK identifier: name, provider, first or third party, purpose, category, duration, and how to change choices. It can be its own page or a section of the privacy policy.
- **When it applies:** wherever the ePrivacy Directive (Article 5(3)) and its national laws, such as PECR in the UK, cover storing or reading information on a device, and as part of transparency under GDPR. This covers browsers and mobile apps, and technologies other than cookies.
- **Implement:** render the table from the consent registry:

  ```json
  {
    "version": "2026-10-01",
    "categories": ["necessary", "preferences", "analytics", "marketing"],
    "items": [
      {"name": "session_id", "provider": "first party", "category": "necessary", "type": "cookie",
       "purpose": "Keeps you signed in", "duration": "Session"},
      {"name": "[[LEGAL: analytics cookie name]]", "provider": "[[LEGAL: analytics provider]]",
       "category": "analytics", "type": "cookie", "purpose": "Counts visits", "duration": "[[LEGAL: duration]]"}
    ]
  }
  ```

  Add a "Cookie settings" link to the footer and app settings that reopens the preferences.
- **Verify:** compare the runtime capture after "Accept all" with the registry. Every observed item must be listed, and every listed item must still exist. A registry version bump triggers the re-consent rule in item 5.
- **Common mistakes:** a generic vendor list; missing local storage keys and SDK identifiers; wrong durations; analytics marked "necessary"; tags added through a tag manager that never reach the policy.

## 5. Cookie consent banner

- **What it is:** the interface that asks before any non-essential storage or tracking, stores the answer and lets people change it.
- **When it applies:**
  - EU and EEA: the ePrivacy Directive needs prior consent for non-essential storage and access, and consent must meet the GDPR standard (freely given, specific, informed, unambiguous, as easy to withdraw as to give). EU data protection authorities have found banners that make refusing harder than accepting to be unlawful.
  - UK: PECR and UK GDPR apply. Recent legislation added consent exemptions for some low-risk uses; check the regulator's current guidance before relying on one.
  - US: there is no general prior-consent rule, but CCPA/CPRA and other state laws give opt-out rights for sale, sharing and targeted advertising. California treats Global Privacy Control (GPC) as a valid opt-out, and several other states require honouring universal opt-out signals.
  - Strictly necessary storage is exempt: sessions, CSRF tokens, load balancing, security, the cart, and the consent choice itself.
- **Implement:**
  - Categories: `necessary` (shown as always on, not a toggle), `preferences`, `analytics`, `marketing`.
  - First layer: "Accept all" and "Reject all" with the same size, style and position weight on the same layer, plus "Choose" for per-category toggles that all start **off**. One or two plain sentences on who and why, with a link to the cookie policy. Closing the banner records no consent; it never counts as acceptance. The banner never hides the privacy and cookie pages. Ask counsel before any cookie wall or "pay or consent" design.
  - Block before consent. Non-essential scripts ship inert and are activated only for granted categories:

    ```html
    <script type="text/plain" data-consent="analytics" data-src="https://analytics.example/tag.js"></script>
    ```

    ```js
    function applyConsent(state) {
      document.querySelectorAll('script[type="text/plain"][data-consent]').forEach((el) => {
        if (!state[el.dataset.consent]) return;
        const s = document.createElement("script");
        s.src = el.dataset.src; s.async = true;
        el.replaceWith(s);
      });
    }
    ```

    Embeds (video, maps, social posts) get a click-to-load placeholder, or a privacy-enhanced embed mode where one exists. Server-side forwarding (conversion APIs, server tag containers) checks the same consent state before sending anything. Server-side tracking is not a way around consent.
  - Store the state in a first-party cookie such as `consent={"v":"2026-10-01","id":"c_8f3a","analytics":false,"marketing":false,"gpc":true}` (`Secure`, `SameSite=Lax`, lifetime per `[[LEGAL: consent lifetime]]`).
  - Record each choice with `POST /api/consent` into an append-only table: `consent_records(id, subject_key, choice, categories, registry_version, banner_text_version, gpc_signal, region, created_at)`. `subject_key` is the user id or the random consent id, never an IP address. `choice` is `accept_all`, `reject_all`, `custom`, `gpc_optout` or `withdraw`. `region` is coarse (a country) or null. Retention is `[[LEGAL: consent record retention]]`.
  - Withdrawal: the "Cookie settings" link stops non-essential scripts from the next page load, deletes the first-party cookies they set and writes a `withdraw` row. Third-party cookies cannot be deleted from your origin; say so in the cookie policy.
  - Re-ask only when the registry changes materially (a new category or vendor), not on every visit. Remember a refusal for a period counsel sets.
  - GPC: read `navigator.globalPrivacyControl === true` in the browser and the `Sec-GPC: 1` request header on the server. Treat it as an opt-out of sale, sharing and targeted advertising: marketing off, `gpc_signal=true` recorded, and the preferences show that the signal is honoured. For a signed-in user, apply it to the account where the law expects that (`[[LEGAL: confirm account-level GPC handling]]`). Publishing `/.well-known/gpc.json` is optional.
  - Where data is sold or shared under US state laws, add a footer link ("Your Privacy Choices" or "Do Not Sell or Share My Personal Information", wording per counsel) that opens the same preferences and works without an account.
  - Regional behaviour, if any, is decided on the server from a coarse country, and the stricter behaviour applies when the country is unknown. Never use precise location for this.
  - Some tag platforms offer a consent mode that still sends cookieless pings before consent. Either get counsel's view or keep those tags unloaded until consent.
  - Mobile: initialise analytics and ad SDKs only after consent, show the operating system's tracking-permission prompt where the platform requires it before cross-app tracking, and keep SDK privacy declarations and store privacy labels in line with what the app actually collects. Ad networks may require a certified consent platform for EEA and UK traffic.
- **Verify:** on staging, in a fresh profile set to an EU region, a recorded capture shows no request to a non-essential vendor and no non-essential storage before any click; after "Reject all" there are still none; after "Accept all" the tags load; after withdrawal they stop on the next page. An end-to-end test sends `Sec-GPC: 1` and sets `navigator.globalPrivacyControl` with an init script, then asserts marketing is off and a `gpc_optout` row exists. Every choice writes a row. The banner works by keyboard alone and with a screen reader, and a screenshot shows equal prominence. Review the scanner's `COOKIE_CONSENT` and `THIRD_PARTY_SCRIPTS` output.
- **Common mistakes:** tags that load and then ask; "By using this site you accept cookies"; only "Accept" and "Settings"; reject buried on a second layer; tracking toggles that start on or are labelled "legitimate interest"; the close button counted as acceptance; a banner covering the policies; no records; server-side tags ignored; GPC ignored; re-prompting after every refusal; a tag manager loaded as "necessary"; a banner that traps or skips keyboard focus.

## 6. Form consents

- **What it is:** opt-ins on forms for marketing by email, SMS, phone or push, sharing with partners, research, or processing sensitive data.
- **When it applies:**
  - Electronic marketing to individuals in the UK and EU generally needs prior consent (PECR regulation 22 and the national laws implementing ePrivacy Article 13), with a narrow "soft opt-in" for existing customers and similar products.
  - GDPR consent must be a clear affirmative act, and pre-ticked boxes are not consent (Recital 32). Special-category data needs explicit consent or another Article 9 condition.
  - In the US, most comprehensive state privacy laws require opt-in consent for sensitive data. Marketing texts and certain calls generally need prior express written consent under the TCPA. Washington's My Health My Data Act requires consent for consumer health data. CAN-SPAM is opt-out based but still needs honest identification and a working unsubscribe (item 18).
- **Implement:**

  ```html
  <label>
    <input type="checkbox" name="marketing_email" value="yes">
    Email me product news and offers from [[LEGAL: brand or legal entity]], about twice a month.
    Unsubscribe any time. <a href="/privacy#marketing">How we use your email</a>
  </label>
  ```

  - Unticked, not required to submit, and separate for each channel (email, SMS) and purpose (partner sharing). Never combined with the terms checkbox, and the service works without it.
  - A short notice at collection beside the submit button: what is collected, why, and a link to the policy.
  - The soft opt-in, where counsel confirms it applies: only for similar products, with a clear way to refuse at collection and in every message.
  - Double opt-in for email lists: a confirmation email with a signed link, and the subscription starts only after the click.
  - `marketing_consents(id, subject_id, channel, purpose, status, wording_version, source, form_url, granted_at, confirmed_at, withdrawn_at, withdrawal_source)` and `consent_wordings(version, locale, text, created_at)`. The database default for any consent column is `false`, and the server writes a grant only when the box was ticked.
  - A "Communication preferences" page to change each choice, and an import rule: no contact is imported without recorded consent evidence.
- **Verify:** a database test asserts the default is false. End-to-end tests show that submitting without ticking creates the account with no consent row, that ticking stores the current wording version, and that withdrawal writes the change and adds the address to suppression. The scanner's `PRECHECKED_CONSENT` check is clean. A screenshot shows the separate boxes.
- **Common mistakes:** pre-ticked boxes or `default: true` in the model; one box for terms and marketing together; marketing consent made a condition of signup or a discount; vague "we may send you updates"; no record of the exact wording; bought lists; SMS without written consent; asking for "consent" to processing the contract actually requires, which confuses the legal basis.
