"""
Python Playwright crawler (non-headless) with depth/visit limits.

Install:
  pip install playwright patchright
  playwright install
  patchright install chromium

Run (examples):
  python crawler.py --seeds-file ./seeds/nfl_seeds.txt --per-page-limit 100 --max-depth 1 --delay-sec 4.0 --selectors "th a" --selectors "div#content td a" --iselectors "footer" --allowed-pattern "https://www.pro-football-reference.com/teams/" --allowed-pattern "https://www.pro-football-reference.com/players/" --disallowed-pattern "draft.htm" 
  python crawler.py --seeds-file ./seeds/nba_seeds.txt --per-page-limit 100 --max-depth 2 --delay-sec 4.0 --iselectors "header" --iselectors "footer" --allowed-pattern "https://www.basketball-reference.com/teams/" --allowed-pattern "https://www.basketball-reference.com/players/" --disallowed-pattern "draft.htm" 
  python crawler.py --seeds-file ./seeds/mlb_seeds.txt --per-page-limit 100 --max-depth 2 --delay-sec 4.0 --iselectors "header" --iselectors "footer" --allowed-pattern "https://www.baseball-reference.com/teams/" --allowed-pattern "https://www.baseball-reference.com/players/" --disallowed-pattern "draft.htm" 
  python crawler.py --seeds-file ./seeds/mma_seeds.txt --per-page-limit 100 --max-depth 2 --delay-sec 4.0 --iselectors "header" --iselectors "footer" --allowed-pattern "http://ufcstats.com/fighter-details/"
"""

import argparse
import asyncio
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse
from patchright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
from organize_html_files import organize_html_files
from link_manager import get_crawled_links_dir, load_recent_crawled_links, save_current_crawled_links

# --------------------------
# Utility helpers
# --------------------------

def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out

def strip_params(url):
    new_url = re.sub('\?.*', '', url)
    return new_url

def normalize_url(base_url: str, href: str) -> str | None:
    """Resolve relative links and drop fragments; return None for non-http(s)."""
    if not href:
        return None
    href = href.strip()
    # Ignore javascript/mailto/tel and similar schemes
    if re.match(r'^(javascript:|mailto:|tel:|#)', href, re.IGNORECASE):
        return None
    # Resolve relative URLs
    abs_url = urljoin(base_url, href)
    # Drop fragments
    abs_url = urldefrag(abs_url).url
    # Remove parameters
    abs_url = strip_params(abs_url)
    # Only allow http/https
    scheme = urlparse(abs_url).scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    return abs_url


def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r'[^a-zA-Z0-9\-_.]+', '-', text).strip('-_.').lower()
    if len(text) > max_len:
        text = text[:max_len].rstrip('-_.')
    return text or "page"


def unique_filename(url: str, out_dir: Path) -> Path:
    """Create a unique filename from URL + uuid."""
    parsed = urlparse(url)
    base = slugify(f"{parsed.netloc}-{parsed.path.replace('/', '-') or 'root'}")
    name = f"{base}-{int(time.time())}-{uuid.uuid4().hex[:8]}.html"
    return out_dir / name


def url_matches(url: str, patterns: list[re.Pattern]) -> bool:
    if not patterns:
        return True
    return any(p.search(url) for p in patterns)

def url_disallowed(url: str, patterns: list[re.Pattern]) -> bool:
    if not patterns:
        return False
    return any(p.search(url) for p in patterns)

# --------------------------
# Core crawler
# --------------------------

class PlaywrightCrawler:
    def __init__(
        self,
        seeds: list[str],
        out_dir: Path,
        per_page_limit: int,
        max_depth: int,
        allowed_patterns: list[str] | None = None,
        disallowed_patterns: list[str] | None = None,
        selectors: list[str] | None = None,
        iselectors: list[str] | None = None,
        navigation_timeout_ms: int = 15000,
        delay_sec: float = 0.0,
    ):
        self.seeds = [urldefrag(s).url for s in seeds]
        self.out_dir = out_dir
        self.per_page_limit = max(0, per_page_limit)
        self.max_depth = max(0, max_depth)
        self.allowed_regex = [re.compile(p, re.IGNORECASE) for p in (allowed_patterns or [])]
        self.disallowed_regex = [re.compile(p, re.IGNORECASE) for p in (disallowed_patterns or [])]
        self.selectors = selectors or []  # If empty, all <a href> considered (subject to allowed_patterns)
        self.iselectors = iselectors or []  # If empty, all <a href> considered (subject to allowed_patterns)
        self.navigation_timeout_ms = navigation_timeout_ms
        self.delay_sec = max(0.0, delay_sec)

        self.base_crawler_dir = Path(__file__).parent
        self.links_crawled_dir = get_crawled_links_dir(self.base_crawler_dir)
        self.recently_crawled_links = load_recent_crawled_links(self.base_crawler_dir)
        self.current_run_crawled_links: set[str] = set()
        self.visited: set[str] = set()

    async def _extract_links(self, page, base_url: str) -> list[str]:
        """Extract candidate links from the current page using BeautifulSoup."""
        links: list[str] = []
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        if self.selectors:
            # Gather hrefs from user-provided selectors
            for sel in self.selectors:
                try:
                    elements = soup.select(sel)
                    for el in elements:
                        # check ignore selectors first
                        should_skip = False
                        for isel in self.iselectors:
                            if soup.select_one(isel) and el.find_parent(isel): # Simplified check for parent matching isel
                                should_skip = True
                                break
                        if should_skip:
                            continue
                        href = el.get('href')
                        url = normalize_url(base_url, href)
                        if url:
                            links.append(url)
                except Exception as e:
                    print(f"DEBUG: Error processing selector '{sel}': {e}")
                    continue
        else:
            # Default: collect all anchor hrefs
            try:
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    url = normalize_url(base_url, href)
                    if url:
                        links.append(url)
            except Exception as e:
                print(f"DEBUG: Error extracting default links: {e}")
                pass

        # Deduplicate while preserving order
        seen = set()
        unique = []

        filtered = [
                    u for u in links
                    if url_matches(u, self.allowed_regex) and not url_disallowed(u, self.disallowed_regex)
                ]
        for u in filtered:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        print(f'DEBUG: Extracted and filtered links: {unique}')
        print(f'Seen: # Seen links: {len(seen)}')
        print(f'Unique: # Links left: {len(unique)}')
        return unique

    async def _save_html(self, html_content: str, url: str):
        """Save current page HTML to disk with a unique filename."""
        path = unique_filename(url, self.out_dir)
        path.write_text(html_content, encoding="utf-8")
        return path

    async def _visit_page(self, page, url: str) -> tuple[bool, str | None]:
        """Navigate to URL and save HTML. Returns True if successful, along with HTML content."""
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
            status = resp.status if resp else None
            if status and (400 <= status < 600):
                print(f"[WARN] HTTP {status} for {url}")
            html_content = await page.content()
            saved_path = await self._save_html(html_content, url)
            print(f"[OK] Saved: {url} -> {saved_path.name}")
            return True, html_content
        except TimeoutError:
            print(f"[TIMEOUT] {url}")
        except Exception as e:
            print(f"[ERROR] {url} :: {e}")
        return False, None

    async def crawl(self):
        ensure_dir(self.out_dir)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1366, "height": 850},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                queue: list[tuple[str, int]] = []
                for s in self.seeds:
                    queue.append((s, 0))

                while queue:
                    current_url, depth = queue.pop(0)
                    
                    # Deduplication check
                    if current_url in self.visited or current_url in self.recently_crawled_links:
                        print(f"[SKIP] Already visited or recently crawled: {current_url}")
                        continue
                    
                    self.visited.add(current_url)

                    ok, html_content = await self._visit_page(page, current_url)
                    if not ok:
                        continue
                    
                    self.current_run_crawled_links.add(current_url) # Add to current run's crawled links

                    if self.delay_sec:
                        await asyncio.sleep(self.delay_sec)

                    try:
                        # Pass html_content to _extract_links
                        links = await self._extract_links(page, current_url)
                    except Exception as e:
                        print(f"[LINK-EXTRACT-ERROR] {current_url} :: {e}")
                        links = []

                    # this has to come after the self._extract_links in order to print the progress
                    if depth >= self.max_depth:
                        continue

                    filtered = [
                        u for u in links
                        if url_matches(u, self.allowed_regex) and not url_disallowed(u, self.disallowed_regex)
                    ]
                    next_links = []
                    for u in filtered:
                        if len(next_links) >= self.per_page_limit:
                            break
                        # Check against both visited and recently_crawled_links for next links
                        if u not in self.visited and u not in self.recently_crawled_links:
                            next_links.append(u)

                    for u in next_links:
                        queue.append((u, depth + 1))

                print("[DONE] All links processed.")
            except KeyboardInterrupt:
                print("\n[INTERRUPT] Crawler stopped by user.")
            finally:
                # Ensure links are saved even on interruption
                if self.current_run_crawled_links:
                    save_current_crawled_links(self.base_crawler_dir, self.current_run_crawled_links)
                await page.close()
                await context.close()
                await browser.close()

# --------------------------
# CLI
# --------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Non-headless stealth Playwright crawler.")
    seed_group = parser.add_mutually_exclusive_group(required=True)
    seed_group.add_argument("--seeds", nargs="+", help="Seed URLs (space-separated).")
    seed_group.add_argument("--seeds-file", type=str, help="Path to a file with one seed URL per line.")

    parser.add_argument("--per-page-limit", type=int, default=5, help="Max links to follow per page (default: 5).")
    parser.add_argument("--max-depth", type=int, default=1, help="Depth beyond seeds to follow (default: 1).")
    parser.add_argument("--out", type=str, default="pages", help="Output directory for saved .html files.")
    parser.add_argument("--allowed-pattern", action="append", help="Regex pattern(s) to whitelist URLs. Repeat flag to add more.")
    parser.add_argument("--disallowed-pattern", action="append", help="Regex pattern(s) to blacklist URLs. Repeat flag to add more.")
    parser.add_argument("--selectors", action="append", help="CSS selector(s) for links to follow. Repeat flag to add more.")
    parser.add_argument("--iselectors", action="append", help="CSS selector(s) for links to ignore. Repeat flag to add more.")
    parser.add_argument("--nav-timeout-ms", type=int, default=15000, help="Navigation timeout per page in ms (default: 15000).")
    parser.add_argument("--delay-sec", type=float, default=0.0, help="Delay between requests in seconds (default: 0).")

    args = parser.parse_args(argv)

    if args.seeds_file:
        path = Path(args.seeds_file)
        if not path.exists():
            parser.error(f"--seeds-file not found: {path}")
        seeds = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        seeds = args.seeds

    # Basic URL sanity check
    bad = [s for s in seeds if not re.match(r"^https?://", s, re.IGNORECASE)]
    if bad:
        parser.error(f"Invalid seed URLs (must start with http:// or https://): {bad}")

    return {
        "seeds": seeds,
        "out_dir": ensure_dir(args.out),
        "per_page_limit": args.per_page_limit,
        "max_depth": args.max_depth,
        "allowed_patterns": args.allowed_pattern or [],
        "disallowed_patterns": args.disallowed_pattern or [],
        "selectors": args.selectors or [],
        "iselectors": args.iselectors or [],
        "navigation_timeout_ms": args.nav_timeout_ms,
        "delay_sec": args.delay_sec,
    }

async def amain():
    cfg = parse_args()
    crawler = PlaywrightCrawler(
        seeds=cfg["seeds"],
        out_dir=cfg["out_dir"],
        per_page_limit=cfg["per_page_limit"],
        max_depth=cfg["max_depth"],
        allowed_patterns=cfg["allowed_patterns"],
        disallowed_patterns=cfg["disallowed_patterns"],
        selectors=cfg["selectors"],
        iselectors=cfg["iselectors"],
        navigation_timeout_ms=cfg["navigation_timeout_ms"],
        delay_sec=cfg["delay_sec"],
    )
    await crawler.crawl()

if __name__ == "__main__":
    ensure_dir('pages')
    asyncio.run(amain())
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    html_directory_to_organize = os.path.join(current_script_dir, "pages")
    organize_html_files(html_directory_to_organize)
