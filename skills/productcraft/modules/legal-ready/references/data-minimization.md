# Data minimization (items 7-8)

General guidance, not legal advice; have a qualified lawyer review. Security controls for the data you keep (encryption, access control, response trimming, logging hygiene) belong to [LaunchGuard](../../launchguard/GUIDE.md) Gate 2 and baseline controls 5, 7 and 17. This file is about collecting and sharing less in the first place.

## 7. Collect only necessary data

- **What it is:** each piece of personal data has a stated purpose, is needed for that purpose, is kept only as long as the purpose requires, and is not quietly reused for something else.
- **When it applies:** always. It is a core GDPR and UK GDPR principle (data minimisation, purpose limitation and storage limitation in Article 5). US state privacy laws increasingly require collection to be "reasonably necessary and proportionate" to the disclosed purposes, COPPA limits collection from children to what an activity needs, and Washington's My Health My Data Act restricts consumer health data. Less data also means less to secure, disclose, export and delete.
- **Implement:**
  - **Data inventory in the repository**, reviewed in pull requests, for example `docs/legal/data-inventory.yaml`:

    ```yaml
    - field: users.phone
      purpose: Two-step sign-in codes
      basis: "[[LEGAL: legal basis]]"
      required: false
      retention: Until removed by the user or account deletion
      recipients: [sms-processor]
      not_used_for: [marketing]
    ```

    Every column, form field, event property and SDK payload that holds personal data has a row. A field with no row is either documented or removed.
  - **Forms:** remove fields with no purpose (`FRM-04`); mark optional ones the same way everywhere (`FRM-12`); ask for the least precise version that works (year of birth or "Are you 18 or over?" instead of a full date of birth when only an age check is needed, a country instead of an address, approximate instead of precise location).
  - **Mobile permissions:** request camera, contacts, location, microphone or photos at the moment of use, with a purpose string that states the real reason. The feature degrades gracefully when the user says no.
  - **Retention jobs:** a scheduled task deletes or anonymises records past their retention (`retention_until` column or a per-table policy), with a test. Logs and analytics have their own retention settings, configured and recorded.
  - **Telemetry hygiene:** events carry pseudonymous ids, not emails or names; request and response bodies are not logged; IP addresses are truncated or dropped where they are not needed; session-replay tools mask all inputs and text by default; prompts and files sent to AI providers are limited to what the feature needs.
  - **Purpose limits in code:** marketing jobs query only users with a marketing consent row (item 6), and data collected for security, such as a phone number for sign-in codes, is not selected by marketing queries.
  - **No production data in development:** use synthetic or properly anonymised fixtures.
- **Verify:** compare the schema, form fields and analytics event definitions against the inventory (a small test can fail when a new column is not in the inventory). Run the retention job against fixtures with expired rows and assert that they are gone. Inspect a captured analytics payload and a log line for personal data. On mobile, check that permission prompts appear only when the feature is used.
- **Common mistakes:** "we might need it later"; a required date of birth or gender with no purpose; a phone number collected "for security" and then used for marketing; keeping everything forever; logging full request bodies; sending the whole user object to analytics, support chat or an AI provider; copying production data to staging; free-text fields that invite sensitive data the product never needed.

## 8. Audit third-party SDKs, pixels and scripts

- **What it is:** a complete, current list of every third party that receives data from the product (scripts, pixels, SDKs, embeds, fonts, captchas, chat widgets, server-side integrations), what each receives, why, under what contract, and whether it waits for consent.
- **When it applies:** whenever third-party code runs in the product or the server forwards data to a vendor. Under GDPR, processors need a contract (Article 28) and transfers outside the EEA or UK need a mechanism. Under CPRA, ad pixels used for cross-context behavioural advertising usually count as "sharing", which triggers opt-out rights. The ePrivacy rules decide whether the code may store or read anything on the device before consent. Pixels on pages about health, finances or children have led to regulatory action in several countries, so treat those pages as high risk.
- **Implement:**
  - **Inventory file** (for example `docs/legal/third-parties.md`, or a machine-readable list that also feeds the consent registry from item 4):

    | Vendor | Where it runs | Purpose | Data sent | Storage set | Category | Consent gate | Contract and transfer | Owner | Keep? |
    |---|---|---|---|---|---|---|---|---|---|
    | `[[LEGAL: vendor]]` | all pages | analytics | page URL, pseudonymous id, device info | 2 cookies | analytics | waits for `analytics` | `[[LEGAL: DPA signed? transfer mechanism]]` | growth | yes |

  - **Sources for the inventory:** dependency manifests, script tags and embeds, the scanner's `THIRD_PARTY_SCRIPTS` output, the tag manager container's tag list, server code that calls vendor APIs, mobile SDK lists and their privacy declarations, and the runtime capture from GUIDE step 0. The runtime capture usually finds vendors the code does not show.
  - **Gate:** non-essential vendors load only through the consent loader from item 5. The tag manager itself is gated if it can fire non-essential tags. New tags in the tag manager need the same review as code changes.
  - **Minimise:** turn off automatic collection features that send form contents, emails or hashed identifiers unless that specific use is consented to and documented. Mask inputs in session replay. Keep pixels off sensitive pages entirely. Self-host fonts and other static assets where possible, because loading them from a third-party CDN sends every visitor's IP address to that provider (a German court treated this as a GDPR breach).
  - **Remove** vendors nobody owns or uses. Each removal is a change to the inventory, the registry and the policy.
  - **Mobile:** check each SDK's own privacy declaration, set its data-collection options explicitly at initialisation, and keep the store privacy labels and data-safety answers in line with the inventory.
- **Verify:** in a fresh profile (GUIDE step 0), every domain contacted after "Accept all" maps to an inventory row, and no non-essential domain is contacted before consent or after "Reject all". The mobile proxy capture of a test session shows the same. Every inventory row has a contract status. The scanner's third-party list holds nothing that is missing from the inventory.
- **Common mistakes:** building the inventory from the package manifest only; assuming "anonymous analytics" needs no consent or contract; forgetting server-side forwarding, embeds, fonts and captchas; chat widgets loading on every page before consent; automatic matching features sending hashed emails; store privacy labels that say "no data collected" while SDKs collect it; an inventory written once and never updated.
