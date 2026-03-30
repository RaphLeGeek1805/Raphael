import re

import config
from searchers.base import BaseSearcher, SearchResult
from searchers.engines import multi_engine_search


class FacebookSearcher(BaseSearcher):
    platform_name = "Facebook"
    platform_icon = "facebook"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = []
        seen = set()

        queries = [
            f'site:facebook.com "{query}"',
            f'site:facebook.com {first_name} {last_name}',
        ]

        for q in queries:
            search_results = multi_engine_search(q)
            for r in search_results:
                match = re.search(r"facebook\.com/([\w.]+)/?", r["url"])
                if not match:
                    # Also try profile.php?id= format
                    match_id = re.search(r"facebook\.com/profile\.php\?id=(\d+)", r["url"])
                    if match_id:
                        uid = match_id.group(1)
                        if uid in seen:
                            continue
                        seen.add(uid)

                        title = r.get("title", "")
                        display_name = re.sub(r"\s*[-|–].*[Ff]acebook.*$", "", title).strip()
                        if not display_name:
                            display_name = query

                        results.append(SearchResult(
                            platform="Facebook",
                            username=uid,
                            display_name=display_name,
                            profile_url=f"https://www.facebook.com/profile.php?id={uid}",
                            bio=r.get("snippet", "") or None,
                            confidence=0.4,
                        ))
                    continue

                slug = match.group(1)
                skip = {"pages", "groups", "events", "marketplace", "watch", "login",
                        "help", "photo", "profile.php", "public", "stories", "reels",
                        "gaming", "fundraisers", "ads", "business", "privacy",
                        "policies", "recover", "settings", "share", "sharer"}
                if slug.lower() in skip or slug in seen:
                    continue
                seen.add(slug)

                title = r.get("title", "")
                display_name = re.sub(r"\s*[-|–].*[Ff]acebook.*$", "", title).strip()
                if not display_name or len(display_name) < 2:
                    display_name = slug.replace(".", " ").title()

                bio = r.get("snippet", "")

                results.append(SearchResult(
                    platform="Facebook",
                    username=slug,
                    display_name=display_name,
                    profile_url=f"https://www.facebook.com/{slug}",
                    bio=bio if bio else None,
                    confidence=0.4,
                ))

            if len(results) >= config.MAX_RESULTS_PER_PLATFORM:
                break

        return results[:config.MAX_RESULTS_PER_PLATFORM]
