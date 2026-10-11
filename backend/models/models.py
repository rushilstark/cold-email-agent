"""SQLAlchemy ORM models for the cold-email agent."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Company(Base):
    """A startup or company sourced from a job board."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str] = mapped_column(String(512), nullable=True)
    one_liner: Mapped[str] = mapped_column(String(512), nullable=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=True)  # Seed, Series A …
    headcount: Mapped[int] = mapped_column(Integer, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=True)  # YC, RemoteOK, HN, Wellfound
    tech_stack: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array as string
    culture_signals: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    recent_news: Mapped[str] = mapped_column(Text, nullable=True)
    founder_info: Mapped[str] = mapped_column(Text, nullable=True)
    f1_friendly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    job_listings: Mapped[list[JobListing]] = relationship(
        "JobListing", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class JobListing(Base):
    """An individual internship / job listing at a company."""

    __tablename__ = "job_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    posted_date: Mapped[date] = mapped_column(Date, nullable=True)
    cpt_friendly_signal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tier: Mapped[str] = mapped_column(String(16), default="unscored", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="new", nullable=False, index=True
    )  # new | researched | scored | emailed | skipped
    # Who to email — you fill this in the UI or let Gemini suggest it
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=True)  # e.g. "Hi Sarah,"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    company: Mapped[Company] = relationship("Company", back_populates="job_listings")
    email_drafts: Mapped[list[EmailDraft]] = relationship(
        "EmailDraft", back_populates="job_listing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JobListing id={self.id} role={self.role_title!r} score={self.score}>"


class EmailDraft(Base):
    """A Gemini-generated cold email draft for a job listing."""

    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization_notes: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False, index=True
    )  # draft | approved | sent | skipped
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    job_listing: Mapped[JobListing] = relationship("JobListing", back_populates="email_drafts")

    def __repr__(self) -> str:
        return f"<EmailDraft id={self.id} status={self.status!r}>"


class SentLog(Base):
    """Immutable audit log of every email actually sent (or dry-run logged)."""

    __tablename__ = "sent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_draft_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("email_drafts.id", ondelete="SET NULL"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<SentLog id={self.id} company={self.company_name!r} sent_at={self.sent_at}>"
