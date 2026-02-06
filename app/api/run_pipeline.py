"""
ShopLens End-to-End Review Pipeline

Runs the full scraping pipeline for a product:
  1. Check product cache
  2. Search YouTube reviews
  3. Ingest YouTube reviews
  4. Search blog reviews
  5. Ingest blog reviews
  6. Generate reviews summary
  7. Find marketplace listings

Usage:
  python run_pipeline.py "Samsung Galaxy S25"
  python run_pipeline.py "iPhone 16 Pro" --youtube-limit 5 --blog-limit 3
  python run_pipeline.py "Pixel 9" --skip-marketplace
  python run_pipeline.py "MacBook Pro M4" --db-host localhost
"""

import argparse
import asyncio
import json
import sys
import time
import os

# ── ANSI colors ──────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Disable colors if not a TTY
if not sys.stdout.isatty():
    BOLD = DIM = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = RESET = ""


def header(step: int, total: int, title: str):
    print(f"\n{'─' * 70}")
    print(f"{BOLD}{CYAN}[Step {step}/{total}]{RESET} {BOLD}{title}{RESET}")
    print(f"{'─' * 70}")


def success(msg: str):
    print(f"  {GREEN}✓{RESET} {msg}")


def warning(msg: str):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def error(msg: str):
    print(f"  {RED}✗{RESET} {msg}")


def info(msg: str):
    print(f"  {DIM}{msg}{RESET}")


def elapsed(start: float) -> str:
    return f"{DIM}({time.time() - start:.1f}s){RESET}"


def print_json_compact(data, indent=4):
    """Print a dict with truncated long strings."""
    def truncate(obj, max_len=200):
        if isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + "..."
        if isinstance(obj, dict):
            return {k: truncate(v, max_len) for k, v in obj.items()}
        if isinstance(obj, list):
            return [truncate(v, max_len) for v in obj]
        return obj

    print(json.dumps(truncate(data), indent=indent, default=str))


# ── Pipeline ─────────────────────────────────────────────────────────────────

async def run_pipeline(
    product_name: str,
    youtube_limit: int = 3,
    blog_limit: int = 2,
    skip_marketplace: bool = False,
    db_host: str | None = None,
):
    """Run the full review scraping pipeline."""

    # ── 0. Setup ─────────────────────────────────────────────────────────────

    # Override DB host before importing session (engine is created at import time)
    if db_host:
        from app.core.config import settings as _settings
        original_url = _settings.DATABASE_URL
        import re as _re
        new_url = _re.sub(r"@[^:]+:", f"@{db_host}:", original_url)
        _settings.DATABASE_URL = new_url
        print(f"{DIM}DB host overridden: {new_url}{RESET}")

    from app.db.session import AsyncSessionLocal
    from app.functions.registry import execute_function
    import app.functions.review_tools  # noqa: F401 — triggers @register_function

    total_steps = 6 if skip_marketplace else 7
    pipeline_start = time.time()
    youtube_urls: list[str] = []
    blog_urls: list[str] = []
    ingested_reviews: list[dict] = []
    summary_data: dict = {}
    marketplace_data: dict = {}

    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  ShopLens Pipeline — {MAGENTA}{product_name}{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}")
    print(f"  YouTube limit: {youtube_limit} | Blog limit: {blog_limit} | Marketplace: {'skip' if skip_marketplace else 'yes'}")

    async with AsyncSessionLocal() as db:
        try:
            # ── Step 1: Check cache ──────────────────────────────────────────

            header(1, total_steps, "Checking product cache")
            t = time.time()

            result = await execute_function(db, "check_product_cache", {
                "product_name": product_name,
            })

            if result.get("error"):
                error(f"Cache check failed: {result['error']}")
            elif result.get("status") == "found":
                product = result.get("product", {})
                reviews = result.get("reviews", [])
                success(f"Found cached: {product.get('name', '?')} (id={product.get('id')}) with {len(reviews)} review(s) {elapsed(t)}")
                for r in reviews:
                    info(f"  • {r.get('reviewer_name', '?')} — {r.get('title', 'untitled')}")

                # Ask whether to re-scrape or use cache
                print(f"\n  {YELLOW}Product already has cached reviews.{RESET}")
                choice = input(f"  Re-scrape anyway? [y/N]: ").strip().lower()
                if choice != "y":
                    print(f"\n  {DIM}Skipping scraping, jumping to summary...{RESET}")
                    # Jump straight to summary (step 6)
                    header(total_steps - (0 if skip_marketplace else 1), total_steps, "Generating reviews summary")
                    t = time.time()
                    summary_data = await execute_function(db, "get_reviews_summary", {
                        "product_name": product_name,
                    })
                    if summary_data.get("error"):
                        error(f"Summary failed: {summary_data['error']} {elapsed(t)}")
                    else:
                        success(f"Summary generated {elapsed(t)}")
                    await db.commit()
                    _print_final_summary(product_name, ingested_reviews, summary_data, marketplace_data, pipeline_start, skip_marketplace)
                    return
            elif result.get("status") == "no_reviews":
                warning(f"Product exists but has no reviews — will scrape {elapsed(t)}")
            else:
                info(f"Not cached — starting fresh scrape {elapsed(t)}")

            # ── Step 2: Search YouTube ───────────────────────────────────────

            header(2, total_steps, "Searching YouTube reviews (Firecrawl)")
            t = time.time()

            yt_result = await execute_function(db, "search_youtube_reviews", {
                "product_name": product_name,
                "limit": youtube_limit,
            })

            if yt_result.get("error"):
                error(f"YouTube search failed: {yt_result['error']} {elapsed(t)}")
            elif yt_result.get("status") == "success":
                youtube_urls = yt_result.get("urls", [])
                videos = yt_result.get("videos", [])
                success(f"Found {len(youtube_urls)} YouTube video(s) {elapsed(t)}")
                for v in videos:
                    title = v.get("title", "")
                    url = v.get("url", "")
                    desc = v.get("description", "")
                    info(f"  • {title or url}")
                    info(f"    {DIM}{url}{RESET}")
                    if desc:
                        info(f"    {DIM}{desc[:100]}{RESET}")
            else:
                warning(f"No YouTube results: {yt_result.get('status')} {elapsed(t)}")

            # ── Step 3: Ingest YouTube reviews ───────────────────────────────

            if youtube_urls:
                header(3, total_steps, f"Ingesting {len(youtube_urls)} YouTube review(s)")
                for i, url in enumerate(youtube_urls, 1):
                    t = time.time()
                    print(f"\n  {BOLD}[{i}/{len(youtube_urls)}]{RESET} {url}")

                    ingest_result = await execute_function(db, "ingest_youtube_review", {
                        "video_url": url,
                        "product_name": product_name,
                    })

                    if ingest_result.get("error"):
                        error(f"Failed: {ingest_result['error']} {elapsed(t)}")
                    elif ingest_result.get("status") == "already_exists":
                        warning(f"Already ingested — skipped {elapsed(t)}")
                        ingested_reviews.append(ingest_result)
                    elif ingest_result.get("status") == "success":
                        success(f"Ingested: {ingest_result.get('title', '?')} by {ingest_result.get('reviewer_name', '?')} {elapsed(t)}")
                        info(f"  review_id={ingest_result.get('review_id')} product_id={ingest_result.get('product_id')}")
                        ingested_reviews.append(ingest_result)
                    else:
                        warning(f"Unexpected status: {ingest_result.get('status')} {elapsed(t)}")
            else:
                header(3, total_steps, "Ingesting YouTube reviews")
                warning("No YouTube URLs to ingest — skipping")

            # ── Step 4: Search blog reviews ──────────────────────────────────

            header(4, total_steps, "Searching blog reviews (Firecrawl)")
            t = time.time()

            blog_result = await execute_function(db, "search_blog_reviews", {
                "product_name": product_name,
                "limit": blog_limit,
            })

            if blog_result.get("error"):
                error(f"Blog search failed: {blog_result['error']} {elapsed(t)}")
            elif blog_result.get("status") == "success":
                blog_urls = blog_result.get("urls", [])
                articles = blog_result.get("articles", [])
                success(f"Found {len(blog_urls)} blog article(s) {elapsed(t)}")
                for a in articles:
                    title = a.get("title", "")
                    url = a.get("url", "")
                    desc = a.get("description", "")
                    info(f"  • {title or url}")
                    info(f"    {DIM}{url}{RESET}")
                    if desc:
                        info(f"    {DIM}{desc[:100]}{RESET}")
            else:
                warning(f"No blog results: {blog_result.get('status')} {elapsed(t)}")

            # ── Step 5: Ingest blog reviews ──────────────────────────────────

            if blog_urls:
                header(5, total_steps, f"Ingesting {len(blog_urls)} blog review(s)")
                for i, url in enumerate(blog_urls, 1):
                    t = time.time()
                    print(f"\n  {BOLD}[{i}/{len(blog_urls)}]{RESET} {url}")

                    ingest_result = await execute_function(db, "ingest_blog_review", {
                        "url": url,
                        "product_name": product_name,
                    })

                    if ingest_result.get("error"):
                        error(f"Failed: {ingest_result['error']} {elapsed(t)}")
                    elif ingest_result.get("status") == "already_exists":
                        warning(f"Already ingested — skipped {elapsed(t)}")
                        ingested_reviews.append(ingest_result)
                    elif ingest_result.get("status") == "success":
                        success(f"Ingested: {ingest_result.get('title', '?')} by {ingest_result.get('reviewer_name', '?')} {elapsed(t)}")
                        info(f"  review_id={ingest_result.get('review_id')} product_id={ingest_result.get('product_id')}")
                        ingested_reviews.append(ingest_result)
                    else:
                        warning(f"Unexpected status: {ingest_result.get('status')} {elapsed(t)}")
            else:
                header(5, total_steps, "Ingesting blog reviews")
                warning("No blog URLs to ingest — skipping")

            # ── Step 6: Generate summary ─────────────────────────────────────

            step_num = 6
            header(step_num, total_steps, "Generating reviews summary")
            t = time.time()

            summary_data = await execute_function(db, "get_reviews_summary", {
                "product_name": product_name,
            })

            if summary_data.get("error"):
                error(f"Summary failed: {summary_data['error']} {elapsed(t)}")
            elif summary_data.get("status") in ("not_found", "no_reviews"):
                warning(f"No reviews to summarize: {summary_data['status']} {elapsed(t)}")
            else:
                success(f"Summary generated for {summary_data.get('total_reviews', '?')} review(s) {elapsed(t)}")

            # ── Step 7: Marketplace listings ─────────────────────────────────

            if not skip_marketplace:
                header(7, total_steps, "Finding marketplace listings")
                t = time.time()

                marketplace_data = await execute_function(db, "find_marketplace_listings", {
                    "product_name": product_name,
                    "count_per_marketplace": 3,
                })

                if marketplace_data.get("error"):
                    error(f"Marketplace search failed: {marketplace_data['error']} {elapsed(t)}")
                elif marketplace_data.get("status") in ("success", "partial"):
                    amazon = marketplace_data.get("amazon", [])
                    ebay = marketplace_data.get("ebay", [])
                    success(f"Found {len(amazon)} Amazon + {len(ebay)} eBay listing(s) {elapsed(t)}")
                else:
                    warning(f"No listings found: {marketplace_data.get('status')} {elapsed(t)}")

            # ── Commit ───────────────────────────────────────────────────────

            await db.commit()

        except Exception as e:
            await db.rollback()
            print(f"\n{RED}{BOLD}Pipeline error:{RESET} {e}")
            raise

    # ── Final summary ────────────────────────────────────────────────────────

    _print_final_summary(product_name, ingested_reviews, summary_data, marketplace_data, pipeline_start, skip_marketplace)


def _print_final_summary(
    product_name: str,
    ingested_reviews: list[dict],
    summary_data: dict,
    marketplace_data: dict,
    pipeline_start: float,
    skip_marketplace: bool,
):
    """Print the final formatted summary."""

    total_time = time.time() - pipeline_start

    print(f"\n\n{'═' * 70}")
    print(f"{BOLD}{MAGENTA}  PIPELINE RESULTS — {product_name}{RESET}")
    print(f"{'═' * 70}")

    # ── Product info ─────────────────────────────────────────────────────
    product = summary_data.get("product", {})
    if product:
        print(f"\n  {BOLD}Product:{RESET} {product.get('name', product_name)}")
        if product.get("brand"):
            print(f"  {BOLD}Brand:{RESET}   {product['brand']}")
        if product.get("category"):
            print(f"  {BOLD}Category:{RESET} {product['category']}")

    # ── Reviews ingested ─────────────────────────────────────────────────
    total_reviews = summary_data.get("total_reviews", len(ingested_reviews))
    print(f"\n  {BOLD}Reviews in DB:{RESET} {total_reviews}")

    # ── Per-reviewer summaries ───────────────────────────────────────────
    reviewer_summaries = summary_data.get("reviewer_summaries", [])
    if reviewer_summaries:
        print(f"\n  {BOLD}{CYAN}── Reviewer Summaries ──{RESET}")
        for rs in reviewer_summaries:
            platform_icon = "🎬" if rs.get("platform") == "youtube" else "📝"
            print(f"\n  {BOLD}{platform_icon} {rs.get('reviewer_name', '?')}{RESET}")
            if rs.get("url"):
                print(f"  {DIM}{rs['url']}{RESET}")
            summary_text = rs.get("summary", "")
            # Word-wrap the summary at ~65 chars
            _print_wrapped(summary_text, indent=4, width=65)

    # ── Overall summary ──────────────────────────────────────────────────
    overall = summary_data.get("overall_summary", "")
    if overall:
        print(f"\n  {BOLD}{CYAN}── Overall Summary ──{RESET}")
        _print_wrapped(overall, indent=4, width=65)

    # ── Pros & Cons ──────────────────────────────────────────────────────
    pros = summary_data.get("common_pros", [])
    cons = summary_data.get("common_cons", [])
    if pros or cons:
        print(f"\n  {BOLD}{CYAN}── Consensus ──{RESET}")
    if pros:
        print(f"\n  {GREEN}{BOLD}Pros:{RESET}")
        for p in pros:
            print(f"    {GREEN}+{RESET} {p}")
    if cons:
        print(f"\n  {RED}{BOLD}Cons:{RESET}")
        for c in cons:
            print(f"    {RED}-{RESET} {c}")

    # ── Marketplace listings ─────────────────────────────────────────────
    if not skip_marketplace and marketplace_data:
        amazon = marketplace_data.get("amazon", [])
        ebay = marketplace_data.get("ebay", [])
        if amazon or ebay:
            print(f"\n  {BOLD}{CYAN}── Where to Buy ──{RESET}")
        if amazon:
            print(f"\n  {YELLOW}{BOLD}Amazon:{RESET}")
            for item in amazon:
                price = item.get("price", "N/A")
                print(f"    • {item.get('title', '?')} — {BOLD}{price}{RESET}")
                if item.get("url"):
                    print(f"      {DIM}{item['url']}{RESET}")
        if ebay:
            print(f"\n  {YELLOW}{BOLD}eBay:{RESET}")
            for item in ebay:
                price = item.get("price", "N/A")
                print(f"    • {item.get('title', '?')} — {BOLD}{price}{RESET}")
                if item.get("url"):
                    print(f"      {DIM}{item['url']}{RESET}")

    # ── Timing ───────────────────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print(f"  {BOLD}Total time:{RESET} {total_time:.1f}s")
    print(f"{'═' * 70}\n")


def _print_wrapped(text: str, indent: int = 4, width: int = 65):
    """Print text with word wrapping."""
    prefix = " " * indent
    words = text.split()
    line = prefix
    for word in words:
        if len(line) + len(word) + 1 > width + indent:
            print(line)
            line = prefix + word
        else:
            line = line + " " + word if line.strip() else prefix + word
    if line.strip():
        print(line)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ShopLens — Run the full review scraping pipeline for a product",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py "Samsung Galaxy S25"
  python run_pipeline.py "iPhone 16 Pro" --youtube-limit 5 --blog-limit 3
  python run_pipeline.py "Pixel 9" --skip-marketplace
  python run_pipeline.py "MacBook Pro M4" --db-host localhost
        """,
    )
    parser.add_argument("product_name", help="Name of the product to research")
    parser.add_argument("--youtube-limit", type=int, default=3, help="Max YouTube videos to find (default: 3)")
    parser.add_argument("--blog-limit", type=int, default=2, help="Max blog articles to find (default: 2)")
    parser.add_argument("--skip-marketplace", action="store_true", help="Skip marketplace listing search")
    parser.add_argument("--db-host", type=str, default=None, help="Override database hostname (e.g. 'localhost' when running outside Docker)")

    args = parser.parse_args()

    asyncio.run(run_pipeline(
        product_name=args.product_name,
        youtube_limit=args.youtube_limit,
        blog_limit=args.blog_limit,
        skip_marketplace=args.skip_marketplace,
        db_host=args.db_host,
    ))


if __name__ == "__main__":
    main()
