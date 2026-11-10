from dotenv import load_dotenv
import asyncio
import logging
from tavily import AsyncTavilyClient

load_dotenv(verbose=True, override=True)

logger = logging.getLogger("tavily_search")

tavily_client = AsyncTavilyClient()
sem = asyncio.Semaphore(20)


async def search_one(q: str, **kw) -> dict:
    """Executes a single Tavily web search query with concurrency throttling, timeouts, and exponential backoff retry logic.

    Args:
        q (str): The search query string.
        **kw: Additional keyword arguments passed directly to `tavily_client.search()`
              (e.g., `search_depth`, `max_results`).

    Returns:
        dict: A dictionary containing the query result status:
            - On success: `{"query": q, "ok": True, "data": <tavily_response>}`
            - On failure: `{"query": q, "ok": False, "error": <error_message>}`
    """
    async with sem:
        logger.info("search_one start: query=%r kwargs=%s", q, kw)
        for attempt in range(5):
            try:
                # Adding a timeout (e.g., 15 seconds) to prevent hanging tasks
                async with asyncio.timeout(15):
                    data = await tavily_client.search(q, **kw)
                    result_count = len(data.get("results", [])) if isinstance(data, dict) else "unknown"
                    logger.info(
                        "search_one ok: query=%r attempt=%d results=%s",
                        q, attempt + 1, result_count,
                    )
                    return {"query": q, "ok": True, "data": data}
            except Exception as e:
                logger.warning(
                    "search_one attempt %d/5 failed: query=%r error=%s",
                    attempt + 1, q, e,
                )
                if attempt == 4:
                    logger.error("search_one giving up after 5 attempts: query=%r error=%s", q, e)
                    return {"query": q, "ok": False, "error": str(e)}
                # Exponential backoff with jitter
                backoff = (2 ** attempt) + (0.1 * attempt)
                logger.debug("search_one backoff %.1fs before retry: query=%r", backoff, q)
                await asyncio.sleep(backoff)

        logger.error("search_one max retries exceeded: query=%r", q)
        return {"query": q, "ok": False, "error": "Max retries exceeded"}


async def deep_search(query: str) -> dict:
    """Performs an advanced, deep-level single search query optimized for thorough research.

    Args:
        query (str): The search query string.

    Returns:
        dict: The search result dictionary returned by `search_one()` using
              `search_depth="advanced"` and `max_results=10`.
    """
    logger.info("deep_search: query=%r (advanced, max_results=10)", query)
    return await search_one(query, search_depth="advanced", max_results=10)


async def filtered_extraction(query: str) -> dict:
    """Performs an advanced Tavily search, filters resulting URLs by a relevance score threshold (>0.5),
    deduplicates them while preserving order, and extracts detailed content chunks.

    Args:
        query (str): The search and extraction query string.

    Returns:
        dict: The extracted data dictionary from `tavily_client.extract()`,
              or `{"results": [], "failed_results": []}` if no URLs meet the relevance threshold.
    """
    logger.info("filtered_extraction start: query=%r", query)
    # Search first
    response = await tavily_client.search(
        query=query,
        search_depth="advanced",
        max_results=20
    )

    # Filter by relevance score (>0.5)
    relevant_urls = [
        result['url'] for result in response.get('results', [])
        if result.get('score', 0) > 0.5
    ]

    # Deduplicate URLs while preserving order to avoid redundant web extractions
    seen = set()
    unique_urls = [url for url in relevant_urls if not (url in seen or seen.add(url))]

    logger.info(
        "filtered_extraction: query=%r relevant=%d unique=%d",
        query, len(relevant_urls), len(unique_urls),
    )

    if not unique_urls:
        logger.info("filtered_extraction: no URLs above relevance threshold for query=%r", query)
        return {"results": [], "failed_results": []}

    # Extract from filtered & deduplicated URLs with targeted query
    extracted_data = await tavily_client.extract(
        urls=unique_urls,
        query=query,
        chunks_per_source=3,
        extract_depth="advanced"
    )

    logger.info(
        "filtered_extraction done: query=%r extracted=%d failed=%d",
        query,
        len(extracted_data.get("results", [])) if isinstance(extracted_data, dict) else -1,
        len(extracted_data.get("failed_results", [])) if isinstance(extracted_data, dict) else -1,
    )
    return extracted_data