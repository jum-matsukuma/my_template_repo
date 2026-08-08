#!/usr/bin/env python3
"""Build a human-readable Japanese layer on top of the fetched research corpus.

`kaggle_research.py` produces the corpus **agents** work from: discussion JSON,
writeup markdown, notebook source, a manifest. This tool produces the corpus
**humans** read: full Japanese translations, with the original figures, and the
reply thread attached to the end of the body it belongs to.

The two corpora are deliberately kept apart, and the split is the point:

    research/rendered/     English.  Agent-facing. The canonical text.
    research/assets/       Figures.  Shared by both (binary, language-neutral).
    docs/<ja-dir>/         Japanese. HUMAN-FACING ONLY. Agents must not read it.

A translation is a lossy derivative. If an agent cites it, every downstream
decision inherits a translator's paraphrase instead of what the author wrote --
and nothing in the chain announces that it happened. So `.claude/settings.json`
puts the Japanese side behind a `permissions.ask` rule, every generated file
carries a machine-greppable HUMAN-ONLY marker, and this script re-asserts that
marker on every `index` run.

What the `ask` rule gates is an agent deciding *by itself* to source an answer
from a translation -- not a human asking it to read one, which is a legitimate
request the user can simply approve. An unattended run has no approver and is
refused outright, which is the case that actually needed closing.

Pipeline
--------
    prep     render selected topics/writeups to markdown, localize figures,
             append the comment thread, record a source sha   [deterministic]
    pending  list what has no up-to-date translation           [deterministic]
    -------- the translating agent runs here, one document at a time ---------
    index    build the Japanese README, enforce HUMAN-ONLY markers
    html     export a self-contained browsable HTML tree

Why a renderer is needed at all: `competitions topics show` returns the reply
thread but **not the topic body** (measured -- the JSON payload carries only
id/title/authorName/commentCount/votes/postDate), and the plain-text form
flattens tables and drops figures entirely. So the body comes from the
r.jina.ai reader as markdown, and the replies come from the official CLI. Two
sources, one document.

Usage
-----
    research_ja.py prep    --comp <slug> [--out research] [--docs docs/research-ja]
    research_ja.py pending [--out research] [--docs docs/research-ja] [--porcelain]
    research_ja.py index   --comp <slug> [--out research] [--docs docs/research-ja]
    research_ja.py html    --dest ~/Downloads/research-ja [--docs docs/research-ja]
"""

from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

JINA = "https://r.jina.ai/"
JINA_SLEEP = 6.0
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# Every file under the Japanese docs directory starts with this. It exists so a
# human skimming the file knows it is a derivative, and so an agent that reaches
# the text through some path the ask rule does not cover (a pasted excerpt, a
# web view of the repo) is told, in the text itself, to go read the original.
HUMAN_ONLY_MARK = "<!-- HUMAN-ONLY-TRANSLATION"

# Titles that mark a thread worth translating even when it has few votes. A
# solution writeup posted an hour before the deadline has no votes yet and is
# still the most valuable thread in the competition.
SOLUTION_RE = re.compile(
    r"\b(\d+(?:st|nd|rd|th)\s+place|solution|write[\s-]?up|approach|our\s+method"
    r"|what\s+worked|lessons?\s+learned|gold|silver|prize)\b",
    re.I,
)

IMG_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"<svg", b"<?xml", b"BM")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")

# Kaggle's own page furniture: medals, avatars, the site logo. Never content.
CHROME_URL_RE = re.compile(
    r"kaggle\.com/static/|/images/medals/|gravatar\.com/"
    r"|/competitions/\d+/images/header"
)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def slug(s: str, n: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:n] or "untitled"


def rank_of(title: str):
    """Private-LB rank if the title advertises one, else None."""
    m = re.search(r"(\d[\d,]*)\s*(?:st|nd|rd|th)\b", title or "", re.I)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.match(r"^\s*#?\s*(\d+)\b", title or "")
    return int(m.group(1)) if m else None


def curl(url: str, out: Path | None = None, timeout: int = 120, headers=()):
    cmd = ["curl", "-sSL", "--max-time", str(timeout), "-A", UA]
    for h in headers:
        cmd += ["-H", h]
    if out:
        cmd += ["-o", str(out)]
    cmd.append(url)
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=(out is None), timeout=timeout + 30
        )
    except subprocess.TimeoutExpired:
        return 124, ""
    return p.returncode, (p.stdout if out is None else "")


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------------
# markdown: figure extraction with balanced-paren URLs
# --------------------------------------------------------------------------
def find_images(text: str):
    """Yield (whole_match, alt, url) for every markdown image.

    Written by hand rather than with `!\\[[^\\]]*\\]\\(([^)]+)\\)` because Kaggle
    serves filenames containing parentheses (`.../image (4).png`). The naive
    pattern truncates at the first `)`, the truncated URL 404s, and the JSON
    error page gets saved with a .png extension -- a failure that looks like a
    successful download until someone opens the file.
    """
    out = []
    for m in re.finditer(r"!\[([^\]]*)\]\(", text):
        i = m.end()
        depth, j = 1, m.end()
        while j < len(text):
            c = text[j]
            if c == "\n":
                break
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0 or j >= len(text) or text[j] != ")":
            continue
        url = text[i:j].strip()
        if url.startswith("http"):
            out.append((text[m.start() : j + 1], m.group(1), url))
    return out


def is_image(p: Path) -> bool:
    if not p.exists() or p.stat().st_size < 200:
        return False
    head = p.open("rb").read(16)
    return head.startswith(IMG_MAGIC) or b"webp" in head.lower()


def ext_of(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    e = os.path.splitext(path)[1].lower()
    return e if e in IMG_EXTS else ".png"


def localize_images(doc: str, assets_dir: Path, rel_prefix: str):
    """Download every figure and rewrite its URL to a repo-relative path.

    Filenames are derived from a hash of the source URL, not from a counter.
    A counter renumbers everything below an inserted figure when the author
    edits their post, which silently repoints the figures of any translation
    written before the edit. A URL hash never moves.
    """
    found = [f for f in find_images(doc) if not CHROME_URL_RE.search(f[2])]
    urls = list(dict.fromkeys(f[2] for f in found))
    records, missing = [], 0
    if urls:
        assets_dir.mkdir(parents=True, exist_ok=True)
    for u in urls:
        name = f"img-{hashlib.sha256(u.encode()).hexdigest()[:10]}{ext_of(u)}"
        fp = assets_dir / name
        if not is_image(fp):
            curl(u, fp)
        ok = is_image(fp)
        if not ok:
            fp.unlink(missing_ok=True)
            missing += 1
        records.append({"url": u, "file": f"{rel_prefix}/{name}" if ok else None})

    # Drop figures this document no longer references. Without this an image
    # that the author removed -- or that turned out to be page furniture -- stays
    # committed forever, and the daily diff keeps implying it is still in use.
    if assets_dir.is_dir():
        keep = {Path(r["file"]).name for r in records if r["file"]}
        for stale in assets_dir.iterdir():
            if stale.is_file() and stale.name not in keep:
                stale.unlink()
        if not any(assets_dir.iterdir()):
            assets_dir.rmdir()

    by_url = {r["url"]: r for r in records}
    for whole, alt, u in found:
        rec = by_url.get(u)
        if rec and rec["file"]:
            doc = doc.replace(whole, f"![{alt or 'figure'}]({rec['file']})")
    # Page furniture that survived: drop the reference rather than leave a
    # dead external link in a document meant to be readable offline.
    doc = re.sub(r"!\[[^\]]*\]\((?:[^()\n]|\([^()\n]*\))*\)", _drop_chrome, doc)
    return doc, records, missing


def _drop_chrome(m):
    return "" if CHROME_URL_RE.search(m.group(0)) else m.group(0)


# --------------------------------------------------------------------------
# jina reader -> clean markdown body
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def has_post(raw: str, title: str | None) -> bool:
    """Did this render actually capture the post, or just the page around it?

    Measured failure mode: the reader intermittently returns the competition
    shell -- cookie banner, org line, competition banner, tab strip -- with the
    discussion body never hydrated. It is ~1.5KB, contains "URL Source:", and so
    passes every structural check, which is how a byte-size threshold lets a
    bodyless page through. Its giveaway is the `Title:` line, which names the
    competition rather than the thread. So the topic title is the check.
    """
    if not title:
        return True
    t = _norm(title)[:40]
    return bool(t) and t in _norm(raw)


def jina_fetch(url: str, api_key: str | None, attempts: int = 3, title=None):
    headers = ["x-no-cache: true", "x-timeout: 30"]
    if api_key:
        headers.append(f"Authorization: Bearer {api_key}")
    last = "unknown"
    for _ in range(attempts):
        rc, body = curl(f"{JINA}{url}", timeout=150, headers=headers)
        # The reader answers 200 even when Kaggle served a 404, putting the real
        # status in the body. Without this check a deleted thread is stored as a
        # ~400 byte cookie-banner stub that looks like a successful fetch.
        if "returned error 404" in body or "returned error 403" in body:
            return None, "GONE"
        if rc == 0 and len(body) > 500 and "URL Source:" in body:
            if has_post(body, title):
                return body, None
            last = f"reader returned the page shell without the post ({len(body)}B)"
        else:
            last = f"short/invalid response ({len(body)}B, rc={rc})"
        time.sleep(15)
    return None, last


# The reader sometimes extracts just the post (the readability path succeeds) and
# sometimes hands back the whole page shell: site nav, the competition banner,
# the byline, AND the rendered reply thread. Both shapes have to be handled, and
# the second one is the dangerous one -- its replies are the same replies the
# Kaggle CLI gives us, so leaving them in produces a document that states every
# reply twice and costs twice the tokens to translate.

# The topic byline, which is the last thing before the post body: a vote count,
# the overflow-menu glyph, then the post title as an h3.
BODY_START_RE = re.compile(
    r"\barrow_drop_up\s+[\d,]+\s*\n+more_vert\s*\n+(?:###\s+.*\n)?"
)

# The competition tab strip (Overview/Data/Code/.../Leaderboard rendered as one
# run of links). Everything above it is the site header and the competition
# banner; the post starts below. Present in some renders and not others, which
# is why both anchors are tried in order.
TAB_BAR_RE = re.compile(r"^.*\]\([^)]*/overview\).*\]\([^)]*/leaderboard\).*$", re.M)

# Where the page stops being the post and starts being the reply thread. The CLI
# is the authority on replies (it reports 11 where this page renders 9), so
# everything from here down is dropped and re-added from JSON.
BODY_END_RE = re.compile(
    r"\n(?:Please \[sign in\]\([^)]*\) to reply to this topic\.|"
    r"##\s+\d[\d,]*\s+Comments?\s*$|"
    r"comment\s*$)",
    re.M,
)


def clean_body(raw: str) -> str:
    i = raw.find("Markdown Content:")
    if i >= 0:
        raw = raw[i + len("Markdown Content:") :]
    raw = re.sub(
        r"Kaggle uses cookies from Google.*?OK, Got it\.\s*", "", raw, flags=re.S
    )
    m = TAB_BAR_RE.search(raw)
    if m:
        raw = raw[m.end() :]
    m = BODY_START_RE.search(raw)
    if m:
        raw = raw[m.end() :]
    m = BODY_END_RE.search(raw)
    if m:
        raw = raw[: m.start()]
    return raw.strip()


# --------------------------------------------------------------------------
# comments: Kaggle CLI JSON (HTML bodies) -> markdown
# --------------------------------------------------------------------------
def html_to_md(s: str) -> str:
    s = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", s, flags=re.S)
    s = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", s, flags=re.S)
    s = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", s, flags=re.S)
    s = re.sub(r"<pre>(.*?)</pre>", r"\n```\n\1\n```\n", s, flags=re.S)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.S)
    s = re.sub(r"<li>(.*?)</li>", r"- \1", s, flags=re.S)
    s = re.sub(r"</?(ul|ol)>", "\n", s)
    s = re.sub(
        r"<blockquote>(.*?)</blockquote>",
        lambda m: (
            "\n" + "\n".join("> " + x for x in m.group(1).strip().splitlines()) + "\n"
        ),
        s,
        flags=re.S,
    )
    s = re.sub(r'<img [^>]*src="([^"]+)"[^>]*>', r"![](\1)", s)
    s = re.sub(r"</p>\s*<p>", "\n\n", s)
    s = re.sub(r"</?p>", "\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def comments_section(comments: list) -> str:
    """The reply thread, rendered as the tail of the document it belongs to.

    Attached to the body rather than filed separately on purpose: in practice
    the correction that matters ("this hyperparameter in the post is wrong") is
    three replies down, and a reader who has to open a second file to find it
    mostly does not.
    """
    if not comments:
        return ""
    out = [f"\n\n---\n\n## Comments ({len(comments)})\n"]
    for c in comments:
        who = c.get("authorName") or "?"
        when = str(c.get("postDate") or "")[:16]
        out.append(f"### {who} — {when} (votes {c.get('votes', 0)})\n")
        out.append(html_to_md(c.get("content") or "") + "\n")
    return "\n".join(out)


# --------------------------------------------------------------------------
# prep
# --------------------------------------------------------------------------
def select_topics(m_tp: dict, a) -> list[tuple[str, dict]]:
    picked = []
    forced = set(a.topic or [])
    for tid, rec in m_tp.items():
        title = rec.get("title") or ""
        votes = int(rec.get("votes") or 0)
        if (
            a.all_topics
            or tid in forced
            or SOLUTION_RE.search(title)
            or votes >= a.min_votes
        ):
            picked.append((tid, rec))
    picked.sort(
        key=lambda kv: (
            rank_of(kv[1].get("title") or "") or 10**9,
            -int(kv[1].get("votes") or 0),
        )
    )
    return picked


def prep(a) -> int:
    out, docs = Path(a.out), Path(a.docs)
    rendered, assets, raw_dir = out / "rendered", out / "assets", out / ".jina_raw"
    for d in (rendered, assets, raw_dir):
        d.mkdir(parents=True, exist_ok=True)

    research = load_json(out / "manifest.json", {}) or {}
    m_tp = research.get("topics") or {}
    m_wu = research.get("writeups") or {}
    if not m_tp and not m_wu:
        print(
            f"error: no fetched corpus in {out}/manifest.json -- run "
            "kaggle_research.py first",
            file=sys.stderr,
        )
        return 2

    state = load_json(out / "translate_manifest.json", {}) or {}
    docs_state = state.setdefault("docs", {})
    errors, warnings = [], []
    jina_key = a.jina_key or os.environ.get("JINA_API_KEY")

    targets = []
    for tid, rec in select_topics(m_tp, a):
        title = rec.get("title") or f"topic {tid}"
        targets.append(
            {
                "kind": "topic",
                "key": f"{tid}-{slug(title)}",
                "id": tid,
                "title": title,
                "author": rec.get("authorName"),
                "votes": int(rec.get("votes") or 0),
                "postDate": (rec.get("postDate") or "")[:10],
                "url": f"https://www.kaggle.com/competitions/{a.comp}/discussion/{tid}",
                "json": out / "discussions" / f"{tid}.json",
            }
        )
    if not a.skip_writeups:
        for key, rec in m_wu.items():
            if rec.get("gone") or not rec.get("path"):
                continue
            targets.append(
                {
                    "kind": "writeup",
                    "key": f"wu-{slug(key.replace('/', '-'))}",
                    "id": key,
                    "title": key,
                    "author": key.split("/")[0],
                    "votes": 0,
                    "postDate": (rec.get("fetched") or "")[:10],
                    "url": rec["url"],
                    "raw": Path(rec["path"]),
                }
            )

    print(f"{len(targets)} documents selected ({len(m_tp)} topics tracked)")
    fetched, deferred = 0, 0
    for t in targets:
        key = t["key"]
        prev = docs_state.get(key) or {}

        # --- body ---------------------------------------------------------
        if t["kind"] == "writeup":
            # Already rendered by kaggle_research.py; no network needed.
            raw = Path(t["raw"]).read_text(errors="replace")
        else:
            raw_path = raw_dir / f"{key}.md"
            fresh = raw_path.exists() and raw_path.stat().st_size > 500
            # Kaggle's comment count is the only cheap signal that a thread
            # moved; re-render when it has, or when we have nothing cached.
            # (A body edited without any new reply is therefore missed until
            # the next --full run -- the same tradeoff kaggle_research.py makes
            # for topics, and the reason --full exists.)
            cc = str((m_tp.get(t["id"]) or {}).get("commentCount"))
            cached = raw_path.read_text(errors="replace") if fresh else ""
            # A cached shell-only render must not be reused, or one bad night is
            # permanent: nothing downstream ever asks the reader again.
            if (
                fresh
                and not a.full
                and prev.get("commentCount") == cc
                and has_post(cached, t["title"])
            ):
                raw = cached
            else:
                # --limit bounds NETWORK work, so a run that hits the cap must
                # skip this document and keep going -- an early `break` here
                # would silently drop every writeup, which needs no network at
                # all, from a run that was only ever rate-limited on topics.
                if a.limit and fetched >= a.limit:
                    deferred += 1
                    continue
                body, err = jina_fetch(t["url"], jina_key, title=t["title"])
                fetched += 1
                if body is None:
                    if err == "GONE":
                        docs_state.setdefault(key, {})["gone"] = (
                            date.today().isoformat()
                        )
                        print(f"  gone   {key}")
                        continue
                    errors.append(f"{key}: {err}")
                    print(f"  FAIL   {key}: {err}", file=sys.stderr)
                    continue
                raw_path.write_text(body)
                raw = body
                time.sleep(JINA_SLEEP)

        body = clean_body(raw)

        # --- comments appended to the body they belong to -------------------
        comments = []
        if t["kind"] == "topic":
            data = load_json(t["json"], {}) or {}
            comments = data.get("comments") or []
            declared = (m_tp.get(t["id"]) or {}).get("commentCount")
            if declared is not None and len(comments) < int(declared or 0):
                warnings.append(
                    f"{key}: {len(comments)} of {declared} comments available"
                )

        provenance = (
            "Body rendered via r.jina.ai; replies via the official Kaggle CLI."
            if t["kind"] == "topic"
            else "Rendered via r.jina.ai. Kaggle writeups have no reply thread."
        )
        # A writeup has no reply surface at all, so "Comments: 0" would read as
        # "nobody replied" rather than "there is nowhere to reply".
        n_comments = f" / **Comments**: {len(comments)}" if t["kind"] == "topic" else ""
        header = (
            f"# {t['title']}\n\n"
            f"> **Author**: {t['author'] or '?'} / **Posted**: {t['postDate'] or '?'}"
            f" / **Votes**: {t['votes']}{n_comments}\n"
            f"> **Source**: {t['url']}\n"
            f"> {provenance}\n\n"
            f"---\n\n"
        )
        doc = header + body + comments_section(comments)

        # Figures live beside the English original and are referenced from both
        # sides with a relative path, so neither corpus owns the other's assets.
        doc, images, missing = localize_images(
            doc, assets / key, rel_prefix=f"../assets/{key}"
        )
        if missing:
            warnings.append(f"{key}: {missing} figures could not be downloaded")

        dest = rendered / f"{key}.md"
        dest.write_text(doc.rstrip() + "\n")
        digest = sha(doc)
        entry = {
            "kind": t["kind"],
            "id": t["id"],
            "title": t["title"],
            "author": t["author"],
            "votes": t["votes"],
            "postDate": t["postDate"],
            "url": t["url"],
            "commentCount": str((m_tp.get(t["id"]) or {}).get("commentCount")),
            "comments": len(comments),
            "src": str(dest),
            "srcSha": digest,
            "images": len([i for i in images if i["file"]]),
            "imagesMissing": missing,
        }
        # Carry the translation record across so a re-render does not forget
        # that a translation exists; `pending` compares the shas to decide.
        if prev.get("translated"):
            entry["translated"] = prev["translated"]
        docs_state[key] = entry
        if prev.get("srcSha") != digest:
            print(
                f"  {'new  ' if not prev else 'CHANGED'} {key}"
                f"  ({entry['images']} figs)"
            )

    state["errors"] = errors
    state["warnings"] = warnings
    state["lastRun"] = date.today().isoformat()
    (out / "translate_manifest.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False)
    )

    pend = pending_list(state, docs)
    print(f"\ntracking {len(docs_state)} documents; {len(pend)} await translation")
    if deferred:
        print(f"  {deferred} deferred by --limit {a.limit}; re-run to continue")
    for w in warnings[:10]:
        print(f"  ! {w}")
    for e in errors[:10]:
        print(f"  ! {e}")
    return 1 if errors else 0


# --------------------------------------------------------------------------
# pending
# --------------------------------------------------------------------------
def pending_list(state: dict, docs: Path) -> list[tuple[str, dict]]:
    out = []
    for key, rec in (state.get("docs") or {}).items():
        if rec.get("gone") or not rec.get("srcSha"):
            continue
        tr = rec.get("translated") or {}
        dest = docs / f"{key}.ja.md"
        if tr.get("srcSha") == rec["srcSha"] and dest.exists():
            continue
        out.append((key, rec))
    out.sort(
        key=lambda kv: (
            rank_of(kv[1].get("title") or "") or 10**9,
            -kv[1].get("votes", 0),
        )
    )
    return out


def pending(a) -> int:
    out, docs = Path(a.out), Path(a.docs)
    state = load_json(out / "translate_manifest.json", {}) or {}
    items = pending_list(state, docs)
    if a.limit:
        items = items[: a.limit]
    if a.porcelain:
        # key<TAB>english-source<TAB>japanese-destination -- consumed by translate.sh
        for key, rec in items:
            print(f"{key}\t{rec['src']}\t{docs / (key + '.ja.md')}")
        return 0
    if not items:
        print("nothing pending: every rendered document has a current translation")
        return 0
    print(f"{len(items)} document(s) awaiting translation:")
    for key, rec in items:
        why = "re-translate (source changed)" if rec.get("translated") else "new"
        print(f"  {key}  [{why}]  votes={rec.get('votes')} figs={rec.get('images')}")
    return 0


# --------------------------------------------------------------------------
# index
# --------------------------------------------------------------------------
def fix_asset_paths(path: Path, out: Path, docs: Path) -> bool:
    """Repoint figure links from source-relative to translation-relative.

    The rendered English lives one directory below `out`, so it refers to a
    figure as `../assets/<key>/<file>`. The translation lives under `docs`, from
    where the same figure is `../../research/assets/<key>/<file>`. Rather than
    ask the translating agent to recompute a relative path per document -- a
    step it will get right most of the time, which is the worst failure rate for
    something this mechanical -- the prompt tells it to copy image lines
    verbatim and the fix happens here. Idempotent: the rewritten prefix no
    longer matches the pattern.
    """
    rel = os.path.relpath(out / "assets", docs)
    text = path.read_text()
    fixed = text.replace("](../assets/", f"]({rel}/")
    if fixed == text:
        return False
    path.write_text(fixed)
    return True


def ensure_marker(path: Path, rec: dict, docs: Path) -> bool:
    """Guarantee the HUMAN-ONLY banner. Returns True if the file was modified.

    Enforced here rather than trusted to the translating agent: the marker is
    the thing that tells the next reader this text is a derivative, so it cannot
    depend on a model remembering to emit it.
    """
    text = path.read_text()
    if HUMAN_ONLY_MARK in text:
        return False
    src = (
        os.path.relpath(rec.get("src") or "", docs)
        if rec.get("src")
        else "research/rendered/"
    )
    origin = rec.get("src") or "research/rendered/"
    banner = (
        f"{HUMAN_ONLY_MARK}\n"
        f"     This file is a Japanese translation kept for human readers.\n"
        f"     Agents must cite the English original instead: {origin}\n"
        f"-->\n\n"
        f"> 🇯🇵 **人間向けの日本語訳です。** エージェントはこのファイルではなく"
        f"英語原文 [`{origin}`]({src}) を参照してください。\n\n"
    )
    path.write_text(banner + text.lstrip())
    return True


def index(a) -> int:
    out, docs = Path(a.out), Path(a.docs)
    docs.mkdir(parents=True, exist_ok=True)
    state = load_json(out / "translate_manifest.json", {}) or {}
    docs_state = state.get("docs") or {}

    rows, fixed, repathed = [], 0, 0
    for key, rec in docs_state.items():
        if rec.get("gone"):
            continue
        p = docs / f"{key}.ja.md"
        translated = p.exists()
        if translated:
            if fix_asset_paths(p, out, docs):
                repathed += 1
            if ensure_marker(p, rec, docs):
                fixed += 1
            tr = rec.get("translated") or {}
            stale = tr.get("srcSha") != rec.get("srcSha")
        else:
            stale = True
        rows.append((key, rec, translated, stale))

    rows.sort(
        key=lambda r: (rank_of(r[1].get("title") or "") or 10**9, -r[1].get("votes", 0))
    )

    comp = a.comp or "the competition"
    L = []
    L.append(f"# {comp} — 公開ディスカッション/解法 writeup の日本語訳")
    L.append("")
    L.append(f"{HUMAN_ONLY_MARK}")
    L.append("     Index of Japanese translations. Human-facing only.")
    L.append("     Agents: read the English originals under research/rendered/.")
    L.append("-->")
    L.append("")
    L.append("> 🇯🇵 **このディレクトリは人間の読者向けです。**")
    L.append(">")
    L.append(
        "> ここにあるのは英語原文の日本語訳（＝二次的な派生物）です。"
        "**エージェントは自分の判断ではここを参照しません。**"
    )
    L.append(
        "> エージェントが根拠にするのは英語原文の方 — `research/rendered/*.md` — です"
        "（ユーザーが明示的に指示した場合を除く）。"
    )
    L.append(
        "> 訳文を根拠に判断すると、著者が書いた内容ではなく訳者の解釈が"
        "下流のすべてに伝播し、しかもそれが起きたことは誰にも分かりません。"
    )
    L.append(
        "> この分離は `.claude/settings.json` の `permissions.ask` で機械的に"
        "一段挟んであります（エージェントが自分の判断で読もうとすると確認が入り、"
        "無人実行は拒否されます）。"
    )
    L.append("")
    L.append("## 方針")
    L.append("")
    L.append(
        "- **要約していません。** 節構成・表・数式・コードブロックを保ったまま全文訳。"
    )
    L.append(
        "- **図は原文から取得**して `research/assets/<key>/` に保存し、"
        "原文と同じ位置に掲載。"
    )
    L.append(
        "- **返信スレッドは本文末尾に「コメント欄」として連結**。訂正や追加情報は"
        "本文ではなく返信に書かれることが多く、別ファイルに分けると読まれません。"
    )
    L.append("- 各ファイル冒頭に著者・投稿日・votes・原文 URL を記載。")
    L.append("")
    L.append(
        "他者の著作物の翻訳です。引用・再配布の際は原文リンクと著者名を必ず併記し、"
        "Kaggle の規約と各投稿のライセンスに従ってください。"
    )
    L.append("")
    done = sum(1 for r in rows if r[2] and not r[3])
    L.append(f"## 一覧（{done} / {len(rows)} 訳出済み）")
    L.append("")
    L.append("| 順位 | タイトル | 著者 | votes | 図 | 状態 | 原文 |")
    L.append("| ---: | --- | --- | ---: | ---: | --- | --- |")
    for key, rec, translated, stale in rows:
        title = str(rec.get("title") or key)
        for ch in ("|", "[", "]"):
            title = title.replace(ch, "\\" + ch)
        rk = rank_of(rec.get("title") or "")
        cell = f"[{title}]({key}.ja.md)" if translated else title
        if translated and not stale:
            status = "訳出済み"
        elif translated:
            status = "⚠️ 原文更新 (再訳待ち)"
        else:
            status = "未訳"
        L.append(
            f"| {rk if rk is not None else '—'} | {cell} | {rec.get('author') or '—'} "
            f"| {rec.get('votes') or 0} | {rec.get('images') or '—'} | {status} "
            f"| [原文]({rec.get('url')}) |"
        )
    L.append("")
    L.append(
        "生成: `kaggle-template/scripts/research_ja.py index`"
        "（`.claude/ops/translate.sh` が日次実行）"
    )

    (docs / "README.md").write_text("\n".join(L) + "\n")
    print(
        f"index: {len(rows)} documents, {done} translated, "
        f"{fixed} marker(s) restored, {repathed} figure path(s) repointed"
    )
    return 0


# --------------------------------------------------------------------------
# mark-translated (called by the ops wrapper after a successful translation)
# --------------------------------------------------------------------------
def mark(a) -> int:
    out = Path(a.out)
    path = out / "translate_manifest.json"
    state = load_json(path, {}) or {}
    rec = (state.get("docs") or {}).get(a.key)
    if rec is None:
        print(f"mark: unknown key {a.key}", file=sys.stderr)
        return 1
    rec["translated"] = {"srcSha": rec.get("srcSha"), "at": date.today().isoformat()}
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"mark: {a.key} recorded as translated at sha {rec.get('srcSha')}")
    return 0


# --------------------------------------------------------------------------
# html export
# --------------------------------------------------------------------------
CSS = """
:root{--bg:#fff;--fg:#1b1f23;--muted:#57606a;--line:#d8dee4;--code:#f6f8fa;--acc:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;
--line:#30363d;--code:#161b22;--acc:#4493f8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.85 -apple-system,BlinkMacSystemFont,"Hiragino Sans",
"Noto Sans JP",sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:2.5rem 1.25rem 6rem}
a{color:var(--acc)}
h1{font-size:1.9rem;line-height:1.35;margin:2.2rem 0 1rem;
border-bottom:1px solid var(--line);
padding-bottom:.5rem}
h2{font-size:1.45rem;margin:2.4rem 0 .9rem;
border-bottom:1px solid var(--line);padding-bottom:.35rem}
h3{font-size:1.18rem;margin:2rem 0 .7rem}
h4,h5,h6{font-size:1.03rem;margin:1.6rem 0 .6rem}
p{margin:.9rem 0}
ul,ol{margin:.9rem 0;padding-left:1.6rem}
li{margin:.3rem 0}
blockquote{margin:1.1rem 0;padding:.2rem 0 .2rem 1rem;border-left:4px solid var(--line);
color:var(--muted)}
blockquote p{margin:.5rem 0}
code{background:var(--code);padding:.15em .38em;border-radius:5px;font-size:.88em;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--code);padding:1rem;border-radius:8px;overflow-x:auto;
border:1px solid var(--line)}
pre code{background:none;padding:0;font-size:.85rem;line-height:1.55}
.tw{overflow-x:auto;margin:1.2rem 0}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border:1px solid var(--line);padding:.5rem .7rem;text-align:left;
vertical-align:top}
th{background:var(--code);font-weight:600}
img{max-width:100%;height:auto;display:block;margin:1.2rem auto;
border:1px solid var(--line);
border-radius:6px;background:#fff}
hr{border:0;border-top:1px solid var(--line);margin:2.2rem 0}
.back{display:inline-block;margin-bottom:1.5rem;font-size:.92rem}
"""

# Escaped table/link punctuation is swapped for sentinels before parsing, so an
# escaped "|" cannot split a table cell and an escaped "[" cannot end a label.
ESC = {"|": "\x02", "[": "\x03", "]": "\x04"}
UNESC = {v: k for k, v in ESC.items()}


def _unescape(s):
    for k, v in UNESC.items():
        s = s.replace(k, v)
    return s


def inline(s):
    s = _html.escape(s, quote=False)
    ph, code_store = [], []

    def keep_code(m):
        code_store.append(m.group(1))
        return f"\x00{len(code_store) - 1}\x00"

    s = re.sub(r"`([^`]+)`", keep_code, s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)

    def keep_tag(m):
        ph.append(m.group(0))
        return f"\x01{len(ph) - 1}\x01"

    s = re.sub(r'<a href="[^"]*">.*?</a>|<img src="[^"]*"[^>]*>', keep_tag, s)
    s = re.sub(r"(?<!\w)(https?://[^\s<>()]+)", r'<a href="\1">\1</a>', s)
    for i, t in enumerate(ph):
        s = s.replace(f"\x01{i}\x01", t)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    for i, c in enumerate(code_store):
        s = s.replace(f"\x00{i}\x00", "<code>" + c + "</code>")
    return _unescape(s)


def md_to_html(md):
    for ch, sent in ESC.items():
        md = md.replace("\\" + ch, sent)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.startswith("```"):
            j, buf = i + 1, []
            while j < n and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(
                "<pre><code>"
                + _html.escape(_unescape("\n".join(buf)))
                + "</code></pre>"
            )
            i = j + 1
            continue
        if re.match(r"^\s*(\*\s*\*\s*\*|---+|\*\*\*+)\s*$", ln):
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lv = len(m.group(1))
            out.append(f"<h{lv}>{inline(m.group(2))}</h{lv}>")
            i += 1
            continue
        if (
            ln.lstrip().startswith("|")
            and i + 1 < n
            and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])
        ):

            def cells(r):
                r = r.strip().strip("|")
                return [c.strip() for c in r.split("|")]

            head, j, body = cells(ln), i + 2, []
            while j < n and lines[j].lstrip().startswith("|"):
                body.append(cells(lines[j]))
                j += 1
            t = ['<div class="tw"><table><thead><tr>']
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in body:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            i = j
            continue
        if ln.lstrip().startswith(">"):
            buf = []
            while i < n and (
                lines[i].lstrip().startswith(">")
                or (
                    buf
                    and lines[i].strip() == ""
                    and i + 1 < n
                    and lines[i + 1].lstrip().startswith(">")
                )
            ):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + md_to_html("\n".join(buf)) + "</blockquote>")
            continue
        if re.match(r"^\s*([*\-+]|\d+\.)\s+(.*)$", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s", ln))
            items, cur = [], None
            while i < n:
                mm = re.match(r"^\s*([*\-+]|\d+\.)\s+(.*)$", lines[i])
                if mm:
                    if cur is not None:
                        items.append(cur)
                    cur = [mm.group(2)]
                    i += 1
                elif (
                    cur is not None
                    and lines[i].strip()
                    and lines[i].startswith((" ", "\t"))
                ):
                    cur.append(lines[i].strip())
                    i += 1
                elif (
                    cur is not None
                    and lines[i].strip() == ""
                    and i + 1 < n
                    and re.match(r"^\s*([*\-+]|\d+\.)\s+", lines[i + 1])
                ):
                    i += 1
                else:
                    break
            if cur is not None:
                items.append(cur)
            tag = "ol" if ordered else "ul"
            out.append(
                f"<{tag}>"
                + "".join(f"<li>{inline(' '.join(x))}</li>" for x in items)
                + f"</{tag}>"
            )
            continue
        if ln.strip() == "":
            i += 1
            continue
        buf = []
        while (
            i < n
            and lines[i].strip()
            and not lines[i].startswith(("#", "```", "|", ">"))
            and not re.match(r"^\s*([*\-+]|\d+\.)\s+", lines[i])
            and not re.match(r"^\s*(\*\s*\*\s*\*|---+)\s*$", lines[i])
        ):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>" + inline(" ".join(buf)) + "</p>")
        else:
            i += 1
    return "\n".join(out)


def html(a) -> int:
    src, dest, out = Path(a.docs), Path(os.path.expanduser(a.dest)), Path(a.out)
    if not src.is_dir():
        print(f"error: {src} does not exist (nothing translated yet)", file=sys.stderr)
        return 2
    dest.mkdir(parents=True, exist_ok=True)

    # Figures live outside the docs tree (they are shared with the English
    # corpus), so the export copies them in and rewrites the relative paths.
    if (out / "assets").is_dir():
        if (dest / "assets").is_dir():
            shutil.rmtree(dest / "assets")
        shutil.copytree(out / "assets", dest / "assets")

    written = 0
    for f in sorted(src.glob("*.md")):
        md = f.read_text()
        md = md.replace("../../research/assets/", "assets/").replace(
            f"../../{out}/assets/", "assets/"
        )
        md = re.sub(r"\((?:\.\./)+[^)]*?/assets/", "(assets/", md)
        md = md.replace(".ja.md)", ".ja.html)").replace("(README.md)", "(index.html)")
        # Anything still pointing at a .md is a repo path (the HUMAN-ONLY
        # banner's link back to the English original). The export is a
        # standalone tree, so that link cannot resolve -- keep the text, drop
        # the href, rather than ship a page with a dead link in its banner.
        md = re.sub(r"\[([^\]]+)\]\([^)]*\.md\)", r"`\1`", md)
        title = next(
            (x.lstrip("# ").strip() for x in md.split("\n") if x.startswith("# ")),
            f.stem,
        )
        name = "index.html" if f.name == "README.md" else f.name.replace(".md", ".html")
        back = (
            ""
            if f.name == "README.md"
            else '<a class="back" href="index.html">&larr; 一覧に戻る</a>'
        )
        (dest / name).write_text(
            f'<!doctype html><html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{_html.escape(title)}</title><style>{CSS}</style></head>"
            f'<body><div class="wrap">{back}{md_to_html(md)}</div></body></html>'
        )
        written += 1

    # Fail loudly on a broken export: a page whose figures 404 looks fine until
    # someone scrolls, and by then nobody remembers which run produced it.
    broken = 0
    for p in dest.glob("*.html"):
        for ref in re.findall(r'(?:src|href)="((?!https?:|#)[^"]+)"', p.read_text()):
            if not (dest / urllib.parse.unquote(ref.split("#")[0])).exists():
                broken += 1
    print(
        f"wrote {written} page(s) to {dest}"
        + (f"  ! {broken} broken local refs" if broken else "")
    )
    return 1 if broken else 0


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument(
            "--out", default="research", help="kaggle_research.py output dir"
        )
        p.add_argument("--docs", default="docs/research-ja", help="Japanese docs dir")

    p = sub.add_parser(
        "prep", help="render selected documents to translatable markdown"
    )
    common(p)
    p.add_argument("--comp", required=True)
    p.add_argument(
        "--min-votes",
        type=int,
        default=20,
        help="translate discussion threads at or above this vote count",
    )
    p.add_argument(
        "--topic", action="append", help="force-include a topic id (repeatable)"
    )
    p.add_argument(
        "--all-topics", action="store_true", help="render every tracked topic"
    )
    p.add_argument("--skip-writeups", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="cap jina fetches this run")
    p.add_argument("--full", action="store_true", help="ignore caches and re-render")
    p.add_argument("--jina-key", default=None)
    p.set_defaults(fn=prep)

    p = sub.add_parser("pending", help="list documents with no current translation")
    common(p)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--porcelain", action="store_true", help="key<TAB>src<TAB>dest")
    p.set_defaults(fn=pending)

    p = sub.add_parser("index", help="rebuild the Japanese README and enforce markers")
    common(p)
    p.add_argument("--comp", default=None)
    p.set_defaults(fn=index)

    p = sub.add_parser(
        "mark", help="record a document as translated at its current sha"
    )
    common(p)
    p.add_argument("--key", required=True)
    p.set_defaults(fn=mark)

    p = sub.add_parser("html", help="export a browsable HTML tree")
    common(p)
    p.add_argument("--dest", required=True)
    p.set_defaults(fn=html)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
