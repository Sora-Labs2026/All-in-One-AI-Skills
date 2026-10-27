# Salesforce

Read this before writing or changing code on the Salesforce platform: Apex classes and triggers, SOQL, asynchronous Apex, Lightning Web Components, integrations, and source-driven deployment with the `sf` CLI. Integration hygiene in general (scopes, webhooks, idempotency) is in `../../engineering-practices/references/resilience.md` and `../../engineering-practices/references/api-contracts.md`.

## Ground rules for orgs

- **An org is an environment, and a production org is production.** Do not deploy, run anonymous Apex, load or delete data, or change setup in a production org without the user's explicit permission for that action. Work in a scratch org or a sandbox, and validate deployments before running them.
- Authenticate with `sf org login web` (the user completes it) or a JWT flow configured by the user; never put passwords, security tokens or auth URLs in the repository or the chat (`../../agent-safety/GUIDE.md`).
- Check what automation already exists on an object (Flows, validation rules, other triggers, managed packages) before adding Apex; overlapping automation is the most common source of surprises.

## Orient first

- `sfdx-project.json`: package directories (usually `force-app`) and `sourceApiVersion`. Each of the three yearly releases (Spring, Summer, Winter) raises the API version by one; write for the project's version.
- The `sf` CLI (v2) replaced the old `sfdx` commands; use `sf`. Check `sf --version` and the plugins the project relies on.
- `package.json` holds LWC tooling: ESLint rules for LWC, Jest (`@salesforce/sfdx-lwc-jest`), Prettier with the Apex plugin.
- Packaging model: unpackaged source deployed to orgs, unlocked packages, or managed packages. Namespaces and package versioning change what you may rename or delete.

```bash
npm run lint && npm run test:unit                         # LWC lint and Jest, no org needed
sf org create scratch -f config/project-scratch-def.json -a dev --duration-days 7
sf project deploy start --target-org dev                  # scratch org or sandbox only
sf apex run test --target-org dev --test-level RunLocalTests --code-coverage --result-format human --wait 20
sf project deploy validate --target-org <alias> --test-level RunLocalTests   # check-only; prepare for the user when the target is production
```

## Governor limits

Apex runs in a shared, multi-tenant runtime with hard per-transaction limits. Exceeding one throws an exception that cannot be caught, and the whole transaction rolls back.

| Limit (per transaction) | Synchronous | Asynchronous |
|---|---|---|
| SOQL queries | 100 | 200 |
| Rows returned by SOQL | 50,000 | 50,000 |
| DML statements | 150 | 150 |
| Rows processed by DML | 10,000 | 10,000 |
| CPU time | 10 seconds | 60 seconds |
| Heap size | 6 MB | 12 MB |
| HTTP callouts | 100 (120 seconds total) | 100 |

These are long-standing values; confirm against the current Apex developer guide and check consumption with the `Limits` class (`Limits.getQueries()`, `Limits.getLimitQueries()`).

**Bulkify everything.** Triggers receive up to 200 records per chunk, and data loads, integrations and Flows call them with many records at once.

- No SOQL or DML inside loops. Collect IDs into a `Set<Id>`, query once into a `Map<Id, SObject>`, modify in memory, and issue one DML statement on a list.
- Test with 200 or more records, not one.
- Large data volumes belong in Batch Apex, not in a trigger.

## Triggers

- **One trigger per object**, containing no logic, delegating to a handler class by context (`before insert`, `after update`, ...). Follow the project's trigger framework if it has one.
- **Before triggers** change fields on the records being saved (no DML needed); **after triggers** work with record IDs and related records.
- **Recursion:** guard with a static `Set<Id>` of records already processed, not a static Boolean, which wrongly skips the second chunk of 200 in a large operation.
- Know the order of execution, roughly: system validation, before-save Flows, before triggers, custom validation and duplicate rules, the save, after triggers, assignment and auto-response rules, workflow rules, after-save Flows, roll-up summaries, then commit. Field updates in later steps can re-fire triggers; check the current Apex guide for the full list.
- Mixing DML on setup objects (users, groups, permission set assignments) and ordinary records in one transaction raises a mixed-DML error; move one side to asynchronous Apex.

## SOQL

- **Selective queries** on large objects: filter on indexed fields (Id, Name, OwnerId, CreatedDate, SystemModstamp, RecordTypeId, lookups and master-detail fields, External ID and unique fields). Leading wildcards (`LIKE '%x'`), negative operators (`!=`, `NOT IN`) and filters on formula fields usually cannot use an index. Non-selective queries inside triggers on large objects fail at runtime. Check with the Query Plan tool in the Developer Console.
- Relationship queries replace extra queries: parent fields with dot notation (`Account.Name`), child rows with subqueries (`(SELECT Id FROM Contacts)`).
- Aggregates (`COUNT()`, `SUM()`, `GROUP BY`) instead of loading rows to count them.
- **Dynamic SOQL:** bind variables (`Database.queryWithBinds(query, binds, AccessLevel.USER_MODE)`), never concatenation of user input. Field and object names from input are checked against an allowlist or the schema describe results.
- SOSL for text search across objects.

## Security model

- Apex runs in system mode: object permissions, field-level security and sharing are **not** applied unless you ask for them.
- Declare a sharing keyword on every class: `with sharing` for code serving users, `inherited sharing` for utilities, `without sharing` only with a written reason.
- Enforce object and field permissions: `WITH USER_MODE` in SOQL, `AccessLevel.USER_MODE` in `Database` methods, `insert as user` and its siblings for DML, or `Security.stripInaccessible` to drop fields the user cannot see. `WITH SECURITY_ENFORCED` is the older, narrower form.
- `@AuraEnabled` methods are endpoints any user with access to the component can call with arbitrary arguments; validate input and re-check access inside them.
- No hard-coded record IDs, user IDs or URLs; they differ between orgs. Use custom metadata types, custom settings or queries by developer name.

## Asynchronous Apex

| Need | Use |
|---|---|
| Work after the transaction, with object parameters, possibly chained | Queueable (`System.enqueueJob`), with a `Finalizer` to handle failures |
| Millions of records | Batch Apex (`Database.Batchable`, scope 200 by default, up to 2,000), `Database.Stateful` only if state must carry across chunks |
| Run on a schedule | Schedulable, which usually starts a Batch or Queueable |
| Decoupled processing or integration events | Platform Events (choose "publish after commit" for events tied to data changes) |
| Reacting to record changes outside the org | Change Data Capture |
| Legacy simple calls | `@future` (primitive arguments only, no chaining); prefer Queueable in new code |

- Callouts cannot follow uncommitted DML in the same transaction; do the callout first, or move it to a Queueable that allows callouts (`Database.AllowsCallouts`).
- Asynchronous jobs are not instant and not guaranteed to run in order; design them idempotent and observable (a status field or a log object).

## Integrations

- Outbound: Named Credentials with External Credentials hold endpoints and authentication; code references the credential name, never a token. Set explicit callout timeouts (default 10 seconds, maximum 120). Map responses into typed wrapper classes; handle non-2xx statuses and retries in a Queueable.
- Inbound: `@RestResource` classes are public API surface; authenticate through connected apps with least-privilege scopes, validate payloads, enforce user mode, and keep responses to allowlisted fields. Bulk API 2.0 suits large loads.
- Events out of the org: Platform Events and Change Data Capture through the Pub/Sub API; subscribers must handle replays and duplicates.

## Lightning Web Components

- Read data with `@wire` and Lightning Data Service (`getRecord`, `getRelatedListRecords`, UI API) where possible: cached, shared across components, respecting permissions. Apex methods used with `@wire` must be `@AuraEnabled(cacheable=true)` and cannot do DML.
- Writes call Apex imperatively or use `updateRecord`/`createRecord`; refresh wired data afterwards (`refreshApex` or `notifyRecordUpdateAvailable`).
- Communication: properties down (`@api`), `CustomEvent` up, Lightning Message Service across unrelated components. Keep events non-bubbling unless a parent outside the shadow tree must hear them.
- Use base components (`lightning-input`, `lightning-datatable`, `lightning-record-form`) before custom markup; they bring accessibility and styling with them.
- Lightning Web Security or Locker restricts DOM and global access; do not reach into other components' DOM.
- Jest tests for components (wire adapters mocked with the test utilities); ESLint with the LWC rules.

## Testing Apex

- Deployment to production requires at least 75% coverage across the deployed Apex and some coverage of every trigger; treat that as a floor, not a target. Assert outcomes with the `Assert` class (`Assert.areEqual`).
- Create data in the test (`@TestSetup` for shared fixtures); `SeeAllData=true` makes tests depend on org data and is avoided.
- Wrap the code under test in `Test.startTest()` and `Test.stopTest()`: limits reset for that block, and queued asynchronous work runs at `stopTest`.
- Test bulk (200+ records), negative cases, and permission scenarios with `System.runAs` and a user built with the right profile and permission sets.
- Callouts in tests use `Test.setMock` with an `HttpCalloutMock`; real callouts are not allowed.
- Static analysis with Salesforce Code Analyzer (PMD rules for Apex) if the project uses it.

## Deployment

- Source-driven: changes live in the repository, are deployed to a scratch org or sandbox for testing, then promoted by a pipeline or by the user.
- Before production: `sf project deploy validate` with `RunLocalTests` (or specified tests), then a quick deploy of the validated job inside its validity window. Prepare these commands; the user runs them or approves them explicitly.
- Deletions need a destructive-changes manifest; deleting fields or objects removes data. Ask before including one.
- Keep profiles and permission sets in source deliberately; deploying a whole profile can overwrite access settings in the target org.

## Done when

- [ ] Apex is bulkified (no SOQL or DML in loops), tested with 200+ records, and within governor limits in those tests.
- [ ] Every class declares sharing; queries and DML enforce user mode or strip inaccessible fields where users are served.
- [ ] LWC lint and Jest pass; Apex tests pass in a scratch org or sandbox with coverage reported.
- [ ] No hard-coded IDs, endpoints or credentials; callouts go through Named Credentials with timeouts.
- [ ] Nothing was deployed to, or run against, a production org without the user's explicit permission.
