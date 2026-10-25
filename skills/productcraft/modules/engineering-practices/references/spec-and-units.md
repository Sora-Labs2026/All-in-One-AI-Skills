# Specification compliance and units of measure

Read this when code must do what a document says (an RFC or other standard, an API contract, a whitepaper, a client's requirements, a design document, a regulation's technical rules, the guarantees a README promises), or when code does arithmetic on quantities that carry units or scale factors: money, time, sizes, rates, percentages, prices, token amounts, coordinates. Both are ways of checking a claim the code cannot check by compiling.

## Part 1: checking code against a specification

The goal is a verdict per requirement backed by evidence, plus an inventory of undocumented behavior. Every gap is either a code defect or a documentation defect; deciding which belongs to the owner.

### 1. Collect and rank the sources

- List every document that states intended behavior, with its version or date. Rank by authority: a standard or contract the project is bound to, then published documentation, then internal design notes, then the README, then code comments.
- When two sources disagree, record the disagreement as a finding before checking any code.
- Read only the parts in scope. For a large standard, agree with the user which sections or conformance levels apply.

### 2. Turn prose into numbered requirements

- One checkable statement per requirement, numbered (`R-01`, `R-02`), with the original sentence quoted exactly and its location (`SPEC.md section 3.2`, `RFC 6749 section 4.1.2`). Paraphrase only in a separate "means" line, never instead of the quote.
- Split compound sentences: "Tokens expire after 10 minutes and are single-use" is two requirements.
- Note the strength: in documents that use RFC 2119 and RFC 8174 keywords, MUST and MUST NOT are mandatory, SHOULD allows documented exceptions, MAY is optional. Elsewhere, judge from context and say so.
- Write what an implementation must make true, concretely enough to search for: the inputs, the condition, the effect, and which values are involved and their sources.
- Vague wording ("handles errors gracefully", "fast") that no implementation could be checked against is reported as a defect of the document: nobody can show it holds.

### 3. Find where each requirement is enforced

- Search by concept, not only by name: the field or quantity involved, the error code it implies, the constant (`600` for ten minutes), the configuration key.
- Read the enforcing code and walk **every path** that can reach the effect: other entry points (API, admin tools, batch jobs, message consumers, migrations, imports), retries and error branches, alternative modes and roles, configuration defaults and feature flags.
- Keep a search log: each pattern and what it returned, empty results and matches that only occur in test files included. A "not found" verdict is worth exactly as much as this log.
- A function name is not evidence. `validate_limit()` that never compares against the limit enforces nothing; read the body.
- For a long specification, check requirements in batches. With helpers available, give each batch to a fresh helper with the quoted requirements, the verdict table below and the search-log rule (`../../engineering-workflow/references/parallel-work.md`), then read every record yourself before accepting it.

### 4. Give each requirement a verdict

| Verdict | Meaning |
|---|---|
| `MET` | Enforced on every path that reaches the effect; cite the lines |
| `PARTLY MET` | Enforced on some paths and missing on at least one reachable path; often the most serious finding, because ordinary testing passes |
| `VIOLATED` | The code does something the requirement rules out |
| `NOT FOUND` | No enforcement found; attach the search log |
| `EXCEEDS` | The code is stricter than required; harmless today, but nothing records that other code may depend on it |
| `UNCLEAR` | The requirement cannot be checked as written, or sources conflict |

For each verdict give the evidence (`file:line`, the paths walked, the searches run) and, where it applies, a test. Name tests after the requirement so the link survives: `test_r07_reset_token_single_use`. A compliance table of requirement, verdict, evidence and test is the traceability record.

### 5. Check the other direction

Inventory undocumented behavior: endpoints, flags, limits, defaults, error codes, retention periods, background jobs. Undocumented behavior is either missing documentation or code nobody asked for; report it either way.

### 6. Rate and report

- Rate by consequence and reach, not by how emphatic the wording is: who can trigger the gap (anyone, an authenticated user, an admin only), on which path, how often, and what they gain or what breaks. Spell out the scenario when you can; when you cannot, name the conditions under which the gap would cause harm. Never invent figures or attack steps.
- A gap where the code is right and the document is wrong is still a finding, filed against the document.
- Before reporting a `PARTLY MET`, `VIOLATED` or `NOT FOUND`, try to refute it: look for enforcement in a caller, base class, middleware, database constraint or configuration. On important audits, have a fresh reviewer try to refute each divergence independently.
- List requirements not checked and why. Security-relevant gaps go into the vocabulary of `../../code-security-review/GUIDE.md`; legal and regulatory interpretation stays with qualified people (`../../legal-ready/GUIDE.md`).

## Part 2: units of measure and dimensional checks

Most languages let you add seconds to milliseconds, cents to dollars, or a 6-decimal amount to an 18-decimal one without complaint. Tests often miss these bugs because test values are round numbers, all values use the same unit, or the expected value was computed with the same mistake.

### Bug classes to look for

| Class | Example |
|---|---|
| Time units | `setTimeout(fn, 30)` meant 30 seconds; `Date.now()` (ms) compared with a Unix timestamp in seconds; Go `time.Sleep(5)` sleeps 5 nanoseconds |
| Percent, fraction, basis points | `price * discount` where `discount` is `15` (percent) rather than `0.15`; 1 basis point is 0.01% |
| Money units and currencies | Major and minor units mixed (`19.99` vs `1999`); amounts in different currencies added; minor-unit exponents differ (JPY has 0 decimals, KWD has 3) |
| Scale factors | Fixed-point values with different decimals combined (a 6-decimal token amount with an 18-decimal one; a price feed with 8 decimals); a scale applied twice or not at all; dividing where you should multiply |
| Inverted ratios | A rate in USD per EUR used as EUR per USD; tokens per share used as shares per token |
| Rates and periods | An annual rate applied per day without conversion; a per-second rate multiplied by milliseconds |
| Sizes | Bits and bytes; KB (1000) and KiB (1024); characters, UTF-16 code units and bytes in a length check |
| Angles and coordinates | Degrees passed to a function that expects radians; latitude and longitude swapped; screen pixels vs device pixels |
| Time zones | A local wall-clock time stored as if it were UTC; dates compared across zones |
| Rounding order | Integer division before multiplication (`a / b * c` loses precision that `a * c / b` keeps, if it cannot overflow); rounding per line vs once per invoice not matching the documented rule |

### Make units explicit in code

- **Prefer types over comments.** Python: `decimal.Decimal` for money, `typing.NewType("Cents", int)` for static distinction, the `pint` library when values need real unit arithmetic, `datetime.timedelta` for durations. TypeScript: branded types (`type Cents = number & { readonly brand: 'Cents' }`) with constructor functions, a money library for currency arithmetic. Rust: newtypes (`struct Cents(i64)`), `std::time::Duration`, the `uom` crate. Go: named types (`type Cents int64`) and `time.Duration` with explicit constants (`5 * time.Second`). C++: `std::chrono` durations. Java: `java.time.Duration`, the Money API (JSR 354) or `javax.measure` (JSR 385). F# has units of measure built in.
- **Where types are not practical, put the unit in the name:** `timeout_ms`, `amount_cents`, `size_bytes`, `fee_basis_points`, `price_usd_per_eur`. Avoid abbreviations that mean two things (`bps` is both basis points and bits per second).
- **Convert once at the boundary.** Parse external values into the internal representation where they enter (API payloads, configuration, database columns, provider responses) and convert back only on output. Configuration should carry its unit (`timeout: 30s`) and be parsed with a duration parser.
- **Read the unit from the other side's documentation** for every external value: provider APIs often take amounts in the smallest currency unit, JavaScript timestamps are milliseconds, Unix timestamps are seconds, Python's `time.time()` returns seconds as a float.
- **Document what types cannot hold:** the scale of a fixed-point field, the rounding rule, the currency's exponent, whether a rate is per period or annualized. A short comment where the value is declared is enough: `# unit=USDC, scale=1e6 (smallest unit)`.

### Walk the formulas

For code where these bugs would cost money or correctness (billing, payouts, pricing, interest, fees, exchange rates, quotas, scheduling, dosing, physical calculations):

1. List the base units in the domain (currency units, token units, shares, seconds, bytes) and the scale each stored value uses.
2. Annotate each input, field and intermediate value with its unit and scale, as a type or a comment.
3. For each expression: add, subtract and compare only values with the same unit **and** the same scale; multiplying and dividing combine units (a price in USD per token times an amount in tokens gives USD); a scale factor changes the scale, never the unit.
4. Check that the result's unit and scale match what the function promises and what callers assume, on every return path (an early return in a different unit is a common slip). Check every conversion's direction and factor, and that each scale is applied exactly once.
5. Check integer arithmetic: order of multiplication and division, where rounding happens and in which direction (whom the specification says rounding should favor), and overflow at the largest realistic values.
6. Find conversion constants worth a second look: `rg -n '\b(1000|1e3|1e6|1e8|1e9|1e18|100|60|3600|86400|1024)\b' src/`. Each hit is a question, not a finding.

### Test for unit mistakes

- **Hand-worked examples with units written out** in the test (`# 3 items at 2.37 EUR = 7.11 EUR = 711 cents`), using values that are not round numbers and that differ per unit, so a mix-up changes the result.
- **Boundaries per scale:** the smallest unit (1 cent, 1 nanosecond, 1 token base unit), zero, the largest realistic value, and currencies or tokens with unusual exponents.
- **Properties** (see `advanced-testing.md`): conversions round-trip (`to_cents(from_cents(x)) == x` for every integer); scaling all quantities by k scales the result by k before rounding; expressing an input in another unit and converting gives the same result; the sum of rounded lines differs from the rounded sum by at most the documented tolerance.

## Checks (done when)

- [ ] Every requirement in scope has a quoted source, a verdict, evidence and, where it applies, a test named after it.
- [ ] Every `NOT FOUND` has a search log; every `PARTLY MET` names the path that misses enforcement.
- [ ] Behavior with no documentation was listed; contradictions between sources were reported.
- [ ] Each quantity in the changed arithmetic has a known unit and scale, as a type, a name or a comment.
- [ ] Each formula was walked; conversions have tests with non-round values and per-scale boundaries.

## Anti-patterns

- Treating a function's name, or a passing happy-path test, as proof a requirement holds.
- Paraphrasing requirements before checking them, so the check tests your reading instead of the text.
- Reporting "not found" after one search.
- Rating findings by how strongly the document words them instead of by consequence.
- Floats for money; durations as bare integers with no unit; magic conversion constants repeated across the code.
- Expected values in tests computed with the same conversion the code uses.
