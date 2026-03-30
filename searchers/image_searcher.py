import re

import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

SOCIAL_PATTERNS = {
    "Twitter / X": (r"(?:x\.com|twitter\.com)/([\w]+)", "https://x.com/{}"),
    "Instagram": (r"instagram\.com/([\w.]+)", "https://www.instagram.com/{}/"),
    "LinkedIn": (r"linkedin\.com/in/([\w-]+)", "https://www.linkedin.com/in/{}"),
    "Facebook": (r"facebook\.com/([\w.]+)", "https://www.facebook.com/{}"),
    "GitHub": (r"github\.com/([\w-]+)", "https://github.com/{}"),
}

SKIP_USERNAMES = {
    "search", "explore", "home", "settings", "login", "signup", "help",
    "pages", "groups", "events", "marketplace", "watch", "p", "reel",
    "stories", "accounts", "in", "company", "jobs",
}


class ImageSearcher(BaseSearcher):
    platform_name = "Reverse Image"
    platform_icon = "image"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        return []

    def search_by_image(self, image_path: str) -> list[SearchResult]:
        results = []
        if config.SERPAPI_KEY:
            results = self._search_serpapi(image_path)
        if not results:
            results = self._search_yandex(image_path)
        return results

    def _search_serpapi(self, image_path: str) -> list[SearchResult]:
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    "https://serpapi.com/search",
                    data={
                        "engine": "google_lens",
                        "api_key": config.SERPAPI_KEY,
                    },
                    files={"encoded_image": f},
                    timeout=config.SEARCH_TIMEOUT,
                )
            if not resp.ok:
                return []
            data = resp.json()
            results = []
            for match in data.get("visual_matches", []):
                url = match.get("link", "")
                found = self._extract_social_profile(url, match.get("title", ""))
                if found:
                    results.append(found)
            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []

    def _search_yandex(self, image_path: str) -> list[SearchResult]:
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    "https://yandex.com/images/search",
                    params={"rpt": "imageview", "format": "json"},
                    files={"upfile": ("image.jpg", f, "image/jpeg")},
                    headers=HEADERS,
                    timeout=config.SEARCH_TIMEOUT,
                )
            if not resp.ok:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for link_tag in soup.find_all("a", href=True):
                href = link_tag.get("href", "")
                title = link_tag.get_text(strip=True)
                found = self._extract_social_profile(href, title)
                if found:
                    results.append(found)
            return results[:config.MAX_RESULTS_PER_PLATFORM]
        except Exception:
            return []

    def _extract_social_profile(self, url: str, title: str) -> SearchResult | None:
        for platform, (pattern, url_template) in SOCIAL_PATTERNS.items():
            match = re.search(pattern, url)
            if match:
                username = match.group(1)
                if username.lower() in SKIP_USERNAMES:
                    continue
                display = title if title else username
                return SearchResult(
                    platform=platform,
                    username=username,
                    display_name=display,
                    profile_url=url_template.format(username),
                    confidence=0.6,
                    extra={"source": "reverse_image_search"},
                )
        return None
