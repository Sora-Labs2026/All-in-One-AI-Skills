# Electronic lab notebooks and lab-data platforms: Benchling, DNAnexus, LabArchives, protocols.io

Read this when code reads from or writes to an electronic lab notebook (ELN), a sample and sequence registry, an inventory system, a genomics or bioinformatics cloud platform, or a protocol repository: syncing results, registering entities, launching analysis jobs, backing up notebooks, or publishing a method. Generic token, webhook and retry practice is in `../../integrations/GUIDE.md`.

**Guardrail.** These systems are often the legal record of research and may be regulated (GLP, GMP, clinical). Read before writing, write only what the user approved, never delete or edit signed records, and keep tokens out of code, logs and chat (`../../agent-safety/GUIDE.md`). Jobs on compute platforms cost money: estimate and get approval before launching.

## Rules for every platform

- **Least privilege.** Use a service account or app credential scoped to the projects and actions needed; prefer read-only for analysis. Personal API keys carry all of the person's permissions.
- **Test tenant first.** Develop against a sandbox or test tenant or a scratch project. IDs (schemas, folders, projects) differ between tenants; look them up by name per environment instead of hard-coding.
- **Dry run by default.** Scripts that write print the planned creates and updates and require an explicit `--apply`. Show the plan to the user first.
- **Idempotent writes.** Search by a stable external key before creating, or use the platform's idempotency or upsert support, so a rerun does not duplicate entities or entries.
- **Pagination and rate limits.** List endpoints page; handle `429` responses with backoff and honor `Retry-After` (`../../integrations/references/reliability-and-testing.md`).
- **Data integrity.** Records should be attributable, legible, contemporaneous, original and accurate, and also complete, consistent, enduring and available (ALCOA+). Automation writes under its own identity, timestamps in UTC with the zone recorded, and attaches raw files with checksums rather than retyped numbers.
- **Never edit history.** Signed or witnessed entries are amended through the platform's amendment or versioning mechanism, not overwritten. Prefer archive to delete, and never delete without explicit approval of the exact items. Electronic records and signatures in regulated work fall under 21 CFR Part 11 in the US and EU GMP Annex 11.

A write script shape that works on any of these platforms:

```python
import argparse, json

def plan(records, find_existing):
    """Return the creates and updates needed; touches nothing."""
    actions = []
    for rec in records:
        current = find_existing(rec["external_id"])      # search by your stable key, never by display name alone
        if current is None:
            actions.append({"op": "create", "external_id": rec["external_id"], "fields": rec["fields"]})
        elif current["fields"] != rec["fields"]:
            actions.append({"op": "update", "id": current["id"], "fields": rec["fields"]})
    return actions

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true", help="perform the writes; default is a dry run")
args = parser.parse_args()
actions = plan(load_records(), find_existing)             # platform-specific helpers you write
print(json.dumps(actions, indent=2))                     # the user reviews this list
if args.apply:
    for action in actions:
        result = execute(action)                         # one write, with backoff on 429
        verify_by_reading_back(result)                   # and record the created ID
```

## Benchling

- Python SDK `benchling-sdk` over the REST API. Authenticate with an API key (acts as that user) or, for integrations, a Benchling App using OAuth client credentials with its own permissions.
- Main objects: registry entities (DNA and AA sequences, custom entities, mixtures) defined by schemas, inventory (containers, boxes, plates, locations), notebook entries created from templates, results captured through result schemas, and workflows. Fields are set by schema field name; read the schema first.
- Registering an entity assigns registry IDs through a naming strategy; decide the strategy with the registry owner, because registration is hard to undo.
- List calls return page iterators; bulk operations are asynchronous tasks that you wait on and then check for per-item errors.
- Analytics belong in the data warehouse (a read-only SQL replica with some lag) rather than in thousands of API calls.
- App integrations receive events and webhooks; verify webhook signatures with the SDK's helpers before acting on them.

```python
import os
from benchling_sdk.benchling import Benchling
from benchling_sdk.auth.api_key_auth import ApiKeyAuth

benchling = Benchling(url=os.environ["BENCHLING_URL"], auth_method=ApiKeyAuth(os.environ["BENCHLING_API_KEY"]))
for page in benchling.dna_sequences.list(name="pUC19"):   # pages of results
    for seq in page:
        print(seq.id, seq.name, len(seq.bases))
```

## DNAnexus

- `dx` command-line tool and the `dxpy` Python library. Work happens in projects with permission levels (view, upload, contribute, administer); files are data objects that become immutable once closed.
- Executables are applets (inside a project) and apps (published, versioned); both are described by `dxapp.json` and built with `dx build`. Workflows chain them, and WDL workflows can be compiled for the platform.
- `dx run` launches jobs on a chosen instance type; cost scales with instance size and run time, and spot instances can be interrupted. Estimate cost, run on a small input first, set the spending limits the project offers, and get approval before large runs. Watch with `dx watch` and stop with `dx terminate`.
- Some programs run their data on this platform under strict access terms (for example, large biobank research platforms where individual-level data may not leave the platform). Read the program's rules before downloading anything.

## Hosted bioinformatics workflow platforms

Several platforms host Nextflow, Snakemake or Python-decorated workflows with generated user interfaces and managed storage.

- Pin container images and tool versions; declare CPU, memory, GPU and disk per task; test with the pipeline's small test profile (nf-core pipelines provide `-profile test`) before real data.
- Paths in the platform's storage are not local paths; stage inputs explicitly and record where outputs land.
- Treat cost and data residency the same way as DNAnexus: estimate, approve, then run.

## LabArchives

- REST API for notebooks, pages, entries and attachments, typically available with an enterprise license. Requests are signed with an access key ID and an access password issued by the institution; user calls also need the user's ID, obtained from their email and an application-specific password. Follow the official signing recipe exactly and keep both secrets out of code.
- Use the regional endpoint that matches the institution's account (US, UK, Australia and others have separate hosts).
- Notebook backup downloads complete notebooks, with or without attachments; schedule backups to storage the institution controls and verify archives open.
- Write results as new entries or attachments on the right page; do not rewrite existing entries.

## protocols.io

- REST API with bearer tokens: a personal client token for your own content, OAuth for applications acting for other users.
- Public protocols are open access and, by default, licensed CC BY 4.0; each published version gets a DOI. Cite the version DOI used in an experiment, not the latest version, and record the license when reusing steps.
- Private workspaces hold unpublished protocols. Publishing is public and permanent for that version; never publish without the authors' explicit approval.
- Steps carry components (reagents with catalog numbers, equipment, timers); keep them structured so they can be checked against the lab's inventory.

## Checks (done when)

- Credentials are least-privileged, referenced by name only, and never printed.
- The write plan from a dry run was shown and approved; writes were verified by reading them back, and created IDs are recorded.
- Reruns create no duplicates (tested once on the test tenant).
- No signed record was edited, nothing was deleted, and nothing was published without explicit approval.
- Compute jobs had a cost estimate and approval; job IDs and logs are kept with the results.
