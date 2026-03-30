import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class TwitterSearcher(BaseSearcher):
    platform_name = "Twitter / X"
    platform_icon = "twitter"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = self._search_via_google_dork(query)
        if not results:
            results = self._search_via_nitter(query)
        return results

    def _search_via_google_dork(self, query: str) -> list[SearchResult]:
        try:
            resp = requests.get(
                "https://www.google.com/search",
                params={"q": f'site:x.com "{query}"', "num": config.MAX_RESULTS_PER_PLATFORM},
                headers=HEADERS,
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for link_tag in soup.select("a[href]"):
                href = link_tag.get("href", "")
                if "x.com/" in href and "/status/" not in href:
                    url = href
                    if "/url?q=" in url:
                        url = url.split("/url?q=")[1].split("&")[0]
                    if "x.com/" not in url:
                        continue
                    parts = url.rstrip("/").split("/")
                    username = parts[-1] if parts else ""
                    if username and not username.startswith("search") and username not in ("home", "explore", "settings"):
                        if not any(r.username == username for r in results):
                            results.append(SearchResult(
                                platform="Twitter / X",
                                username=f"@{username}",
                                display_name=username,
                                profile_url=f"https://x.com/{username}",
                                confidence=0.5,
                            ))
            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []

    def _search_via_nitter(self, query: str) -> list[SearchResult]:
        for instance in NITTER_INSTANCES:
            try:
                resp = requests.get(
                    f"{instance}/search",
                    params={"f": "users", "q": query},
                    headers=HEADERS,
                    timeout=config.SEARCH_TIMEOUT,
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
