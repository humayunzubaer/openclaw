"""
এজেন্ট-সেবা — চ্যাট এজেন্টকে অ্যাপের সহিত যুক্ত করে
========================================================

`ai/agent.py` এজেন্টের মস্তিষ্ক; এই মডিউল তাহাকে চলমান অ্যাপে বসায় —

    • সেশনভিত্তিক এজেন্ট (স্মৃতিসহ)
    • চলমান নিরীক্ষার ফলাফল এজেন্টের নাগালে রাখা
    • ★ নিরীক্ষা-পরিচালনার টুল — এজেন্ট কেবল উত্তর দেয় না, কাজ করাইতে পারে

★ সীমা (কঠোরভাবে পালনীয়):
    এজেন্ট আইনের উৎস নহে। আইন, বিধি, সীমা ও দাবির অঙ্ক আসে KB ও
    নিয়ম-ইঞ্জিন হইতে — এলএলএম কেবল ভাষা ও সমন্বয়ের স্তর। এলএলএম
    নিজে কোনো অঙ্ক বা বিধি-সংখ্যা সৃষ্টি করিবে না।
"""
from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Any, Optional

from utils.logger import logger


# ==========================================================
# সেশন — প্রতি নিরীক্ষকের এজেন্ট ও চলমান কাজ
# ==========================================================

class AgentSession:
    """একটি নিরীক্ষা-সেশন: এজেন্ট + চলমান বিশ্লেষণ + অনুপস্থিত দলিল"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.analysis: Any = None          # সর্বশেষ ImportAnalysisResult
        self.data_loader: Any = None
        self.missing_docs: list[str] = []  # নিরীক্ষক-ঘোষিত অনুপস্থিত দলিল
        self.profile: dict = {}            # নিরীক্ষার ধরন
        self.last_reply: dict = {}
        self._agent: Any = None

    # ------------------------------------------------------
    def agent(self):
        """এজেন্ট (প্রথমবার ডাকিলে তৈরি হয়; টুল-ভান্ডার হালনাগাদ থাকে)"""
        from ai.agent import AuditAgent
        if self._agent is None:
            self._agent = AuditAgent(
                rule_store=_rule_store(),
                tools=self._tools(),
                session_ref=self.session_id,
            )
        else:
            # নূতন বিশ্লেষণ আসিলে টুল-ভান্ডার পুনর্গঠন
            self._agent.tools = self._tools()
        return self._agent

    # ------------------------------------------------------
    def _tools(self):
        """মূল টুল-ভান্ডার + নিরীক্ষা-পরিচালনার টুল"""
        from ai.agent_tools import build_tools
        reg = build_tools(
            rule_store=_rule_store(),
            analysis_result=self.analysis,
            data_loader=self.data_loader,
            kb=_kb(),
        )
        _register_audit_tools(reg, self)
        return reg

    def snapshot(self) -> dict:
        s = self.analysis.summary if self.analysis is not None else {}
        return {
            "session_id": self.session_id,
            "has_analysis": self.analysis is not None,
            "missing_documents": self.missing_docs,
            "profile": self.profile,
            "claim_total": s.get("সর্বমোট রাজস্ব দাবি (BDT)", 0) if s else 0,
        }


# ---- সেশন-ভান্ডার (process-স্থানীয়; ডেটাবেজ যুক্ত হইলে সরিবে) ----
_SESSIONS: dict[str, AgentSession] = {}
_LOCK = threading.Lock()


def get_session(session_id: str = "default") -> AgentSession:
    sid = (session_id or "default").strip() or "default"
    with _LOCK:
        if sid not in _SESSIONS:
            _SESSIONS[sid] = AgentSession(sid)
            logger.info(f"নূতন এজেন্ট-সেশন: {sid}")
        return _SESSIONS[sid]


def reset_session(session_id: str = "default") -> None:
    with _LOCK:
        _SESSIONS.pop(session_id, None)


# ==========================================================
# সহায়ক — নিয়ম-ভান্ডার ও জ্ঞানভান্ডার (একবার লোড)
# ==========================================================

_RULE_STORE = None
_KB = None


def _rule_store():
    global _RULE_STORE
    if _RULE_STORE is None:
        try:
            from knowledge.learned_rules import LearnedRuleStore
            from config import DATABASE_DIR
            _RULE_STORE = LearnedRuleStore(DATABASE_DIR / "learned_rules.db")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"নিয়ম-ভান্ডার খোলা যায় নাই: {e}")
            _RULE_STORE = None
    return _RULE_STORE


def _kb():
    global _KB
    if _KB is None:
        try:
            from pathlib import Path
            from knowledge.kb_loader import KnowledgeBase
            kb_dir = Path(__file__).resolve().parent.parent / "knowledge" / "kb"
            _KB = KnowledgeBase(str(kb_dir))
            _KB.load()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"জ্ঞানভান্ডার লোড হয় নাই: {e}")
            _KB = None
    return _KB


# ==========================================================
# ★ নিরীক্ষা-পরিচালনার টুল — এজেন্ট এইগুলি দিয়া কাজ করায়
# ==========================================================

def _register_audit_tools(reg, sess: "AgentSession") -> None:
    """সেশন-সচেতন টুল যোগ করে (এজেন্ট ইঞ্জিনকে কমান্ড দিতে পারে)"""

    @reg.add(
        name="list_required_documents",
        description=(
            "প্রতিষ্ঠানের শ্রেণি অনুযায়ী নিরীক্ষায় চাহিত দলিলাদির তালিকা ও "
            "প্রযোজ্য তফসিল-ছক ফেরত দেয়। শ্রেণি: direct, deemed, "
            "epz_direct, epz_deemed, rmg_direct।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "description":
                    "শ্রেণি: direct | deemed | epz_direct | epz_deemed | rmg_direct"},
            },
            "required": ["entity_type"],
        },
        category="audit",
    )
    def _required_docs(entity_type: str = "direct"):
        from services.doc_requisition import build_requisition
        r = build_requisition(entity_type)
        return {
            "শ্রেণি": r.entity_label,
            "মোট দলিল": len(r.documents),
            "আবশ্যিক": r.mandatory_count,
            "দলিল": [{"নাম": d.name, "আইনি ভিত্তি": d.legal_ref,
                      "আবশ্যিক": d.mandatory} for d in r.documents],
            "তফসিল-ছক": [{"ছক": s.label, "শিরোনাম": s.title,
                          "বিধি": s.rule_ref} for s in r.schedules],
        }

    @reg.add(
        name="plan_audit_without_documents",
        description=(
            "★ কোনো মৌলিক দলিল অনুপস্থিত হইলে বিকল্প পথে নিরীক্ষার পরিকল্পনা "
            "দেয় — কোন বিকল্প উৎস, তবু কী নির্ণয় করা যাইবে, কী যাইবে না "
            "(দাবি নিষিদ্ধ), কী তলব করিতে হইবে। দলিলের সাংকেতিক নাম: "
            "bond_register, coefficient, mis_import, entitlement, up, "
            "export_data, closing_stock, mushak_43, mushak_91, prc, "
            "electricity, machine_list, local_purchase।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "missing": {"type": "string", "description":
                    "অনুপস্থিত দলিলের সাংকেতিক নাম, কমা দিয়া পৃথক"},
            },
            "required": ["missing"],
        },
        category="audit",
    )
    def _plan_without(missing: str = ""):
        from services.evidence_paths import audit_route
        docs = [m.strip() for m in (missing or "").split(",") if m.strip()]
        if docs:
            sess.missing_docs = docs
        route = audit_route(docs)
        return {
            "অনুপস্থিত দলিল": docs,
            "বিকল্প পথ": [
                {"দলিল": p["label"], "বিকল্প উৎস": p["alternatives"],
                 "তবু নির্ণেয়": p["still_possible"],
                 "নির্ণেয় নহে": p["blocked"]}
                for p in route["paths"]
            ],
            "তলব করিতে হইবে": route["requisitions"],
            "প্রস্তাবনায় যাইবে": route["proposals"],
            "দাবি নিষিদ্ধ (ছাঁচ)": route["blocked_kinds"],
        }

    @reg.add(
        name="get_report_plan",
        description=(
            "নিরীক্ষার ধরন অনুযায়ী প্রতিবেদনে কোন অনুচ্ছেদ, কোন পর্যালোচনা-প্রশ্ন "
            "ও কোন ফাইন্ডিং আসিবে তাহার পরিকল্পনা দেয়। অপ্রাসঙ্গিক অংশ বাদ পড়ে।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "is_epz": {"type": "boolean", "description": "ইপিজেডস্থ কি না"},
                "is_deemed": {"type": "boolean", "description": "প্রচ্ছন্ন কি না"},
                "is_rmg": {"type": "boolean", "description": "পোশাক শিল্প কি না"},
                "includes_vat": {"type": "boolean", "description":
                    "সিএ/ভ্যাট পার্শ্বও নিরীক্ষিত কি না"},
            },
            "required": [],
        },
        category="audit",
    )
    def _report_plan(is_epz: bool = False, is_deemed: bool = False,
                     is_rmg: bool = False, includes_vat: bool = False):
        from knowledge.report_style import AuditProfile, assemble_report_plan
        prof = AuditProfile(
            is_epz=is_epz, is_deemed=is_deemed, is_rmg=is_rmg,
            includes_vat=includes_vat,
            has_register="bond_register" not in sess.missing_docs,
            has_export_data="export_data" not in sess.missing_docs,
        )
        sess.profile = asdict(prof)
        plan = assemble_report_plan(prof, _engine_findings(sess))
        return {
            "অনুচ্ছেদ": plan["paragraphs"],
            "পর্যালোচনার প্রশ্ন": [q for q, _, _ in plan["review_questions"]],
            "প্রযোজ্য ফাইন্ডিং": [f.get("kind") for f in plan["findings"]],
            "বাদ পড়া": plan["excluded_findings"],
        }

    @reg.add(
        name="draft_opinion_paragraphs",
        description=(
            "★ চলমান নিরীক্ষার ফাইন্ডিং হইতে 'মতামত ও প্রস্তাবনা' অনুচ্ছেদের "
            "খসড়া বাংলা বাক্য তৈরি করে (দাপ্তরিক ভাষায়, অঙ্ক ও কথায়সহ)। "
            "প্রমাণাভাবে নিষিদ্ধ দাবি স্বয়ংক্রিয়ভাবে বাদ পড়ে।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "প্রতিষ্ঠানের নাম"},
                "period_from": {"type": "string", "description": "মেয়াদ শুরু"},
                "period_to": {"type": "string", "description": "মেয়াদ শেষ"},
            },
            "required": [],
        },
        category="audit",
    )
    def _draft_opinion(company: str = "আলোচ্য প্রতিষ্ঠান",
                       period_from: str = "", period_to: str = ""):
        from knowledge.report_style import build_opinion, OPINION_CLOSING
        from services.evidence_paths import filter_findings
        fnd = _engine_findings(sess)
        filt = filter_findings(fnd, sess.missing_docs)
        items = build_opinion(company, period_from, period_to,
                              findings=filt["kept"])
        return {
            "দফা": [{"ক্রম": i.label, "ধরন": i.kind, "বাক্য": i.text}
                    for i in items],
            "সমাপনী": OPINION_CLOSING,
            "প্রমাণাভাবে বাদ": filt["suppressed"],
        }

    @reg.add(
        name="get_current_audit_state",
        description="চলমান নিরীক্ষার অবস্থা — বিশ্লেষণ হইয়াছে কি না, "
                    "অনুপস্থিত দলিল, মোট দাবি।",
        parameters={"type": "object", "properties": {}, "required": []},
        category="audit",
    )
    def _state():
        return sess.snapshot()


def _engine_findings(sess: "AgentSession") -> list[dict]:
    """
    ★ চলমান বিশ্লেষণ হইতে ফাইন্ডিং-তালিকা (দাবির অঙ্ক ইঞ্জিন হইতেই আসে)।

    এলএলএম কখনো এই তালিকা তৈরি করে না — কেবল ইঞ্জিনের গণনা।
    """
    r = sess.analysis
    if r is None:
        return []
    s = r.summary or {}
    out: list[dict] = []

    def add(kind: str, amount_key: str, **extra):
        amt = s.get(amount_key, 0) or 0
        if amt > 0:
            out.append({"kind": kind, "amount": float(amt), **extra})

    add("unauthorized_hs_demand", "দাবি ১ — অননুমোদিত এইচএস কোড (BDT)",
        para="", quantity="", unit="")
    add("excess_import_demand", "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)",
        para="", quantity="", unit="")
    add("capacity_breach_demand", "দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত (BDT)",
        para="", capacity="", held="", excess="", unit="", breach_date="")
    add("post_period_demand",
        "দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি (BDT)",
        para="", from_date="", to_date="", quantity="", unit="")
    add("overstay_demand",
        "দাবি ৬ — মেয়াদোত্তীর্ণ (২ বছর+) কাঁচামাল (BDT)",
        para="", quantity="", unit="")

    if s.get("ইন্টু-বন্ড বিলম্ব [বিধি ৮] — সীমা অতিক্রম", 0):
        out.append({"kind": "into_bond_delay", "amount": 0, "para": "",
                    "count": str(s["ইন্টু-বন্ড বিলম্ব [বিধি ৮] — সীমা অতিক্রম"])})
    return out


__all__ = ["AgentSession", "get_session", "reset_session"]
