#!/usr/bin/env python3
"""Differential fetch of a Kaggle competition's public research surface.

Covers four surfaces. Three come from the official Kaggle CLI; only writeup
*bodies* need an external renderer:

  notebook source        kernels pull
  discussion list        competitions topics list -p 1..N   (ALL pages)
  discussion + comments  competitions topics show --format json
  kernel comments        kernels topics list -> kernels topics show
  writeup DISCOVERY      regex over the fetched discussion corpus  (CLI-native)
  writeup BODY           r.jina.ai reader                         (external)

Design notes, each of which exists because the naive version cost us real
information on a live competition:

  * FULL ENUMERATION IS THE DEFAULT. Paging stops only when Kaggle runs out of
    topics. `--top-topics N` is an opt-in fast path. A top-N-only fetcher builds
    a permanent blind spot: the manifest then only ever refreshes what it
    already knows, so whatever fell outside the first cut is never seen again.
    (Measured: 158 threads existed, 43 were tracked.)
  * COUNTS ARE SELF-VERIFIED. Kaggle reports `commentCount` on the topic; we
    compare it against what we actually parsed and record any shortfall. An
    earlier fetcher silently returned 15 comments where Kaggle showed 64.
  * --format json EVERYWHERE. The plain-text CLI output truncates comment
    bodies; the JSON form does not.
  * WRITEUP EDITS ARE DETECTED, not just new writeups: we store a sha256 of the
    body and re-fetch on a schedule, so an in-place revision shows up as a diff.
  * FAILURES ARE LOUD. Anything that could not be fetched lands in the manifest
    under `errors` and in the printed summary, so the unattended daily job can
    put it in the PR body instead of quietly reporting success.

State lives in <out>/manifest.json so re-runs pull only new or changed items.

Raw pulls go under <out>/ and are meant to be gitignored (other people's source
and licensing). Only your own derived digests get committed.

Usage:
  kaggle_research.py --comp <slug> [--out research]
  kaggle_research.py --comp <slug> --audit          # coverage report, no fetch
  kaggle_research.py --comp <slug> --dry-run
  kaggle_research.py --comp <slug> --full           # ignore manifest, re-pull all

Requires the official Kaggle CLI >= 2.2 (`kernels topics` landed in 2.2).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

KAGGLE = "kaggle"
JINA = "https://r.jina.ai/"

# Kaggle starts 429-ing on sustained sequential topic fetches; 4s was the
# measured-safe spacing for a >60 item run.
DEFAULT_SLEEP = 4.0
JINA_SLEEP = 6.0
WRITEUP_RE = re.compile(
    r"https?://(?:www\.)?kaggle\.com/writeups/([A-Za-z0-9_\-]+)/([A-Za-z0-9_\-]+)"
)


# --------------------------------------------------------------------------
# process helpers
# --------------------------------------------------------------------------
def kaggle(args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            [KAGGLE, *args], capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        print(
            "error: `kaggle` CLI not found on PATH. Install with "
            "`uv tool install kaggle` and authenticate (see kaggle-api-setup.md).",
            file=sys.stderr,
        )
        sys.exit(2)


# The CLI reports an empty collection as prose on stdout rather than as `[]`.
# That is a legitimate "nothing here", not a failure, and must not be counted as
# an error -- most notebooks have no comment thread at all.
EMPTY_SENTINELS = ("no topics found", "not found", "no results", "none found")


def kaggle_json(args: list[str], timeout: int = 300):
    """Run a CLI command with --format json and parse it.

    Returns (data, error). `data == []` means the collection is genuinely empty;
    `data is None` means the call failed and `error` explains why.
    """
    rc, out, err = kaggle([*args, "--format", "json"], timeout=timeout)
    if rc != 0:
        return None, (err.strip() or out.strip())[:200]
    out = out.strip()
    if not out:
        return [], None
    # The CLI occasionally prefixes a warning line before the JSON payload.
    start = min((i for i in (out.find("["), out.find("{")) if i != -1), default=-1)
    if start == -1:
        if any(s in out.lower() for s in EMPTY_SENTINELS):
            return [], None
        return None, f"no JSON in output: {out[:120]}"
    try:
        return json.loads(out[start:]), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode: {e}"


def parse_csv(text: str) -> list[dict]:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(("ref,", "id,")):
            return list(csv.DictReader(io.StringIO("\n".join(lines[i:]))))
    return []


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def safe_name(ref: str) -> str:
    return ref.replace("/", "__")


# --------------------------------------------------------------------------
# discussion topics
# --------------------------------------------------------------------------
def list_all_topics(comp: str, max_pages: int = 60, sleep: float = 0.5):
    """Page through EVERY discussion topic. This is the default on purpose.

    Returns (topics, error). A non-None error means enumeration stopped early --
    auth, rate limit, network -- so the caller is holding a PARTIAL list. That
    has to be reported: silently returning what we happened to collect would let
    the daily job mark a run successful while whole pages went unseen.
    """
    seen: dict[str, dict] = {}
    for page in range(1, max_pages + 1):
        rows, err = kaggle_json(
            ["competitions", "topics", "list", comp, "-p", str(page), "-s", "new"]
        )
        if rows is None:
            print(f"  ! topics list page {page}: {err}", file=sys.stderr)
            return seen, f"topic enumeration stopped at page {page}: {err}"
        if not rows:
            break
        before = len(seen)
        for r in rows:
            tid = str(r.get("id") or "")
            if tid:
                seen[tid] = r
        # No new ids on a full page means the API is repeating itself; stop.
        if len(seen) == before:
            break
        if len(rows) < 20:
            break
        time.sleep(sleep)
    return seen, None


def list_top_topics(comp: str, n: int):
    """Opt-in fast path: only the top-N. Leaves a blind spot by construction."""
    seen: dict[str, dict] = {}
    errs = []
    for sort in ("top", "new"):
        rows, err = kaggle_json(["competitions", "topics", "list", comp, "-s", sort])
        if rows is None:
            print(f"  ! topics list ({sort}): {err}", file=sys.stderr)
            errs.append(f"topics list ({sort}): {err}")
            continue
        for r in rows[:n]:
            tid = str(r.get("id") or "")
            if tid:
                seen.setdefault(tid, r)
    return seen, ("; ".join(errs) if errs else None)


def fetch_topic(tid: str, dest: Path) -> tuple[dict | None, str | None]:
    """Fetch one topic with its full comment tree as JSON."""
    data, err = kaggle_json(["competitions", "topics", "show", str(tid)])
    if data is None:
        return None, err
    if not isinstance(data, dict) or "topic" not in data:
        return None, f"unexpected payload shape: {type(data).__name__}"
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    topic = data.get("topic") or {}
    comments = data.get("comments") or []
    return {
        "title": (topic or {}).get("title"),
        "votes": (topic or {}).get("votes"),
        "commentCount": (topic or {}).get("commentCount"),
        "commentsFetched": len(comments),
        "postDate": (topic or {}).get("postDate"),
        "path": str(dest),
    }, None


# --------------------------------------------------------------------------
# notebooks + kernel comments
# --------------------------------------------------------------------------
def list_kernels(comp: str, sort: str, n: int) -> list[dict]:
    rc, out, err = kaggle(
        [
            "kernels",
            "list",
            "--competition",
            comp,
            "--sort-by",
            sort,
            "--page-size",
            str(n),
            "--csv",
        ]
    )
    if rc != 0:
        print(f"  ! kernels list ({sort}): {err.strip()[:200]}", file=sys.stderr)
    return parse_csv(out)


def list_all_kernels(comp: str, max_pages: int = 40, page_size: int = 50) -> dict:
    """Page through every public notebook for the competition."""
    seen: dict[str, dict] = {}
    for page in range(1, max_pages + 1):
        rc, out, err = kaggle(
            [
                "kernels",
                "list",
                "--competition",
                comp,
                "--sort-by",
                "dateCreated",
                "--page-size",
                str(page_size),
                "-p",
                str(page),
                "--csv",
            ]
        )
        if rc != 0:
            print(f"  ! kernels list page {page}: {err.strip()[:160]}", file=sys.stderr)
            break
        rows = parse_csv(out)
        if not rows:
            break
        before = len(seen)
        for r in rows:
            if r.get("ref"):
                seen[r["ref"]] = r
        if len(seen) == before:
            break
    return seen


def list_kernel_topics(ref: str) -> tuple[list | None, str | None]:
    """Cheap probe: the comment threads on a notebook, with their counts.

    One call per notebook. It is what makes change detection correct: comments
    accumulate on their own timeline, entirely independent of when the notebook
    last ran. (Measured: a thread posted 2026-06-23 on a notebook whose
    lastRunTime is 2026-08-01.) Keying comment freshness off lastRunTime would
    mean a new comment on an older notebook is never seen -- precisely the kind
    of silent miss this tool exists to prevent.
    """
    return kaggle_json(["kernels", "topics", "list", ref])


def fetch_kernel_comments(
    ref: str, dest: Path, topics: list
) -> tuple[dict | None, str | None]:
    """Pull the full comment tree for each of a notebook's threads.

    This is the surface an earlier implementation missed entirely, reaching for
    the kagglesdk discussions client instead and under-fetching by ~4x.
    """
    if not topics:
        dest.write_text("[]")
        return {"threads": 0, "commentCount": 0, "commentsFetched": 0}, None

    threads, declared, fetched = [], 0, 0
    for t in topics:
        declared += int(t.get("commentCount") or 0)
        data, terr = kaggle_json(["kernels", "topics", "show", str(t.get("id"))])
        if data is None:
            print(f"  ! kernel topic {t.get('id')}: {terr}", file=sys.stderr)
            continue
        comments = data.get("comments") or [] if isinstance(data, dict) else []
        fetched += len(comments)
        threads.append(data)
        time.sleep(1.0)

    dest.write_text(json.dumps(threads, indent=2, ensure_ascii=False))
    return {
        "threads": len(threads),
        "commentCount": declared,
        "commentsFetched": fetched,
    }, None


# --------------------------------------------------------------------------
# writeups: CLI-native discovery, external body fetch
# --------------------------------------------------------------------------
def discover_writeups(disc_dir: Path) -> dict[str, str]:
    """Extract every writeup URL mentioned anywhere in the discussion corpus.

    Discovery deliberately uses only CLI-fetched material, so a writeup is never
    missed because an external service was unavailable.
    """
    found: dict[str, str] = {}
    for f in sorted(disc_dir.glob("*.json")):
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for user, slug in WRITEUP_RE.findall(text):
            found[f"{user}/{slug}"] = f"https://www.kaggle.com/writeups/{user}/{slug}"
    return found


def fetch_writeup(
    url: str, dest: Path, api_key: str | None
) -> tuple[str | None, str | None]:
    """Fetch a rendered writeup body through the Jina reader.

    The only external dependency in this tool. Kaggle serves writeups as a JS
    shell (a direct curl returns ~8KB with none of the prose), and the official
    CLI exposes no writeup surface at all, so a renderer is unavoidable here.
    """
    if not shutil.which("curl"):
        return None, "curl not found"
    cmd = ["curl", "-sS", "-m", "120", "-H", "x-no-cache: true", "-H", "x-timeout: 30"]
    if api_key:
        cmd += ["-H", f"Authorization: Bearer {api_key}"]
    cmd.append(f"{JINA}{url}")

    last = "unknown"
    for _attempt in range(3):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
        except subprocess.TimeoutExpired:
            last = "timeout"
            time.sleep(15)
            continue
        body = p.stdout
        # The reader answers 200 even when Kaggle served a 404, embedding the
        # real status in the body. Without this check a deleted writeup gets
        # saved as a ~400 byte cookie-banner stub that looks like a real fetch --
        # which is exactly what an earlier ad-hoc process did.
        if "returned error 404" in body or "returned error 403" in body:
            return None, "GONE"
        if p.returncode == 0 and len(body) > 400 and "URL Source:" in body:
            dest.write_text(body)
            return body, None
        last = (p.stderr.strip() or f"short/invalid response ({len(body)}B)")[:160]
        time.sleep(15)
    return None, last


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Differential fetch of a Kaggle competition's research surface."
    )
    ap.add_argument("--comp", required=True, help="competition slug")
    ap.add_argument("--out", default="research")
    ap.add_argument(
        "--top-topics",
        type=int,
        default=0,
        help="opt-in fast path: only top-N topics instead of full enumeration "
        "(leaves a permanent blind spot; default 0 = fetch everything)",
    )
    ap.add_argument(
        "--top-notebooks",
        type=int,
        default=0,
        help="0 = enumerate all notebooks; N = top-N by votes + newest",
    )
    ap.add_argument("--skip-notebooks", action="store_true")
    ap.add_argument(
        "--skip-comments",
        action="store_true",
        help="skip kernel comments (the slowest stage)",
    )
    ap.add_argument("--skip-writeups", action="store_true")
    ap.add_argument(
        "--writeup-refresh-days",
        type=int,
        default=7,
        help="re-fetch known writeup bodies this often to catch edits",
    )
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    ap.add_argument("--full", action="store_true", help="ignore manifest, re-pull all")
    ap.add_argument(
        "--audit",
        action="store_true",
        help="report coverage vs manifest and exit without fetching",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--jina-key", default=None, help="optional JINA_API_KEY for a higher rate limit"
    )
    ap.add_argument(
        "--now",
        default=None,
        help="ISO date override for reproducible runs (default: today)",
    )
    a = ap.parse_args()

    import os
    from datetime import date, timedelta

    today = date.fromisoformat(a.now) if a.now else date.today()
    jina_key = a.jina_key or os.environ.get("JINA_API_KEY")

    out = Path(a.out)
    nb_dir, disc_dir = out / "notebooks", out / "discussions"
    kc_dir, wu_dir = out / "kernel_comments", out / "writeups"
    for d in (nb_dir, disc_dir, kc_dir, wu_dir):
        d.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"

    disk = {}
    if manifest_path.exists():
        try:
            disk = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            print("! manifest.json unreadable; starting fresh", file=sys.stderr)

    if not a.full:
        manifest = disk
    else:
        # --full re-pulls from scratch, but the manifest is written back as a
        # whole file. Sections this run is NOT re-fetching must be carried over
        # or they are erased -- including the writeup `gone` / `lastError`
        # markers, whose whole purpose is to stop the daily job re-reporting
        # writeups that were deleted upstream.
        manifest = {}
        if a.skip_notebooks or a.skip_comments:
            manifest["kernel_comments"] = disk.get("kernel_comments", {})
        if a.skip_notebooks:
            manifest["notebooks"] = disk.get("notebooks", {})
        if a.skip_writeups:
            manifest["writeups"] = disk.get("writeups", {})
        carried = [
            k for k in ("notebooks", "kernel_comments", "writeups") if k in manifest
        ]
        if carried:
            print(f"  --full: carrying over skipped sections {carried}")

    m_nb = manifest.setdefault("notebooks", {})
    m_tp = manifest.setdefault("topics", {})
    m_kc = manifest.setdefault("kernel_comments", {})
    m_wu = manifest.setdefault("writeups", {})
    errors: list[str] = []
    warnings: list[str] = []
    wu_gone: list[str] = []
    kc_changed: list[str] = []

    # ---- enumerate discussion topics (ALL of them, by default) ----
    print(f"enumerating topics for {a.comp} ...")
    topics, enum_err = (
        list_top_topics(a.comp, a.top_topics)
        if a.top_topics
        else list_all_topics(a.comp)
    )
    if enum_err:
        # Loud, and fatal to the run's exit status: everything downstream is
        # computed against a list we know is incomplete.
        errors.append(enum_err)
    print(f"  {len(topics)} topics visible on Kaggle, {len(m_tp)} tracked in manifest")

    missing = sorted(set(topics) - set(m_tp))
    if a.audit:
        print(f"\n=== coverage audit: {a.comp} ===")
        print(f"topics on Kaggle : {len(topics)}")
        print(f"tracked          : {len(m_tp)}")
        print(f"NEVER FETCHED    : {len(missing)}")
        for t in missing[:40]:
            r = topics[t]
            title = (r.get("title") or "")[:64]
            print(
                f"  {t}  votes={r.get('votes', '?'):>3} "
                f"comments={r.get('commentCount', '?'):>3}  {title}"
            )
        if len(missing) > 40:
            print(f"  ... and {len(missing) - 40} more")
        short = [
            (k, v)
            for k, v in m_tp.items()
            if v.get("commentCount") is not None
            and (v.get("commentsFetched") or 0) < v["commentCount"]
        ]
        print(f"\ntopics with FEWER comments fetched than Kaggle reports: {len(short)}")
        for k, v in short[:20]:
            print(f"  {k}: got {v.get('commentsFetched')} of {v['commentCount']}")
        wu_known = len(m_wu)
        print(f"\nwriteups tracked : {wu_known}")
        return 0

    # ---- fetch changed topics ----
    tp_new, tp_upd = [], []
    for tid, t in sorted(topics.items()):
        prev = m_tp.get(tid)
        cc = t.get("commentCount")
        changed = prev is None or str(prev.get("commentCount")) != str(cc)
        if not changed:
            continue
        (tp_new if prev is None else tp_upd).append(tid)
        if a.dry_run:
            continue
        rec, err = fetch_topic(tid, disc_dir / f"{tid}.json")
        if rec is None:
            errors.append(f"topic {tid}: {err}")
            continue
        declared, got = rec.get("commentCount"), rec.get("commentsFetched")
        if declared is not None and got is not None and got < declared:
            warnings.append(f"topic {tid}: fetched {got} of {declared} comments")
        m_tp[tid] = rec
        time.sleep(a.sleep)

    # ---- notebooks ----
    nb_new, nb_upd = [], []
    if not a.skip_notebooks:
        if a.top_notebooks:
            kernels = {
                k["ref"]: k for k in list_kernels(a.comp, "voteCount", a.top_notebooks)
            }
            for k in list_kernels(a.comp, "dateCreated", max(3, a.top_notebooks // 2)):
                kernels.setdefault(k["ref"], k)
        else:
            kernels = list_all_kernels(a.comp)
        print(f"  {len(kernels)} notebooks visible, {len(m_nb)} tracked")

        for ref, k in sorted(kernels.items()):
            prev = m_nb.get(ref)
            changed = prev is None or prev.get("lastRunTime") != k.get("lastRunTime")
            if not changed:
                continue
            (nb_new if prev is None else nb_upd).append(ref)
            if a.dry_run:
                continue
            dest = nb_dir / safe_name(ref)
            dest.mkdir(parents=True, exist_ok=True)
            rc, o, e = kaggle(["kernels", "pull", ref, "-p", str(dest)])
            if rc == 0:
                m_nb[ref] = {
                    "title": k.get("title"),
                    "author": k.get("author"),
                    "votes": k.get("totalVotes"),
                    "lastRunTime": k.get("lastRunTime"),
                    "path": str(dest),
                }
            else:
                errors.append(f"kernels pull {ref}: {e.strip()[:160]}")

        # ---- kernel comments (official CLI, with count verification) ----
        #
        # Freshness is keyed off the notebook's own comment count, NOT its
        # lastRunTime: the two move independently, so a new comment on an
        # untouched notebook must still be picked up. That costs one cheap
        # `topics list` call per notebook per run; the expensive `topics show`
        # only runs when the count actually moved.
        if not a.skip_comments and not a.dry_run:
            for ref in sorted(kernels):
                prev = m_kc.get(ref)
                topics_l, err = list_kernel_topics(ref)
                if topics_l is None:
                    errors.append(f"kernel topics list {ref}: {err}")
                    continue
                declared = sum(int(t.get("commentCount") or 0) for t in topics_l)
                if (
                    prev is not None
                    and prev.get("commentCount") == declared
                    and prev.get("threads") == len(topics_l)
                    and not a.full
                ):
                    continue
                rec, err = fetch_kernel_comments(
                    ref, kc_dir / f"{safe_name(ref)}.json", topics_l
                )
                if rec is None:
                    errors.append(f"kernel comments {ref}: {err}")
                    continue
                if rec["commentsFetched"] < rec["commentCount"]:
                    warnings.append(
                        f"kernel {ref}: fetched {rec['commentsFetched']} of "
                        f"{rec['commentCount']} comments"
                    )
                m_kc[ref] = rec
                kc_changed.append(ref)
                time.sleep(1.0)

    # ---- writeups: discover via CLI corpus, fetch bodies via Jina ----
    wu_new, wu_changed = [], []
    if not a.skip_writeups:
        discovered = discover_writeups(disc_dir)
        print(
            f"  {len(discovered)} writeup URLs referenced in the discussion corpus, "
            f"{len(m_wu)} tracked"
        )
        stale_before = today - timedelta(days=a.writeup_refresh_days)
        for key, url in sorted(discovered.items()):
            prev = m_wu.get(key)
            if prev is None:
                wu_new.append(key)
            else:
                if prev.get("gone") and not a.full:
                    continue  # deleted upstream; nothing to re-fetch
                try:
                    last = date.fromisoformat((prev.get("fetched") or "")[:10])
                except ValueError:
                    last = date.min
                if last > stale_before and not a.full:
                    continue
            if a.dry_run:
                continue
            dest = wu_dir / f"{safe_name(key)}.md"
            body, err = fetch_writeup(url, dest, jina_key)
            if err == "GONE":
                # Deleted upstream. Terminal state: record it once so the daily
                # job stops re-reporting it, and keep any body we fetched before.
                m_wu.setdefault(key, {"url": url})["gone"] = today.isoformat()
                wu_gone.append(key)
                continue
            if body is None:
                # Detection already succeeded and is recorded; only the body is
                # missing, and it will be retried on the next run.
                errors.append(f"writeup {key}: {err}")
                m_wu.setdefault(key, {"url": url})["lastError"] = err
                continue
            digest = sha(body)
            if prev and prev.get("sha") and prev["sha"] != digest:
                wu_changed.append(key)
            # Full replace, which is what clears any previous lastError/gone
            # marker: a writeup that fetched cleanly is no longer in either state.
            m_wu[key] = {
                "url": url,
                "sha": digest,
                "bytes": len(body),
                "fetched": today.isoformat(),
                "path": str(dest),
            }
            time.sleep(JINA_SLEEP)

    if not a.dry_run:
        manifest["errors"] = errors
        manifest["warnings"] = warnings
        manifest["lastRun"] = today.isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # ---- summary (parsed by the daily job for the PR body) ----
    print(f"\n=== {a.comp} ===")
    print(f"topics:     {len(tp_new)} new, {len(tp_upd)} updated (tracked {len(m_tp)})")
    print(f"notebooks:  {len(nb_new)} new, {len(nb_upd)} updated (tracked {len(m_nb)})")
    print(
        f"comments:   {len(kc_changed)} notebooks with new/changed comments "
        f"(tracked {len(m_kc)})"
    )
    print(
        f"writeups:   {len(wu_new)} new, {len(wu_changed)} edited (tracked {len(m_wu)})"
    )
    if tp_new:
        print("  new topics:", ", ".join(tp_new[:15]))
    if wu_new:
        print("  new writeups:", ", ".join(wu_new[:10]))
    if wu_changed:
        print("  EDITED writeups:", ", ".join(wu_changed[:10]))
    if wu_gone:
        print("  deleted upstream (404):", ", ".join(wu_gone[:10]))
    if warnings:
        print(f"\n! {len(warnings)} count mismatches (possible silent under-fetch):")
        for w in warnings[:10]:
            print(f"    {w}")
    if errors:
        print(f"\n! {len(errors)} errors:")
        for e in errors[:10]:
            print(f"    {e}")
    if a.dry_run:
        print("(dry-run: nothing fetched)")
    # Non-zero only on hard errors; count mismatches are surfaced, not fatal.
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
