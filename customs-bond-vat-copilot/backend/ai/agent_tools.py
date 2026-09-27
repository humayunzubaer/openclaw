"""
Agent Tools — এজেন্টের কর্মক্ষমতা
====================================

এজেন্ট কেবল কথা বলে না — ইঞ্জিনের প্রকৃত কাজ সম্পাদন করে।
এই মডিউল ইঞ্জিনের ফাংশনসমূহকে টুল আকারে এজেন্টের হাতে তুলিয়া দেয়।

টুলের শ্রেণী:
    calculation — হিসাব ও সূত্র প্রয়োগ
    analysis    — ফাইল বিশ্লেষণ
    legal       — আইনি পরিধি ও উদ্ধৃতি
    knowledge   — শেখা নিয়ম অনুসন্ধান
    report      — প্রতিবেদন প্রস্তুতি
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from ai.agent import ToolRegistry
from utils.logger import logger


def build_tools(
    rule_store=None,
    analysis_result=None,
    data_loader=None,
    output_dir: str = "",
    kb=None,
) -> ToolRegistry:
    """
    এজেন্টের জন্য টুল-ভান্ডার প্রস্তুত করো।

    analysis_result থাকিলে চলমান নিরীক্ষার তথ্য সম্পর্কেও
    প্রশ্নের উত্তর দিতে পারিবে।
    """
    reg = ToolRegistry()

    # ======================================================
    # হিসাব সংক্রান্ত টুল
    # ======================================================

    @reg.add(
        name="calculate_warehouse_capacity",
        description=(
            "ওয়্যারহাউসের ধারণক্ষমতা নির্ণয় করে। "
            "এসআরও ২০৯/২০২৪ বিধি ৭(২) অনুযায়ী: "
            "[{(আয়তন − আয়তনের ১০%) ÷ ১৩৬০} × ১২] মেট্রিক টন। "
            "দৈর্ঘ্য, প্রস্থ ও উচ্চতা ফুটে দিতে হবে।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "length_ft": {"type": "number", "description": "দৈর্ঘ্য (ফুট)"},
                "width_ft": {"type": "number", "description": "প্রস্থ (ফুট)"},
                "height_ft": {"type": "number", "description": "উচ্চতা (ফুট)"},
            },
            "required": ["length_ft", "width_ft", "height_ft"],
        },
        category="calculation",
    )
    def _warehouse_capacity(length_ft: float, width_ft: float, height_ft: float):
        from services.capacity_ledger import compute_warehouse_capacity
        wc = compute_warehouse_capacity(
            length_ft=length_ft, width_ft=width_ft, height_ft=height_ft
        )
        return {
            "আয়তন (ঘনফুট)": round(wc.volume_cft, 2),
            "ব্যবহারযোগ্য (ঘনফুট)": round(wc.usable_cft, 2),
            "ধারণক্ষমতা (মে.টন)": round(wc.capacity_mt, 3),
            "ধারণক্ষমতা (কেজি)": round(wc.capacity_kg, 2),
            "সূত্র": wc.formula,
            "আইনি ভিত্তি": wc.legal_basis,
        }

    @reg.add(
        name="calculate_bonding_capacity",
        description=(
            "এককালীন বন্ডিং ক্যাপাসিটি নির্ণয় করে। "
            "সূত্র: min(প্রাপ্যতা ÷ ৩, ওয়্যারহাউসের ধারণক্ষমতা)। "
            "প্রাপ্যতা = প্রাপ্যতা শীটে প্রদত্ত পরিমাণ (মজুত বাদে) + প্রারম্ভিক মজুত। "
            "০১.০৭.২০২৬ বা তৎপরবর্তী মেয়াদে ক্যাপাসিটি = কেবল ধারণক্ষমতা।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "sheet_quantity": {
                    "type": "number",
                    "description": "প্রাপ্যতা শীটে প্রদত্ত পরিমাণ (মজুত বাদে), কেজিতে",
                },
                "opening_stock": {
                    "type": "number",
                    "description": "প্রারম্ভিক মজুত (বিগত নিরীক্ষার সমাপনী), কেজিতে",
                },
                "warehouse_capacity_kg": {
                    "type": "number",
                    "description": "ওয়্যারহাউসের ধারণক্ষমতা, কেজিতে",
                },
                "period_start": {
                    "type": "string",
                    "description": "নিরীক্ষা মেয়াদের শুরু (YYYY-MM-DD)",
                },
            },
            "required": ["sheet_quantity", "opening_stock", "warehouse_capacity_kg"],
        },
        category="calculation",
    )
    def _bonding_capacity(
        sheet_quantity: float, opening_stock: float,
        warehouse_capacity_kg: float, period_start: str = "",
    ):
        from services.capacity_ledger import compute_one_time_capacity
        from services.bonding_rules import NEW_REGIME_DATE

        regime = "old"
        if period_start:
            try:
                d = datetime.fromisoformat(period_start).date()
                regime = "new" if d >= NEW_REGIME_DATE else "old"
            except ValueError:
                pass

        c = compute_one_time_capacity(
            entitlement_sheet_kg=sheet_quantity,
            opening_stock_kg=opening_stock,
            warehouse_capacity_kg=warehouse_capacity_kg,
            regime=regime,
        )
        return {
            "শীটে প্রদত্ত (কেজি)": round(c.entitlement_sheet_kg, 2),
            "প্রারম্ভিক মজুত (কেজি)": round(c.opening_stock_kg, 2),
            "প্রকৃত প্রাপ্যতা (কেজি)": round(c.total_entitlement_kg, 2),
            "এক-তৃতীয়াংশ (কেজি)": round(c.one_third_kg, 2),
            "ধারণক্ষমতা (কেজি)": round(c.warehouse_capacity_kg, 2),
            "এককালীন বন্ডিং ক্যাপাসিটি (কেজি)": round(c.capacity_kg, 2),
            "একই (মে.টন)": round(c.capacity_mt, 3),
            "নির্ধারক": c.binding_constraint,
            "পদ্ধতি": "নূতন (০১.০৭.২০২৬ হইতে)" if regime == "new" else "পুরাতন",
            "সূত্র": c.formula,
            "আইনি ভিত্তি": c.legal_basis,
        }

    @reg.add(
        name="calculate_duty_cascade",
        description=(
            "শুল্কায়িত মূল্যের উপর শুল্ক-করের ক্যাসকেড হিসাব করে "
            "(বাংলাদেশ কাস্টমস পদ্ধতি)। "
            "এসডি ভিত্তি = AV+CD+RD; মূসক ভিত্তি = AV+CD+RD+SD।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "assessable_value": {"type": "number", "description": "শুল্কায়িত মূল্য (টাকা)"},
                "cd_rate": {"type": "number", "description": "সিডি হার (%)"},
                "rd_rate": {"type": "number", "description": "আরডি হার (%)"},
                "sd_rate": {"type": "number", "description": "এসডি হার (%)"},
                "vat_rate": {"type": "number", "description": "মূসক হার (%)"},
                "at_rate": {"type": "number", "description": "এটি হার (%)"},
                "ait_rate": {"type": "number", "description": "এআইটি হার (%)"},
            },
            "required": ["assessable_value"],
        },
        category="calculation",
    )
    def _duty_cascade(
        assessable_value: float, cd_rate: float = 0, rd_rate: float = 0,
        sd_rate: float = 0, vat_rate: float = 15, at_rate: float = 5,
        ait_rate: float = 5,
    ):
        av = assessable_value
        cd = av * cd_rate / 100
        rd = av * rd_rate / 100
        sd = (av + cd + rd) * sd_rate / 100
        vat = (av + cd + rd + sd) * vat_rate / 100
        at = av * at_rate / 100
        ait = av * ait_rate / 100
        total = cd + rd + sd + vat + at + ait
        return {
            "শুল্কায়িত মূল্য": round(av, 2),
            "সিডি": round(cd, 2), "আরডি": round(rd, 2), "এসডি": round(sd, 2),
            "মূসক": round(vat, 2), "এটি": round(at, 2), "এআইটি": round(ait, 2),
            "মোট শুল্ক-কর": round(total, 2),
            "কার্যকর হার (%)": round(total / av * 100, 2) if av else 0,
            "গণনার ক্রম": (
                "CD = AV×cd% | RD = AV×rd% | SD = (AV+CD+RD)×sd% | "
                "VAT = (AV+CD+RD+SD)×vat% | AT = AV×at% | AIT = AV×ait%"
            ),
        }

    @reg.add(
        name="calculate_production_capacity",
        description=(
            "বার্ষিক উৎপাদন ক্ষমতা নির্ণয় করে। "
            "এসআরও ২১৪/২০২৪ বিধি ৩(৪): "
            "৩০০ কার্যদিবস × শিফট সংখ্যা × ৮ ঘণ্টা × মেশিন সংখ্যা "
            "× প্রতি ঘণ্টায় উৎপাদন ক্ষমতা।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "shifts": {"type": "number", "description": "দৈনিক শিফট সংখ্যা"},
                "machines": {"type": "number", "description": "উৎপাদনে ব্যবহৃত মেশিন সংখ্যা"},
                "output_per_hour": {"type": "number", "description": "প্রতি ঘণ্টায় প্রতি মেশিনের উৎপাদন"},
                "working_days": {"type": "number", "description": "বার্ষিক কার্যদিবস (সাধারণত ৩০০)"},
            },
            "required": ["shifts", "machines", "output_per_hour"],
        },
        category="calculation",
    )
    def _production_capacity(
        shifts: float, machines: float, output_per_hour: float,
        working_days: float = 300,
    ):
        cap = working_days * shifts * 8 * machines * output_per_hour
        return {
            "বার্ষিক উৎপাদন ক্ষমতা (১০০%)": round(cap, 2),
            "৮০% সীমা": round(cap * 0.80, 2),
            "৬০%": round(cap * 0.60, 2),
            "৩০% (নূতন লাইসেন্স)": round(cap * 0.30, 2),
            "সূত্র": (
                f"{working_days:g} কার্যদিবস × {shifts:g} শিফট × ৮ ঘণ্টা "
                f"× {machines:g} মেশিন × {output_per_hour:g} = {cap:,.2f}"
            ),
            "আইনি ভিত্তি": (
                "বার্ষিক আমদানি প্রাপ্যতা নির্ধারণ বিধিমালা, ২০২৪ "
                "[এসআরও ২১৪-আইন/২০২৪] — বিধি ৩(৪)"
            ),
        }

    # ======================================================
    # আইনি টুল
    # ======================================================

    @reg.add(
        name="check_legal_scope",
        description=(
            "নিরীক্ষার ধরন ও প্রতিষ্ঠানের অবস্থান অনুযায়ী কোন আইন-বিধি "
            "প্রযোজ্য ও কোনটি প্রযোজ্য নহে তাহা নির্ণয় করে।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "audit_type": {
                    "type": "string", "enum": ["bond", "vat", "bond_vat"],
                    "description": "নিরীক্ষার ধরন",
                },
                "zone": {
                    "type": "string", "enum": ["general", "epz", "ez", "hitech"],
                    "description": "প্রতিষ্ঠানের অবস্থান",
                },
            },
            "required": ["audit_type"],
        },
        category="legal",
    )
    def _legal_scope(audit_type: str, zone: str = "general"):
        from knowledge.legal_scope import (
            AuditContext, AuditType, ZoneType, LegalScopeEngine
        )
        ctx = AuditContext(
            audit_type=AuditType(audit_type), zone=ZoneType(zone)
        )
        eng = LegalScopeEngine(ctx)
        return eng.summary()

    @reg.add(
        name="search_law",
        description=(
            "প্রকল্পে সংরক্ষিত আইন, বিধিমালা ও এসআরও-র মধ্যে অনুসন্ধান করে। "
            "নির্দিষ্ট বিধি বা ধারার পাঠ্য খুঁজিতে ব্যবহার্য।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "অনুসন্ধানের বিষয়"},
            },
            "required": ["query"],
        },
        category="legal",
    )
    def _search_law(query: str):
        return {
            "নোট": (
                "আইনি পাঠ্য অনুসন্ধান ডেস্কটপ অ্যাপে সংরক্ষিত পিডিএফ হইতে "
                "সম্পাদিত হয়। এই মুহূর্তে সূচিকরণ সম্পন্ন হয় নাই।"
            ),
            "অনুসন্ধান": query,
            "উপলব্ধ দলিল": [
                "কাস্টমস আইন, ২০২৩",
                "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ [এসআরও ২০৯/২০২৪]",
                "ওয়্যারহাউস পরিচালনা ও কার্যপদ্ধতি বিধিমালা, ২০২৪ [এসআরও ২১২/২০২৪]",
                "বার্ষিক আমদানি প্রাপ্যতা নির্ধারণ বিধিমালা, ২০২৪ [এসআরও ২১৪/২০২৪]",
                "সংশোধনী [এসআরও ২৩৫/২০২৫]",
                "মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
                "মূল্য সংযোজন কর ও সম্পূরক শুল্ক বিধিমালা, ২০১৬",
                "ভ্যাট নিরীক্ষা ম্যানুয়াল, ২০২২",
            ],
        }

    # ======================================================
    # জ্ঞান সংক্রান্ত টুল
    # ======================================================

    if rule_store is not None:

        @reg.add(
            name="search_learned_rules",
            description=(
                "নিরীক্ষক কর্তৃক পূর্বে শেখানো নিয়মসমূহের মধ্যে অনুসন্ধান করে।"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "অনুসন্ধানের বিষয়"},
                },
                "required": ["query"],
            },
            category="knowledge",
        )
        def _search_rules(query: str):
            rules = rule_store.search(query, limit=8)
            if not rules:
                return {"পাওয়া গিয়াছে": 0,
                        "বার্তা": "এই বিষয়ে পূর্বে কোনো নিয়ম শেখানো হয় নাই"}
            return {
                "পাওয়া গিয়াছে": len(rules),
                "নিয়মসমূহ": [
                    {
                        "নং": r.id, "পরিধি": r.scope, "ধরন": r.kind,
                        "নিয়ম": r.statement,
                        "আইনি ভিত্তি": r.legal_reference or "—",
                        "প্রয়োগ হইয়াছে": f"{r.times_applied} বার",
                    }
                    for r in rules
                ],
            }

        @reg.add(
            name="list_learned_rules",
            description="নির্দিষ্ট পরিধির সকল শেখা নিয়ম তালিকাভুক্ত করে।",
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": (
                            "পরিধি: import, entitlement, capacity, assessment, "
                            "consumption, export, inventory, vat, legal, report, general"
                        ),
                    },
                },
            },
            category="knowledge",
        )
        def _list_rules(scope: str = ""):
            rules = rule_store.list_rules(scope=scope or None, limit=50)
            return {
                "মোট": len(rules),
                "নিয়মসমূহ": [
                    {"নং": r.id, "পরিধি": r.scope, "সারসংক্ষেপ": r.summary}
                    for r in rules
                ],
            }

    # ======================================================
    # চলমান নিরীক্ষার তথ্য
    # ======================================================

    if analysis_result is not None:

        @reg.add(
            name="get_audit_summary",
            description=(
                "চলমান নিরীক্ষার সারসংক্ষেপ — চারটি দাবির অঙ্ক, "
                "আপত্তির সংখ্যা ও সামগ্রিক পরিসংখ্যান।"
            ),
            parameters={"type": "object", "properties": {}},
            category="analysis",
        )
        def _audit_summary():
            return analysis_result.summary

        @reg.add(
            name="get_findings",
            description=(
                "নির্দিষ্ট ধরনের আপত্তির বিস্তারিত তালিকা। "
                "ধরন: excess (অতিরিক্ত আমদানি), unauthorized (অননুমোদিত এইচএস), "
                "capacity (বন্ডিং ক্যাপাসিটি), limit (৮০% সীমা), "
                "machinery (মেশিনারিজ), review (যাচাই প্রয়োজন)"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["excess", "unauthorized", "capacity",
                                 "limit", "machinery", "review"],
                    },
                    "limit": {"type": "number", "description": "সর্বোচ্চ কয়টি"},
                },
                "required": ["kind"],
            },
            category="analysis",
        )
        def _findings(kind: str, limit: int = 10):
            from dataclasses import asdict as _asdict
            mapping = {
                "excess": analysis_result.excess_records,
                "unauthorized": analysis_result.unauthorized_records,
                "capacity": analysis_result.capacity_breach_records,
                "limit": analysis_result.capacity_limit_records,
                "machinery": analysis_result.machinery_records,
            }
            if kind == "review":
                rows = analysis_result.low_confidence_matches[:limit]
                return {"সংখ্যা": len(rows), "তালিকা": rows}
            recs = mapping.get(kind, [])[:limit]
            return {
                "সংখ্যা": len(recs),
                "তালিকা": [_asdict(r) for r in recs],
            }

        @reg.add(
            name="get_warnings",
            description="বিশ্লেষণকালীন সতর্কতা ও টীকাসমূহ।",
            parameters={"type": "object", "properties": {}},
            category="analysis",
        )
        def _warnings():
            return {"সতর্কতা": analysis_result.warnings}


    # ======================================================
    # ★ জ্ঞানভান্ডার (KB) টুল — ১৫টি ফাইল হইতে
    # ======================================================

    if kb is not None:

        @reg.add(
            name="kb_find_citation",
            description=(
                "জ্ঞানভান্ডার থেকে প্রাসঙ্গিক আইনি উদ্ধৃতি (ধারা/বিধি/এসআরও) "
                "খুঁজে দেয়, প্রতিটির certainty grade সহ — 【V】যাচাইকৃত, "
                "【E】অনুমিত, 【P】অযাচাইকৃত। ★ কখনো উদ্ধৃতি বানায় না; "
                "KB-তে না থাকলে খালি ফেরত দেয়।"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "বিষয়"},
                    "limit": {"type": "number"},
                },
                "required": ["query"],
            },
            category="legal",
        )
        def _kb_cite(query: str, limit: int = 8):
            cs = kb.find_citations(query, limit=int(limit))
            if not cs:
                return {
                    "পাওয়া গেছে": 0,
                    "নির্দেশ": (
                        "জ্ঞানভান্ডারে এই বিষয়ে উদ্ধৃতি পাওয়া যায়নি। "
                        "output-এ '[যাচাই করুন]' লিখতে হবে — কখনো অনুমানে "
                        "ধারা/বিধি নম্বর লেখা যাবে না।"
                    ),
                }
            return {
                "পাওয়া গেছে": len(cs),
                "উদ্ধৃতি": [
                    {"উদ্ধৃতি": c.cite, "grade": c.certainty,
                     "SCN-যোগ্য": c.certainty.startswith("V"),
                     "Module": c.module, "প্রসঙ্গ": c.note}
                    for c in cs
                ],
            }

        @reg.add(
            name="kb_get_test",
            description=(
                "Audit Test Library থেকে একটি test-এর সূত্র, threshold ও "
                "আইনি ভিত্তি ফেরত দেয়। T01=বন্ড রেজিস্টার মিলকরণ, "
                "T02=মূসক ত্রিভুজ, T03=FIFO lot, T04=সহগ/UP-UD, "
                "T04A_entitlement_ceiling=প্রাপ্যতা সীমা, T05=অপচয়, "
                "T06=মূল্য সংযোজন, T07=BTB LC, T08=রপ্তানি প্রত্যাবাসন, "
                "T09=DTA/Ex-bond শুল্কায়ন, T10=মেশিনারি, T11=সচ্ছলতা, "
                "T12=উৎসে মূসক চার-স্তর, T13=শূন্যহার দলিল"
            ),
            parameters={
                "type": "object",
                "properties": {"test_id": {"type": "string"}},
                "required": ["test_id"],
            },
            category="knowledge",
        )
        def _kb_test(test_id: str):
            t = kb.get_test(test_id)
            if not t:
                near = [x.id for x in kb.find_tests(test_id)][:5]
                return {"ত্রুটি": f"'{test_id}' পাওয়া যায়নি",
                        "নিকটতম": near or sorted(kb.tests.keys())}
            return {
                "id": t.id, "নাম": t.name, "severity": t.severity,
                "প্রয়োজনীয় তথ্য": t.inputs,
                "সূত্র": t.formula or t.formulas,
                "যাচাই": t.checks,
                "threshold": t.threshold,
                "আইনি ভিত্তি": [
                    {"উদ্ধৃতি": c.cite, "grade": c.certainty} for c in t.law_refs
                ],
                "পরিণতি": t.consequence,
            }

        @reg.add(
            name="kb_resolve_temporal",
            description=(
                "ঘটনার তারিখ বা নিরীক্ষা মেয়াদ অনুযায়ী প্রযোজ্য আইনের সংস্করণ "
                "নির্ণয় করে। ০৬-০৬-২০২৪ এর আগে Customs Act 1969, পরে কাস্টমস "
                "আইন ২০২৩। মেয়াদ এই তারিখ অতিক্রম করলে খণ্ডভিত্তিক ভাগ করে দেয়।"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "period_from": {"type": "string"},
                    "period_to": {"type": "string"},
                },
            },
            category="legal",
        )
        def _kb_temporal(event_date: str = "", period_from: str = "",
                         period_to: str = ""):
            from knowledge.kb_loader import resolve_temporal
            from datetime import date as _d

            def _p(x):
                try:
                    return _d.fromisoformat(x) if x else None
                except ValueError:
                    return None

            r = resolve_temporal(_p(event_date), _p(period_from), _p(period_to))
            return {
                "রেজিম": r.regime, "প্রযোজ্য আইন": r.instrument,
                "ভিত্তি": r.basis, "খণ্ড": r.segments, "সতর্কতা": r.warnings,
            }

        @reg.add(
            name="kb_limitation_note",
            description=(
                "একটি ঘটনার তামাদি-নোট তৈরি করে — কাস্টমস আইন ২০২৩ এর "
                "ধারা ২০৪(১) অনুযায়ী ৩ বছর। প্রতিটি finding-এ বাধ্যতামূলক।"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "fraud_alleged": {"type": "boolean"},
                },
                "required": ["event_date"],
            },
            category="legal",
        )
        def _kb_limit(event_date: str, fraud_alleged: bool = False):
            from knowledge.kb_loader import limitation_note, resolve_temporal
            from datetime import date as _d
            try:
                d = _d.fromisoformat(event_date)
            except ValueError:
                return {"ত্রুটি": "তারিখ YYYY-MM-DD আকারে দিন"}
            r = resolve_temporal(event_date=d)
            return {"তামাদি-নোট": limitation_note(d, r.regime, fraud_alleged)}

        @reg.add(
            name="kb_check_term",
            description=(
                "আইনি পরিভাষার সূক্ষ্ম পার্থক্য যাচাই করে — যেমন 'খালাস' বনাম "
                "'ছাড়', 'অপসারণ' বনাম 'ঘাটতি', 'প্রত্যর্পণ' বনাম 'refund'। "
                "adjudication-এ শব্দচয়নই মামলা জেতায় বা হারায়।"
            ),
            parameters={
                "type": "object",
                "properties": {"term": {"type": "string"}},
                "required": ["term"],
            },
            category="legal",
        )
        def _kb_term(term: str):
            r = kb.check_term(term)
            return r or {"বার্তা": f"'{term}' পরিভাষা-সারণিতে নেই"}

        @reg.add(
            name="kb_search_docs",
            description=(
                "জ্ঞানভান্ডারের ১৫টি দলিলে পাঠ্য অনুসন্ধান করে, উৎস Module "
                "উল্লেখসহ। নির্দিষ্ট বিধানের ব্যাখ্যা খুঁজতে ব্যবহার্য।"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "number"},
                },
                "required": ["query"],
            },
            category="knowledge",
        )
        def _kb_docs(query: str, limit: int = 6):
            hits = kb.search_docs(query, limit=int(limit))
            return {"পাওয়া গেছে": len(hits), "ফলাফল": hits}

    # ======================================================
    # সাধারণ টুল
    # ======================================================

    @reg.add(
        name="convert_units",
        description=(
            "একক রূপান্তর করে। নিরাপদ (পণ্য-নিরপেক্ষ) রূপান্তর কেবল — "
            "গজ↔মিটার, ডজন↔পিস, কেজি↔মেট্রিক টন। "
            "কেজি↔গজ রূপান্তর করা হয় না কারণ উহা পণ্যের GSM ও প্রস্থ নির্ভর।"
        ),
        parameters={
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string", "description": "যেমন YDS, MTR, KG, MT, PCS, DOZ"},
                "to_unit": {"type": "string"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
        category="calculation",
    )
    def _convert(value: float, from_unit: str, to_unit: str):
        from services.unit_extractor import normalize_unit
        SAFE = {
            ("YDS", "MTR"): 0.9144, ("MTR", "YDS"): 1.09361,
            ("DOZ", "PCS"): 12.0, ("PCS", "DOZ"): 1 / 12.0,
            ("MT", "KG"): 1000.0, ("KG", "MT"): 0.001,
        }
        f = normalize_unit(from_unit) or from_unit.upper()
        t = normalize_unit(to_unit) or to_unit.upper()
        if f == t:
            return {"ফলাফল": value, "নোট": "একই একক"}
        factor = SAFE.get((f, t))
        if factor is None:
            return {
                "ত্রুটি": (
                    f"{f} হইতে {t} — এই রূপান্তর পণ্য-নির্ভর হওয়ায় "
                    f"স্বয়ংক্রিয়ভাবে করা হয় না। বিল অব এন্ট্রির পণ্য "
                    f"বর্ণনা হইতে প্রকৃত পরিমাণ গ্রহণ করুন।"
                )
            }
        return {
            "ফলাফল": round(value * factor, 4),
            "একক": t,
            "রূপান্তর হার": factor,
        }

    logger.info(f"এজেন্টের জন্য {len(reg.tools)}টি টুল প্রস্তুত")
    return reg


__all__ = ["build_tools"]
