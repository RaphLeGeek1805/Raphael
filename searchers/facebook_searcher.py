import re
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class FacebookSearcher(BaseSearcher):
    platform_name = "Facebook"
    platform_icon = "facebook"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = self._search_google_dork(query)
        if not results:
            results = self._search_duckduckgo(query)
        return results

    def _search_google_dork(self, query: str) -> list[SearchResult]:
        try:
            resp = requests.get(
                "https://www.google.com/search",
                params={"q": f'site:facebook.com "{query}"', "num": 10},
                headers=HEADERS,
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []
            return self._parse_results(resp.text)
        except Exception:
            return []

    def _search_duckduckgo(self, query: str) -> list[SearchResult]:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f'site:facebook.com "{query}"'},
                headers=HEADERS,
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []
            return self._parse_results(resp.text)
        except Exception:
            return []

    def _parse_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen = set()

        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if "/url?q=" in href:
                href = unquote(href.split("/url?q=")[1].split("&")[0])

            match = re.search(r"facebook\.com/([\w.]+)/?", href)
            if not match:
                continue

            slug = match.group(1)
            skip = {"pages", "groups", "events", "marketplace", "watch", "login", "help", "photo", "profile.php"}
            if slug in seen or slug.lower() in skip:
                continue
            seen.add(slug)

            title_text = tag.get_text(strip=True)
            display_name = re.sub(r"\s*[-|].*Facebook.*$", "", title_text).strip()
            if not display_name or display_name.lower() == slug.lower():
                display_name = slug.replace(".", " ").title()

            results.append(SearchResult(
                platform="Facebook",
                username=slug,
                display_name=display_name,
                profile_url=f"https://www.facebook.com/{slug}",
                confidence=0.4,
            ))

        return results[:config.MAX_RESULTS_PER_PLATFORM]
