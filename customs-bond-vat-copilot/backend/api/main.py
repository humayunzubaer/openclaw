"""
FastAPI সার্ভার — Customs Bond Audit Intelligence Platform
==========================================================

Module 1 (Import Intelligence) engine-কে একটি চলমান অ্যাপ হিসেবে প্রকাশ করে:
আপলোড করা প্রাপ্যতা শীট + আমদানি (AIS/MIS) → ImportAnalysisEngine → ফলাফল
(৫টি দাবিসহ সারসংক্ষেপ) + ঐচ্ছিক Excel কার্যপত্র।

একই process-এ static UI (api/static/) পরিবেশন করে — শুধু একটি কমান্ড:
    cd backend && uvicorn api.main:app --host 0.0.0.0 --port 4800

সব লোকাল; কোনো ডেটা ইন্টারনেটে যায় না।
"""
from __future__ import annotations

import tempfile
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.data_loader import DataLoader
from services.import_analysis import ImportAnalysisEngine
from services.report_writer import write_report
from utils.logger import logger

app = FastAPI(
    title="Customs Bond Audit Intelligence Platform",
    description="বাংলাদেশ কাস্টমস বন্ড ও ভ্যাট অডিট — Module 1 (Import Intelligence)",
    version="1.0.0",
)

# লোকাল LAN/Tailscale-এ ফোন/অন্য ডিভাইস থেকে অ্যাক্সেসের জন্য
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


# ----------------------------------------------------------
def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s or not s.strip():
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise HTTPException(400, f"তারিখ পড়া যায়নি: '{s}' (গ্রহণযোগ্য: YYYY-MM-DD)")


async def _save_upload(up: UploadFile, tmpdir: str) -> str:
    """আপলোড ফাইল temp-এ সংরক্ষণ করে path ফেরত দেয়"""
    suffix = Path(up.filename or "upload.xlsx").suffix or ".xlsx"
    dest = Path(tmpdir) / f"{Path(up.filename or 'upload').stem}{suffix}"
    dest.write_bytes(await up.read())
    return str(dest)


def _run_engine(
    ent_path: str,
    imp_path: str,
    local_path: Optional[str],
    next_entitlement_date: Optional[date],
    bond_license_capacity_mt: float,
    warehouse_capacity_mt: float,
    extension_applies: bool = False,
):
    """ফাইল লোড করে ImportAnalysisEngine চালায়; (result, dl, meta) ফেরত দেয়"""
    dl = DataLoader(verbose=False)
    entitlements = dl.load_entitlement(ent_path)
    if not entitlements:
        raise HTTPException(422, "প্রাপ্যতা শীটে কোনো সারি পাওয়া যায়নি — ফাইল/শীট যাচাই করুন।")
    imports = dl.load_imports(imp_path)

    local_purchases = None
    if local_path:
        try:
            local_purchases = dl.load_imports(local_path)
            for lp in local_purchases:
                lp.source_type = "local_purchase"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"স্থানীয় ক্রয় ফাইল পড়া যায়নি: {e}")

    engine = ImportAnalysisEngine(
        entitlements,
        imports,
        local_purchases=local_purchases,
        next_entitlement_date=next_entitlement_date,
        bond_license_capacity_mt=bond_license_capacity_mt or 0.0,
        warehouse_capacity_mt=warehouse_capacity_mt or 0.0,
        extension_applies=extension_applies,
        bonding_capacity_value_bdt=dl.bonding_capacity.get("value_bdt", 0.0),
        bonding_capacity_value_usd=dl.bonding_capacity.get("value_usd", 0.0),
    )
    result = engine.analyze()
    meta = {
        "institution": "",
        "period": getattr(dl.period, "entitlement_label", "") if getattr(dl, "period", None) else "",
        "auditor": "",
    }
    return result, dl, meta


def _result_payload(result, dl) -> dict:
    """ফলাফলকে JSON-বান্ধব dict-এ রূপান্তর"""
    return {
        "summary": result.summary,
        "warnings": result.warnings,
        "period": {
            "from": str(dl.period.audit_from) if dl.period.audit_from else None,
            "to": str(dl.period.audit_to) if dl.period.audit_to else None,
            "label": getattr(dl.period, "entitlement_label", ""),
        },
        "records": {
            "excess": [asdict(r) for r in result.excess_records],
            "cluster_excess": [asdict(r) for r in result.cluster_excess_records],
            "unauthorized": [asdict(r) for r in result.unauthorized_records],
            "post_period": [asdict(r) for r in result.post_period_records],
            "rule8": [asdict(r) for r in result.rule8_observations],
            "capacity_breach": [asdict(r) for r in result.capacity_breach_records],
            "capacity_limit": [asdict(r) for r in result.capacity_limit_records],
            "utilization": [asdict(r) for r in result.utilization_records],
            "machinery": [asdict(r) for r in result.machinery_records],
            "unmatched": result.unmatched_imports,
            "low_confidence": result.low_confidence_matches,
        },
    }


# ----------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "module": "import-intelligence", "version": app.version}


@app.post("/api/analyze/import")
async def analyze_import(
    entitlement_file: UploadFile = File(...),
    imports_file: UploadFile = File(...),
    local_file: Optional[UploadFile] = File(None),
    next_entitlement_date: Optional[str] = Form(None),
    bond_license_capacity_mt: float = Form(0.0),
    warehouse_capacity_mt: float = Form(0.0),
    extension_applies: bool = Form(False),
):
    """প্রাপ্যতা + আমদানি বিশ্লেষণ করে ফলাফল (JSON) ফেরত দেয়"""
    nxt = _parse_date(next_entitlement_date)
    with tempfile.TemporaryDirectory() as tmp:
        ent_path = await _save_upload(entitlement_file, tmp)
        imp_path = await _save_upload(imports_file, tmp)
        local_path = await _save_upload(local_file, tmp) if local_file else None
        try:
            result, dl, _ = _run_engine(
                ent_path, imp_path, local_path, nxt,
                bond_license_capacity_mt, warehouse_capacity_mt, extension_applies,
            )
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"বিশ্লেষণ ব্যর্থ: {e}")
            raise HTTPException(500, f"বিশ্লেষণ ব্যর্থ: {e}")
        return JSONResponse(_result_payload(result, dl))


@app.post("/api/analyze/import/xlsx")
async def analyze_import_xlsx(
    entitlement_file: UploadFile = File(...),
    imports_file: UploadFile = File(...),
    local_file: Optional[UploadFile] = File(None),
    next_entitlement_date: Optional[str] = Form(None),
    bond_license_capacity_mt: float = Form(0.0),
    warehouse_capacity_mt: float = Form(0.0),
    extension_applies: bool = Form(False),
):
    """একই বিশ্লেষণ; ১০-শীট Excel কার্যপত্র (.xlsx) ডাউনলোড হিসেবে ফেরত দেয়"""
    nxt = _parse_date(next_entitlement_date)
    tmp = tempfile.mkdtemp()
    ent_path = await _save_upload(entitlement_file, tmp)
    imp_path = await _save_upload(imports_file, tmp)
    local_path = await _save_upload(local_file, tmp) if local_file else None
    try:
        result, _, meta = _run_engine(
            ent_path, imp_path, local_path, nxt,
            bond_license_capacity_mt, warehouse_capacity_mt, extension_applies,
        )
        out = Path(tmp) / "audit_workpaper.xlsx"
        write_report(result, out, meta)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"কার্যপত্র তৈরি ব্যর্থ: {e}")
        raise HTTPException(500, f"কার্যপত্র তৈরি ব্যর্থ: {e}")
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="audit_workpaper.xlsx",
    )


# ---- static frontend (সবার শেষে mount, যাতে /api/* আগে ম্যাচ করে) ----
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    async def _no_ui():
        return "<h1>Customs Bond Audit — API চলছে</h1><p>UI ফাইল পাওয়া যায়নি (api/static/)।</p>"
