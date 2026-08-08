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
| `translate` | 04:04 | render → per-document translating agent → Japanese docs → draft PR |
| `factcheck` | 05:05 | deterministic ground truth → scoped agent → commit |

`run-daily.sh <job>` is the entry point for all of them; it dispatches to
`<job>.sh`. Add your own by dropping in a `myjob.sh` and adding it to
`OPS_JOBS` in `jobs.def` — that one list is what install, uninstall and the
auto-stop loop all read, so a job cannot end up registered by one and forgotten
by another.

`translate` is **off by default**: it is the only job that spends model tokens
per document. Set `TRANSLATE_ENABLED=1` in `ops.conf` and re-run `./install.sh`.

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
- **The translate agent gets one document at a time.** Same tool restrictions,
  plus a per-document turn budget. An agent handed the whole batch starts
  summarizing when it runs low on turns — which is the single failure the job
  exists to prevent — and a crash at document 30 of 48 would lose the 29
  finished translations.

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

## The translation layer, and why it is quarantined

`translate` produces Japanese full translations of **every** discussion thread and
writeup the fetcher tracks, with the original figures downloaded and the reply
thread attached to the end of the body it belongs to. It is for **humans**.

Nothing is filtered: the fetch already enumerated the whole corpus, and the Kaggle
CLI payload carries no post body, so a thread that is never rendered has no body in
the repo in either language. Volume is absorbed by ordering — ranked writeups
first, then by votes — so `TRANSLATE_MAX_PER_RUN` caps a night's cost without
deciding what gets read. On a busy competition expect 150-250 documents and about
ten nights at the default 20/night, with the ones worth reading landing first.

    research/rendered/     English.  Agent-facing. The canonical text.
    research/assets/       Figures.  Referenced by both sides.
    docs/research-ja/      Japanese. HUMAN-FACING ONLY.

A translation is a lossy derivative. An agent that cites one inherits a
translator's paraphrase instead of what the author wrote, and nothing
downstream announces the substitution — a single mistranslated hyperparameter
becomes a premise nobody can trace back. So the separation is mechanical, not a
convention people are asked to remember:

1. `.claude/settings.json` puts `Read(./docs/research-ja/**)` in `permissions.ask`.
   What that blocks is an agent *deciding on its own* to read a translation: the
   attempt becomes a prompt you have to approve. If you asked for it, approve it.
   An unattended run has nobody to ask and is refused — measured, not assumed.
2. Every generated file carries a `<!-- HUMAN-ONLY-TRANSLATION -->` marker with
   the path of its English original. `research_ja.py index` re-asserts the
   marker on every run, so it does not depend on the translating agent
   remembering to emit it.
3. The index and the PR body say the same thing in the place someone would
   actually be standing when they get it wrong.

Read the translations yourself freely. When an agent needs the *substance*, point
it at `research/rendered/<key>.md` — that is the sanctioned path and it needs no
approval. The prompt is not there to stop you; it is there so that "the agent read
a translation" is always a decision someone made, never a default.

Details, including the failure modes behind each design choice, are in
`.claude/skills/kaggle/research-ja-translation.md`.
