"""
Pillar I: High-Frequency ATS Extraction Engine

Strategy shift: We no longer filter for intern-only postings.
Summer 2027 CPT roles barely exist in September 2026.
Instead we extract ALL relevant SWE/AI/ML remote or NYC jobs
and cold-email companies with a compelling internship pitch.

ATS sources: Greenhouse JSON API, Lever JSON API, Workday cxs (curl_cffi), Crawl4AI deep-crawl.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import backend.main as app_main

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geofence: NYC or remote/anywhere — no international
# ---------------------------------------------------------------------------

NYC_INCLUDE = {"new york", "nyc", "manhattan", "brooklyn", "queens",
               "long island", "hoboken", "jersey city", "remote", "anywhere"}
INTL_EXCLUDE = {"seoul", "london", "paris", "berlin", "amsterdam", "singapore",
                "toronto", "barcelona", "newcastle", "australia", "göteborg",
                "spain", "germany", "france", "india", "china", "japan",
                "méxico", "brasil", "ukraine", "poland"}

def _is_nyc_or_remote(location_str: str) -> bool:
    loc = location_str.lower()
    # Hard exclude international
    if any(k in loc for k in INTL_EXCLUDE):
        return False
    # Accept NYC or remote
    return any(k in loc for k in NYC_INCLUDE) or loc == "" or loc == "remote / unknown"


# ---------------------------------------------------------------------------
# SWE role filter — keep engineering/AI/data, drop irrelevant
# ---------------------------------------------------------------------------

SWE_INCLUDE = {
    "software", "engineer", "engineering", "developer", "backend", "frontend",
    "full stack", "fullstack", "machine learning", "ml ", " ml", "ai ", " ai",
    "data engineer", "data scientist", "platform", "devops", "sre", "infra",
    "intern", "internship", "co-op",
}
SWE_EXCLUDE = {
    "marketing", "social media", "copywrite", "graphic design", "customer success",
    "account manager", "sales", "business development", "recruiter", "hr ",
    "quality dispense", "cider", "tester qa", "paralegal", "legal",
    "product manager", "project manager", "scrum", "supply chain",
}

def _is_relevant_swe_role(title: str) -> bool:
    t = title.lower()
    if any(bad in t for bad in SWE_EXCLUDE):
        return False
    return any(good in t for good in SWE_INCLUDE)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedupe(listings: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for item in listings:
        key = (
            item.get("company_name", "").lower().strip(),
            item.get("role_title", "").lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Source 1: Greenhouse
# ---------------------------------------------------------------------------

async def _fetch_greenhouse_board(board_token: str, company_name: str) -> list[dict]:
    results = []
    try:
        if app_main.http_client is None:
            return []
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        resp = await app_main.http_client.get(url)
        resp.raise_for_status()
        for job in resp.json().get("jobs", []):
            title    = job.get("title", "")
            location = job.get("location", {}).get("name", "")
            url_out  = job.get("absolute_url", "")
            if not _is_relevant_swe_role(title):
                continue
            if not _is_nyc_or_remote(location):
                continue
            results.append({
                "company_name":    company_name,
                "company_website": url_out,
                "role_title":      title,
                "role_description": "",
                "apply_url":       url_out,
                "location":        location or "Remote",
                "source":          "Greenhouse",
                "cpt_friendly_signal": False,
            })
        logger.info(f"Greenhouse [{board_token}]: {len(results)} matches")
    except Exception as exc:
        logger.warning(f"Greenhouse [{board_token}]: {exc}")
    return results


# ---------------------------------------------------------------------------
# Source 2: Lever
# ---------------------------------------------------------------------------

async def _fetch_lever_board(board_token: str, company_name: str) -> list[dict]:
    results = []
    try:
        if app_main.http_client is None:
            return []
        url  = f"https://api.lever.co/v0/postings/{board_token}?mode=json"
        resp = await app_main.http_client.get(url)
        resp.raise_for_status()
        for job in resp.json():
            title    = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            url_out  = job.get("hostedUrl", "")
            desc     = job.get("descriptionPlain", "")
            if not _is_relevant_swe_role(title):
                continue
            if not _is_nyc_or_remote(location):
                continue
            results.append({
                "company_name":    company_name,
                "company_website": url_out,
                "role_title":      title,
                "role_description": desc[:2000],
                "apply_url":       url_out,
                "location":        location or "Remote",
                "source":          "Lever",
                "cpt_friendly_signal": "cpt" in desc.lower() or "f-1" in desc.lower(),
            })
        logger.info(f"Lever [{board_token}]: {len(results)} matches")
    except Exception as exc:
        logger.warning(f"Lever [{board_token}]: {exc}")
    return results


# ---------------------------------------------------------------------------
# Source 3: Workday (curl_cffi TLS bypass)
# ---------------------------------------------------------------------------

async def _fetch_workday_tenant(tenant: str, company_name: str, endpoint: str) -> list[dict]:
    results = []
    try:
        if app_main.impersonated_client is None:
            return []
        payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "software engineer"}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        resp = await asyncio.to_thread(
            app_main.impersonated_client.post, endpoint, json=payload, headers=headers
        )
        if resp.status_code != 200:
            return []
        for job in resp.json().get("jobPostings", []):
            title    = job.get("title", "")
            location = job.get("locationsText", "")
            ext_path = job.get("externalPath", "")
            url_out  = f"https://{tenant}.myworkdayjobs.com/en-US/{tenant}{ext_path}"
            if not _is_relevant_swe_role(title):
                continue
            if not _is_nyc_or_remote(location):
                continue
            results.append({
                "company_name":    company_name,
                "company_website": url_out,
                "role_title":      title,
                "role_description": "",
                "apply_url":       url_out,
                "location":        location or "Remote",
                "source":          "Workday",
                "cpt_friendly_signal": False,
            })
        logger.info(f"Workday [{tenant}]: {len(results)} matches")
    except Exception as exc:
        logger.warning(f"Workday [{tenant}]: {exc}")
    return results


# ---------------------------------------------------------------------------
# Source 4: Crawl4AI deep crawl (anti-bot tier fallback)
# ---------------------------------------------------------------------------

async def _fetch_with_crawl4ai(url: str, company_name: str) -> list[dict]:
    results = []
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        from crawl4ai.async_configs import BrowserConfig
        try:
            from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
            strategy = BFSDeepCrawlStrategy(
                max_depth=2,
                include_patterns=["*jobs*", "*careers*", "*intern*"],
                exclude_patterns=["*login*", "*signup*"],
            )
        except ImportError:
            strategy = None

        browser_cfg = BrowserConfig(headless=True)
        run_cfg_kwargs = dict(simulate_user=True, override_navigator=True, magic=True)
        if strategy:
            run_cfg_kwargs["deep_crawl_strategy"] = strategy
        run_cfg = CrawlerRunConfig(**run_cfg_kwargs)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            if result.success:
                logger.info(f"Crawl4AI [{company_name}]: crawled {url}")
            else:
                logger.warning(f"Crawl4AI [{company_name}]: {result.error_message}")
    except Exception as exc:
        logger.warning(f"Crawl4AI [{company_name}]: {exc}")
    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Companies to target — broad SWE hiring, NYC or remote
GREENHOUSE_TARGETS = [
    ("anthropic",   "Anthropic"),
    ("discord",     "Discord"),
    ("scaleai",     "Scale AI"),
    ("plaid",       "Plaid"),
    ("mongodb",     "MongoDB"),
    ("notion",      "Notion"),
    ("figma",       "Figma"),
    ("retool",      "Retool"),
    ("stripe",      "Stripe"),
    ("brex",        "Brex"),
]

LEVER_TARGETS = [
    ("palantir",    "Palantir"),
    ("anduril",     "Anduril"),
    ("verkada",     "Verkada"),
    ("coda",        "Coda"),
    ("loom",        "Loom"),
]


async def fetch_all_listings(max_per_source: int = 50) -> list[dict]:
    """Fetch SWE listings from targeted companies for cold-email outreach."""
    logger.info("Pillar I: Starting ATS Extraction (cold-pitch strategy — no intern filter)")

    tasks = []
    for token, name in GREENHOUSE_TARGETS:
        tasks.append(_fetch_greenhouse_board(token, name))
    for token, name in LEVER_TARGETS:
        tasks.append(_fetch_lever_board(token, name))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    combined: list[dict] = []
    for res in results:
        if isinstance(res, list):
            combined.extend(res)
        else:
            logger.warning(f"Extraction task error: {res}")

    deduped = _dedupe(combined)
    logger.info(f"Pillar I done — {len(deduped)} unique SWE listings (ready for cold-pitch emails)")
    return deduped
