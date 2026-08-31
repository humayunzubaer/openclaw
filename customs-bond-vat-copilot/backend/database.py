"""
Customs Bond Audit Intelligence Platform
ডেটাবেস কানেকশন ম্যানেজার
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from utils.logger import logger
from typing import Generator
from config import settings


# === Base Model Class ===
class Base(DeclarativeBase):
    """সকল Model-এর Base Class"""
    pass


# === Database Engine তৈরি ===
def create_db_engine():
    """SQLite Database Engine তৈরি করো"""
    
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }
    
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        connect_args=connect_args,
        poolclass=StaticPool,  # SQLite এর জন্য উপযুক্ত
    )
    
    # SQLite Performance Optimization
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # WAL Mode — দ্রুত Read/Write
        cursor.execute("PRAGMA journal_mode=WAL")
        # Foreign Key Constraint চালু
        cursor.execute("PRAGMA foreign_keys=ON")
        # Cache Size বাড়াও (64MB)
        cursor.execute("PRAGMA cache_size=-65536")
        # Temp Store RAM এ
        cursor.execute("PRAGMA temp_store=MEMORY")
        # মেমরি ম্যাপ সাইজ
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()
    
    return engine


engine = create_db_engine()

# === Session Factory ===
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# === Database Session Dependency ===
def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency — Database Session দেয়"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_database():
    """Database এবং সকল Table তৈরি করো"""
    from models import (
        company, user_model, audit_session,
        import_data, entitlement, hs_master,
        knowledge, risk_finding
    )
    
    logger.info("ডেটাবেস ইনিশিয়ালাইজ হচ্ছে...")
    Base.metadata.create_all(bind=engine)
    logger.success("✅ ডেটাবেস সফলভাবে তৈরি হয়েছে")
    
    # Initial data seed করো
    _seed_initial_data()


def _seed_initial_data():
    """প্রথমবার চালানোর সময় Initial Data লোড করো"""
    db = SessionLocal()
    try:
        from models.user_model import User
        from models.hs_master import HsMaster
        
        # Default Admin User
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            admin = User(
                username="admin",
                full_name="System Administrator",
                email="admin@auditplatform.local",
                hashed_password=pwd_context.hash("admin123"),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            logger.info("✅ Default Admin User তৈরি হয়েছে (admin/admin123)")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Initial data seed error: {e}")
        db.rollback()
    finally:
        db.close()


def backup_database(backup_path: str = None):
    """Database Backup করো"""
    import shutil
    from datetime import datetime
    from pathlib import Path
    from config import BACKUP_DIR
    
    if not backup_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(BACKUP_DIR / f"audit_platform_backup_{timestamp}.db")
    
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    shutil.copy2(db_path, backup_path)
    logger.success(f"✅ Database Backup সম্পন্ন: {backup_path}")
    return backup_path


def get_db_stats() -> dict:
    """Database Statistics"""
    db = SessionLocal()
    try:
        with engine.connect() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()
            
            stats = {"tables": {}}
            for table in tables:
                table_name = table[0]
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
                stats["tables"][table_name] = count
            
            # DB Size
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            import os
            if os.path.exists(db_path):
                stats["size_mb"] = round(os.path.getsize(db_path) / 1024 / 1024, 2)
            
            return stats
    finally:
        db.close()
