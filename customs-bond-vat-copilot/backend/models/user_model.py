"""
User Model — Authentication & Authorization
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    AUDITOR = "auditor"           # পূর্ণ অ্যাক্সেস
    SENIOR_AUDITOR = "senior_auditor"
    SUPERVISOR = "supervisor"     # রিভিউ করতে পারবেন
    VIEWER = "viewer"             # শুধু দেখতে পারবেন


class User(Base):
    """
    ব্যবহারকারী টেবিল
    
    সিস্টেমের সকল ব্যবহারকারীর তথ্য সংরক্ষণ করে।
    Role-based access control নিশ্চিত করে।
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    designation: Mapped[str] = mapped_column(String(200), nullable=True)
    department: Mapped[str] = mapped_column(String(200), nullable=True)
    
    # Security
    hashed_password: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(UserRole), 
        default=UserRole.AUDITOR,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Preferences
    theme: Mapped[str] = mapped_column(String(20), default="dark")
    language: Mapped[str] = mapped_column(String(10), default="bn")  # Bengali
    
    # Relationships
    audit_sessions = relationship("AuditSession", back_populates="created_by_user")
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
