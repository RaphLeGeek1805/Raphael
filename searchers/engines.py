import re
from urllib.parse import unquote, quote_plus

import requests
from bs4 import BeautifulSoup

import config
from searchers.base import BaseSearcher, SearchResult

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def search_duckduckgo(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo HTML search — more reliable than Google for scraping."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=config.SEARCH_TIMEOUT,
        )
        if not resp.ok:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for r in soup.select(".result"):
            link = r.select_one(".result__a")
            snippet = r.select_one(".result__snippet")
            if link:
                href = link.get("href", "")
                # DuckDuckGo redirects
                if "uddg=" in href:
                    href = unquote(href.split("uddg=")[1].split("&")[0])
                results.append({
                    "url": href,
                    "title": link.get_text(strip=True),
                    "snippet": snippet.get_text(strip=True) if snippet else "",
                })
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def search_bing(query: str, max_results: int = 10) -> list[dict]:
    """Bing search as additional fallback."""
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "count": max_results},
            headers=HEADERS,
            timeout=config.SEARCH_TIMEOUT,
        )
        if not resp.ok:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for li in soup.select("#b_results .b_algo"):
            link = li.select_one("h2 a")
            snippet_el = li.select_one(".b_caption p")
            if link:
                results.append({
                    "url": link.get("href", ""),
                    "title": link.get_text(strip=True),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def search_google(query: str, max_results: int = 10) -> list[dict]:
    """Google search — may get blocked but worth trying."""
    try:
        resp = requests.get(
            "https://www.google.com/search",
            params={"q": query, "num": max_results},
            headers=HEADERS,
            timeout=config.SEARCH_TIMEOUT,
        )
        if not resp.ok:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for tag in soup.select("a[href]"):
            href = tag.get("href", "")
            if "/url?q=" in href:
                href = unquote(href.split("/url?q=")[1].split("&")[0])
                title = tag.get_text(strip=True)
                if href.startswith("http"):
                    results.append({"url": href, "title": title, "snippet": ""})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def multi_engine_search(query: str, max_results: int = 10) -> list[dict]:
    """Try multiple search engines, merge results."""
    results = search_duckduckgo(query, max_results)
    if len(results) < 3:
        bing_results = search_bing(query, max_results)
        seen_urls = {r["url"] for r in results}
        for r in bing_results:
            if r["url"] not in seen_urls:
                results.append(r)
                seen_urls.add(r["url"])
    if len(results) < 3:
        google_results = search_google(query, max_results)
        seen_urls = {r["url"] for r in results}
        for r in google_results:
            if r["url"] not in seen_urls:
                results.append(r)
                seen_urls.add(r["url"])
    return results[:max_results]
