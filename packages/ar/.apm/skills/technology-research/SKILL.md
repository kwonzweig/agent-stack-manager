---
name: technology-research
description: Use when a decision needs factual investigation, background, alternatives or evidence of effectiveness, or when a company requests a technology assessment, an adoption recommendation, or a recurring scan of AI tools, agent stacks, or its technical domain. Routine implementation under an accepted specification does not require a separate research project.
---

# Technology research

## Start

Read the task and company brief: question, intended decision, goals, stack, constraints,
approved sources and accounts, scan window, effort cap, durable record directory, and
report destination. Ask for missing inputs that prevent useful work. Use an existing
approved connection; an unavailable account is a coverage gap. Research and adoption
are separate decisions.

A single question needs no scan records. Choose evidence that fits it. For a current
fact, read an official specification, versioned implementation or live record. For
background or alternatives, compare primary sources within a stated search scope. For
effectiveness or adoption, inspect observed use, contrary evidence, local conditions
and operating burden. A missing optional skill does not authorize installation or
prevent the inquiry. A targeted inquiry is not a systematic review.

A recurring scan names the company brief, the approved sources and the durable research
directory. If one is missing, report the missing setting on the task and stop before
research or state writes. The lookback window and effort limit must be positive.
Derive the window from the occurrence timestamp and keep it unchanged on retry. Save
records in the named directory.

Load `state.json` using [the record format](references/records.md), previous reports, unfinished
scans, and findings awaiting a decision. Give each run a stable ID from its Paperclip
task or routine occurrence. A retry keeps that ID. On a first run, initialize empty
`sources`, `items`, and `runs` maps. Track versions of the brief and source list so
changes can trigger reassessment without discarding reading history.

## Collect

Start with one approved feed or API and one browser source. Expand when the current
sources no longer answer the question.

For a GitHub repository on the source list, read its releases through
`GET /repos/{owner}/{repo}/releases?per_page=100`. Follow pagination and rate-limit
headers. Use conditional requests where the connection exposes them. Match release
IDs and compare update timestamps or body hashes before rereading bodies. Old
publication dates alone do not prove an entry is unchanged.

For browser research, open the approved source in the actual browser. Record the
visible account scope, query, filters, time window, pages read, and stopping point.
Search results and personalized feeds are samples. Open promising originals; do not
report a snippet or remembered fact as a completed read. Read the relevant original
sections before claiming to apply a method.

Keep the collection route in each source record. If one source fails, record its
unread range, disclose the gap and continue with other accessible sources within the
effort limit. Do not claim to have read an original you could not open. Do not switch
accounts or bypass access controls.

## Assess

Follow important claims to the original release, repository, paper, dataset, or
documented observation. Keep discovery links while counting repeated claims from one
origin once. Distinguish publisher claims, independent evidence, company observations,
and your inference. Seek relevant failure cases and conflicting evidence. State what
could change the recommendation. Missing evidence remains a limit; do not invent
observations to fill a report.

Rank by the company's problem, practical value, compatibility, evidence, adoption
effort, and maintenance cost. Explain the order. GitHub trends, skills.sh installs,
publisher reputation and social attention help discover candidates; they do not prove
effectiveness in this company's setting.
For example, a tool that works with the company's stack can outrank a popular
incompatible demo. A speed claim without a baseline calls for a trial.

Read changed material and unresolved sources. Reuse unchanged content. When the
company brief changes, reassess cached findings without calling them new discoveries.
A source correction updates the existing finding and explains what changed.

## Save progress

Use one active writer for the research directory. Save inspected items and each
completed page before advancing its cursor. Write a temporary state file, validate
it, then replace `state.json` atomically. Keep the prior snapshot for recovery.

A cursor records the next unread page. Completed coverage advances only across a
fully checked window; page progress can advance while that window remains incomplete.
Advance a page cursor only when the response identifies the page and confirms its
completion or next cursor. An unlabeled batch or a reference to a later page does
not establish that an earlier pending page was fully read. Keep that pending cursor
and record the uncertainty as a gap.
Overlap time windows to catch late items and deduplicate the overlap. For an expired
cursor, make a bounded recovery scan and record any gap that remains.

Match items by provider ID and canonical URL, revisions by fingerprint or provider
revision, and repeated claims by origin. Keep unknown values null with a reason in
the item's `unknowns` or the source's `pending_reason`. Never store credentials.
Preserve previous conclusions in run reports when updating current item records.

## Report

Publishing a recommendation does not authorize installing a tool or changing policy.
CAO owns any consolidated user-facing report.

For a single question, answer on the source Task with direct source locators, the
checked version or date, what you actually read, findings, contrary evidence,
applicability limits, and a recommendation or the unresolved decision. A simple lookup
can be a short comment; a substantive comparison can be a Task document or artifact.
Reuse an existing evidence record instead of duplicating it.

For a scan, write `reports/<run-id>.md` in the assigned directory and link it from the
Paperclip task. Each useful finding states the company use, cited evidence and relevant
version/date, uncertainty and contrary evidence, prerequisites and costs, and a
proposed owner and next step. Recommend investigate, trial, watch, or dismiss.

Include a short note on what was checked, unchanged, or inaccessible. No useful
change is a valid result. Notify for useful findings, changed conclusions, or failures
requiring action; otherwise retain the record quietly unless regular summaries were
requested.

Save a stable report ID before delivery. On retry, check the destination for that ID
before sending again. Mark it delivered only after confirmation. If confirmation is
uncertain, reconcile the destination first; do not assume delivery failed.
