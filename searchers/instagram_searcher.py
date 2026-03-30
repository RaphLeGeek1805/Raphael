import re

import requests

import config
from searchers.base import BaseSearcher, SearchResult
from searchers.engines import multi_engine_search

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}


class InstagramSearcher(BaseSearcher):
    platform_name = "Instagram"
    platform_icon = "instagram"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = self._search_via_web(query)
        if not results:
            results = self._search_via_engines(query)
        return results

    def _search_via_web(self, query: str) -> list[SearchResult]:
        """Try Instagram's web search endpoint."""
        try:
            resp = requests.get(
                "https://www.instagram.com/web/search/topsearch/",
                params={"query": query},
                headers={
                    **HEADERS,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.instagram.com/",
                },
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                return []
            data = resp.json()
            results = []
            for item in data.get("users", []):
                user = item.get("user", {})
                username = user.get("username", "")
                if not username:
                    continue
                results.append(SearchResult(
                    platform="Instagram",
                    username=f"@{username}",
                    display_name=user.get("full_name", username),
                    profile_url=f"https://www.instagram.com/{username}/",
                    avatar_url=user.get("profile_pic_url"),
                    bio=None,
                    confidence=0.7,
                    extra={"is_verified": user.get("is_verified", False)},
                ))
            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []

    def _search_via_engines(self, query: str) -> list[SearchResult]:
        """Fallback: search via multiple search engines."""
        search_results = multi_engine_search(f'site:instagram.com "{query}"')
        results = []
        seen = set()

        for r in search_results:
            match = re.search(r"instagram\.com/([\w.]+)/?", r["url"])
            if not match:
                continue
            username = match.group(1)
            skip = {"p", "explore", "accounts", "reel", "reels", "stories",
                    "about", "legal", "developer", "directory"}
            if username.lower() in skip or username in seen:
                continue
            seen.add(username)

            title = r.get("title", "")
            # Clean display name: "John Doe (@johndoe) • Instagram" -> "John Doe"
            display_name = re.sub(r"\s*[\(@].*$", "", title).strip()
            display_name = re.sub(r"\s*[•\-|].*[Ii]nstagram.*$", "", display_name).strip()
            if not display_name or len(display_name) < 2:
                display_name = username

            bio = r.get("snippet", "")

            results.append(SearchResult(
                platform="Instagram",
                username=f"@{username}",
                display_name=display_name,
                profile_url=f"https://www.instagram.com/{username}/",
                bio=bio if bio else None,
                confidence=0.5,
            ))

        return results[:config.MAX_RESULTS_PER_PLATFORM]
