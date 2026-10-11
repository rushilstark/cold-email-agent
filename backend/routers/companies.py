"""
Companies router — /api/companies

Handles company + job listing CRUD, scraping, researching, and scoring.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models.models import Company, JobListing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CompanyOut(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    one_liner: Optional[str] = None
    stage: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    culture_signals: list[str] = Field(default_factory=list)
    f1_friendly: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: int
    company_id: int
    company: Optional[CompanyOut] = None
    role_title: str
    location: Optional[str] = None
    apply_url: Optional[str] = None
    score: float = 0.0
    tier: str = "unscored"
    status: str = "new"
    cpt_friendly_signal: bool = False
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingDetail(ListingOut):
    role_description: Optional[str] = None
    personalization_notes: Optional[str] = None  # from latest EmailDraft


class StatusUpdate(BaseModel):
    status: str


class RecipientUpdate(BaseModel):
    recipient_email: str
    recipient_name: Optional[str] = None


class ScrapeResult(BaseModel):
    new_companies: int
    new_listings: int
    total_scraped: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_field(value: Optional[str]) -> list[str]:
    """Safely parse a JSON-array string; return empty list on failure."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        return [value] if value else []


def _company_to_out(company: Company) -> CompanyOut:
    return CompanyOut(
        id=company.id,
        name=company.name,
        website=company.website,
        one_liner=company.one_liner,
        stage=company.stage,
        location=company.location,
        source=company.source,
        tech_stack=_parse_json_field(company.tech_stack),
        culture_signals=_parse_json_field(company.culture_signals),
        f1_friendly=company.f1_friendly,
        created_at=company.created_at,
    )


def _listing_to_out(listing: JobListing, include_detail: bool = False) -> ListingOut | ListingDetail:
    company_out = _company_to_out(listing.company) if listing.company else None

    personalization_notes: Optional[str] = None
    if include_detail and listing.email_drafts:
        latest = sorted(listing.email_drafts, key=lambda d: d.created_at, reverse=True)[0]
        personalization_notes = latest.personalization_notes

    data = dict(
        id=listing.id,
        company_id=listing.company_id,
        company=company_out,
        role_title=listing.role_title,
        location=listing.location,
        apply_url=listing.apply_url,
        score=listing.score,
        tier=listing.tier,
        status=listing.status,
        cpt_friendly_signal=listing.cpt_friendly_signal,
        recipient_email=listing.recipient_email,
        recipient_name=listing.recipient_name,
        created_at=listing.created_at,
    )

    if include_detail:
        data["role_description"] = listing.role_description
        data["personalization_notes"] = personalization_notes
        return ListingDetail(**data)
    return ListingOut(**data)


# ---------------------------------------------------------------------------
# Background task: scrape + upsert
# ---------------------------------------------------------------------------

async def _scrape_and_upsert(db: Session) -> dict:
    """Run all scrapers and upsert results into DB."""
    from backend.agents.sourcer import fetch_all_listings

    listings = await fetch_all_listings(max_per_source=50)
    new_companies = 0
    new_listings = 0

    for item in listings:
        company_name: str = (item.get("company_name") or "Unknown").strip()
        if not company_name:
            continue

        # --- Upsert company ---
        company = db.query(Company).filter(Company.name == company_name).first()
        if not company:
            company = Company(
                name=company_name,
                website=item.get("company_website") or "",
                location=item.get("location") or "",
                source=item.get("source") or "",
                created_at=datetime.utcnow(),
            )
            db.add(company)
            db.flush()  # get company.id
            new_companies += 1

        # --- Upsert job listing (dedup by company_id + role_title) ---
        role_title = (item.get("role_title") or "Intern").strip()
        existing = (
            db.query(JobListing)
            .filter(
                JobListing.company_id == company.id,
                JobListing.role_title == role_title,
            )
            .first()
        )
        if not existing:
            listing_obj = JobListing(
                company_id=company.id,
                role_title=role_title,
                role_description=item.get("role_description") or "",
                apply_url=item.get("apply_url") or "",
                location=item.get("location") or "",
                source=item.get("source") or "",
                posted_date=date.today(),
                cpt_friendly_signal=bool(item.get("cpt_friendly_signal", False)),
                status="new",
                created_at=datetime.utcnow(),
            )
            db.add(listing_obj)
            new_listings += 1

    db.commit()
    return {
        "new_companies": new_companies,
        "new_listings": new_listings,
        "total_scraped": len(listings),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ListingOut])
def list_companies(
    tier: Optional[str] = Query(None, description="Filter by tier: tier1, tier2, tier3, unscored"),
    db: Session = Depends(get_db),
) -> list[ListingOut]:
    """List all job listings with their company info, optionally filtered by tier."""
    query = db.query(JobListing)
    if tier:
        query = query.filter(JobListing.tier == tier)
    listings = query.order_by(JobListing.score.desc()).all()
    return [_listing_to_out(l) for l in listings]


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)) -> CompanyOut:
    """Get a single company by ID."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return _company_to_out(company)


@router.get("/{company_id}/listings", response_model=list[ListingDetail])
def get_company_listings(company_id: int, db: Session = Depends(get_db)) -> list[ListingDetail]:
    """Get all job listings for a specific company."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return [_listing_to_out(l, include_detail=True) for l in company.job_listings]


@router.post("/scrape", response_model=ScrapeResult)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ScrapeResult:
    """Trigger a scrape of all job sources and upsert results into the database."""
    result = await _scrape_and_upsert(db)
    return ScrapeResult(**result)


@router.post("/research/{listing_id}", response_model=dict)
async def research_listing(listing_id: int, db: Session = Depends(get_db)) -> dict:
    """Research a specific listing with Gemini and update DB."""
    from backend.agents.researcher import research_company_and_role

    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    company = listing.company
    profile = await research_company_and_role(
        company_name=company.name if company else "Unknown",
        company_website=company.website if company else "",
        role_title=listing.role_title,
        role_description=listing.role_description or "",
    )

    # Persist research results to company
    if company:
        company.tech_stack = json.dumps(profile.get("tech_stack", []))
        company.culture_signals = json.dumps(profile.get("culture_signals", []))
        company.founder_info = profile.get("rushil_fit_notes", "")
        company.f1_friendly = bool(profile.get("f1_friendly_signals"))

    listing.status = "researched"
    db.commit()

    return profile


@router.post("/score/{listing_id}", response_model=dict)
async def score_listing_endpoint(listing_id: int, db: Session = Depends(get_db)) -> dict:
    """Score a specific listing with Gemini-enhanced scoring."""
    from backend.agents.scorer import score_listing_with_gemini

    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    company = listing.company
    listing_dict = {
        "role_title": listing.role_title,
        "role_description": listing.role_description,
        "company_name": company.name if company else "",
        "one_liner": company.one_liner if company else "",
        "stage": company.stage if company else "",
        "location": listing.location,
        "recent_news": company.recent_news if company else "",
        "cpt_friendly_signal": listing.cpt_friendly_signal,
    }
    profile_dict = {
        "tech_stack": _parse_json_field(company.tech_stack if company else None),
        "culture_signals": _parse_json_field(company.culture_signals if company else None),
        "f1_friendly_signals": [],
        "founder_accessible": False,
        "rushil_fit_notes": company.founder_info if company else "",
    }

    score, rationale = score_listing_with_gemini(listing_dict, profile_dict)

    # Determine tier
    if score >= 75:
        tier = "tier1"
    elif score >= 50:
        tier = "tier2"
    else:
        tier = "tier3"

    listing.score = score
    listing.tier = tier
    listing.status = "scored"
    db.commit()

    return {"listing_id": listing_id, "score": score, "tier": tier, "rationale": rationale}


@router.post("/score-all", response_model=dict)
async def score_all_listings(db: Session = Depends(get_db)) -> dict:
    """Score all unscored / new listings."""
    from backend.agents.scorer import score_listing

    listings = db.query(JobListing).all()

    scored = 0
    removed = 0
    for listing in listings:
        company = listing.company
        listing_dict = {
            "role_title": listing.role_title,
            "role_description": listing.role_description or "",
            "company_name": company.name if company else "",
            "location": listing.location or "",
            "cpt_friendly_signal": listing.cpt_friendly_signal,
        }
        score, rationale = score_listing(listing_dict, {})

        # Auto-remove clearly irrelevant roles (score 0 on fit dimension means excluded)
        if score == 0:
            db.delete(listing)
            removed += 1
            continue

        listing.score = score
        listing.tier = "tier1" if score >= 75 else ("tier2" if score >= 50 else "tier3")
        listing.status = "scored"
        scored += 1

    db.commit()
    return {"scored": scored, "removed_irrelevant": removed}


@router.delete("/purge-irrelevant", response_model=dict)
def purge_irrelevant_listings(db: Session = Depends(get_db)) -> dict:
    """Delete all listings that score 0 (irrelevant roles like cider, marketing, etc)."""
    from backend.agents.scorer import score_listing
    from backend.agents.sourcer import _is_relevant_swe_role

    all_listings = db.query(JobListing).all()
    removed = 0
    for listing in all_listings:
        if not _is_relevant_swe_role(listing.role_title or ""):
            db.delete(listing)
            removed += 1

    db.commit()
    logger.info(f"Purged {removed} irrelevant listings")
    return {"removed": removed}


@router.put("/{company_id}/status", response_model=dict)
def update_company_status(
    company_id: int,
    update: StatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update the status of all listings under a company (e.g. skip all)."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for listing in company.job_listings:
        listing.status = update.status
    db.commit()
    return {"company_id": company_id, "status": update.status}


@router.put("/listings/{listing_id}/recipient", response_model=ListingOut)
def set_recipient(
    listing_id: int,
    update: RecipientUpdate,
    db: Session = Depends(get_db),
) -> ListingOut:
    """
    Set the recipient email (and optional name) for a specific job listing.
    This is who the cold email will be sent TO.
    """
    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.recipient_email = update.recipient_email
    if update.recipient_name:
        listing.recipient_name = update.recipient_name
    db.commit()
    db.refresh(listing)
    return _listing_to_out(listing)


@router.post("/listings/{listing_id}/find-email", response_model=dict)
async def find_recipient_email(
    listing_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Find the best person to cold email at this company.
    Uses hardcoded known contacts first, then Gemini AI fallback.
    Auto-saves the contact info to the listing.
    """
    from backend.agents.contact_finder import find_contact

    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    company = listing.company
    company_name = company.name if company else "Unknown"
    company_website = company.website if company else ""
    company_location = listing.location or ""

    result = await find_contact(
        company_name=company_name,
        company_website=company_website,
        role_title=listing.role_title,
        company_location=company_location,
    )

    if result.get("email_guess"):
        listing.recipient_email = result["email_guess"]
        listing.recipient_name = result.get("contact_name")
        db.commit()

    return result


@router.post("/find-all-contacts", response_model=dict)
async def find_all_contacts(
    tier: str = Query("tier1", description="Which tier to run contact-finding for: tier1, tier2, all"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Bulk find contacts for listings using hardcoded patterns + Gemini AI.
    Auto-saves contact email and name directly to the listing.
    """
    import asyncio
    from backend.agents.contact_finder import find_contact

    query = db.query(JobListing).filter(JobListing.recipient_email.is_(None))
    if tier != "all":
        query = query.filter(JobListing.tier == tier)
    listings = query.order_by(JobListing.score.desc()).all()

    found = 0
    skipped = 0

    for listing in listings:
        company = listing.company
        if not company:
            skipped += 1
            continue

        result = await find_contact(
            company_name=company.name,
            company_website=company.website or "",
            role_title=listing.role_title,
            company_location=listing.location or "",
        )

        if result.get("email_guess"):
            listing.recipient_email = result["email_guess"]
            listing.recipient_name = result.get("contact_name")
            found += 1
        else:
            skipped += 1

        await asyncio.sleep(0.1)

    db.commit()
    return {
        "contacts_found": found,
        "skipped": skipped,
        "total_processed": found + skipped,
    }

