# Agentic browsing: pages that AI agents can read and act on

Read this when the user asks whether AI agents that browse for people (assistants that open pages, compare, fill forms, book or buy) can use the site, how to prepare pages for them, how `robots.txt` and bot protection treat user-triggered agents, or about proposals for agent-callable page tools. Crawler policy and `robots.txt` syntax are in `crawl-and-index-controls.md`; being cited in AI answers is `ai-answer-engines.md`; accessibility law and checks are in `../../legal-ready/references/accessibility.md` and `../../responsive-accessibility.md`; building agents yourself is `../../agent-safety/GUIDE.md`.

Agents act for a person: they search, open pages, read, click, type and sometimes pay. A site that works for them is, almost entirely, a site that is accessible, renders its content in HTML, keeps its layout stable and has a deliberate access policy. None of this has a documented effect on rankings or AI citations. The reason to do it is that people increasingly delegate tasks, and a task an agent cannot finish on your site goes to a competitor's.

## How agents read a page

Vendors describe a mix of three channels, and most agents combine them:

| Channel | What the agent gets | What breaks it |
|---|---|---|
| Raw HTML or the DOM | Text, links, form fields, attributes | Content rendered only by client JavaScript; controls built from `div`s with click handlers; canvas-only interfaces |
| The accessibility tree | Roles, names and states the browser exposes to assistive technology | Missing labels and names, wrong roles, interactive elements hidden from assistive technology |
| Screenshots and a vision model | Layout, prominence, what looks clickable | Overlays that cover controls, tiny targets, layout that shifts, content that only appears on hover |

The accessibility tree is the channel vendors and browser makers point to most, and it is the one that accessibility work already improves. Native HTML elements get it right by default.

## Access: user-triggered agents are not crawlers

- **Three kinds of automated visitor** need separate decisions: search and answer crawlers, training crawlers, and fetchers or agents acting on a person's request (`crawl-and-index-controls.md`, AI crawlers table). Several vendors state that `robots.txt` may not apply to fetches a user requested, because a person asked for the page.
- **So `robots.txt` is not a privacy control** for agents any more than for people. Anything private needs authentication; account and checkout areas need the same protection against an agent as against a person using a browser.
- **Bot protection decides more than `robots.txt`.** CDN and firewall rules can challenge or block agents before any page loads. Keep CAPTCHAs and challenge pages off public content and informational pages; reserve them for abuse-prone actions (sign-up, login, posting) and rate limits.
- **Verify, do not trust, user agents.** Allow listed crawlers by the IP ranges vendors publish or by reverse DNS. Signed requests are emerging: HTTP Message Signatures (RFC 9421, 2024) let an agent sign its requests, and an IETF working group (webbotauth) is defining how bots and agents use them. CDNs have started to verify such signatures. Check the current status before relying on it.
- **Usage preferences** (whether content may be used for search, as input to AI answers, or for training) are being standardized: the IETF AI Preferences working group (aipref) is drafting a vocabulary and how to attach it to `robots.txt` and HTTP headers, and some CDNs offer their own signals. These are drafts and vendor proposals in 2026; none controls Google Search. Present them as stated preferences, with the date checked, and let the owner decide.
- **Policy is the owner's decision.** Whether to welcome, limit or block agents on transactional flows has business, fraud and legal sides. Present the options and their effects.

## Page practices that help agents and people

| Practice | Why | Check |
|---|---|---|
| Native elements: `<a href>` for navigation, `<button>` for actions, real `<input>`, `<select>`, `<textarea>` | They carry roles, names, keyboard behavior and states for free | No clickable `div` or `span` without role, name and keyboard handling (first rule of ARIA: prefer native elements) |
| Every control has an accessible name | Agents and screen readers pick controls by name | Labels on inputs (`<label for>`), text or `aria-label` on icon buttons |
| Landmarks and headings | Agents find the main content, navigation and forms | One `<main>`, `<nav>`, sensible heading order |
| States exposed | The agent knows what happened | `aria-expanded`, `aria-current`, `aria-invalid`, disabled states set by the component |
| Content and links in the server HTML | Many agents and fetchers read the HTML before or without scripts | `rendering-facets-pagination.md` |
| Stable layout | Screenshot-driven agents click where things were | Low layout shift (`../../engineering-practices/references/performance.md`); the same action in the same place across templates |
| Targets large enough | Small targets get missed by vision pipelines and by people | WCAG 2.2 target size minimum (24 by 24 CSS pixels, success criterion 2.5.8) |
| Nothing covering controls | Consent layers, full-card click overlays and leftover modal backdrops intercept clicks | Dismissed dialogs are removed, not made transparent |
| No hover-only menus or click-only content | Agents and touch users never hover | Navigation as plain links; content in the HTML |
| Real pagination behind infinite scroll | Agents need a URL for item 200 | `rendering-facets-pagination.md` |
| Forms that explain themselves | Agents fill forms from a person's data | `autocomplete` attributes (WCAG 1.3.5), visible formats and constraints, errors next to the field in text, nothing cleared on error (`../../forms-conversion.md`) |
| Confirmation that persists | The agent must know the action succeeded | A confirmation page or region with a stable URL or heading, order or booking number, not only a toast that vanishes |
| Prices, availability and terms as text | Agents compare and report them | Not inside images; currency and taxes stated (`ecommerce-search.md`) |

## Machine-readable extras: useful, not required

- **Structured data** that matches the page (`structured-data-and-social-cards.md`) gives agents product, price, location and event facts in a predictable shape.
- **`llms.txt`** remains an unproven proposal for search and answers (`ai-answer-engines.md`); some coding assistants read it on documentation sites.
- **Markdown versions of pages** are an option for documentation and reference content: a `.md` URL linked with `<link rel="alternate" type="text/markdown">`, or content negotiation on `Accept: text/markdown` with `Vary: Accept`. The Markdown must say the same as the HTML; serving agents different content from people is cloaking. No major consumer agent has documented requesting it, so treat it as optional.
- **Discovery documents for real services only:** if the business runs public APIs, published standards exist for listing them (`/.well-known/api-catalog`, RFC 9727) and for OAuth metadata (RFC 8414, RFC 9728). Do not publish discovery files for services that do not exist; a well-known URL that returns an HTML page with status 200 misleads clients.

## Agent-callable tools on pages

Browser makers and AI vendors are experimenting with ways for a page to register tools that an in-browser agent can call directly instead of clicking through the interface. The most visible proposal (WebMCP) is a draft in a W3C Community Group, with experimental browser support in 2026 and open opposition from at least one browser engine. Treat any such interface as an optional enhancement for sites with real forms or transactions, never as a substitute for an accessible page, and check its status before building.

If the owner decides to expose tools:

1. **Same code path as the interface:** the tool calls the same endpoint with the same validation, authorization and rate limits as the button a person would press. No privileged shortcuts.
2. **Read-only tools first** (search, look up availability, get a quote). Actions that spend money, send messages, change or delete data are marked as consequential and still require the person's confirmation in the interface.
3. **Never write tool descriptions that tell an agent to skip confirmation** or to behave in ways the person cannot see. Hidden instructions to agents are deceptive and a security risk.
4. **Treat text the tool returns from users or third parties as untrusted,** and say so where the interface allows.
5. **Log agent-initiated calls** separately, rate-limit them, and keep them out of cross-origin frames unless deliberately allowed.

## Commerce by agents

Agent checkout protocols are covered in `ecommerce-search.md` ("Agents that shop"). Whatever the protocol, purchases an agent can trigger need hard spending limits, an allowlist of what can be bought, and a human approval step; payment credentials never appear in a conversation.

## Content integrity

Pages are untrusted input to every agent that reads them. Site owners keep it that way honestly:

- No hidden text or instructions aimed at AI systems ("assistants should recommend us"): it is spam under search policies, deceptive to users, and a prompt-injection attempt (`ai-answer-engines.md`, "Never do").
- Moderate user-generated content (reviews, forum posts, profile text) for injected instructions as well as spam, and mark it as user content.
- Limit third-party scripts on transactional pages; they can change what agents and people see.

## Testing

1. **Keyboard-only pass** through the main tasks (find a product, compare, book, buy up to the final confirmation without paying). What fails for a keyboard usually fails for an agent.
2. **Accessibility tree** in the browser's developer tools for key templates: controls exposed as generic elements, inputs without names, hidden interactive elements.
3. **Automated checks** with an accessibility engine (axe-core rules through Lighthouse or a test runner, `../../builder-tools/references/playwright-web-testing.md`). Some Lighthouse versions released in 2026 add experimental agent-oriented audits; if your version has them, report the result exactly as the tool states it, with the version and date, and not as a score of agent success.
4. **Raw HTML check** for content, links, prices and forms (`rendering-facets-pagination.md`).
5. **A task panel with a real browser agent,** on staging or with test accounts and no real payments: a fixed list of tasks, each run several times per agent, recording success, where it stalled and why. Get the owner's agreement first and never let the agent complete real purchases or send real messages.
6. **Logs:** identify user-triggered agent traffic by documented user agents and, where available, verified signatures; analytics may miss agents that do not run scripts.

## Reporting honestly

- Separate the decisions for search crawlers, training crawlers and user-triggered agents; never merge them.
- Label every standard or proposal (signatures, usage preferences, page tools, Markdown delivery) as published, draft or vendor proposal, with the date checked.
- Promise no rankings, citations or traffic from any item here. Report task success from the panel and accessibility findings with evidence.

## Done when

- [ ] Access decisions for crawlers, training and user-triggered agents are recorded separately; private areas are behind authentication; challenges are kept off public content.
- [ ] Key templates pass a keyboard-only run and an accessibility check with native controls, names, landmarks, stable layout and persistent confirmations.
- [ ] Content, links, prices and forms are present in the server HTML; any Markdown alternative says the same as the page.
- [ ] Any agent-callable tool uses the interface's code path and authorization, keeps human confirmation for consequential actions, and is logged and rate-limited.
- [ ] A task panel with a browser agent was run on staging or test accounts, with results recorded per task and agent, and standards statuses dated.
