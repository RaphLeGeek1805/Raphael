import re

import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult
from searchers.engines import multi_engine_search

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
]


class TwitterSearcher(BaseSearcher):
    platform_name = "Twitter / X"
    platform_icon = "twitter"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"

        # Try multiple approaches in order
        results = self._search_via_engines(query)
        if not results:
            results = self._search_via_nitter(query)
        return results

    def _search_via_engines(self, query: str) -> list[SearchResult]:
        """Search via DuckDuckGo/Bing/Google for X.com profiles."""
        search_results = multi_engine_search(
            f'site:x.com OR site:twitter.com "{query}"'
        )
        results = []
        seen = set()

        for r in search_results:
            url = r["url"]
            # Match x.com/username or twitter.com/username (not /status/, /search, etc.)
            match = re.search(r"(?:x\.com|twitter\.com)/([\w]+)$", url.rstrip("/"))
            if not match:
                continue

            username = match.group(1)
            skip = {"search", "explore", "home", "settings", "login", "signup",
                    "help", "i", "hashtag", "intent", "tos", "privacy"}
            if username.lower() in skip or username in seen:
                continue
            seen.add(username)

            # Extract display name from title
            title = r.get("title", "")
            display_name = title.split("(")[0].strip() if "(" in title else title.split("-")[0].strip()
            if not display_name or display_name.lower() in ("x", "twitter"):
                display_name = username

            bio = r.get("snippet", "")

            results.append(SearchResult(
                platform="Twitter / X",
                username=f"@{username}",
                display_name=display_name,
                profile_url=f"https://x.com/{username}",
                bio=bio if bio else None,
                confidence=0.6,
            ))

        return results[:config.MAX_RESULTS_PER_PLATFORM]

    def _search_via_nitter(self, query: str) -> list[SearchResult]:
        for instance in NITTER_INSTANCES:
            try:
                resp = requests.get(
                    f"{instance}/search",
                    params={"f": "users", "q": query},
                    headers=HEADERS,
                    timeout=8,
                )
                if not resp.ok:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                results = []
                for card in soup.select(".timeline-item, .user-card"):
                    username_el = card.select_one(".username")
                    name_el = card.select_one(".fullname")
                    bio_el = card.select_one(".bio, .tweet-content")
                    if username_el:
                        username = username_el.get_text(strip=True)
                        results.append(SearchResult(
                            platform="Twitter / X",
                            username=username,
                            display_name=name_el.get_text(strip=True) if name_el else username,
                            profile_url=f"https://x.com/{username.lstrip('@')}",
                            bio=bio_el.get_text(strip=True) if bio_el else None,
                            confidence=0.6,
                        ))
                if results:
                    return results[:config.MAX_RESULTS_PER_PLATFORM]
            except Exception:
                continue
        return []
