"""
Search tools — snippets-first context engineering
====================================================
Why two tools instead of one `internet_search(include_raw_content=True)`:

Fetching full page content for every result is expensive in context tokens
and most of it is never used. The snippets-first pattern (used by Tavily's
own deep-research recipes and Anthropic's research-agent examples) is:

  1. `internet_search` — cheap, returns titles + short snippets for many
     results. The agent reads these to decide what's actually relevant.
  2. `fetch_full_content` — only called on the small number of URLs whose
     snippet looked worth the extra context cost.

This keeps a researcher subagent's context window full of *signal* (curated
full pages) rather than *noise* (ten pages it never needed).
"""

from __future__ import annotations

import os
from typing import Literal

from tavily import TavilyClient

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Add it to your .env file."
            )
        _client = TavilyClient(api_key=api_key)
    return _client


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> dict:
    """Search the web and return short snippets (title, URL, ~snippet) for
    each result. Cheap — use this first, for as many queries/angles as you
    need. Do NOT request raw content here; use `fetch_full_content` for the
    few URLs that are actually worth reading in full.
    """
    return _get_client().search(
        query,
        max_results=max_results,
        include_raw_content=False,
        topic=topic,
    )


def fetch_full_content(url: str) -> dict:
    """Fetch the full extracted content of a single URL. Expensive in
    context tokens — only call this for URLs whose snippet (from
    `internet_search`) looked directly relevant to the question, ideally no
    more than 2-3 URLs per research task.
    """
    result = _get_client().extract(urls=[url])
    return result
