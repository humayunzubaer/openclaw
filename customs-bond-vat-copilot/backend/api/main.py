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

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.data_loader import DataLoader
from services.import_analysis import ImportAnalysisEngine
from services.capacity_ledger import BondRegisterReader
from services.bond_register import RegisterDecision
from services.report_writer import write_report
from services.checks.numeric import run_numeric_checks
from services.checks.validity import run_validity_checks
from services.checks.evidence import scan_documents
from services.schedule_checks import (
    check_coefficient_validity, check_up_arithmetic,
)
from services.evidence_paths import (
    audit_route, filter_findings, DOC_LABELS,
)
from services.electricity_consistency import (
    check_electricity_consistency,
    DEFAULT_THRESHOLD_PCT,
)
from knowledge.check_specs import NUMERIC_CHECKS, VALIDITY_CHECKS
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
    register_path: Optional[str] = None,
    provisional_entitlement_date: Optional[date] = None,
    commissioner_extension_days: int = 0,
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

    # ★ বন্ড রেজিস্টার (তফসিল-১) — ইন্টু/এক্স-বন্ড ঘটনাবলি (দাবি ২ প্রবেশক্রম ও দাবি ৩)
    ledger_events = None
    register_decision = None
    if register_path:
        try:
            ledger_events = BondRegisterReader(verbose=False).read(register_path)
            register_decision = RegisterDecision(provided=True, file_path=register_path)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"বন্ড রেজিস্টার পড়া যায়নি: {e}")

    engine = ImportAnalysisEngine(
        entitlements,
        imports,
        local_purchases=local_purchases,
        next_entitlement_date=next_entitlement_date,
        bond_license_capacity_mt=bond_license_capacity_mt or 0.0,
        warehouse_capacity_mt=warehouse_capacity_mt or 0.0,
        extension_applies=extension_applies,
        provisional_entitlement_date=provisional_entitlement_date,
        commissioner_extension_days=commissioner_extension_days,
        bonding_capacity_value_bdt=dl.bonding_capacity.get("value_bdt", 0.0),
        bonding_capacity_value_usd=dl.bonding_capacity.get("value_usd", 0.0),
        ledger_events=ledger_events,
        register_decision=register_decision,
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
            "provisional": [asdict(r) for r in result.provisional_records],
            "into_bond_delay": [
                asdict(r) for r in result.into_bond_delay_records
            ],
            "overstay": [asdict(r) for r in result.overstay_records],
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
    register_file: Optional[UploadFile] = File(None),
    next_entitlement_date: Optional[str] = Form(None),
    bond_license_capacity_mt: float = Form(0.0),
    warehouse_capacity_mt: float = Form(0.0),
    extension_applies: bool = Form(False),
    provisional_entitlement_date: Optional[str] = Form(None),
    commissioner_extension_days: int = Form(0),
):
    """প্রাপ্যতা + আমদানি বিশ্লেষণ করে ফলাফল (JSON) ফেরত দেয়"""
    nxt = _parse_date(next_entitlement_date)
    prov_dt = _parse_date(provisional_entitlement_date)
    with tempfile.TemporaryDirectory() as tmp:
        ent_path = await _save_upload(entitlement_file, tmp)
        imp_path = await _save_upload(imports_file, tmp)
        local_path = await _save_upload(local_file, tmp) if local_file else None
        register_path = await _save_upload(register_file, tmp) if register_file else None
        try:
            result, dl, _ = _run_engine(
                ent_path, imp_path, local_path, nxt,
                bond_license_capacity_mt, warehouse_capacity_mt, extension_applies,
                register_path, prov_dt, commissioner_extension_days,
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
    register_file: Optional[UploadFile] = File(None),
    next_entitlement_date: Optional[str] = Form(None),
    bond_license_capacity_mt: float = Form(0.0),
    warehouse_capacity_mt: float = Form(0.0),
    extension_applies: bool = Form(False),
    provisional_entitlement_date: Optional[str] = Form(None),
    commissioner_extension_days: int = Form(0),
):
    """একই বিশ্লেষণ; ১০-শীট Excel কার্যপত্র (.xlsx) ডাউনলোড হিসেবে ফেরত দেয়"""
    nxt = _parse_date(next_entitlement_date)
    prov_dt = _parse_date(provisional_entitlement_date)
    tmp = tempfile.mkdtemp()
    ent_path = await _save_upload(entitlement_file, tmp)
    imp_path = await _save_upload(imports_file, tmp)
    local_path = await _save_upload(local_file, tmp) if local_file else None
    register_path = await _save_upload(register_file, tmp) if register_file else None
    try:
        result, _, meta = _run_engine(
            ent_path, imp_path, local_path, nxt,
            bond_license_capacity_mt, warehouse_capacity_mt, extension_applies,
            register_path, prov_dt, commissioner_extension_days,
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


# ----------------------------------------------------------
# ম্যানুয়াল সংখ্যাগত / মেয়াদ যাচাই ও Evidence Chip (JS হইতে পোর্ট)
# ----------------------------------------------------------
@app.get("/api/checks/specs")
async def check_specs():
    return {"numeric": NUMERIC_CHECKS, "validity": VALIDITY_CHECKS}


@app.post("/api/checks/numeric")
async def checks_numeric(body: dict = Body(default={})):
    return run_numeric_checks(NUMERIC_CHECKS, body.get("inputs") or {})


@app.post("/api/checks/validity")
async def checks_validity(body: dict = Body(default={})):
    return run_validity_checks(VALIDITY_CHECKS, body.get("inputs") or {})


@app.post("/api/checks/evidence/scan")
async def checks_evidence_scan(body: dict = Body(default={})):
    """documents:[{id, filename, ocrText, ocrStatus?}] → Evidence Chips।"""
    return scan_documents(body.get("documents") or [], NUMERIC_CHECKS)


@app.get("/api/evidence/documents")
async def evidence_documents():
    """যে মৌলিক দলিলগুলির বিকল্প-পথ জানা আছে — সাংকেতিক নাম ও বাংলা নাম।"""
    return [{"key": k, "label": v} for k, v in DOC_LABELS.items()]


@app.post("/api/evidence/route")
async def evidence_route(body: dict = Body(default={})):
    """
    ★ মৌলিক দলিল অনুপস্থিত হইলে নিরীক্ষার বিকল্প পরিকল্পনা।
    body: {missing: ["bond_register", "up", ...]}
    """
    return audit_route(body.get("missing") or [])


@app.post("/api/evidence/filter-findings")
async def evidence_filter(body: dict = Body(default={})):
    """
    ★ অহেতুক দাবিনামা রোধ — প্রমাণাভাবে নিষিদ্ধ দাবি ছাঁকিয়া ফেলে।
    body: {findings: [{kind, ...}], missing: [...]}
    """
    return filter_findings(body.get("findings") or [], body.get("missing") or [])


@app.post("/api/checks/coefficient-validity")
async def checks_coefficient_validity(body: dict = Body(default={})):
    """
    বিধি ৯ — ইউপি ইস্যুর তারিখে DEDO সহগ বৈধ ছিল কি না।
    body: {ups:[{up_no, issue_date, coefficient_ref, valid_from, valid_to,
                 similar_coefficient?, similar_since?}]}
    """
    return [asdict(r) for r in check_coefficient_validity(body.get("ups") or [])]


@app.post("/api/checks/up-arithmetic")
async def checks_up_arithmetic(body: dict = Body(default={})):
    """
    ইউপির গাণিতিক যোগফল — ঘোষিত মোট বনাম লাইন আইটেমের যোগফল।
    body: {ups:[{up_no, declared_total, line_items:[...], unit?}], tolerance?}
    """
    return [
        asdict(r) for r in check_up_arithmetic(
            body.get("ups") or [], tolerance=float(body.get("tolerance") or 0.0)
        )
    ]


@app.post("/api/checks/electricity")
async def checks_electricity(body: dict = Body(default={})):
    """
    C5 — বিদ্যুৎ-উৎপাদন সামঞ্জস্য।
    body: {declared_rate_per_unit, total_electricity_cost, produced_units,
           unit?, threshold_pct?, monthly_costs?[]}
    """
    return asdict(check_electricity_consistency(
        declared_rate_per_unit=float(body.get("declared_rate_per_unit") or 0),
        total_electricity_cost=float(body.get("total_electricity_cost") or 0),
        produced_units=float(body.get("produced_units") or 0),
        unit=body.get("unit") or "কেজি",
        threshold_pct=float(body.get("threshold_pct") or DEFAULT_THRESHOLD_PCT),
        monthly_costs=body.get("monthly_costs"),
    ))


# ==========================================================
# এজেন্ট — চ্যাট সহকারী ও উপদেষ্টা
# ==========================================================

@app.post("/api/agent/ask")
async def agent_ask(body: dict = Body(default={})):
    """
    এজেন্টকে প্রশ্ন করো / কমান্ড দাও।

    body: {question, session_id?, allow_cloud?, prefer_llm?}

    স্তর: নিশ্চিত রাউটার আগে; বোঝা না গেলে (বা prefer_llm হইলে) এলএলএম।
    """
    from services.agent_service import get_session
    from services.agent_router import AgentRouter

    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "প্রশ্ন খালি")

    sess = get_session(body.get("session_id") or "default")
    rep = AgentRouter(sess).route(question)

    out = {
        "session_id": sess.session_id,
        "intent": rep.intent,
        "answer": rep.render(),
        "text": rep.text,
        "basis": rep.basis,
        "needs_documents": rep.needs_documents,
        "next_actions": rep.next_actions,
        "data": rep.data,
        "source": "rules",
        "confidence": rep.confidence,
    }

    # রাউটার সামলাইতে না পারিলে — এলএলএম থাকিলে তাহাকে দাও
    if (not rep.handled) or body.get("prefer_llm"):
        try:
            agent = sess.agent()
            reply = agent.ask(
                question, allow_cloud=bool(body.get("allow_cloud")),
            )
            if reply.text and reply.provider != "rules_only":
                out.update({
                    "answer": reply.text, "text": reply.text,
                    "source": reply.provider, "model": reply.model,
                    "tools_used": reply.tools_used,
                    "applied_rules": reply.applied_rules,
                    "rule_detected": reply.rule_detected,
                    "rule_proposal": reply.rule_proposal,
                })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"এলএলএম স্তর ব্যর্থ: {e}")

    sess.last_reply = out
    return out


@app.get("/api/agent/status")
async def agent_status(session_id: str = "default"):
    """এজেন্টের অবস্থা — কোন স্তর সক্রিয়, কী কী টুল আছে"""
    from services.agent_service import get_session
    sess = get_session(session_id)
    try:
        st = sess.agent().status()
    except Exception as e:  # noqa: BLE001
        st = {"ত্রুটি": str(e)}
    return {"session": sess.snapshot(), "agent": st}


@app.post("/api/agent/learn")
async def agent_learn(body: dict = Body(default={})):
    """
    ★ এজেন্টকে নূতন নিয়ম শেখাও (নিরীক্ষকের নিশ্চিতকরণের পর)।
    body: {statement, scope?, kind?, legal_reference?, session_id?}
    """
    from services.agent_service import get_session
    statement = (body.get("statement") or "").strip()
    if not statement:
        raise HTTPException(400, "নিয়মের বিবরণ খালি")
    sess = get_session(body.get("session_id") or "default")
    return sess.agent().learn(
        statement=statement,
        scope=body.get("scope") or "general",
        kind=body.get("kind") or "procedure",
        legal_reference=body.get("legal_reference") or "",
    )


@app.post("/api/agent/profile")
async def agent_profile(body: dict = Body(default={})):
    """
    নিরীক্ষার ধরন জানাও — ইহাতেই প্রাসঙ্গিকতা-ছাঁকনি চলে।
    body: {session_id?, entity_type?, company?, period_from?, period_to?,
           includes_vat?, missing_documents?[]}
    """
    from services.agent_service import get_session
    sess = get_session(body.get("session_id") or "default")
    for k in ("entity_type", "company", "period_from", "period_to",
              "includes_vat"):
        if k in body and body[k] not in (None, ""):
            sess.profile[k] = body[k]
    if isinstance(body.get("missing_documents"), list):
        sess.missing_docs = [str(x) for x in body["missing_documents"]]
    return sess.snapshot()


@app.post("/api/agent/reset")
async def agent_reset(body: dict = Body(default={})):
    """সেশন মুছিয়া নূতন করিয়া শুরু"""
    from services.agent_service import reset_session
    reset_session(body.get("session_id") or "default")
    return {"ok": True, "message": "সেশন মুছিয়া ফেলা হইয়াছে।"}


# ==========================================================
# প্রতিবেদন — Word (.docx), ফন্ট বাছাইসহ
# ==========================================================

@app.get("/api/report/fonts")
async def report_fonts():
    """কোন কোন ফন্ট-বিন্যাসে প্রতিবেদন দেওয়া যায়"""
    from services.docx_report import SCHEMES
    return [
        {"key": s.key, "label": s.label, "bangla_font": s.bangla_font,
         "latin_font": s.latin_font, "note": s.note}
        for s in SCHEMES.values()
    ]


@app.post("/api/report/font-proof")
async def report_font_proof(body: dict = Body(default={})):
    """
    ফন্ট যাচাই-নথি — নিরীক্ষক নিজের কম্পিউটারে খুলিয়া চোখে দেখিয়া
    নিশ্চিত হইতে পারেন লেখা বিকৃত কি না।
    body: {font?: "nikosh" | "sutonnymj"}
    """
    from services.docx_report import scheme_for
    from services.font_proof import build_font_proof
    scheme = scheme_for(body.get("font"))
    out = Path(tempfile.gettempdir()) / f"font_proof_{scheme.key}.docx"
    build_font_proof(scheme, out)
    return FileResponse(
        str(out),
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        filename=f"ফন্ট-যাচাই-{scheme.bangla_font}.docx",
    )


@app.post("/api/report/convert")
async def report_convert(body: dict = Body(default={})):
    """
    যেকোনো বাংলা লেখা বিজয় (SutonnyMJ) ASCII-তে বদলায়।
    body: {text}
    """
    from services.bijoy import to_bijoy_runs, unicode_to_bijoy
    text = body.get("text") or ""
    return {
        "bijoy": unicode_to_bijoy(text),
        "runs": [{"font": k, "text": v} for k, v in to_bijoy_runs(text)],
        "note": ("'other' রানগুলি ইংরেজি ফন্টে রাখিতে হইবে — "
                 "SutonnyMJ-তে রাখিলে বিকৃত দেখাইবে।"),
    }


@app.post("/api/report/docx")
async def report_docx(body: dict = Body(default={})):
    """
    পূর্ণাঙ্গ নিরীক্ষা প্রতিবেদন — Word (.docx), বাছাই করা ফন্টে।

    body: {session_id?, font?: "nikosh"|"sutonnymj",
           company?, address?, bond_license?, bin_no?,
           period_from?, period_to?, entitlement_para?}

    সেশনে চলমান বিশ্লেষণ থাকিলে তাহার ফল ব্যবহৃত হয়; নতুবা কেবল
    কাঠামো ও পর্যালোচনার ছক আসে।
    """
    from knowledge.report_style import AuditProfile
    from services.agent_service import get_session, _engine_findings
    from services.audit_report_docx import ReportContext, build_audit_report
    from services.doc_requisition import build_requisition

    sess = get_session(body.get("session_id") or "default")
    prof = sess.profile
    ent = body.get("entity_type") or prof.get("entity_type") or "direct"

    try:
        entity_label = build_requisition(ent).entity_label
    except Exception:  # noqa: BLE001
        entity_label = ""

    summary = (sess.analysis.summary if sess.analysis is not None else {}) or {}
    kinds = _engine_findings(sess) if sess.analysis is not None else []
    findings = [{"kind": k, "para": "", "amount": 0} for k in kinds]

    ctx = ReportContext(
        company=body.get("company") or prof.get("company") or "নিরীক্ষাধীন প্রতিষ্ঠান",
        address=body.get("address") or "",
        bond_license=body.get("bond_license") or "",
        bin_no=body.get("bin_no") or "",
        entity_label=entity_label,
        period_from=body.get("period_from") or prof.get("period_from") or "",
        period_to=body.get("period_to") or prof.get("period_to") or "",
        profile=AuditProfile(
            is_epz=ent.startswith("epz"),
            is_deemed="deemed" in ent,
            is_rmg=ent.startswith("rmg"),
            includes_vat=bool(prof.get("includes_vat", True)),
            has_register="bond_register" not in sess.missing_docs,
            has_export_data="export_data" not in sess.missing_docs,
        ),
        summary=summary,
        findings=findings,
        missing_docs=list(sess.missing_docs),
        entitlement_para=body.get("entitlement_para") or "",
    )

    font = body.get("font") or "nikosh"
    out = Path(tempfile.gettempdir()) / f"audit_report_{sess.session_id}_{font}.docx"
    build_audit_report(ctx, out, font=font)
    return FileResponse(
        str(out),
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        filename="নিরীক্ষা-প্রতিবেদন.docx",
    )


# ---- static frontend (সবার শেষে mount, যাতে /api/* আগে ম্যাচ করে) ----
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    async def _no_ui():
        return "<h1>Customs Bond Audit — API চলছে</h1><p>UI ফাইল পাওয়া যায়নি (api/static/)।</p>"
