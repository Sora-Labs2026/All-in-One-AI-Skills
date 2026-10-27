# Internal communications and meeting notes

Read this when writing a team status update, leadership update, project status, company newsletter, FAQ, announcement or incident note, or when turning meeting notes or transcripts into decisions and actions, or analyzing communication patterns in the user's own meetings.

These are documents, not chat replies: they follow the organization's conventions, not the chat length settings in `../../lean-output.md`.

## Principles for every internal message

- **First line answers the reader's first question:** is it on track, what changed, what do you need from me.
- **Facts with sources:** link the ticket, document, dashboard or decision record. Numbers come from those sources; never estimate a metric and present it as measured. Missing data is written as missing.
- **Bad news early and plainly,** with what is being done about it.
- **Owners and dates** on every action and every ask.
- **Match the house format.** Ask for a recent example of the same kind of message and follow it; templates below are defaults.
- **Fit the channel:** a chat post is read in seconds, an email in a minute, a document when someone needs depth.

## Gathering the input

Use what the user gives you, or the sources they connect and authorize (chat channels, documents, tickets, calendar, email). Read only what the message needs. Respect the audience boundary: content from private channels, personnel matters or confidential deals does not move into a broad message without the user's explicit decision. When sources conflict, say so and ask.

## Formats

**Weekly team update (progress, plans, problems).** For readers with some context and little time; readable in under a minute.

```text
<Team> - week of <dates>
Progress: <1-3 sentences: shipped, decided, learned; numbers where they exist>
Plans: <1-3 sentences: the most important work for next week>
Problems: <1-3 sentences: blockers, risks, what help is needed and from whom>
```

The bigger the team, the higher the level: a squad reports features and bugs, a company reports hires, launches and deals.

**Leadership update.** Decision or ask first; then status (on track, at risk, off track) with the criterion behind it; then the two or three risks with mitigations and owners; then what changed since last time. Define the status colors once (for example "at risk: the milestone date holds only if X happens by Friday") so they mean something.

**Project status.** A milestone table (milestone, date planned, date forecast, status, note), the changes since the last report, decisions needed, and risks. Forecast dates move only with a reason.

**Company newsletter.** Grouped by area (announcements, progress on priorities, people and teams, external news), one or two sentences per item with a link, written in the company's voice. Company-wide relevance only; team detail belongs in team updates. Credit people by name only with their agreement when the item is personal.

**FAQ.** Questions phrased the way people actually ask them, answers in one to three sentences, a link to the authoritative source, and a date. When the answer is uncertain or needs an official decision, say so and name who will answer.

**Announcement or change notice.** What is changing, who is affected, when, what they need to do, where to ask. Put the action in the subject line or the first sentence when there is one.

**Incident note.** While the incident is live: what is affected and for whom, since when (UTC), current status, what is being done, and when the next update will come. After resolution, a blameless review: summary, impact (users, duration, data), timeline in UTC, contributing factors (systems and conditions, not individuals), what went well, what was hard, and action items with owners and dates. Customer-facing statements are separate documents reviewed by the people responsible for communications and, where relevant, legal; incident data handling and runbooks are in `../../engineering-practices/references/observability.md`.

## Tone

Plain, specific and calm. No hype, no emoji unless the organization's style uses them, no blame. Inclusive language. Short sentences; one topic per paragraph.

## Meeting notes

From notes or a transcript, produce:

1. **Decisions** made, each in one sentence, with who decided.
2. **Action items:** what, owner, due date. If an owner or date was not agreed, write "owner not agreed" rather than assigning one.
3. **Open questions** and who will answer them.
4. **Key points of discussion,** briefly, when the decision needs context.

Separate what was said from your interpretation. Check names and numbers against the transcript, and send the notes to attendees for correction before treating them as the record.

## Analyzing communication patterns in meetings

Users sometimes want feedback on their own habits: talk-time share, interruptions, how they handle disagreement, how clear their asks are.

- **Consent and privacy first.** Analyze recordings or transcripts only where the user has the right to: their own meetings, recorded with participants' knowledge and in line with the organization's policy and recording-consent law. Focus on the user's own behavior. Do not build profiles of colleagues, and keep transcripts local.
- **Know the data's limits.** Automatic transcripts misattribute speakers, drop or invent filler words and miss overlaps. Treat counts as approximate and say so.
- **Measure what the transcript supports:** talk-time share per speaker (from timestamps), number and length of turns, questions asked, explicit asks and whether they had an owner and date. Interruption counts from overlapping timestamps are unreliable; report them only as rough indicators.
- **Show evidence:** for each pattern, two or three quoted examples with meeting and timestamp, why it matters, and an alternative phrasing.
- **Do not diagnose:** no inferences about personality, emotions, mental health or intent. Describe behavior and its likely effect on the conversation.

Talk time per speaker from a WebVTT file with voice tags (`<v Name>`), standard library only:

```python
import re, sys
from collections import defaultdict

CUE = re.compile(r"(\d+):(\d\d):(\d\d)\.(\d+)\s+-->\s+(\d+):(\d\d):(\d\d)\.(\d+)")
VOICE = re.compile(r"<v\s+([^>]+)>")

def seconds(h, m, s, frac):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(frac) / 10 ** len(frac)

def talk_time(path):
    totals, start, end = defaultdict(float), None, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = CUE.search(line)
            if m:
                start, end = seconds(*m.group(1, 2, 3, 4)), seconds(*m.group(5, 6, 7, 8))
                continue
            v = VOICE.search(line)
            if v and start is not None:
                totals[v.group(1).strip()] += end - start
                start = None          # count each cue once
    whole = sum(totals.values()) or 1
    for name, secs in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"{name:25s} {secs / 60:6.1f} min  {100 * secs / whole:5.1f} %")

talk_time(sys.argv[1])
```

Export formats differ (speaker names in a prefix like `Name:` instead of voice tags, SRT instead of VTT); adapt the parser and check its totals against the meeting length.

## Checks (done when)

- [ ] The format matches the organization's example or the defaults above; the first line answers the reader's main question.
- [ ] Every number links to its source; missing data is marked, not estimated.
- [ ] Actions have owners and dates, or are marked unassigned.
- [ ] No confidential content crossed into a wider audience without the user's decision.
- [ ] Meeting analyses used only material the user may analyze, stated the transcript's limits, quoted evidence and avoided judgments about people.
