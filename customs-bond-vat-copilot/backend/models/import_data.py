"""
Import Data Models — আমদানি বিল (IM-4, IM-7)
"""

from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, Text, Integer, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


class BillType(str, enum.Enum):
    IM4 = "IM-4"   # Against Entitlement
    IM7 = "IM-7"   # Amendment Bill


class ImportBill(Base):
    """
    আমদানি বিল হেডার (IM-4 / IM-7)
    
    AIS (Automated Import System) থেকে আহরিত
    প্রতিটি আমদানির বিল এন্ট্রি।
    """
    __tablename__ = "import_bills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    audit_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_sessions.id"), nullable=False, index=True
    )
    
    # === বিল তথ্য ===
    bill_type: Mapped[str] = mapped_column(Enum(BillType), default=BillType.IM4, nullable=False)
    bill_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=True)
    
    # === সরবরাহকারী তথ্য ===
    supplier_name: Mapped[str] = mapped_column(String(500), nullable=True)
    supplier_country: Mapped[str] = mapped_column(String(100), nullable=True)
    country_of_origin: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # === বন্দর তথ্য ===
    port_of_entry: Mapped[str] = mapped_column(String(200), nullable=True)
    customs_station: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === মূল্য ===
    total_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    exchange_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === শুল্ক ===
    total_duty_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_at_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_rd_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_sd_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_ait_paid: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === Entitlement Reference ===
    entitlement_ref: Mapped[str] = mapped_column(String(200), nullable=True)
    entitlement_number: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === Transport ===
    vessel_name: Mapped[str] = mapped_column(String(200), nullable=True)
    voyage_number: Mapped[str] = mapped_column(String(100), nullable=True)
    bl_number: Mapped[str] = mapped_column(String(200), nullable=True)  # Bill of Lading
    bl_date: Mapped[date] = mapped_column(Date, nullable=True)
    
    # === L/C Information ===
    lc_number: Mapped[str] = mapped_column(String(200), nullable=True)
    lc_date: Mapped[date] = mapped_column(Date, nullable=True)
    lc_bank: Mapped[str] = mapped_column(String(300), nullable=True)
    
    # === Risk ===
    has_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # === Source ===
    source_file: Mapped[str] = mapped_column(String(500), nullable=True)
    source_row: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    audit_session = relationship("AuditSession", back_populates="import_bills")
    items = relationship("ImportItem", back_populates="bill", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ImportBill {self.bill_type} {self.bill_number} | {self.bill_date}>"


class ImportItem(Base):
    """
    আমদানি বিলের আইটেম (Line Items)
    
    প্রতিটি বিলের প্রতিটি পণ্যের বিস্তারিত।
    """
    __tablename__ = "import_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    bill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_bills.id"), nullable=False, index=True
    )
    
    # === HS কোড ===
    hs_code: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    hs_description: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === পণ্যের নাম ===
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    commercial_name: Mapped[str] = mapped_column(String(500), nullable=True)
    standard_name: Mapped[str] = mapped_column(String(500), nullable=True)  # AI resolved
    
    # === পরিমাণ ===
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    std_quantity: Mapped[float] = mapped_column(Float, default=0.0)   # Standardized unit
    std_unit: Mapped[str] = mapped_column(String(30), nullable=True)
    
    # === মূল্য ===
    unit_price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === শুল্ক ===
    duty_rate: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    at_rate: Mapped[float] = mapped_column(Float, default=5.0)
    rd_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sd_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ait_rate: Mapped[float] = mapped_column(Float, default=5.0)
    
    duty_paid: Mapped[float] = mapped_column(Float, default=0.0)
    vat_paid: Mapped[float] = mapped_column(Float, default=0.0)
    at_paid: Mapped[float] = mapped_column(Float, default=0.0)
    rd_paid: Mapped[float] = mapped_column(Float, default=0.0)
    sd_paid: Mapped[float] = mapped_column(Float, default=0.0)
    ait_paid: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === AI Analysis ===
    cluster: Mapped[str] = mapped_column(String(200), nullable=True)
    entitlement_item_id: Mapped[int] = mapped_column(Integer, nullable=True)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    hs_in_entitlement: Mapped[bool] = mapped_column(Boolean, nullable=True)
    name_match_score: Mapped[float] = mapped_column(Float, nullable=True)
    
    # === Risk Flags ===
    unauthorized_hs: Mapped[bool] = mapped_column(Boolean, default=False)
    excess_quantity: Mapped[bool] = mapped_column(Boolean, default=False)
    duty_undervalued: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # === Row Info ===
    row_number: Mapped[int] = mapped_column(Integer, nullable=True)
    serial_no: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bill = relationship("ImportBill", back_populates="items")
    
    def __repr__(self):
        return f"<ImportItem {self.hs_code} | {self.item_name[:30]} | Qty: {self.quantity}>"


class ImportSummary(Base):
    """
    আমদানি সারসংক্ষেপ টেবিল
    
    প্রতিটি Audit Session এর HS Code ভিত্তিক সারসংক্ষেপ।
    Analysis এর জন্য Pre-computed data।
    """
    __tablename__ = "import_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    audit_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_sessions.id"), nullable=False, index=True
    )
    
    hs_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(500), nullable=True)
    commercial_name: Mapped[str] = mapped_column(String(500), nullable=True)
    cluster: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # Aggregated Data
    total_bills: Mapped[int] = mapped_column(Integer, default=0)
    total_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    total_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    total_duty_paid: Mapped[float] = mapped_column(Float, default=0.0)
    total_vat_paid: Mapped[float] = mapped_column(Float, default=0.0)
    
    # vs Entitlement
    approved_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    excess_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Risk
    risk_level: Mapped[str] = mapped_column(String(20), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ImportSummary {self.hs_code} | {self.total_quantity} {self.unit}>"
