import requests

import config
from searchers.base import BaseSearcher, SearchResult


class GitHubSearcher(BaseSearcher):
    platform_name = "GitHub"
    platform_icon = "github"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if config.GITHUB_TOKEN:
            headers["Authorization"] = f"token {config.GITHUB_TOKEN}"

        resp = requests.get(
            "https://api.github.com/search/users",
            params={"q": f"fullname:{query}", "per_page": config.MAX_RESULTS_PER_PLATFORM},
            headers=headers,
            timeout=config.SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("items", []):
            user_resp = requests.get(
                item["url"],
                headers=headers,
                timeout=config.SEARCH_TIMEOUT,
            )
            user_data = user_resp.json() if user_resp.ok else {}

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
