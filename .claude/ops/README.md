# Unattended daily jobs (`.claude/ops/`)

Scheduled jobs that fetch competition research and fact-check your docs, then
publish the result as a **draft PR** so nothing lands on a branch you rely on
without review.

## Setup

```bash
cd .claude/ops
cp ops.conf.example ops.conf     # fill in REPO, COMP, PREFIX, STOP_DATE
./install.sh                     # registers the LaunchAgents
launchctl list | grep <PREFIX>   # verify
```

Removal, which you should do the day the competition ends:

```bash
./uninstall.sh
```

## What runs

| job | default time | what it does |
|---|---|---|
| `research` | 03:03 | `kaggle_research.py` differential fetch → commit → draft PR |
| `factcheck` | 05:05 | deterministic ground truth → scoped agent → commit |

`run-daily.sh <job>` is the entry point for both; it dispatches to `<job>.sh`.
Add your own job by dropping in a `myjob.sh` and adding it to `JOBS` in
`install.sh`.

## Why launchd, and not an in-session scheduler

A schedule owned by a chat session is a schedule that fails quietly. Session
schedulers expire (typically after 7 days) and **duplicate across concurrent
sessions**, so two sessions each fetch, each commit, and each push. launchd is
one per machine, survives session restarts and reboots, and is inspectable with
`launchctl list`.

The design rule that follows: **sessions hold no schedule at all.** Jobs publish
through git; sessions pick results up with a pull.

Caveat: LaunchAgents only fire while the user is logged in, because they need
keychain access for the Kaggle and GitHub credentials.

## Safety properties

These exist because each one has a matching failure story.

- **Atomic lock.** `mkdir` on a lockdir, with a 3-hour staleness reclaim. Two
  runs cannot overlap even if one hangs.
- **Per-day dedup.** A `.state-<job>` file holds the last completed date, so a
  manual run plus the scheduled run does not double-commit.
- **Sync in first.** `git pull --rebase --autostash` before doing anything,
  which absorbs whatever your interactive sessions pushed overnight.
- **Auto-stop.** Past `STOP_DATE` the runner boots out its own LaunchAgents and
  deletes the plists. A job that outlives its competition is a job you will
  forget to turn off.
- **No agent in the fetch path.** `research.sh` is a plain script. Judgement
  belongs in a session where you can see it, not in a 3am cron.
- **The factcheck agent has no Bash and no Task.** It reads, searches and
  edits. It cannot run training code, submit, or spawn subagents. The wrapper
  does the git work, where it is auditable.

## The PR flow

When the fetch finds a diff, `research.sh` commits to `ops/research-YYYY-MM-DD`
and opens a **draft** PR. If an `ops/research-*` PR is already open, it pushes
to that branch instead and appends the run summary as a comment — a week of
fetches becomes one reviewable thread, not seven abandoned PRs. No diff means no
PR at all.

## Reading the PR

The run summary is in the PR body. The section worth your attention is
**warnings**:

```
! 1 count mismatches (possible silent under-fetch):
    kernel foo/bar: fetched 3 of 4 comments
```

That means Kaggle reports more comments than the fetcher retrieved. Usually it
is a deleted comment. Occasionally it is the fetcher losing content, which is
exactly the failure that motivated the check — an earlier tool returned 15
comments where Kaggle showed 64, and nothing announced it.
