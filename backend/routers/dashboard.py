"""
Dashboard router — /api/dashboard

Provides aggregated stats and recent activity for the frontend dashboard.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models.models import Company, EmailDraft, JobListing, SentLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_companies: int
    total_listings: int
    tier1_count: int
    tier2_count: int
    tier3_count: int
    unscored_count: int
    emails_drafted: int
    emails_approved: int
    emails_sent_total: int
    emails_sent_today: int
    daily_limit: int
    daily_limit_remaining: int


class ActivityItem(BaseModel):
    timestamp: datetime
    event_type: str  # scrape | email_sent | email_drafted | email_approved
    description: str
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)) -> DashboardStats:
    """Return aggregated pipeline statistics."""
    from backend.config import get_settings
    settings = get_settings()

    total_companies = db.query(func.count(Company.id)).scalar() or 0
    total_listings = db.query(func.count(JobListing.id)).scalar() or 0

    tier1_count = (
        db.query(func.count(JobListing.id))
        .filter(JobListing.tier == "tier1")
        .scalar() or 0
    )
    tier2_count = (
        db.query(func.count(JobListing.id))
        .filter(JobListing.tier == "tier2")
        .scalar() or 0
    )
    tier3_count = (
        db.query(func.count(JobListing.id))
        .filter(JobListing.tier == "tier3")
        .scalar() or 0
    )
    unscored_count = (
        db.query(func.count(JobListing.id))
        .filter(JobListing.tier == "unscored")
        .scalar() or 0
    )

    emails_drafted = (
        db.query(func.count(EmailDraft.id))
        .filter(EmailDraft.status == "draft")
        .scalar() or 0
    )
    emails_approved = (
        db.query(func.count(EmailDraft.id))
        .filter(EmailDraft.status == "approved")
        .scalar() or 0
    )
    emails_sent_total = db.query(func.count(SentLog.id)).scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    emails_sent_today = (
        db.query(func.count(SentLog.id))
        .filter(SentLog.sent_at >= today_start)
        .scalar() or 0
    )

    daily_limit = settings.DAILY_SEND_LIMIT
    daily_limit_remaining = max(0, daily_limit - emails_sent_today)

    return DashboardStats(
        total_companies=total_companies,
        total_listings=total_listings,
        tier1_count=tier1_count,
        tier2_count=tier2_count,
        tier3_count=tier3_count,
        unscored_count=unscored_count,
        emails_drafted=emails_drafted,
        emails_approved=emails_approved,
        emails_sent_total=emails_sent_total,
        emails_sent_today=emails_sent_today,
        daily_limit=daily_limit,
        daily_limit_remaining=daily_limit_remaining,
    )


@router.get("/activity", response_model=list[ActivityItem])
def get_activity(db: Session = Depends(get_db)) -> list[ActivityItem]:
    """
    Return the last 20 notable events across the pipeline.

    Combines sent emails, approved drafts, and recently scored listings.
    """
    activity: list[ActivityItem] = []

    # --- Recent sends ---
    sent_logs = (
        db.query(SentLog)
        .order_by(SentLog.sent_at.desc())
        .limit(10)
        .all()
    )
    for log in sent_logs:
        activity.append(
            ActivityItem(
                timestamp=log.sent_at,
                event_type="email_sent",
                description=f"Email sent to {log.company_name} — {log.role_title}",
                metadata={
                    "company": log.company_name,
                    "role": log.role_title,
                    "recipient": log.recipient_email,
                    "gmail_message_id": log.gmail_message_id or "",
                },
            )
        )

    # --- Recently approved drafts ---
    approved_drafts = (
        db.query(EmailDraft)
        .filter(EmailDraft.status == "approved")
        .order_by(EmailDraft.created_at.desc())
        .limit(5)
        .all()
    )
    for draft in approved_drafts:
        company_name = ""
        role_title = ""
        if draft.job_listing:
            role_title = draft.job_listing.role_title
            if draft.job_listing.company:
                company_name = draft.job_listing.company.name
        activity.append(
            ActivityItem(
                timestamp=draft.created_at,
                event_type="email_approved",
                description=f"Draft approved: {company_name} — {role_title}",
                metadata={"draft_id": draft.id, "company": company_name, "role": role_title},
            )
        )

    # --- Recently scored listings (tier1 only as signal of pipeline progress) ---
    tier1_listings = (
        db.query(JobListing)
        .filter(JobListing.tier == "tier1")
        .order_by(JobListing.created_at.desc())
        .limit(5)
        .all()
    )
    for listing in tier1_listings:
        company_name = listing.company.name if listing.company else "Unknown"
        activity.append(
            ActivityItem(
                timestamp=listing.created_at,
                event_type="scored_tier1",
                description=f"Tier-1 listing found: {company_name} — {listing.role_title} (score: {listing.score:.0f})",
                metadata={
                    "listing_id": listing.id,
                    "company": company_name,
                    "score": listing.score,
                },
            )
        )

    # Sort all events newest-first, return top 20
    activity.sort(key=lambda a: a.timestamp, reverse=True)
    return activity[:20]
