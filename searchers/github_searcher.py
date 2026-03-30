import requests

import config
from searchers.base import BaseSearcher, SearchResult
from searchers.engines import multi_engine_search

import re


class GitHubSearcher(BaseSearcher):
    platform_name = "GitHub"
    platform_icon = "github"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = self._search_api(query)
        if not results:
            results = self._search_web(query)
        return results

    def _search_api(self, query: str) -> list[SearchResult]:
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            if config.GITHUB_TOKEN:
                headers["Authorization"] = f"token {config.GITHUB_TOKEN}"

            resp = requests.get(
                "https://api.github.com/search/users",
                params={"q": f"fullname:{query}", "per_page": config.MAX_RESULTS_PER_PLATFORM},
                headers=headers,
                timeout=config.SEARCH_TIMEOUT,
            )
            if not resp.ok:
                # Try simpler query without fullname prefix
                resp = requests.get(
                    "https://api.github.com/search/users",
                    params={"q": query, "per_page": config.MAX_RESULTS_PER_PLATFORM},
                    headers=headers,
                    timeout=config.SEARCH_TIMEOUT,
                )
                if not resp.ok:
                    return []

            data = resp.json()
            results = []
            for item in data.get("items", [])[:config.MAX_RESULTS_PER_PLATFORM]:
                # Fetch user details
                user_data = {}
                try:
                    user_resp = requests.get(item["url"], headers=headers, timeout=5)
                    if user_resp.ok:
                        user_data = user_resp.json()
                except Exception:
                    pass

                results.append(SearchResult(
                    platform="GitHub",
                    username=item.get("login", ""),
                    display_name=user_data.get("name") or item.get("login", ""),
                    profile_url=item.get("html_url", ""),
                    avatar_url=item.get("avatar_url"),
                    bio=user_data.get("bio"),
                    confidence=0.7,
                    extra={
                        "repos": user_data.get("public_repos", 0),
                        "followers": user_data.get("followers", 0),
                        "location": user_data.get("location"),
                        "company": user_data.get("company"),
                    },
                ))
            return results
        except Exception:
            return []

    def _search_web(self, query: str) -> list[SearchResult]:
        """Fallback: search via web search engines."""
        search_results = multi_engine_search(f'site:github.com "{query}"')
        results = []
        seen = set()
        for r in search_results:
            match = re.search(r"github\.com/([\w-]+)$", r["url"].rstrip("/"))
            if not match:
                continue
            username = match.group(1)
            skip = {"features", "about", "pricing", "enterprise", "topics", "collections",
                    "trending", "explore", "settings", "login", "join", "orgs", "search"}
            if username in seen or username.lower() in skip:
                continue
            seen.add(username)

            display = r["title"].split("-")[0].strip() if "-" in r["title"] else username
            results.append(SearchResult(
                platform="GitHub",
                username=username,
                display_name=display,
                profile_url=f"https://github.com/{username}",
                avatar_url=f"https://github.com/{username}.png",
                confidence=0.5,
            ))
        return results[:config.MAX_RESULTS_PER_PLATFORM]
