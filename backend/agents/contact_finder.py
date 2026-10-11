"""
Contact Finder — Gemini-powered + hardcoded patterns for major companies.

Finds the best person to cold-email for a Summer 2027 CPT internship at each company.
Uses hardcoded known patterns for top targets, falls back to Gemini for unknowns.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded university recruiting contacts for major companies
# (publicly known or well-documented formats)
# ---------------------------------------------------------------------------

KNOWN_CONTACTS: dict[str, dict] = {
    "palantir": {
        "contact_name": "University Recruiting Team",
        "contact_title": "University Recruiting",
        "email_guess": "university@palantir.com",
        "email_confidence": "high",
        "reasoning": "Palantir has a dedicated university recruiting team that handles all intern/new grad hiring including CPT.",
        "linkedin_search_tip": "Palantir university recruiter site:linkedin.com",
    },
    "anthropic": {
        "contact_name": "Campus Recruiting Team",
        "contact_title": "University Recruiting",
        "email_guess": "university@anthropic.com",
        "email_confidence": "high",
        "reasoning": "Anthropic's campus team handles all university hires including CPT internships.",
        "linkedin_search_tip": "Anthropic university recruiter site:linkedin.com",
    },
    "figma": {
        "contact_name": "University Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "universityhiring@figma.com",
        "email_confidence": "high",
        "reasoning": "Figma has an active university hiring program with Summer 2027 intern roles already posted.",
        "linkedin_search_tip": "Figma university recruiter site:linkedin.com",
    },
    "stripe": {
        "contact_name": "Campus Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "campus@stripe.com",
        "email_confidence": "high",
        "reasoning": "Stripe's campus team handles intern and new grad hiring including CPT/OPT.",
        "linkedin_search_tip": "Stripe campus recruiter site:linkedin.com",
    },
    "scale ai": {
        "contact_name": "University Recruiting Team",
        "contact_title": "University Recruiting",
        "email_guess": "university@scale.com",
        "email_confidence": "high",
        "reasoning": "Scale AI's university recruiting team coordinates CPT/OPT internship programs.",
        "linkedin_search_tip": "Scale AI university recruiter site:linkedin.com",
    },
    "mongodb": {
        "contact_name": "University Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "university@mongodb.com",
        "email_confidence": "high",
        "reasoning": "MongoDB has an established campus recruiting program across US universities.",
        "linkedin_search_tip": "MongoDB university recruiter site:linkedin.com",
    },
    "discord": {
        "contact_name": "University Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "university@discord.com",
        "email_confidence": "medium",
        "reasoning": "Discord's recruiting team handles university and intern pipelines.",
        "linkedin_search_tip": "Discord university recruiter site:linkedin.com",
    },
    "brex": {
        "contact_name": "University Recruiting Team",
        "contact_title": "University Recruiting",
        "email_guess": "university@brex.com",
        "email_confidence": "medium",
        "reasoning": "Brex's recruiting team handles campus and early career hiring.",
        "linkedin_search_tip": "Brex university recruiter New York site:linkedin.com",
    },
    "retool": {
        "contact_name": "Engineering Recruiting",
        "contact_title": "Technical Recruiter",
        "email_guess": "recruiting@retool.com",
        "email_confidence": "medium",
        "reasoning": "Retool is mid-size; engineering recruiting handles intern hiring directly.",
        "linkedin_search_tip": "Retool technical recruiter site:linkedin.com",
    },
    "notion": {
        "contact_name": "University Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "university@makenotion.com",
        "email_confidence": "medium",
        "reasoning": "Notion has an active internship program through their university recruiting channel.",
        "linkedin_search_tip": "Notion university recruiter site:linkedin.com",
    },
    "plaid": {
        "contact_name": "University Recruiting",
        "contact_title": "University Recruiting",
        "email_guess": "university@plaid.com",
        "email_confidence": "medium",
        "reasoning": "Plaid's university recruiting team coordinates intern hiring.",
        "linkedin_search_tip": "Plaid university recruiter site:linkedin.com",
    },
    "coda": {
        "contact_name": "Engineering Recruiting",
        "contact_title": "Technical Recruiter",
        "email_guess": "recruiting@coda.io",
        "email_confidence": "medium",
        "reasoning": "Coda is mid-size; engineering team handles intern pipeline directly.",
        "linkedin_search_tip": "Coda.io recruiter site:linkedin.com",
    },
    "sticker mule": {
        "contact_name": "Anthony Constantino",
        "contact_title": "CEO / Co-founder",
        "email_guess": "anthony@stickermule.com",
        "email_confidence": "medium",
        "reasoning": "Sticker Mule is small and founder-led; CPT intern pitch goes directly to Anthony.",
        "linkedin_search_tip": "Anthony Constantino Sticker Mule site:linkedin.com",
    },
    "pivotal health": {
        "contact_name": "Engineering Lead",
        "contact_title": "Head of Engineering",
        "email_guess": "engineering@pivotalhealth.com",
        "email_confidence": "low",
        "reasoning": "Small healthtech startup; engineering lead handles intern decisions.",
        "linkedin_search_tip": "Pivotal Health Software Engineer New York site:linkedin.com",
    },
}


def _lookup_hardcoded(company_name: str) -> Optional[dict]:
    """Check if we have a hardcoded contact for this company."""
    name_lower = company_name.lower().strip()
    # Exact or substring match
    for key, contact in KNOWN_CONTACTS.items():
        if key in name_lower or name_lower in key:
            return contact
    return None


async def find_contact(company_name: str, company_website: str, role_title: str, company_location: str = "") -> dict:
    """
    Find the best contact to cold-email. Uses hardcoded patterns first, then Gemini.
    Always returns a result — never returns None.
    """
    fallback = {
        "contact_name": "University Recruiting Team",
        "contact_title": "University Recruiting",
        "email_guess": f"university@{_domain_from_website(company_website)}",
        "email_confidence": "low",
        "reasoning": "Generic best-guess based on company domain.",
        "linkedin_search_tip": f"{company_name} university recruiter site:linkedin.com",
    }

    # 1. Try hardcoded first
    hardcoded = _lookup_hardcoded(company_name)
    if hardcoded:
        return hardcoded

    # 2. Try Gemini with new SDK
    try:
        from google import genai
        from backend.config import get_settings
        settings = get_settings()
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""Find the best specific person for Rushil Chirla (F-1 MS CS student at Stony Brook, NYC) to cold email for a Summer 2027 CPT internship.

Company: {company_name}
Website: {company_website or "unknown"}
Role posted: {role_title}

Target the right person based on company size:
- Large company (500+): University/Campus Recruiter by name
- Mid-size (50-500): Engineering Manager or Technical Recruiter
- Small startup (<50): CTO or Co-founder

Use known real names and email formats from your training data if available.
Email format should use the company's domain from their website.

Return ONLY valid JSON (no markdown):
{{"contact_name": "First Last", "contact_title": "Their role", "email_guess": "email@domain.com", "email_confidence": "high|medium|low", "reasoning": "Why this person", "linkedin_search_tip": "LinkedIn search string"}}"""

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)

        # Fill in missing keys
        for k, v in fallback.items():
            if k not in result or not result[k]:
                result[k] = v

        return result

    except Exception as exc:
        logger.warning(f"Gemini contact lookup failed for {company_name}: {exc}")
        return fallback


def _domain_from_website(website: str) -> str:
    """Extract domain from website URL."""
    if not website:
        return "company.com"
    website = website.lower().replace("https://", "").replace("http://", "").replace("www.", "")
    return website.split("/")[0] or "company.com"
