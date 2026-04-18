"""
Kaggle Competition Discussion Scraper

Hybrid approach:
- Topic list: requests + Kaggle internal API (fast)
- Topic details: Playwright page visits with response interception
  (required because Kaggle validates browser context for this endpoint)

Usage:
    uv run python scripts/fetch_discussions.py                    # Full fetch
    uv run python scripts/fetch_discussions.py --topics-only      # List only
    uv run python scripts/fetch_discussions.py --resume --delay 1  # Resume incomplete
    uv run python scripts/fetch_discussions.py --limit 10          # First 10 details

Requirements:
    uv pip install playwright requests
    uv run playwright install chromium
"""

import asyncio
import argparse
import json
import time
from pathlib import Path

import requests
from playwright.async_api import async_playwright


DEFAULT_COMPETITION = "your-competition-slug"  # override via --competition / -c
DEFAULT_OUTPUT_DIR = "docs/discussions"
API_BASE = "https://www.kaggle.com/api/i/discussions.DiscussionsService"


# ---------------------------------------------------------------------------
# Step 1 & 2: Session cookies + topic list via requests (fast)
# ---------------------------------------------------------------------------

async def get_session_cookies_and_forum_id(competition_slug: str) -> tuple[dict, int | None]:
    """Use Playwright once to get cookies and forum ID."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        forum_id = None

        async def capture(response):
            nonlocal forum_id
            if "GetForum" in response.url and "discussions" in response.url.lower():
                try:
                    body = await response.json()
                    forum_id = body.get("forum", {}).get("id")
                except Exception:
                    pass

        page.on("response", capture)
        await page.goto(
            f"https://www.kaggle.com/competitions/{competition_slug}/discussion",
            wait_until="networkidle", timeout=30000,
        )
        await page.wait_for_timeout(2000)

        cookies = {c["name"]: c["value"] for c in await ctx.cookies()}
        await browser.close()
        return cookies, forum_id


def fetch_all_topics(cookies: dict, forum_id: int) -> list[dict]:
    """Fetch all topics via requests + internal API."""
    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v)
    headers = {
        "Content-Type": "application/json",
        "X-XSRF-TOKEN": cookies.get("XSRF-TOKEN", ""),
    }

    all_topics = []
    page_num = 1

    while True:
        payload = {
            "forumId": forum_id,
            "page": page_num,
            "category": "TOPIC_LIST_CATEGORY_ALL",
            "group": "TOPIC_LIST_GROUP_ALL",
            "customGroupingIds": [],
            "author": "TOPIC_LIST_AUTHOR_UNSPECIFIED",
            "myActivity": "TOPIC_LIST_MY_ACTIVITY_UNSPECIFIED",
            "recency": "TOPIC_LIST_RECENCY_UNSPECIFIED",
            "filterCategoryIds": [],
            "searchQuery": "",
            "sortBy": "TOPIC_LIST_SORT_BY_UNSPECIFIED",
        }

        resp = session.post(f"{API_BASE}/GetTopicListByForumId", json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"  Error: {resp.status_code} {resp.text[:300]}")
            break

        data = resp.json()
        topics = data.get("topics", [])
        total = data.get("count", 0)

        if not topics:
            break

        all_topics.extend(topics)
        print(f"  Page {page_num}: {len(all_topics)}/{total} topics")

        if len(all_topics) >= total:
            break

        page_num += 1
        time.sleep(1.0)

    return all_topics


# ---------------------------------------------------------------------------
# Step 3: Topic details via Playwright (browser context required)
# ---------------------------------------------------------------------------

async def fetch_topic_details_batch(
    competition_slug: str,
    topic_ids: list[int],
    delay: float = 1.0,
    batch_size: int = 1,
) -> dict[str, dict]:
    """Fetch topic details by visiting each page in Playwright."""
    results = {}

    # Block external third-party requests and throttle Kaggle internal APIs.
    # The SPA fires ~17 API calls per page load; throttling spreads them out.
    BLOCK_EXTERNAL = [
        "google-analytics.com",
        "googletagmanager.com",
        "accounts.google.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "apis.google.com",
        "firebaseio.com",
        "typekit.net",
        ".png",
        ".jpg",
        ".svg",
        ".woff",
    ]
    # Delay per internal API call (seconds). With ~17 calls/page,
    # 0.5s = ~8.5s of throttled API time per page.
    API_THROTTLE = 0.5

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()

        block_external = BLOCK_EXTERNAL
        api_throttle = API_THROTTLE

        async def route_handler(route):
            url = route.request.url
            if any(pat in url for pat in block_external):
                await route.abort()
            elif "/api/i/" in url:
                await asyncio.sleep(api_throttle)
                await route.continue_()
            else:
                await route.continue_()

        for i, tid in enumerate(topic_ids):
            page = await ctx.new_page()
            captured = {}

            await page.route("**/*", route_handler)

            async def make_handler(_captured=captured):
                async def handler(response):
                    if "GetForumTopicById" in response.url:
                        try:
                            _captured["data"] = await response.json()
                        except Exception:
                            pass
                return handler

            page.on("response", await make_handler())

            url = f"https://www.kaggle.com/competitions/{competition_slug}/discussion/{tid}"
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(1500)
            except Exception as e:
                print(f"    Warning on {tid}: {e}")

            ft = captured.get("data", {}).get("forumTopic", {})
            n_comments = len(ft.get("comments", []))
            title = ft.get("title", "")[:60]
            print(f"  [{i+1}/{len(topic_ids)}] {title} ({n_comments} comments)")

            results[str(tid)] = ft
            await page.close()

            # Periodic save every 50 topics
            if (i + 1) % 50 == 0:
                print(f"    [checkpoint: {len(results)} topics saved]")

            await asyncio.sleep(delay)

        await browser.close()

    return results


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def flatten_comments(comments: list[dict], depth: int = 0) -> list[dict]:
    """Flatten nested comment replies into a flat list with depth info."""
    result = []
    for c in comments:
        c_flat = {**c, "_depth": depth}
        c_flat.pop("replies", None)
        result.append(c_flat)
        for reply in c.get("replies", []):
            result.extend(flatten_comments([reply], depth + 1))
    return result


def format_discussion_markdown(topic: dict, meta: dict | None = None) -> str:
    """Convert a topic with comments to readable markdown.

    Args:
        topic: Topic detail from GetForumTopicById (comments, author, etc.)
        meta: Topic metadata from topic list (title, votes, postDate, etc.)
    """
    meta = meta or {}
    lines = []
    title = meta.get("title") or topic.get("title", "Untitled")
    author = topic.get("authorUserDisplayName") or meta.get("authorUser", {}).get("displayName", "Unknown")
    date = meta.get("postDate") or topic.get("dateCreated", "")
    votes = meta.get("votes", 0) or topic.get("voteCount", 0)
    topic_id = meta.get("id") or topic.get("id", "")
    topic_url = meta.get("topicUrl", "")

    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Author:** {author} | **Date:** {date} | **Votes:** {votes} | **ID:** {topic_id}")
    if topic_url:
        lines.append(f"**URL:** https://www.kaggle.com{topic_url}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # The first comment in the detail is often the topic body
    raw_comments = topic.get("comments", [])
    all_comments = flatten_comments(raw_comments)

    if all_comments:
        lines.append(f"## Discussion ({len(all_comments)} messages)")
        lines.append("")
        for c in all_comments:
            c_author = c.get("authorDisplayName", "Unknown")
            c_date = c.get("postDate", "")
            c_content = c.get("content") or c.get("rawMarkdown", "(no content)")
            c_votes = c.get("voteCount", 0)
            indent = ">" * c.get("_depth", 0)
            prefix = f"{indent} " if indent else ""

            lines.append(f"### {prefix}{c_author} ({c_date}) [votes: {c_votes}]")
            lines.append("")
            if indent:
                lines.append(f"{prefix}{c_content}")
            else:
                lines.append(c_content)
            lines.append("")
    else:
        lines.append("(no comments)")
        lines.append("")

    return "\n".join(lines)


def save_outputs(
    all_details: dict, topic_meta: dict[str, dict],
    output_dir: Path, competition: str,
):
    details_path = output_dir / "discussions_full.json"
    with open(details_path, "w") as f:
        json.dump(
            {
                "competition": competition,
                "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "topics": all_details,
            },
            f, indent=2, ensure_ascii=False,
        )
    print(f"  Saved JSON to {details_path}")

    md_dir = output_dir / "markdown"
    md_dir.mkdir(exist_ok=True)

    index_lines = [
        f"# {competition} Discussions\n",
        f"Fetched: {time.strftime('%Y-%m-%d %H:%M UTC')}\n",
        f"Total: {len(all_details)} topics\n\n",
    ]

    for tid, detail in all_details.items():
        meta = topic_meta.get(str(tid), {})
        title = meta.get("title") or detail.get("title", "Untitled")
        all_comments = flatten_comments(detail.get("comments", []))
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80].strip()
        if not safe:
            safe = "Untitled"
        md_path = md_dir / f"{tid}_{safe}.md"
        with open(md_path, "w") as f:
            f.write(format_discussion_markdown(detail, meta))
        index_lines.append(f"- [{title}](markdown/{md_path.name}) ({len(all_comments)} messages)")

    with open(output_dir / "INDEX.md", "w") as f:
        f.write("\n".join(index_lines))
    print(f"  Saved markdown to {md_dir}/")


# ---------------------------------------------------------------------------
# Incremental update
# ---------------------------------------------------------------------------

def _find_updated_topics(
    all_topics: list[dict], existing: dict[str, dict], prev_fetched_at: str,
) -> list[dict]:
    """Find topics that are new or have been updated since prev_fetched_at.

    A topic needs re-fetching if:
    1. It doesn't exist in the previous data (new topic), OR
    2. Its lastCommentPostDate is after prev_fetched_at (has new comments)
    """
    new_topics = []
    updated_topics = []

    for topic in all_topics:
        tid = str(topic["id"])
        if tid not in existing:
            new_topics.append(topic)
            continue

        last_comment = topic.get("lastCommentPostDate", "")
        if last_comment and last_comment > prev_fetched_at:
            updated_topics.append(topic)

    if new_topics:
        print(f"  New topics: {len(new_topics)}")
    if updated_topics:
        print(f"  Updated topics (new comments): {len(updated_topics)}")
    if not new_topics and not updated_topics:
        print("  No changes since last fetch.")

    return new_topics + updated_topics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch Kaggle competition discussions")
    parser.add_argument("--competition", "-c", default=DEFAULT_COMPETITION)
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--topics-only", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limit topics (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Skip already-fetched topics")
    parser.add_argument("--update", action="store_true",
                        help="Incremental update: only fetch new/updated topics since last run")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between page visits (s)")
    args = parser.parse_args()

    if args.competition == "your-competition-slug":
        parser.error(
            "competition slug is not set. Pass --competition <slug> "
            "or edit DEFAULT_COMPETITION at the top of this script."
        )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    topic_list_path = output_dir / "topic_list.json"
    details_path = output_dir / "discussions_full.json"

    print(f"Fetching discussions for: {args.competition}")
    start = time.time()

    # Step 1: Cookies + forum ID
    print("\n[Step 1] Getting session via Playwright...")
    cookies, forum_id = asyncio.run(get_session_cookies_and_forum_id(args.competition))
    print(f"  forum_id={forum_id}")

    if not forum_id:
        print("  ERROR: Could not get forum ID")
        return

    # Step 2: Topic list via requests
    print("\n[Step 2] Fetching topic list...")
    all_topics = fetch_all_topics(cookies, forum_id)
    print(f"  Total: {len(all_topics)} topics")

    # Fallback to previous data if fetch failed
    if not all_topics and args.resume:
        if topic_list_path.exists():
            with open(topic_list_path) as f:
                all_topics = json.load(f).get("topics", [])
        if not all_topics and details_path.exists():
            with open(details_path) as f:
                for tid, d in json.load(f).get("topics", {}).items():
                    all_topics.append({"id": int(tid), "title": d.get("title", "")})
        if all_topics:
            print(f"  Loaded {len(all_topics)} from previous run")

    if all_topics:
        with open(topic_list_path, "w") as f:
            json.dump({
                "competition": args.competition, "forumId": forum_id,
                "totalTopics": len(all_topics),
                "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "topics": all_topics,
            }, f, indent=2, ensure_ascii=False)

    if args.topics_only:
        return

    # Load existing details
    existing = {}
    prev_fetched_at = None
    if (args.resume or args.update) and details_path.exists():
        with open(details_path) as f:
            prev_data = json.load(f)
        existing = prev_data.get("topics", {})
        prev_fetched_at = prev_data.get("fetchedAt")
        if args.resume:
            # Keep only topics that have comments (re-fetch empty ones)
            existing = {
                k: v for k, v in existing.items()
                if len(v.get("comments", [])) > 0
            }
            print(f"  Resuming: {len(existing)} topics with comments cached")
        elif args.update:
            print(f"  Previous fetch: {prev_fetched_at} ({len(existing)} topics)")

    # Determine which topics need fetching
    targets = all_topics
    if args.limit > 0:
        targets = all_topics[:args.limit]

    if args.update and prev_fetched_at:
        need_fetch = _find_updated_topics(targets, existing, prev_fetched_at)
    else:
        need_fetch = [t for t in targets if str(t["id"]) not in existing]

    print(f"\n[Step 3] Fetching {len(need_fetch)} topic details via Playwright (delay={args.delay}s)...")

    if need_fetch:
        new_details = asyncio.run(
            fetch_topic_details_batch(
                args.competition,
                [t["id"] for t in need_fetch],
                delay=args.delay,
            )
        )
        # Merge
        all_details = {**existing, **new_details}
    else:
        all_details = existing
        print("  All topics already cached.")

    # Build topic metadata lookup from topic list
    topic_meta = {str(t["id"]): t for t in all_topics}

    # Save
    save_outputs(all_details, topic_meta, output_dir, args.competition)

    elapsed = time.time() - start
    total_comments = sum(
        len(flatten_comments(d.get("comments", []))) for d in all_details.values()
    )
    print(f"\nDone in {elapsed:.0f}s — {len(all_details)} topics, {total_comments} comments")


if __name__ == "__main__":
    main()

