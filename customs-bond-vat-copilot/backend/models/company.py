"""
Company Model — Bonded Warehouse / Factory Information
কাস্টমস বন্ড কোম্পানির তথ্য
"""

from datetime import datetime
from sqlalchemy import String, Float, Date, DateTime, Text, Integer, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


class BondType(str, enum.Enum):
    GARMENTS = "garments"           # পোশাক শিল্প
    TEXTILE = "textile"             # টেক্সটাইল
    ELECTRONICS = "electronics"     # ইলেকট্রনিক্স
    PHARMACEUTICAL = "pharmaceutical" # ওষুধ
    FOOTWEAR = "footwear"           # জুতা
    LEATHER = "leather"             # চামড়া
    CHEMICAL = "chemical"           # রাসায়নিক
    FOOD_PROCESSING = "food_processing" # খাদ্য প্রক্রিয়াজাত
    OTHER = "other"


class Company(Base):
    """
    বন্ড কোম্পানির তথ্য টেবিল
    
    প্রতিটি অডিট এই কোম্পানির সাথে সম্পর্কিত।
    এক কোম্পানির একাধিক অডিট সেশন থাকতে পারে।
    """
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # === মূল তথ্য ===
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    name_bengali: Mapped[str] = mapped_column(String(500), nullable=True)
    bond_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    bond_type: Mapped[str] = mapped_column(Enum(BondType), default=BondType.GARMENTS)
    
    # === নিবন্ধন তথ্য ===
    tin_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    bin_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    erc_number: Mapped[str] = mapped_column(String(100), nullable=True)  # Export RC
    irc_number: Mapped[str] = mapped_column(String(100), nullable=True)  # Import RC
    
    # === বন্ড লাইসেন্স ===
    bond_license_number: Mapped[str] = mapped_column(String(100), nullable=True)
    bond_license_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    bond_license_expiry: Mapped[datetime] = mapped_column(Date, nullable=True)
    bonding_authority: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === বন্ডিং ক্যাপাসিটি ===
    bonding_capacity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    bonding_capacity_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    
    # === ঠিকানা ===
    factory_address: Mapped[str] = mapped_column(Text, nullable=True)
    bonded_warehouse_address: Mapped[str] = mapped_column(Text, nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True)
    customs_zone: Mapped[str] = mapped_column(String(200), nullable=True)
    customs_station: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === যোগাযোগ ===
    contact_person: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # === উৎপাদন ক্ষমতা ===
    annual_production_capacity: Mapped[float] = mapped_column(Float, nullable=True)
    production_unit: Mapped[str] = mapped_column(String(50), nullable=True)
    main_product: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # === ব্যাংক তথ্য ===
    bank_name: Mapped[str] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # === Status ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_profile: Mapped[str] = mapped_column(String(20), default="medium")
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # === Relationships ===
    audit_sessions = relationship("AuditSession", back_populates="company")
    
    def __repr__(self):
        return f"<Company {self.name} | Bond: {self.bond_number}>"
