"""
Risk & Finding Models — ঝুঁকি ও অডিট আপত্তি
Explainable AI — প্রতিটি Finding এর ব্যাখ্যা, প্রমাণ ও আইনি ভিত্তি থাকবে।
"""

from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class RiskFlag(Base):
    """
    ঝুঁকি চিহ্ন টেবিল
    
    Rule Engine বা AI যখন কোনো অসঙ্গতি পায়, এখানে Flag তৈরি হয়।
    এটি Finding এর কাঁচামাল।
    """
    __tablename__ = "risk_flags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    audit_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_sessions.id"), nullable=False, index=True
    )

    # === উৎস ===
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # import | consumption | export | inventory

    rule_code: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    detection_level: Mapped[str] = mapped_column(String(20), default="rule")
    # rule (L1) | local_ai (L2) | cloud_ai (L3)

    # === সংশ্লিষ্ট রেকর্ড ===
    entity_type: Mapped[str] = mapped_column(String(50), nullable=True)
    # import_item | entitlement_item | bill | summary
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    reference_key: Mapped[str] = mapped_column(String(300), nullable=True)

    # === বিবরণ ===
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_bn: Mapped[str] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # === ঝুঁকি ===
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # === পরিমাপ ===
    expected_value: Mapped[float] = mapped_column(Float, nullable=True)
    actual_value: Mapped[float] = mapped_column(Float, nullable=True)
    deviation: Mapped[float] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[float] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)

    # === রাজস্ব প্রভাব ===
    revenue_impact_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    duty_impact: Mapped[float] = mapped_column(Float, default=0.0)
    vat_impact: Mapped[float] = mapped_column(Float, default=0.0)

    # === Explainability ===
    evidence_json: Mapped[str] = mapped_column(Text, nullable=True)   # JSON
    why_detected: Mapped[str] = mapped_column(Text, nullable=True)
    calculation_steps: Mapped[str] = mapped_column(Text, nullable=True)

    # === Review Status ===
    status: Mapped[str] = mapped_column(String(30), default="open")
    # open | accepted | rejected | false_positive | converted_to_finding
    reviewed_by: Mapped[int] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    audit_session = relationship("AuditSession", back_populates="risk_flags")

    def __repr__(self):
        return f"<RiskFlag {self.flag_type} | {self.severity} | {self.title[:40]}>"


class AuditFinding(Base):
    """
    অডিট আপত্তি টেবিল
    
    চূড়ান্ত অডিট আপত্তি — রিপোর্টে যাবে।
    একাধিক RiskFlag একত্রিত হয়ে একটি Finding হতে পারে।
    """
    __tablename__ = "audit_findings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    audit_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_sessions.id"), nullable=False, index=True
    )

    # === পরিচয় ===
    finding_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    para_number: Mapped[str] = mapped_column(String(50), nullable=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    finding_type: Mapped[str] = mapped_column(String(100), nullable=True, index=True)

    # === শিরোনাম ও বিবরণ ===
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    title_bn: Mapped[str] = mapped_column(String(1000), nullable=True)

    observation: Mapped[str] = mapped_column(Text, nullable=True)      # পর্যবেক্ষণ
    observation_bn: Mapped[str] = mapped_column(Text, nullable=True)

    criteria: Mapped[str] = mapped_column(Text, nullable=True)         # মানদণ্ড (আইন)
    condition: Mapped[str] = mapped_column(Text, nullable=True)        # প্রকৃত অবস্থা
    cause: Mapped[str] = mapped_column(Text, nullable=True)            # কারণ
    effect: Mapped[str] = mapped_column(Text, nullable=True)           # প্রভাব
    recommendation: Mapped[str] = mapped_column(Text, nullable=True)   # সুপারিশ
    recommendation_bn: Mapped[str] = mapped_column(Text, nullable=True)

    # === আইনি ভিত্তি ===
    law_reference: Mapped[str] = mapped_column(String(1000), nullable=True)
    section_reference: Mapped[str] = mapped_column(String(500), nullable=True)
    sro_reference: Mapped[str] = mapped_column(String(1000), nullable=True)
    circular_reference: Mapped[str] = mapped_column(String(1000), nullable=True)

    # === রাজস্ব ===
    quantity_involved: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    value_involved_usd: Mapped[float] = mapped_column(Float, default=0.0)
    value_involved_bdt: Mapped[float] = mapped_column(Float, default=0.0)

    duty_short: Mapped[float] = mapped_column(Float, default=0.0)
    vat_short: Mapped[float] = mapped_column(Float, default=0.0)
    at_short: Mapped[float] = mapped_column(Float, default=0.0)
    rd_short: Mapped[float] = mapped_column(Float, default=0.0)
    sd_short: Mapped[float] = mapped_column(Float, default=0.0)
    ait_short: Mapped[float] = mapped_column(Float, default=0.0)
    interest: Mapped[float] = mapped_column(Float, default=0.0)
    penalty: Mapped[float] = mapped_column(Float, default=0.0)
    total_demand: Mapped[float] = mapped_column(Float, default=0.0)

    # === শ্রেণী ===
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.5)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)

    # === প্রমাণ ===
    evidence_json: Mapped[str] = mapped_column(Text, nullable=True)
    linked_flag_ids: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    annexure_reference: Mapped[str] = mapped_column(String(200), nullable=True)
    working_paper_ref: Mapped[str] = mapped_column(String(200), nullable=True)

    # === AI তথ্য ===
    generated_by: Mapped[str] = mapped_column(String(30), default="rule")
    # rule | local_ai | cloud_ai | manual
    ai_explanation: Mapped[str] = mapped_column(Text, nullable=True)

    # === Workflow ===
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # draft | reviewed | approved | issued | settled | dropped
    company_response: Mapped[str] = mapped_column(Text, nullable=True)
    auditor_comment: Mapped[str] = mapped_column(Text, nullable=True)
    is_included_in_report: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=100)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    audit_session = relationship("AuditSession", back_populates="findings")

    def __repr__(self):
        return f"<Finding {self.finding_number} | {self.title[:50]}>"
