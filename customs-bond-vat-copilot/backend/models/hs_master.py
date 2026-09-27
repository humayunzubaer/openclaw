"""
HS Master Model — HS কোড ডেটাবেস
"""

from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class HsMaster(Base):
    """
    HS কোড মাস্টার টেবিল
    
    বাংলাদেশ কাস্টমসের সম্পূর্ণ HS কোড তালিকা।
    শুল্ক হার, ভ্যাট, এবং বিধিনিষেধ সংরক্ষণ করে।
    """
    __tablename__ = "hs_master"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # === HS কোড ===
    hs_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    chapter: Mapped[str] = mapped_column(String(10), nullable=True, index=True)   # প্রথম ২ সংখ্যা
    heading: Mapped[str] = mapped_column(String(10), nullable=True)               # প্রথম ৪ সংখ্যা
    subheading: Mapped[str] = mapped_column(String(10), nullable=True)            # প্রথম ৬ সংখ্যা
    
    # === বিবরণ ===
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_bn: Mapped[str] = mapped_column(Text, nullable=True)
    common_name: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === শুল্ক হার ===
    cd_rate: Mapped[float] = mapped_column(Float, default=0.0)   # Customs Duty
    rd_rate: Mapped[float] = mapped_column(Float, default=0.0)   # Regulatory Duty
    sd_rate: Mapped[float] = mapped_column(Float, default=0.0)   # Supplementary Duty
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0) # VAT
    at_rate: Mapped[float] = mapped_column(Float, default=5.0)   # Advance Tax
    ait_rate: Mapped[float] = mapped_column(Float, default=5.0)  # Advance Income Tax
    
    # === বিধিনিষেধ ===
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_prohibited: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_permit: Mapped[bool] = mapped_column(Boolean, default=False)
    permit_authority: Mapped[str] = mapped_column(String(300), nullable=True)
    
    # === বন্ড সম্পর্কিত ===
    bond_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    common_in_garments: Mapped[bool] = mapped_column(Boolean, default=False)
    common_in_textile: Mapped[bool] = mapped_column(Boolean, default=False)
    common_in_pharma: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # === SRO Reference ===
    sro_reference: Mapped[str] = mapped_column(String(500), nullable=True)
    sro_duty_rate: Mapped[float] = mapped_column(Float, nullable=True)
    sro_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # === Unit ===
    standard_unit: Mapped[str] = mapped_column(String(30), nullable=True)
    alternative_units: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === Version ===
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), nullable=True)  # e.g., "2024"
    
    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    @property
    def total_tax_rate(self) -> float:
        """মোট করের হার"""
        return self.cd_rate + self.rd_rate + self.vat_rate + self.at_rate + self.ait_rate
    
    def __repr__(self):
        return f"<HsMaster {self.hs_code} | {self.description_en[:40]}>"
