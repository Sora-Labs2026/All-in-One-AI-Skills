# Wearable and consumer health data: import, normalize and protect

Read this when an application or analysis imports data from phones, smartwatches, fitness trackers, smart rings, scales, blood-pressure cuffs or glucose monitors: full exports from a phone's health app, a vendor's cloud API, CSV or JSON downloads, or a mobile health framework. Signal processing of raw waveforms is in `physiological-signals.md`. Privacy-policy and consent pages for the product are in `../../legal-ready/GUIDE.md`.

**Guardrail.** Consumer health data is sensitive personal data and usually not clinically validated. Summaries describe what was recorded; they do not diagnose, and they do not tell a person they have or lack a condition. Never fabricate a user's data, even as a placeholder in a demo; use generated synthetic data labeled as such.

## Sources and what they look like

| Source | Shape | Watch for |
|---|---|---|
| Full export from a phone health app | One large archive with an XML file of typed records (type, value, unit, start and end time with offset, source app and device), workouts, and sometimes clinical records as FHIR JSON | Hundreds of MB to several GB; many sources writing the same type |
| Vendor cloud API | OAuth 2.0; endpoints per data type and date range; daily summaries and intraday series; webhooks or subscriptions | Scopes per data type, token expiry and refresh, rate limits, data available only after the device syncs |
| Vendor CSV or JSON download | One file per type or per day | Column names and units change between export versions |
| Mobile health frameworks inside your own app | Per-type read and write permissions granted by the user; background delivery | Users grant some types and deny others; revocation at any time |

## Parse large exports by streaming

```python
import xml.etree.ElementTree as ET
from collections import Counter

counts = Counter()
for _, elem in ET.iterparse("export.xml", events=("end",)):
    if elem.tag == "Record":
        counts[(elem.get("type"), elem.get("unit"), elem.get("sourceName"))] += 1
        # convert and write the record to Parquet or a database here
    elem.clear()                      # free memory; never build the whole tree
print(counts.most_common(20))
```

- Inspect types, units and sources first (the counts above) and decide the mapping before converting anything.
- Treat the archive as untrusted input: extract into an empty directory, refuse paths that escape it, and parse XML with the standard library's defaults (no external entities) or `defusedxml`.

## Normalize

- **Time.** Keep each record's original offset and store UTC. Aggregate to "days" in the user's local time zone at that date, which changes when they travel and at daylight-saving transitions; test a day with 23 and a day with 25 hours. Interval records (sleep, workouts) cross midnight; split or assign them by a stated rule.
- **Duplicates across sources.** A phone and a watch can both count the same steps; summing them double-counts. Choose one source per data type by priority, or use the platform's own merged statistic, and record the choice.
- **Units.** Convert once at import to a canonical unit (kg, m, kcal, mmol/L or mg/dL as the product decides, beats per minute) and keep the original unit in a column. Use UCUM unit codes when exchanging data.
- **Sampling.** Heart rate is sparse at rest and dense during workouts; a plain mean over samples overweights workouts. Use time-weighted averages or the vendor's daily resting value, and say which.
- **Algorithms change.** Sleep stages, energy expenditure, readiness and stress scores are proprietary estimates that change with firmware and app versions and differ between vendors. Do not compare them across vendors or across algorithm versions as if they were the same measurement; store the source and version where available.
- **Interoperable output.** For clinical systems, map to FHIR R4 `Observation` resources with LOINC codes and UCUM units: for example heart rate 8867-4, body weight 29463-7, body height 8302-2, blood pressure panel 85354-9 with systolic 8480-6 and diastolic 8462-4, oxygen saturation by pulse oximetry 59408-5. Verify each code in the LOINC database before use. Open mHealth (IEEE 1752.1) schemas are an alternative for mobile health data.

A daily resting heart rate as a FHIR Observation (synthetic example):

```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
  "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}],
           "text": "Resting heart rate, daily value from wearable"},
  "subject": {"reference": "Patient/example"},
  "effectivePeriod": {"start": "2026-03-01T00:00:00+01:00", "end": "2026-03-02T00:00:00+01:00"},
  "valueQuantity": {"value": 58, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min"},
  "device": {"display": "[[device model and firmware]]"},
  "note": [{"text": "Synthetic example. Vendor-derived daily value, not a clinical measurement."}]
}
```

Validate resources against the target server's profiles (for example US Core) before sending; many servers reject resources that are valid FHIR but miss profile-required elements.

## OAuth integrations

- Request only the scopes the feature needs (steps and sleep do not need heart rate or location), explain each to the user, and handle partial grants.
- Store refresh tokens server-side, encrypted, never in the client, logs or chat; rotate on refresh; revoke tokens and delete data when the user disconnects (`../../integrations/references/oauth-and-tokens.md`).
- Respect rate limits and backfill history in throttled batches; verify webhook signatures and fetch the changed data rather than trusting the webhook body (`../../integrations/references/webhooks.md`).
- Vendor terms often restrict use of the data (no resale, no advertising, display requirements). Read them before building.

## Privacy and law

- **HIPAA** usually does not cover a consumer app unless it works for a covered entity or business associate. That does not make the data unregulated.
- **US Federal Trade Commission:** the Health Breach Notification Rule, amended in 2024, covers health apps and treats unauthorized disclosure (for example to advertising partners) as a breach; health claims need competent and reliable scientific evidence.
- **US states:** consumer health data laws such as Washington's My Health My Data Act require separate consent and a dedicated policy (`../../legal-ready/references/laws-and-standards.md`).
- **GDPR and UK GDPR:** data concerning health is special-category data; an Article 9 condition (usually explicit consent) is needed, along with data minimization, a DPIA for large-scale processing, and rights to access, export and delete.
- Minimize: collect the types and resolution the feature uses, keep raw intraday data only as long as needed, encrypt at rest, and keep health data out of analytics and crash-reporting tools.

## Presenting results

- Describe, do not diagnose: "your average resting heart rate this week was 58 bpm, 4 lower than last week", not "your heart is healthy".
- Thresholds that prompt someone to seek care must come from a clinically validated source and be reviewed by a clinician; features that detect conditions (irregular rhythm, sleep apnea) are medical device functions (`medical-device-quality.md`).
- Show data gaps and device changes on charts instead of interpolating across them.

## Checks (done when)

- An import report lists records per type and source, date range, unit conversions, duplicates resolved by which rule, and rejected rows with reasons.
- A few days were spot-checked against the source app's own display, including a daylight-saving day and a travel day if present.
- Tokens are stored server-side and encrypted with minimal scopes; disconnect revokes tokens and deletes data.
- Outputs contain no diagnostic language; synthetic test data is labeled; the applicable privacy duties are listed for the user.
