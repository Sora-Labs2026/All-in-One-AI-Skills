# Business details, children, email, assets and data rights (items 16-20)

General guidance, not legal advice; have a qualified lawyer review. Endpoint security for the routes below (authentication, record ownership, rate limits) belongs to [LaunchGuard](../../launchguard/GUIDE.md); run its scoped controls on every endpoint you add.

## 16. Business and contact details

- **What it is:** showing who is behind the product: legal name, trading name, geographic address, a contact email (and phone, if offered), company register and number, VAT number, and any regulator or professional body where the activity is regulated.
- **When it applies:**
  - EU: the E-Commerce Directive (2000/31/EC, Article 5) requires these details to be easily, directly and permanently accessible. Germany and Austria enforce this strictly as an imprint ("Impressum"). The Consumer Rights Directive requires trader identity before a contract. The Digital Services Act adds contact points and, for marketplaces, trader traceability.
  - UK: the Electronic Commerce (EC Directive) Regulations 2002 and the company trading-disclosure rules made under the Companies Act 2006 require the registered name, number and office on the website.
  - Email: marketing email must identify the sender with a valid postal address (CAN-SPAM, PECR).
  - Privacy: the privacy notice must name the controller (GDPR).
  - Apps: the major app stores ask developers to declare trader status and show trader contact details to EU users.
- **Implement:**
  - One source of truth that every surface renders from, for example `config/legal-entity.json`:

    ```json
    {
      "legal_name": "[[LEGAL: registered legal name]]",
      "trading_name": "[[LEGAL: brand, if different]]",
      "address": "[[LEGAL: registered or geographic address]]",
      "email": "[[LEGAL: contact email]]",
      "phone": null,
      "register": "[[LEGAL: company register and number]]",
      "vat_id": "[[LEGAL: VAT number, if registered]]",
      "regulator": null,
      "privacy_contact": "[[LEGAL: privacy email]]",
      "eu_representative": null,
      "uk_representative": null
    }
    ```

  - Render it in the footer of every page (legal name plus links to `/contact` and `/imprint` or `/legal`), on `/contact` (an email address, not only a form, plus the address), at checkout and in order confirmations, on invoices, in every marketing email footer (item 18), in the app's "About and legal" screen, and in the controller section of the privacy policy.
  - Sole traders worried about publishing a home address should ask counsel which alternatives are permitted in their markets.
- **Verify:** the scanner's `BUSINESS_DETAILS` and `UNRESOLVED_PLACEHOLDERS` checks; an end-to-end test that the footer links resolve on every template; a search showing no hard-coded copy of the entity details outside the config; the store trader details match the config.
- **Common mistakes:** an invented company name or number; the brand name with no legal entity; a contact form as the only channel; a post-office box where a geographic address is required; details on one buried page; an old address after a move; different entity names across the policy, invoices and store listing.

## 17. Parental consent for children's data

- **What it is:** finding out, without leading the answer, whether a user is a child, and not collecting a child's personal data until a parent has given verifiable consent where the law requires it.
- **When it applies:**
  - US: COPPA covers services directed to children under 13, and general-audience services with actual knowledge that a user is under 13. It requires a notice to parents, verifiable parental consent before collection (with narrow exceptions, such as collecting a parent's contact to ask for consent), parental rights to review and delete, limited retention and reasonable security. Whether a service is "directed to children" depends on its subject matter, visuals, characters, music, advertising and actual audience. The FTC amended the COPPA Rule in 2025, for example requiring separate consent before disclosing children's data to third parties such as for targeted advertising, and a written data retention policy. Check the current text.
  - EU: GDPR Article 8 requires parental consent where an online service relies on consent from a child below 16; member states may lower this to no less than 13.
  - UK: the age is 13. The Age Appropriate Design Code applies to services likely to be used by under-18s in the UK and expects high-privacy defaults, location off by default and no nudging.
  - Other: several US states have newer children's privacy, design-code or social-media laws; ask counsel which apply. App store kids' categories restrict third-party analytics and advertising.
- **Implement:**
  - Agree the audience with the owner (`[[LEGAL: audience classification]]`). **Not for children:** an age screen at signup keeps children out. **Mixed audience:** an age screen routes children to a child-safe mode with parental consent. **Child-directed:** treat every user as a child.
  - **Neutral age screen:** empty date-of-birth fields (or month and year), no default adult year, no hint of the cut-off age, never an "I am over 13" checkbox. Store only the outcome (`age_band` or `is_child`, plus `age_checked_at`), not the full date unless it is needed. Set a session and device flag so a child cannot immediately retry with a different date.
  - Collect nothing before the gate: no analytics beyond strictly necessary storage on that screen.
  - **Parental flow:** collect only the parent's email, send a notice of what will be collected and why with the policy link, obtain consent through a method the regulator accepts, record it, then activate the account. Examples the FTC has accepted include a signed form returned by post or scan, a payment-card transaction with notice to the cardholder, a call or video call with trained staff, and checking government ID against records and then deleting it. The lighter "email plus" method is limited to data used only internally. Delete the parent's contact if consent does not arrive within `[[LEGAL: period]]`.
  - `parental_consents(child_user_id, parent_contact, method, scope, notice_version, verified_at, revoked_at)` where `scope` separates `internal_use` from `third_party_disclosure`.
  - **Child accounts:** non-essential SDKs are never initialised; no behavioural ads; profiles private by default; location off; chat restricted. A parent area (`/parent`) to review, delete and revoke.
- **Verify:** tests with dates of birth on both sides of every threshold for each market; the retry flag blocks a second attempt; network captures of the gate screen and of a child session show no non-essential vendors; the server refuses to store child data without a consent record; parental deletion works end to end.
- **Common mistakes:** an "I am 13 or older" checkbox; a birth year pre-filled with 1990; asking for email or photos before the gate; retry through the back button; terms saying "not for children" while the content is clearly aimed at them; ad SDKs in a kids' app; storing the full date of birth; using child data for targeted ads.

## 18. Unsubscribe link and one-click headers in marketing email

- **What it is:** an easy, immediate way to stop marketing email: a visible link in every message, plus the headers that let mail clients show their own one-click "Unsubscribe" button.
- **When it applies:**
  - US: CAN-SPAM covers commercial email. Header information must be accurate and subject lines not deceptive. The message must identify itself as an advertisement unless the recipient opted in, and must include the sender's valid physical postal address and a clear opt-out. Opt-outs must be honoured within 10 business days, and the mechanism must keep working for at least 30 days after sending. Opting out cannot require a fee or more than an email address and a preference choice, and opted-out addresses cannot be sold or transferred. The duties remain when another company sends on your behalf.
  - UK and EU: PECR and the national ePrivacy laws require sender identity and a simple opt-out in every marketing message. GDPR gives an absolute right to object to direct marketing (Article 21).
  - Deliverability: large mailbox providers require bulk senders to support one-click unsubscribe as defined in RFC 8058 (built on the `List-Unsubscribe` header of RFC 2369), to process unsubscribes within about two days, and to authenticate mail with SPF, DKIM and DMARC.
- **Implement:**
  - Headers on every marketing or bulk message, with the DKIM signature covering both (RFC 8058 requires this):

    ```text
    List-Unsubscribe: <https://example.com/email/unsubscribe/one-click?t=TOKEN>, <mailto:unsubscribe@example.com?subject=unsubscribe-TOKEN>
    List-Unsubscribe-Post: List-Unsubscribe=One-Click
    ```

  - `TOKEN` is opaque and signed (for example an HMAC over subscriber id, list and issue date), never the plain email address, and stays valid for well over 30 days.
  - `POST /email/unsubscribe/one-click` accepts the body `List-Unsubscribe=One-Click`, needs no cookie or login, does not redirect, unsubscribes at once and returns `200`.
  - `GET /email/unsubscribe?t=TOKEN` (the footer link) shows a page with one "Unsubscribe" button and optional preferences, with no login. It does not unsubscribe on the GET alone, because security scanners open links in mail.
  - Footer in the HTML and plain-text parts: why the person receives this, "Unsubscribe" and "Email preferences" links in readable size and contrast, and the legal name and postal address from item 16.
  - Data: `email_subscriptions(subscriber_id, list_key, status, consent_id, subscribed_at, unsubscribed_at, unsubscribe_source)` where `unsubscribe_source` is `one_click`, `link`, `mailto`, `reply`, `complaint`, `support` or `settings`. `suppressions(email_hash, scope, reason, created_at)` where `scope` is all marketing or one list. Keep the suppression entry even after account deletion, because it is what keeps the opt-out working.
  - The send path checks suppression at send time, not only when the list is built. Run transactional and marketing mail as separate streams (separate sender subdomains), and never put promotions into receipts or password resets. Feed mailto unsubscribes and spam complaints into suppression.
- **Verify:** in the local mail catcher, the raw message has both headers and a staging DKIM check shows them in the signed header list. `curl -X POST -d 'List-Unsubscribe=One-Click' 'https://staging.example.com/email/unsubscribe/one-click?t=TOKEN'` returns 200 without cookies and changes the status. A test shows the next send to that address is skipped. Opening the GET link alone changes nothing. A token for another subscriber is rejected. The scanner's `EMAIL_UNSUBSCRIBE_LINK` and `EMAIL_ONE_CLICK_HEADERS` checks pass, or the provider's headers are confirmed on a received message.
- **Common mistakes:** unsubscribe behind a login; links that expire after a week; no "unsubscribe from all" option; re-importing unsubscribed contacts from a CRM; deleting the suppression list with the account; promotions in transactional mail; a one-click endpoint that redirects or needs a cookie; DKIM not covering the headers; an image-only or tiny grey footer.

## 19. Licences for fonts, images, icons, music and other assets

- **What it is:** proof of the right to use every font, image, icon, illustration, video, music track, sound, 3D model, dataset and generated asset that the product or its marketing ships, used within the licence's scope.
- **When it applies:** always. Copyright and trademark law apply everywhere, and each licence sets its own scope: for example the SIL Open Font License 1.1, Creative Commons licences such as CC BY 4.0 and CC0, permissive code licences such as MIT and Apache-2.0, and commercial stock and font licences priced by pageviews, installs, seats or media. Open-source notices for code dependencies are a related duty: show them in an app's "Open source licences" screen.
- **Implement:**
  - An inventory, for example `docs/legal/asset-licenses.md` (the scanner recognises `ASSET-LICENSES`, `CREDITS`, `THIRD_PARTY_NOTICES` and similar names):

    | Path or glob | Type | Source | Owner | Licence (SPDX id if any) | Permitted use | Restrictions | Attribution and where shown | Proof | Acquired |
    |---|---|---|---|---|---|---|---|---|---|
    | `public/fonts/inter/*` | font | `[[LEGAL: source]]` | `[[LEGAL: owner]]` | OFL-1.1 | web and app embedding | keep licence with files | none | `OFL.txt` beside the files | 2026-09 |

  - **Fonts:** a web licence, an app-embedding licence and a desktop licence are different things. Ship the licence file beside open-licensed fonts wherever the font files are redistributed (apps, downloads). Commercial fonts need the tier that matches the domain, app and traffic.
  - **Images and video:** keep model and property releases for identifiable people and places. Do not use editorial-only stock in ads. "Royalty-free" does not mean free. Music in video needs synchronisation rights, and a platform's audio library is licensed for that platform only.
  - **Logos and trademarks:** written permission for customer logos (item 11); care with competitors' marks in comparisons.
  - **Generated assets:** check that the generator's terms allow commercial use (`[[LEGAL: confirm]]`), avoid outputs that imitate trademarks or real people, and note that purely machine-generated material may not get copyright protection in some countries.
  - Show the required attributions on a `/credits` page or the app's "About" screen.
  - Add a small CI check that lists files under `public/`, `assets/`, `static/` and `fonts/` not covered by an inventory glob, and fails when the list is not empty.
- **Verify:** the scanner's `ASSET_LICENSES` check is clean for fonts; the coverage check reports nothing uncovered; every paid licence has proof stored privately; required attributions are visible; the app bundle contains the font licence texts.
- **Common mistakes:** "found it online"; images from a search engine; a desktop font licence used on the web or in an app; editorial stock in ads; missing releases; streaming-service music in a promo video; watermarked trial assets left in; required attribution missing; competitors' screenshots used without care.

## 20. Data deletion, access and export

- **What it is:** working ways for people to get a copy of their data, take it elsewhere, correct it and delete it, with identity checks and tracked deadlines.
- **When it applies:**
  - EU and UK: GDPR and UK GDPR (Articles 12 and 15 to 22) require a response without undue delay and within one month. The deadline can be extended by two further months for complex or numerous requests, if the person is told within the first month. Requests are usually free. Extra identity checks are allowed only where there is reasonable doubt. Portability (Article 20) covers data the person provided, in a structured, commonly used, machine-readable format.
  - US: CCPA/CPRA gives rights to know, delete, correct, opt out of sale or sharing, and limit use of sensitive data. Responses are due within 45 days, extendable once by 45 more with notice, and the current regulations expect receipt to be confirmed within 10 business days. Identity checks must be proportionate to the data, and authorised agents must be supported. Other state laws give similar rights, mostly with 45-day deadlines, and many require an appeal process.
  - COPPA gives parents review and deletion rights (item 17).
  - Apps: the major app stores require apps that offer account creation to let people start account deletion inside the app, and one also requires a web link for deletion requests.
- **Implement:**
  - In the product, `/account/privacy` with "Download my data" and "Delete my account". For people without an account (newsletter subscribers, visitors), a form at `/privacy/requests` asking for request type, email, region (to set the deadline) and details.
  - Endpoints, all acting only on the authenticated subject, with re-authentication for export and deletion:
    - `POST /api/me/export` starts a job and emails a link when it is ready. `GET /api/me/exports/:id` returns a short-lived signed URL to a ZIP of JSON and CSV covering profile, content, activity, consents and orders. Include the person's own contributions to shared spaces, and ask counsel about other people's data inside them.
    - `POST /api/me/delete` follows a confirmation step, then an optional grace period that is stated and cancellable, then the deletion job.
    - `POST /api/privacy-requests` for the form: confirm control of the email address with a signed link, and add checks proportionate to the risk. Do not ask for identity documents by default.
  - The deletion job covers every store in the data map: the primary database (hard delete, or irreversible anonymisation of rows that must stay), uploaded files, search indexes, caches and queues, analytics and session replay (through the vendors' deletion interfaces), the CRM and email provider (delete the profile but keep the hashed suppression entry from item 18), support tools, and the payment provider's customer record (keep invoices for the tax retention period, `[[LEGAL: retention period]]`). Backups expire on their documented rotation, and a tombstone list of deleted ids is re-applied after any restore. Tell processors to delete, and record what was kept and why.
  - `privacy_requests(id, type, subject_ref, channel, jurisdiction, received_at, acknowledged_at, verified_at, verification_method, due_at, extended_until, extension_reason, status, completed_at, response_ref, handled_by, appeal_of)` where `type` is `access`, `export`, `delete`, `correct`, `opt_out`, `limit_sensitive`, `object` or `restrict`. Compute `due_at` from a jurisdiction table (one month for GDPR and UK GDPR; 45 days for California and most other US states; `[[LEGAL: deadlines for our markets]]`). Alert before due dates and keep an audit log.
  - Correction: profile fields are editable, and other corrections go through the form.
  - Apply LaunchGuard controls 6 and 7 (server-side authorization and record ownership) and add cross-user tests.
- **Verify:** an integration test seeds a fixture user with data in every store (local services or provider sandboxes), runs deletion, and asserts the data is gone or anonymised everywhere while the suppression entry remains. The export test checks every data category is present and no other user's private data appears. Tests show re-authentication is required and that user B cannot export or delete user A. Due-date tests cover each jurisdiction. Deletion is reachable from the app's settings, and the web deletion link exists for store listings. The scanner's `DATA_DELETION` check finds the routes.
- **Common mistakes:** a soft-delete flag only; forgetting analytics, the email provider, support tools, search indexes or backups; deleting the suppression list and then emailing someone who opted out; "email us to delete" as the only route; exports sent as unencrypted attachments or links that never expire; demanding passport scans by default; no tracking, so deadlines are missed; deletion without re-authentication; deleting records the law requires you to keep without documenting why.
