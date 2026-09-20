"""
Audit Session Model — অডিট সেশন ব্যবস্থাপনা
"""

from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, Text, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class AuditSession(Base):
    """
    অডিট সেশন টেবিল
    
    প্রতিটি অডিট একটি Session হিসেবে ট্র্যাক করা হয়।
    একই কোম্পানির বিভিন্ন বছরের অডিট আলাদা Session।
    """
    __tablename__ = "audit_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # === সম্পর্ক ===
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    
    # === অডিট পিরিয়ড ===
    audit_year: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., "2023-24"
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    
    # === অডিট তথ্য ===
    audit_number: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    audit_type: Mapped[str] = mapped_column(String(50), default="annual")
    # annual | special | re_audit | follow_up
    
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft | in_progress | review | completed | closed
    
    # === অডিট অফিসার ===
    lead_auditor: Mapped[str] = mapped_column(String(200), nullable=True)
    team_members: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string
    supervisor: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === তারিখ ===
    audit_start_date: Mapped[date] = mapped_column(Date, nullable=True)
    audit_end_date: Mapped[date] = mapped_column(Date, nullable=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=True)
    
    # === ফাইল তথ্য ===
    entitlement_file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    ais_import_file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === Summary Statistics (computed) ===
    total_import_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_import_value_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    total_export_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_findings: Mapped[int] = mapped_column(Integer, default=0)
    total_risk_flags: Mapped[int] = mapped_column(Integer, default=0)
    
    # === Revenue Impact ===
    total_duty_short: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat_short: Mapped[float] = mapped_column(Float, default=0.0)
    total_penalty_proposed: Mapped[float] = mapped_column(Float, default=0.0)
    total_revenue_impact: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === AI Analysis ===
    ai_risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=True)
    analysis_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # === Notes ===
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # === Relationships ===
    company = relationship("Company", back_populates="audit_sessions")
    created_by_user = relationship("User", back_populates="audit_sessions")
    entitlements = relationship("Entitlement", back_populates="audit_session")
    import_bills = relationship("ImportBill", back_populates="audit_session")
    risk_flags = relationship("RiskFlag", back_populates="audit_session")
    findings = relationship("AuditFinding", back_populates="audit_session")
    
    @property
    def period_display(self):
        return f"{self.period_from.strftime('%d/%m/%Y')} — {self.period_to.strftime('%d/%m/%Y')}"
    
    def __repr__(self):
        return f"<AuditSession {self.audit_number} | {self.audit_year}>"
