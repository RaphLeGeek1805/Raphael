import re
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class InstagramSearcher(BaseSearcher):
    platform_name = "Instagram"
    platform_icon = "instagram"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = self._search_via_web(query)
        if not results:
            results = self._search_via_google(query)
        return results

    def _search_via_web(self, query: str) -> list[SearchResult]:
        try:
            resp = requests.get(
                "https://www.instagram.com/web/search/topsearch/",
                params={"query": query},
                headers={
                    **HEADERS,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []
            data = resp.json()
            results = []
            for item in data.get("users", []):
                user = item.get("user", {})
                results.append(SearchResult(
                    platform="Instagram",
                    username=f"@{user.get('username', '')}",
                    display_name=user.get("full_name", user.get("username", "")),
                    profile_url=f"https://www.instagram.com/{user.get('username', '')}/",
                    avatar_url=user.get("profile_pic_url"),
                    bio=None,
                    confidence=0.7,
                    extra={"is_verified": user.get("is_verified", False)},
                ))
            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []

    def _search_via_google(self, query: str) -> list[SearchResult]:
        try:
            resp = requests.get(
                "https://www.google.com/search",
                params={"q": f'site:instagram.com "{query}"', "num": 10},
                headers=HEADERS,
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            seen = set()

            for tag in soup.find_all("a", href=True):
                href = tag["href"]
                if "/url?q=" in href:
                    href = unquote(href.split("/url?q=")[1].split("&")[0])

                match = re.search(r"instagram\.com/([\w.]+)/?", href)
                if not match:
                    continue
                username = match.group(1)
                if username in seen or username in ("p", "explore", "accounts", "reel", "stories"):
                    continue
                seen.add(username)

                title_text = tag.get_text(strip=True)
                display_name = re.sub(r"\s*[-|(].*Instagram.*$", "", title_text).strip()
                if not display_name:
                    display_name = username

                results.append(SearchResult(
                    platform="Instagram",
                    username=f"@{username}",
                    display_name=display_name,
                    profile_url=f"https://www.instagram.com/{username}/",
                    confidence=0.5,
                ))

            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []
