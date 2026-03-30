import re

import config
from searchers.base import BaseSearcher, SearchResult
from searchers.engines import multi_engine_search


class LinkedInSearcher(BaseSearcher):
    platform_name = "LinkedIn"
    platform_icon = "linkedin"

    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        query = f"{first_name} {last_name}"
        results = []
        seen = set()

        # Search with multiple query variations for better coverage
        queries = [
            f'site:linkedin.com/in "{query}"',
            f'site:linkedin.com/in {first_name} {last_name}',
        ]

        for q in queries:
            search_results = multi_engine_search(q)
            for r in search_results:
                match = re.search(r"linkedin\.com/in/([\w-]+)", r["url"])
                if not match:
                    continue
                slug = match.group(1)
                if slug in seen:
                    continue
                seen.add(slug)

                # Extract display name from search result title
                title = r.get("title", "")
                # Remove " - LinkedIn", " | LinkedIn", etc.
                display_name = re.sub(r"\s*[-|–].*[Ll]inked[Ii]n.*$", "", title).strip()
                if not display_name or len(display_name) < 2:
                    display_name = slug.replace("-", " ").title()

                bio = r.get("snippet", "")

                results.append(SearchResult(
                    platform="LinkedIn",
                    username=slug,
                    display_name=display_name,
                    profile_url=f"https://www.linkedin.com/in/{slug}",
                    bio=bio if bio else None,
                    confidence=0.6,
                ))

            if len(results) >= config.MAX_RESULTS_PER_PLATFORM:
                break

        return results[:config.MAX_RESULTS_PER_PLATFORM]
