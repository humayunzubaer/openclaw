"""
Knowledge Base Models — Audit Brain এর স্মৃতি
এই টেবিলগুলোতে সফটওয়্যার শেখা জ্ঞান সংরক্ষণ করে।
"""

from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, Text, Integer, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class CommercialDictionary(Base):
    """
    বাণিজ্যিক নাম অভিধান
    
    একই পণ্য বিভিন্ন নামে আমদানি হয়।
    যেমন: "Polyester Fabric" = "PE Fabric" = "পলিয়েস্টার কাপড়"
    Audit Brain এই ম্যাপিং শেখে ও সংরক্ষণ করে।
    """
    __tablename__ = "commercial_dictionary"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # === নাম ===
    commercial_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    standard_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    name_bengali: Mapped[str] = mapped_column(String(500), nullable=True)

    # === শ্রেণীবিভাগ ===
    hs_code: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    cluster: Mapped[str] = mapped_column(String(200), nullable=True, index=True)
    sub_cluster: Mapped[str] = mapped_column(String(200), nullable=True)
    material_type: Mapped[str] = mapped_column(String(100), nullable=True)
    # raw_material | packing_material | accessories | chemical | finished_goods

    # === একক ===
    standard_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    # === শিল্প ===
    industry: Mapped[str] = mapped_column(String(100), nullable=True, index=True)

    # === শেখার তথ্য ===
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    # manual | learned | imported | ai_suggested
    verified_by_user: Mapped[bool] = mapped_column(Boolean, default=False)

    # === Embedding Reference ===
    embedding_id: Mapped[int] = mapped_column(Integer, nullable=True)

    # === Timestamps ===
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_comm_dict_norm_hs", "normalized_name", "hs_code"),
    )

    def __repr__(self):
        return f"<CommercialDict {self.commercial_name} → {self.standard_name}>"


class ClusterMaster(Base):
    """
    ক্লাস্টার মাস্টার
    
    পণ্যকে গোষ্ঠীবদ্ধ করে বিশ্লেষণ সহজ করে।
    যেমন: Fabric Cluster, Accessories Cluster, Chemical Cluster
    """
    __tablename__ = "cluster_master"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    cluster_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    cluster_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cluster_name_bn: Mapped[str] = mapped_column(String(200), nullable=True)
    parent_cluster: Mapped[str] = mapped_column(String(50), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True, index=True)

    # HS Ranges (comma separated, e.g. "5208,5209,5210")
    hs_prefixes: Mapped[str] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)

    material_type: Mapped[str] = mapped_column(String(100), nullable=True)
    default_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    # Risk Profile
    risk_weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False)

    item_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Cluster {self.cluster_code} | {self.cluster_name}>"


class UnitConversion(Base):
    """
    একক রূপান্তর টেবিল
    
    বিভিন্ন এককের মধ্যে রূপান্তর।
    কিছু রূপান্তর পণ্য-নির্দিষ্ট (যেমন GSM অনুযায়ী কাপড়ের ওজন)।
    """
    __tablename__ = "unit_conversions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    from_unit: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    to_unit: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    factor: Mapped[float] = mapped_column(Float, nullable=False)

    # Item-specific conversion (optional)
    hs_code: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    item_name: Mapped[str] = mapped_column(String(500), nullable=True)
    cluster: Mapped[str] = mapped_column(String(200), nullable=True)

    # Formula-based conversion (e.g. YDS→KG needs GSM & width)
    formula: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="standard")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("from_unit", "to_unit", "hs_code", name="uq_unit_conv"),
    )

    def __repr__(self):
        return f"<UnitConv {self.from_unit}→{self.to_unit} = {self.factor}>"


class AuditRule(Base):
    """
    অডিট রুল ইঞ্জিন
    
    Level-1 AI (Rule Engine) এর নিয়মাবলী।
    প্রতিটি রুল একটি নির্দিষ্ট অসঙ্গতি শনাক্ত করে।
    """
    __tablename__ = "audit_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    rule_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(300), nullable=False)
    rule_name_bn: Mapped[str] = mapped_column(String(300), nullable=True)

    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # import | consumption | export | inventory | general

    category: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # === Rule Logic ===
    condition_type: Mapped[str] = mapped_column(String(50), nullable=True)
    # threshold | comparison | existence | pattern | formula
    condition_expression: Mapped[str] = mapped_column(Text, nullable=True)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=True)
    threshold_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    # === Output ===
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    # critical | high | medium | low | info
    risk_score: Mapped[float] = mapped_column(Float, default=0.5)

    finding_template: Mapped[str] = mapped_column(Text, nullable=True)
    observation_template: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation_template: Mapped[str] = mapped_column(Text, nullable=True)

    # === Legal Reference ===
    law_reference: Mapped[str] = mapped_column(String(500), nullable=True)
    section_reference: Mapped[str] = mapped_column(String(300), nullable=True)
    sro_reference: Mapped[str] = mapped_column(String(500), nullable=True)
    penalty_reference: Mapped[str] = mapped_column(String(500), nullable=True)

    # === Revenue Calculation ===
    has_revenue_impact: Mapped[bool] = mapped_column(Boolean, default=False)
    revenue_formula: Mapped[str] = mapped_column(Text, nullable=True)

    # === Meta ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_order: Mapped[int] = mapped_column(Integer, default=100)
    times_triggered: Mapped[int] = mapped_column(Integer, default=0)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(50), default="builtin")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<AuditRule {self.rule_code} | {self.rule_name[:40]}>"


class LawDatabase(Base):
    """
    আইন ডেটাবেস
    
    Customs Act, VAT Act এর প্রাসঙ্গিক ধারা।
    """
    __tablename__ = "law_database"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    law_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    law_name_bn: Mapped[str] = mapped_column(String(300), nullable=True)
    law_year: Mapped[str] = mapped_column(String(10), nullable=True)

    section_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sub_section: Mapped[str] = mapped_column(String(50), nullable=True)
    clause: Mapped[str] = mapped_column(String(50), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=True)
    title_bn: Mapped[str] = mapped_column(String(500), nullable=True)
    text_en: Mapped[str] = mapped_column(Text, nullable=True)
    text_bn: Mapped[str] = mapped_column(Text, nullable=True)

    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    # penalty | duty | procedure | bond | offence

    applies_to: Mapped[str] = mapped_column(String(200), nullable=True)
    penalty_min: Mapped[float] = mapped_column(Float, nullable=True)
    penalty_max: Mapped[float] = mapped_column(Float, nullable=True)
    penalty_multiplier: Mapped[float] = mapped_column(Float, nullable=True)
    penalty_description: Mapped[str] = mapped_column(Text, nullable=True)

    keywords: Mapped[str] = mapped_column(Text, nullable=True)
    embedding_id: Mapped[int] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Law {self.law_name} §{self.section_number}>"


class SRODatabase(Base):
    """
    SRO (Statutory Regulatory Order) ডেটাবেস
    """
    __tablename__ = "sro_database"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    sro_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sro_date: Mapped[date] = mapped_column(Date, nullable=True)
    sro_year: Mapped[str] = mapped_column(String(10), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(1000), nullable=True)
    title_bn: Mapped[str] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=True)

    issuing_authority: Mapped[str] = mapped_column(String(300), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    # duty_exemption | bond | vat | procedure

    # HS scope
    applicable_hs_codes: Mapped[str] = mapped_column(Text, nullable=True)
    applicable_industries: Mapped[str] = mapped_column(String(500), nullable=True)

    # Rates
    exempted_duty_rate: Mapped[float] = mapped_column(Float, nullable=True)
    exempted_vat_rate: Mapped[float] = mapped_column(Float, nullable=True)
    conditions: Mapped[str] = mapped_column(Text, nullable=True)

    # Amendments
    amends_sro: Mapped[str] = mapped_column(String(100), nullable=True)
    amended_by_sro: Mapped[str] = mapped_column(String(100), nullable=True)
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)

    effective_from: Mapped[date] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=True)
    embedding_id: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<SRO {self.sro_number} | {self.sro_date}>"


class YieldDatabase(Base):
    """
    ইল্ড / Input-Output Coefficient ডেটাবেস
    
    কোন কাঁচামাল থেকে কত পরিমাণ পণ্য উৎপাদন হয়।
    Module-2 (Consumption) এর জন্য মূল ভিত্তি।
    """
    __tablename__ = "yield_database"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    industry: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_category: Mapped[str] = mapped_column(String(200), nullable=True)

    finished_good: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    finished_good_hs: Mapped[str] = mapped_column(String(20), nullable=True)
    fg_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    raw_material: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    raw_material_hs: Mapped[str] = mapped_column(String(20), nullable=True)
    rm_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    # Coefficient: কত RM লাগে ১ একক FG তৈরিতে
    consumption_coefficient: Mapped[float] = mapped_column(Float, nullable=False)
    min_coefficient: Mapped[float] = mapped_column(Float, nullable=True)
    max_coefficient: Mapped[float] = mapped_column(Float, nullable=True)

    # Wastage
    standard_wastage_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_wastage_pct: Mapped[float] = mapped_column(Float, nullable=True)
    scrap_recovery_pct: Mapped[float] = mapped_column(Float, default=0.0)

    yield_pct: Mapped[float] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(100), default="learned")
    # approved | learned | industry_standard | sro
    approval_reference: Mapped[str] = mapped_column(String(300), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)

    notes: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Yield {self.raw_material}→{self.finished_good} = {self.consumption_coefficient}>"


class LearningHistory(Base):
    """
    শিক্ষণ ইতিহাস
    
    "Train Audit Brain" বাটন চাপলে কী কী শেখা হলো তার রেকর্ড।
    """
    __tablename__ = "learning_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    audit_session_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)

    learning_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # commercial_name | hs_code | cluster | unit | yield | rule | decision

    entity_before: Mapped[str] = mapped_column(Text, nullable=True)
    entity_after: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    items_learned: Mapped[int] = mapped_column(Integer, default=0)
    confidence_gain: Mapped[float] = mapped_column(Float, nullable=True)

    triggered_by: Mapped[str] = mapped_column(String(50), default="auto")
    # auto | manual | user_correction

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Learning {self.learning_type} | {self.items_learned} items>"
