"""
Emails router — /api/emails

Handles email draft generation, approval, sending, and logging.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db import get_db
from backend.models.models import Company, EmailDraft, JobListing, SentLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emails", tags=["emails"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DraftOut(BaseModel):
    id: int
    job_listing_id: int
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    subject: str
    body: str
    personalization_notes: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    personalization_notes: Optional[str] = None


class GenerateRequest(BaseModel):
    cpt_strategy: str = "natural"  # natural | explicit | hidden


class TestSendRequest(BaseModel):
    subject: str = "Cold Email Agent — Test"
    body: str = "This is a test email from your cold email agent. Setup is working!"


class SentLogOut(BaseModel):
    id: int
    email_draft_id: Optional[int] = None
    company_name: str
    role_title: str
    recipient_email: str
    subject: str
    sent_at: datetime
    gmail_message_id: Optional[str] = None

    model_config = {"from_attributes": True}


class BatchSendResult(BaseModel):
    sent: int
    skipped: int
    dry_run: bool
    daily_limit_remaining: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_field(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except Exception:
        return []


def _draft_to_out(draft: EmailDraft) -> DraftOut:
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    if draft.job_listing:
        role_title = draft.job_listing.role_title
        if draft.job_listing.company:
            company_name = draft.job_listing.company.name
    return DraftOut(
        id=draft.id,
        job_listing_id=draft.job_listing_id,
        company_name=company_name,
        role_title=role_title,
        subject=draft.subject,
        body=draft.body,
        personalization_notes=draft.personalization_notes,
        status=draft.status,
        sent_at=draft.sent_at,
        created_at=draft.created_at,
    )


def _build_listing_dict(listing: JobListing) -> dict:
    company = listing.company
    return {
        "company_name": company.name if company else "Unknown",
        "one_liner": company.one_liner if company else "",
        "role_title": listing.role_title,
        "role_description": listing.role_description or "",
        "location": listing.location or "",
        "stage": company.stage if company else "",
        "cpt_friendly_signal": listing.cpt_friendly_signal,
        "recent_news": company.recent_news if company else "",
    }


def _build_profile_dict(listing: JobListing) -> dict:
    company = listing.company
    return {
        "tech_stack": _parse_json_field(company.tech_stack if company else None),
        "culture_signals": _parse_json_field(company.culture_signals if company else None),
        "f1_friendly_signals": [],
        "founder_accessible": False,
        "rushil_fit_notes": company.founder_info if company else "",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[DraftOut])
def list_drafts(db: Session = Depends(get_db)) -> list[DraftOut]:
    """List all email drafts ordered by creation date descending."""
    drafts = (
        db.query(EmailDraft)
        .order_by(EmailDraft.created_at.desc())
        .all()
    )
    return [_draft_to_out(d) for d in drafts]


@router.get("/sent", response_model=list[SentLogOut])
def get_sent_log(db: Session = Depends(get_db)) -> list[SentLogOut]:
    """Return the full sent log ordered by sent_at descending."""
    logs = db.query(SentLog).order_by(SentLog.sent_at.desc()).all()
    return [SentLogOut.model_validate(log) for log in logs]


@router.get("/{listing_id}/preview", response_model=DraftOut)
async def preview_email(
    listing_id: int,
    db: Session = Depends(get_db),
) -> DraftOut:
    """
    Return existing draft for listing_id, or generate one on-the-fly.
    """
    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Return existing draft if present
    existing = (
        db.query(EmailDraft)
        .filter(EmailDraft.job_listing_id == listing_id)
        .order_by(EmailDraft.created_at.desc())
        .first()
    )
    if existing:
        return _draft_to_out(existing)

    # Generate a new draft
    from backend.agents.email_writer import generate_email

    listing_dict = _build_listing_dict(listing)
    profile_dict = _build_profile_dict(listing)
    result = await generate_email(listing_dict, profile_dict, cpt_strategy="natural")

    draft = EmailDraft(
        job_listing_id=listing_id,
        subject=result["subject"],
        body=result["body"],
        personalization_notes=result.get("personalization_notes"),
        status="draft",
        created_at=datetime.utcnow(),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.post("/{listing_id}/generate", response_model=DraftOut)
async def generate_email_endpoint(
    listing_id: int,
    req: GenerateRequest,
    db: Session = Depends(get_db),
) -> DraftOut:
    """Force-regenerate an email draft for the given listing."""
    from backend.agents.email_writer import generate_email

    listing = db.query(JobListing).filter(JobListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing_dict = _build_listing_dict(listing)
    profile_dict = _build_profile_dict(listing)
    result = await generate_email(listing_dict, profile_dict, cpt_strategy=req.cpt_strategy)

    draft = EmailDraft(
        job_listing_id=listing_id,
        subject=result["subject"],
        body=result["body"],
        personalization_notes=result.get("personalization_notes"),
        status="draft",
        created_at=datetime.utcnow(),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.put("/{draft_id}", response_model=DraftOut)
def update_draft(
    draft_id: int,
    update: DraftUpdate,
    db: Session = Depends(get_db),
) -> DraftOut:
    """Edit the subject, body, or notes of an existing draft."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if update.subject is not None:
        draft.subject = update.subject
    if update.body is not None:
        draft.body = update.body
    if update.personalization_notes is not None:
        draft.personalization_notes = update.personalization_notes

    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve_draft(draft_id: int, db: Session = Depends(get_db)) -> DraftOut:
    """Approve a draft for sending."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "approved"
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.post("/{draft_id}/skip", response_model=DraftOut)
def skip_draft(draft_id: int, db: Session = Depends(get_db)) -> DraftOut:
    """Skip / reject a draft."""
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "skipped"
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.post("/send-batch", response_model=BatchSendResult)
def send_batch(db: Session = Depends(get_db)) -> BatchSendResult:
    """
    Send all approved email drafts up to the daily limit.

    Respects DRY_RUN setting and DAILY_SEND_LIMIT.
    """
    from backend.agents.sender import GmailSender

    settings = get_settings()
    sender = GmailSender()
    sent_today = sender.get_sent_count_today(db)
    remaining = settings.DAILY_SEND_LIMIT - sent_today

    if remaining <= 0:
        return BatchSendResult(
            sent=0,
            skipped=0,
            dry_run=settings.DRY_RUN,
            daily_limit_remaining=0,
        )

    approved_drafts = (
        db.query(EmailDraft)
        .filter(EmailDraft.status == "approved")
        .order_by(EmailDraft.created_at.asc())
        .limit(remaining)
        .all()
    )

    sent_count = 0
    skipped_count = 0

    for draft in approved_drafts:
        listing = draft.job_listing
        if not listing:
            skipped_count += 1
            continue

        company = listing.company

        # Must have a recipient email set — can't guess one
        recipient_email = listing.recipient_email
        if not recipient_email:
            logger.warning(
                f"Skipping draft {draft.id} for {company.name if company else '?'} "
                "— no recipient_email set. Add it in the Companies view first."
            )
            skipped_count += 1
            continue

        # Resolve resume path relative to backend/ folder
        import os
        resume_path = settings.RESUME_PATH
        if not os.path.isabs(resume_path):
            resume_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                resume_path.lstrip("./"),
            )

        result = sender.send_email(
            to=recipient_email,
            subject=draft.subject,
            body=draft.body,
            attachment_path=resume_path,
            dry_run=settings.DRY_RUN,
            sender=settings.GMAIL_FROM,
        )

        if result["success"]:
            now = datetime.utcnow()
            draft.status = "sent"
            draft.sent_at = now

            log = SentLog(
                email_draft_id=draft.id,
                company_name=company.name if company else "Unknown",
                role_title=listing.role_title,
                recipient_email=recipient_email,
                subject=draft.subject,
                sent_at=now,
                gmail_message_id=result.get("message_id", ""),
            )
            db.add(log)
            sent_count += 1
        else:
            skipped_count += 1

    db.commit()

    new_remaining = max(0, remaining - sent_count)
    return BatchSendResult(
        sent=sent_count,
        skipped=skipped_count,
        dry_run=settings.DRY_RUN,
        daily_limit_remaining=new_remaining,
    )


@router.post("/test-send", response_model=dict)
def test_send(req: Optional[TestSendRequest] = None, db: Session = Depends(get_db)) -> dict:
    """Send a test email to rushil.chirla@gmail.com to verify Gmail setup."""
    req = req or TestSendRequest()
    from backend.agents.sender import GmailSender, check_credentials_exist

    settings = get_settings()

    if not settings.DRY_RUN and not check_credentials_exist():
        raise HTTPException(
            status_code=400,
            detail="RESEND_API_KEY not found. Add it to your .env file.",
        )

    sender = GmailSender()
    result = sender.send_email(
        to="rushil.chirla@gmail.com",
        subject=req.subject,
        body=req.body,
        dry_run=settings.DRY_RUN,
        sender=settings.GMAIL_FROM,
    )
    return result
