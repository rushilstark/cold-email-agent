"""
Hybrid Scoring Engine: BM25 + weighted heuristics.

Scores job listings 0-100 against Rushil's profile.
Replaces the pure RRF approach that was causing everything to score 100.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rushil's tech stack
# ---------------------------------------------------------------------------

RUSHIL_TECH: set[str] = {
    "python", "java", "javascript", "typescript", "sql",
    "spring boot", "angular", "node.js", "nodejs", "django", "express", "react",
    "aws", "lambda", "ec2", "s3", "textract", "docker", "ci/cd", "cicd",
    "tensorflow", "hugging face", "huggingface", "openai", "nlp", "llm",
    "gemini", "machine learning", "ml", "ai", "langchain", "langgraph",
    "git", "postgresql", "postgres", "mongodb", "mysql", "swagger", "fastapi",
    "github copilot", "copilot",
}

# ---------------------------------------------------------------------------
# Penalty / bonus keywords
# ---------------------------------------------------------------------------

NYC_KEYWORDS = {"new york", "nyc", "manhattan", "brooklyn", "queens", "long island",
                "hoboken", "jersey city", "remote"}
IRRELEVANT_ROLES = {
    "marketing", "sales", "designer", "graphic", "copywriter", "social media",
    "product manager", "account manager", "recruiter", "hr ", "human resources",
    "quality dispense", "cider", "tester qa", "customer success", "business development",
}
SENIOR_KEYWORDS = {"staff", "principal", "director", "vp ", "vice president", "c-level",
                   "cto", "ceo", "team lead education", "consultant implementation"}
STRONG_FIT_KEYWORDS = {"software engineer", "backend", "full stack", "fullstack",
                       "ai engineer", "ml engineer", "data engineer", "platform engineer",
                       "swe", "intern", "internship", "entry", "junior", "new grad"}

# ---------------------------------------------------------------------------
# Individual dimension scorers (0-100 each, then weighted)
# ---------------------------------------------------------------------------

def _tech_score(role_title: str, role_description: str) -> float:
    """How much does the role's tech overlap with Rushil's stack? (0-30 pts)"""
    combined = (role_title + " " + (role_description or "")).lower()
    matches = sum(1 for t in RUSHIL_TECH if t in combined)
    return min(matches * 3, 30)   # 3pts per match, cap at 30


def _role_fit_score(role_title: str) -> float:
    """Is this a SWE/AI/ML/data role Rushil should care about? (0-30 pts)"""
    title_lower = role_title.lower()

    # Hard penalty for irrelevant roles
    if any(kw in title_lower for kw in IRRELEVANT_ROLES):
        return 0.0

    # Heavy penalty for roles that are too senior (we're cold-pitching for intern)
    senior_penalty = 5.0 if any(kw in title_lower for kw in SENIOR_KEYWORDS) else 0.0

    if any(kw in title_lower for kw in STRONG_FIT_KEYWORDS):
        return max(30.0 - senior_penalty, 0)
    if "engineer" in title_lower or "developer" in title_lower or "data" in title_lower:
        return max(20.0 - senior_penalty, 0)
    return 5.0


def _location_score(location: str) -> float:
    """NYC or remote = full points. Overseas = 0. (0-20 pts)"""
    loc = (location or "").lower()
    if any(k in loc for k in {"new york", "nyc", "manhattan", "brooklyn", "queens",
                               "long island", "hoboken", "jersey city"}):
        return 20.0
    if "remote" in loc or "anywhere" in loc or not loc or loc == "remote / unknown":
        return 15.0
    if any(k in loc for k in {"boston", "cambridge", "san francisco", "sf", "seattle", "chicago"}):
        return 8.0
    # International / clearly non-US
    international = {"seoul", "london", "paris", "berlin", "amsterdam", "singapore",
                     "toronto", "barcelona", "newcastle", "göteborg", "australia"}
    if any(k in loc for k in international):
        return 0.0
    return 5.0


def _cpt_bonus(cpt_friendly_signal: bool, description: str) -> float:
    """Extra points if company signals openness to visa/CPT. (0-10 pts)"""
    if cpt_friendly_signal:
        return 10.0
    desc_lower = (description or "").lower()
    if any(k in desc_lower for k in {"cpt", "opt", "f-1", "f1", "visa", "sponsorship", "international students"}):
        return 7.0
    return 0.0


def _ai_company_bonus(role_title: str, description: str) -> float:
    """Bonus for AI/ML-first companies. (0-10 pts)"""
    combined = (role_title + " " + (description or "")).lower()
    ai_hits = sum(1 for kw in {"ai", "ml", "llm", "generative", "nlp", "inference"} if kw in combined)
    if ai_hits >= 3:
        return 10.0
    if ai_hits >= 1:
        return 5.0
    return 0.0


# ---------------------------------------------------------------------------
# Main public scorer
# ---------------------------------------------------------------------------

def _intern_bonus(role_title: str) -> float:
    """Explicit internship postings get a massive bonus. (0-20 pts)"""
    t = role_title.lower()
    # These are explicitly posted intern roles — jackpot
    if "intern" in t or "internship" in t or "new grad" in t or "early career" in t:
        # Summer 2027 specifically mentioned = max bonus
        if "2027" in t:
            return 20.0
        return 17.0
    return 0.0


def _senior_penalty(role_title: str) -> float:
    """Subtract points for roles too senior to realistically cold-pitch as an intern. (0-15 pts)"""
    t = role_title.lower()
    # Director/VP/Manager titles
    if any(kw in t for kw in {"director", "vp ", "vice president", " manager", "principal",
                               "c-level", "cto", "ceo", "chief", "head of"}):
        # Manager of Engineering = 10pt penalty, but Engineering Manager != bad if we're pitching
        if "engineering manager" in t or "manager, software" in t or "manager, applied" in t:
            return 5.0
        return 10.0
    # Staff / Senior+ still fine to cold email, just mild penalty vs intern-specific
    if t.startswith("staff ") or t.startswith("senior staff") or "staff+" in t or "senior staff" in t:
        return 5.0
    return 0.0


# ---------------------------------------------------------------------------
# Main public scorer
# ---------------------------------------------------------------------------

def score_listing(listing_dict: dict, profile_dict: dict) -> tuple[float, str]:
    """
    Score a listing against Rushil's profile.

    Returns (score 0-100, rationale string).
    """
    role_title = listing_dict.get("role_title") or ""
    role_desc  = listing_dict.get("role_description") or ""
    location   = listing_dict.get("location") or ""
    cpt_signal = bool(listing_dict.get("cpt_friendly_signal", False))

    tech    = _tech_score(role_title, role_desc)        # 0-30
    fit     = _role_fit_score(role_title)               # 0-30
    loc     = _location_score(location)                 # 0-20
    cpt     = _cpt_bonus(cpt_signal, role_desc)         # 0-10
    ai_co   = _ai_company_bonus(role_title, role_desc)  # 0-10
    intern_b = _intern_bonus(role_title)                # 0-20 BONUS
    sr_pen  = _senior_penalty(role_title)               # 0-15 PENALTY

    total   = tech + fit + loc + cpt + ai_co + intern_b - sr_pen
    total   = round(min(max(total, 0.0), 100.0), 1)

    rationale = (
        f"Tech: {tech:.0f}/30 | Fit: {fit:.0f}/30 | Loc: {loc:.0f}/20 | "
        f"CPT: {cpt:.0f}/10 | AI-co: {ai_co:.0f}/10 | "
        f"Intern bonus: +{intern_b:.0f} | Senior penalty: -{sr_pen:.0f}"
    )
    return total, rationale


# Backwards-compat alias used by companies router score-all endpoint
def score_listing_with_gemini(listing_dict: dict, profile_dict: dict) -> tuple[float, str]:
    """Alias — runs the same weighted scorer (no extra LLM call needed)."""
    return score_listing(listing_dict, profile_dict)
