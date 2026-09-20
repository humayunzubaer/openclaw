"""
Customs Bond Audit Intelligence Platform
কনফিগারেশন ম্যানেজার
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

# === Root Paths ===
ROOT_DIR = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent
DATABASE_DIR = ROOT_DIR / "database"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge_base"
MODELS_DIR = ROOT_DIR / "local_models"
LOGS_DIR = ROOT_DIR / "logs"
BACKUP_DIR = ROOT_DIR / "backup"
CONFIG_DIR = ROOT_DIR / "config"

# Directories তৈরি করো যদি না থাকে
for d in [DATABASE_DIR, KNOWLEDGE_DIR, MODELS_DIR, LOGS_DIR, BACKUP_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """প্ল্যাটফর্মের সকল সেটিংস"""

    # === Application ===
    APP_NAME: str = "Customs Bond Audit Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    APP_BUILD: str = "2025.01"
    DEBUG: bool = False

    # === Server ===
    HOST: str = "127.0.0.1"
    PORT: int = 8765
    RELOAD: bool = False

    # === Database ===
    DATABASE_URL: str = f"sqlite:///{DATABASE_DIR}/audit_platform.db"
    DATABASE_ECHO: bool = False
    # ভবিষ্যতে PostgreSQL এর জন্য:
    # DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/auditdb"

    # === Security ===
    SECRET_KEY: str = "customs-bond-audit-secret-key-change-in-production-2025"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # ৮ ঘণ্টা

    # === Encryption ===
    DB_ENCRYPTION_KEY: Optional[str] = None  # SQLite Encryption

    # === File Upload ===
    MAX_UPLOAD_SIZE_MB: int = 100
    UPLOAD_DIR: str = str(ROOT_DIR / "uploads")
    ALLOWED_EXTENSIONS: list = [
        ".xlsx", ".xls", ".csv",
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff",
        ".docx", ".doc"
    ]

    # === OCR Settings ===
    OCR_ENGINE: str = "tesseract"  # tesseract | easyocr | paddleocr
    OCR_LANGUAGE: str = "ben+eng"  # Bengali + English
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # === AI Settings ===
    # Level 1: Rule Engine
    RULE_ENGINE_ENABLED: bool = True

    # Level 2: Local AI
    LOCAL_AI_ENABLED: bool = True
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    FAISS_INDEX_PATH: str = str(MODELS_DIR / "faiss_index")

    # Level 3: Ollama
    OLLAMA_ENABLED: bool = False
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"  # ছোট মডেল, কম RAM লাগে
    OLLAMA_TIMEOUT: int = 120

    # Cloud AI (শুধু User Enable করলে)
    CLOUD_AI_ENABLED: bool = False
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # === Knowledge Base ===
    KNOWLEDGE_BASE_DIR: str = str(KNOWLEDGE_DIR)
    AUTO_LEARN: bool = True  # Audit শেষে স্বয়ংক্রিয়ভাবে শিখবে

    # === Risk Thresholds ===
    RISK_HIGH_THRESHOLD: float = 0.7
    RISK_MEDIUM_THRESHOLD: float = 0.4
    EXCESS_IMPORT_TOLERANCE: float = 0.05  # ৫% tolerance
    CONSUMPTION_DEVIATION_THRESHOLD: float = 0.10  # ১০% deviation

    # === Reporting ===
    REPORT_LOGO_PATH: str = str(CONFIG_DIR / "logo.png")
    REPORT_FOOTER: str = "Customs Bond Audit Intelligence Platform"
    REPORT_OUTPUT_DIR: str = str(ROOT_DIR / "reports")

    # === Logging ===
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(LOGS_DIR / "audit_platform.log")
    LOG_ROTATION: str = "10 MB"

    # === Backup ===
    AUTO_BACKUP: bool = True
    BACKUP_DIR_PATH: str = str(BACKUP_DIR)
    BACKUP_KEEP_DAYS: int = 30

    @field_validator("UPLOAD_DIR", "REPORT_OUTPUT_DIR")
    @classmethod
    def create_dir(cls, v):
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

    class Config:
        env_file = str(CONFIG_DIR / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# === VAT & Customs Constants (Bangladesh) ===
VAT_RATE = 15.0          # Standard VAT Rate
AIT_RATE = 5.0           # Advance Income Tax
AT_RATE = 5.0            # Advance Tax
RD_RATE = 3.0            # Regulatory Duty (varies)
SD_RATE_DEFAULT = 0.0    # Supplementary Duty (item specific)

# === Import Bill Types ===
BILL_TYPE_IM4 = "IM-4"    # Against Entitlement
BILL_TYPE_IM7 = "IM-7"    # Amendment

# === Audit Status ===
AUDIT_STATUS_DRAFT = "draft"
AUDIT_STATUS_IN_PROGRESS = "in_progress"
AUDIT_STATUS_REVIEW = "review"
AUDIT_STATUS_COMPLETED = "completed"
AUDIT_STATUS_CLOSED = "closed"

# === Risk Levels ===
RISK_CRITICAL = "critical"
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"
RISK_INFO = "info"

# === Finding Types ===
FINDING_EXCESS_IMPORT = "excess_import"
FINDING_UNAUTHORIZED_HS = "unauthorized_hs"
FINDING_UNDERPAID_DUTY = "underpaid_duty"
FINDING_EXCESS_CONSUMPTION = "excess_consumption"
FINDING_NEGATIVE_STOCK = "negative_stock"
FINDING_EXPORT_MISMATCH = "export_mismatch"
FINDING_BOM_VIOLATION = "bom_violation"
FINDING_YIELD_ANOMALY = "yield_anomaly"

# === Unit Types ===
UNIT_KG = "KG"
UNIT_MT = "MT"
UNIT_LTR = "LTR"
UNIT_PCS = "PCS"
UNIT_DOZEN = "DOZ"
UNIT_YARD = "YRD"
UNIT_METER = "MTR"

# Unit Conversion Table
UNIT_CONVERSIONS = {
    ("MT", "KG"): 1000,
    ("KG", "MT"): 0.001,
    ("LTR", "ML"): 1000,
    ("ML", "LTR"): 0.001,
    ("DOZ", "PCS"): 12,
    ("PCS", "DOZ"): 1/12,
    ("YRD", "MTR"): 0.9144,
    ("MTR", "YRD"): 1.0936,
}
