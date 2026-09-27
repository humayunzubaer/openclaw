"""
নিরীক্ষা প্রতিবেদন — Word (.docx) নির্মাতা
=============================================

ইঞ্জিনের ফল ও প্রতিবেদন-পরিকল্পনা হইতে পূর্ণাঙ্গ প্রতিবেদন গড়ে,
নিরীক্ষকের বাছাই করা ফন্টে (Nikosh অথবা SutonnyMJ)।

গঠন — নমুনা প্রতিবেদনের ধারাবাহিকতা অনুসারে
    ১. শিরোনাম ও প্রতিষ্ঠান-পরিচিতি
    ২. নিরীক্ষার পটভূমি ও পরিধি
    ৩. অনুচ্ছেদক্রম (কেবল প্রাসঙ্গিকগুলি)
    ৪. পর্যালোচনা (প্রশ্ন-উত্তর ছক)
    ৫. প্রাপ্ত আপত্তির সারসংক্ষেপ (অঙ্কসহ)
    ৬. দলিল-ঘাটতি ও তাহার প্রভাব
    ৭. প্রস্তাব ও মতামত

★ যাহা এই নথিতে থাকে না
    প্রমাণ নাই এমন কোনো দাবি। দলিলের অভাবে যে যাচাই সম্ভব হয় নাই
    তাহা "নির্ণয় করা যায় নাই" বলিয়া লেখা হয় — দাবি হিসাবে নহে।
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from knowledge.report_style import (
    AuditProfile, OPINION_CLOSING, OPINION_OPENING,
    assemble_report_plan, build_opinion, _indian_group, _to_bangla_digits,
)
from services.docx_report import FontScheme, ReportDocument, scheme_for
from utils.logger import logger

bn = _to_bangla_digits


# ==========================================================
# প্রতিবেদনের উপাদান
# ==========================================================

@dataclass
class ReportContext:
    """প্রতিবেদন লিখিবার জন্য যাহা যাহা লাগে"""
    company: str = "নিরীক্ষাধীন প্রতিষ্ঠান"
    address: str = ""
    bond_license: str = ""
    bin_no: str = ""
    entity_label: str = ""
    period_from: str = ""
    period_to: str = ""
    audit_date: str = ""

    profile: Optional[AuditProfile] = None
    summary: dict = field(default_factory=dict)      # ইঞ্জিনের সারসংক্ষেপ
    findings: list[dict] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)
    entitlement_para: str = ""

    def label_or(self, value: str, fallback: str = "—") -> str:
        return value.strip() if value and value.strip() else fallback


# ==========================================================
# সহায়ক
# ==========================================================

def _claim_rows(summary: dict) -> list[list[str]]:
    """সারসংক্ষেপ হইতে দাবির ছক — কেবল শূন্যের অধিক অঙ্কগুলি"""
    rows = []
    for k, v in summary.items():
        if not k.startswith("দাবি") or not isinstance(v, (int, float)):
            continue
        if not v:
            continue
        rows.append([k.replace(" (BDT)", ""), _indian_group(float(v))])
    return rows


def _total_claim(summary: dict) -> float:
    return float(summary.get("সর্বমোট রাজস্ব দাবি (BDT)") or 0)


# ==========================================================
# নির্মাতা
# ==========================================================

class AuditReportBuilder:
    """পূর্ণাঙ্গ নিরীক্ষা প্রতিবেদন গড়ে"""

    def __init__(self, ctx: ReportContext, scheme: FontScheme | str = "nikosh"):
        self.ctx = ctx
        self.scheme = scheme if isinstance(scheme, FontScheme) else scheme_for(scheme)
        self.doc = ReportDocument(self.scheme)
        self.plan = assemble_report_plan(
            ctx.profile or AuditProfile(), ctx.findings
        )

    # ------------------------------------------------------
    def build(self) -> ReportDocument:
        self._cover()
        self._background()
        self._paragraph_index()
        self._review()
        self._findings()
        self._document_gaps()
        self._opinion()
        return self.doc

    # ---- ১. শিরোনাম ও পরিচিতি --------------------------
    def _cover(self) -> None:
        c = self.ctx
        self.doc.title(
            "নিরীক্ষা প্রতিবেদন",
            f"{c.label_or(c.period_from)} হইতে {c.label_or(c.period_to)} মেয়াদ",
        )
        self.doc.spacer()
        self.doc.table(
            ["বিবরণ", "তথ্য"],
            [
                ["প্রতিষ্ঠানের নাম", c.label_or(c.company)],
                ["ঠিকানা", c.label_or(c.address)],
                ["প্রতিষ্ঠানের শ্রেণি", c.label_or(c.entity_label)],
                ["বন্ড লাইসেন্স নং", c.label_or(c.bond_license)],
                ["ব্যবসা শনাক্তকরণ নম্বর", c.label_or(c.bin_no)],
                ["নিরীক্ষা মেয়াদ",
                 f"{c.label_or(c.period_from)} — {c.label_or(c.period_to)}"],
                ["প্রতিবেদনের তারিখ",
                 c.label_or(c.audit_date, bn(date.today().strftime("%d/%m/%Y")))],
            ],
        )

    # ---- ২. পটভূমি ------------------------------------
    def _background(self) -> None:
        self.doc.heading("নিরীক্ষার পটভূমি ও পরিধি")
        self.doc.para(
            "কাস্টমস আইন, ২০২৩ এবং উহার অধীন প্রণীত এসআরও নং "
            "২১২-আইন/২০২৪/৪৬৭/কাস্টমস ও এসআরও নং ২১৪-আইন/২০২৪/৪৬৯/কাস্টমস "
            "এর বিধানাবলির আলোকে আলোচ্য প্রতিষ্ঠানের বন্ড সুবিধায় আমদানিকৃত "
            "কাঁচামালের ব্যবহার, মজুদ ও রপ্তানি সংক্রান্ত নিরীক্ষা কার্যক্রম "
            "সম্পন্ন করা হইয়াছে।"
        )
        self.doc.para(
            "নিরীক্ষায় প্রতিষ্ঠান কর্তৃক দাখিলকৃত দলিলাদি, জাতীয় রাজস্ব "
            "বোর্ডের এমআইএস তথ্য এবং সংশ্লিষ্ট কাস্টম হাউসের রেকর্ড "
            "পর্যালোচনা করা হইয়াছে।"
        )

    # ---- ৩. অনুচ্ছেদক্রম -------------------------------
    def _paragraph_index(self) -> None:
        paras = self.plan.get("paragraphs", [])
        if not paras:
            return
        self.doc.heading("প্রতিবেদনের অনুচ্ছেদক্রম")
        self.doc.para(
            f"নিরীক্ষার ধরন অনুযায়ী নিম্নবর্ণিত {bn(str(len(paras)))}টি "
            "অনুচ্ছেদ প্রযোজ্য হইয়াছে। অপ্রাসঙ্গিক অনুচ্ছেদসমূহ বাদ "
            "দেওয়া হইয়াছে।"
        )
        self.doc.numbered(paras)

    # ---- ৪. পর্যালোচনা ---------------------------------
    def _review(self) -> None:
        qs = self.plan.get("review_questions", [])
        if not qs:
            return
        self.doc.page_break()
        self.doc.heading("পর্যালোচনা")
        self.doc.para(
            "নিম্নের ছকে নিরীক্ষাকালে যাচাইকৃত বিষয়সমূহ ও তাহার ফলাফল "
            "উপস্থাপন করা হইল।"
        )
        rows = [[bn(str(i)), q, fmt] for i, (q, fmt, _) in enumerate(qs, 1)]
        self.doc.table(["ক্রমিক", "যাহা যাচাই করা হইয়াছে", "ফলাফল"], rows)

    # ---- ৫. প্রাপ্ত আপত্তি ------------------------------
    def _findings(self) -> None:
        rows = _claim_rows(self.ctx.summary)
        self.doc.heading("নিরীক্ষায় উদ্ঘাটিত আপত্তি")

        if not rows:
            self.doc.para(
                "আলোচ্য নিরীক্ষা মেয়াদে পরিমাণগত কোনো আপত্তি উদ্ঘাটিত "
                "হয় নাই। প্রতিষ্ঠানের বন্ড সুবিধায় আমদানিকৃত কাঁচামালের "
                "ব্যবহার ও মজুদ বিধি-বিধানের সহিত সামঞ্জস্যপূর্ণ পাওয়া "
                "গিয়াছে।"
            )
            return

        total = _total_claim(self.ctx.summary)
        self.doc.para(
            "নিরীক্ষায় নিম্নবর্ণিত আপত্তিসমূহ উদ্ঘাটিত হইয়াছে। প্রতিটি "
            "খাতের বিস্তারিত বর্ণনা সংশ্লিষ্ট অনুচ্ছেদে এবং আদায়যোগ্য "
            "শুল্ক-করাদির হিসাব সংযুক্ত ছকে উপস্থাপিত হইল।"
        )
        rows.append(["সর্বমোট", _indian_group(total)])
        self.doc.table(["আপত্তির খাত", "টাকার পরিমাণ"], rows)

    # ---- ৬. দলিল-ঘাটতি ---------------------------------
    def _document_gaps(self) -> None:
        if not self.ctx.missing_docs:
            return
        from services.evidence_paths import audit_route
        route = audit_route(self.ctx.missing_docs)

        self.doc.heading("দলিলের ঘাটতি ও তাহার প্রভাব")
        self.doc.para(
            "প্রতিষ্ঠান কর্তৃক নিম্নবর্ণিত দলিলাদি দাখিল করা হয় নাই। "
            "ইহার ফলে যে বিষয়গুলি নিশ্চিতভাবে নির্ণয় করা সম্ভব হয় নাই "
            "তাহা পৃথকভাবে উল্লেখ করা হইল। উক্ত বিষয়ে প্রমাণের অভাবে "
            "কোনো দাবি উত্থাপন করা হয় নাই।"
        )
        for p in route["paths"]:
            self.doc.para(f"{p['label']} — {p['normally_proves']}",
                          indent_cm=0.6)
            if p["blocked"]:
                self.doc.para(
                    "নির্ণয় করা সম্ভব হয় নাই: " + "; ".join(p["blocked"]),
                    indent_cm=1.2,
                )
        if route["requisitions"]:
            self.doc.spacer()
            self.doc.para("নিম্নবর্ণিত দলিলাদি তলব করা প্রয়োজন —")
            self.doc.numbered(route["requisitions"])

    # ---- ৭. প্রস্তাব ও মতামত ---------------------------
    def _opinion(self) -> None:
        c = self.ctx
        items = build_opinion(
            company=c.company,
            period_from=c.period_from,
            period_to=c.period_to,
            findings=self.plan.get("findings", []),
            entitlement_para=c.entitlement_para,
        )
        if not items:
            return

        self.doc.page_break()
        self.doc.heading("প্রস্তাব ও মতামত")
        paras = self.plan.get("paragraphs", [])
        self.doc.para(OPINION_OPENING.format(
            from_para="০২", to_para=bn(str(len(paras) or 39))
        ))
        self.doc.spacer()
        for it in items:
            self.doc.para(f"{it.label}\t{it.text}", indent_cm=0.8)
        self.doc.spacer()
        self.doc.para(OPINION_CLOSING)


# ==========================================================
# সহজ প্রবেশদ্বার
# ==========================================================

def build_audit_report(
    ctx: ReportContext, out_path: str | Path, font: str = "nikosh",
) -> Path:
    """প্রতিবেদন লিখিয়া ফাইলের পথ ফেরত দেয়"""
    b = AuditReportBuilder(ctx, font)
    b.build()
    path = b.doc.save(out_path)
    logger.info(
        f"নিরীক্ষা প্রতিবেদন: {ctx.company} | ফন্ট {b.scheme.bangla_font} | "
        f"আপত্তি {len(b.plan.get('findings', []))}টি"
    )
    return path


__all__ = ["AuditReportBuilder", "ReportContext", "build_audit_report"]
