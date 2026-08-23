"""
Entitlement Models — এন্টাইটেলমেন্ট / অনুমোদিত আমদানি তালিকা
"""

from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Entitlement(Base):
    """
    এন্টাইটেলমেন্ট হেডার টেবিল
    
    প্রতিটি অডিট পিরিয়ডের জন্য অনুমোদিত আমদানির তালিকা।
    কাস্টমস কর্তৃপক্ষ কর্তৃক অনুমোদিত।
    """
    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    audit_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_sessions.id"), nullable=False, index=True
    )
    
    # === সনদ তথ্য ===
    entitlement_number: Mapped[str] = mapped_column(String(200), nullable=True)
    entitlement_date: Mapped[date] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date] = mapped_column(Date, nullable=True)
    issuing_authority: Mapped[str] = mapped_column(String(300), nullable=True)
    
    # === পণ্যের বিবরণ ===
    product_category: Mapped[str] = mapped_column(String(200), nullable=True)
    main_product: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === Source File ===
    source_file: Mapped[str] = mapped_column(String(500), nullable=True)
    source_sheet: Mapped[str] = mapped_column(String(200), nullable=True)
    upload_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # === Status ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    audit_session = relationship("AuditSession", back_populates="entitlements")
    items = relationship("EntitlementItem", back_populates="entitlement", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Entitlement {self.entitlement_number}>"


class EntitlementItem(Base):
    """
    এন্টাইটেলমেন্ট আইটেম টেবিল
    
    প্রতিটি অনুমোদিত পণ্যের বিস্তারিত তথ্য।
    এক এন্টাইটেলমেন্টে একাধিক আইটেম থাকতে পারে।
    """
    __tablename__ = "entitlement_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    entitlement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entitlements.id"), nullable=False, index=True
    )
    
    # === HS কোড ===
    hs_code: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    hs_description: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === পণ্যের নাম ===
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    commercial_name: Mapped[str] = mapped_column(String(500), nullable=True)
    standard_name: Mapped[str] = mapped_column(String(500), nullable=True)  # AI resolved
    
    # === পরিমাণ ও মূল্য ===
    approved_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    unit_price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    approved_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    approved_value_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === শুল্ক হার ===
    duty_rate: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    at_rate: Mapped[float] = mapped_column(Float, default=5.0)
    rd_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sd_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === Cluster / Category ===
    cluster: Mapped[str] = mapped_column(String(200), nullable=True)
    sub_cluster: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === AI Analysis ===
    hs_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    hs_verified_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    hs_match_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    hs_mismatch_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    name_match_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    
    # === Actual vs Approved ===
    actual_imported_qty: Mapped[float] = mapped_column(Float, default=0.0)
    excess_import_qty: Mapped[float] = mapped_column(Float, default=0.0)
    excess_import_pct: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === Row Info ===
    row_number: Mapped[int] = mapped_column(Integer, nullable=True)
    serial_no: Mapped[str] = mapped_column(String(20), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    entitlement = relationship("Entitlement", back_populates="items")
    
    def __repr__(self):
        return f"<EntitlementItem {self.hs_code} | {self.item_name[:30]}>"
