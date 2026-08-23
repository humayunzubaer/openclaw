"""
Knowledge Base Loader — ১৫টি KB ফাইল থেকে ইঞ্জিনে জ্ঞান স্থাপন
=================================================================

উৎস: Project Knowledge-এ সংরক্ষিত ১৫টি সুগঠিত ফাইল (KB v1.0, 08-08-2026)

    00  Master Index ও Operating Protocol
    01  কাস্টমস আইন ২০২৩
    02  বন্ড বিধিমালা ও SRO
    03  মূসক ও এসডি আইন/বিধিমালা
    04  উৎসে মূসক (VDS) + CA Audit
    05  EPZ / BEPZA
    06  বৈদেশিক মুদ্রা ও বাণিজ্য নীতি
    07  Audit Test Library (১৪টি test)
    08  Rules Engine (machine-readable JSON)
    09  বন্ড SRO ২০৯–২১৪/২০২৪ পূর্ণ গেজেট-পাঠ
    10  মূসক ফরম (ঘর-স্তরে)
    11  নিরীক্ষা ম্যানুয়াল
    12  মূসক ফরম পূরণ ও ত্রুটি-শনাক্ত
    13  Temporal Resolver (কাল-নির্ণয়)
    14  ঐতিহাসিক রেজিম (Customs Act 1969)

★ তিনটি মৌলিক নীতি যা ইঞ্জিন কঠোরভাবে মানবে:

    ১) Certainty Grading — 【V】যাচাইকৃত | 【E】অনুমিত | 【P】অযাচাইকৃত
       কোনো ধারা/বিধি/SRO/হার/তারিখ **কখনো বানানো যাবে না**।
       KB-তে না থাকলে output-এ `[যাচাই করুন]` লিখতে হবে।

    ২) Finding-এর চার ধাপ — identify → quantify → cite law → state consequence
       সঙ্গে Defensibility-নোট ও তামাদি-নোট।

    ৩) Temporal Applicability — ঘটনার তারিখ অনুযায়ী আইনের সংস্করণ নির্বাচন।
       ০৬-০৬-২০২৪ এর আগে Customs Act 1969; পরে কাস্টমস আইন ২০২৩।
       দ্বৈত-রেজিম মেয়াদে খণ্ডভিত্তিক পৃথক উপ-finding; এক বাক্যে দুই
       রেজিমের ধারা মিশ্রিত করা নিষিদ্ধ।
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from utils.logger import logger

_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def bn_date(d: Optional[date]) -> str:
    """তারিখ বাংলা অঙ্কে — ১৪-০৮-২০২৫"""
    return d.strftime("%d-%m-%Y").translate(_BN) if d else "—"


# ==========================================================
# Certainty Grading
# ==========================================================

class Certainty:
    VERIFIED = "V"      # 【V】 প্রাথমিক উৎস থেকে যাচাইকৃত
    ESTIMATED = "E"     # 【E】 নির্ভরযোগ্য secondary উৎস
    PENDING = "P"       # 【P】 অযাচাইকৃত — অনুমানে পূরণ নিষিদ্ধ

    LABELS = {
        "V": "যাচাইকৃত",
        "E": "অনুমিত",
        "P": "অযাচাইকৃত",
    }
    MARKS = {"V": "【V】", "E": "【E】", "P": "【P】"}

    BEHAVIOUR = {
        "V": "SCN ও আনুষ্ঠানিক finding-এ ব্যবহারযোগ্য",
        "E": "খসড়ায় ব্যবহারযোগ্য; SCN-এর পূর্বে গেজেটে যাচাই বাধ্যতামূলক",
        "P": "ফাঁকা রাখুন বা [যাচাই করুন] flag দিন — কখনো অনুমানে পূরণ নয়",
    }

    @classmethod
    def mark(cls, grade: str) -> str:
        return cls.MARKS.get((grade or "P").upper()[:1], "【P】")

    @classmethod
    def usable_in_scn(cls, grade: str) -> bool:
        return (grade or "P").upper().startswith("V")


# ==========================================================
# আইনি উদ্ধৃতি
# ==========================================================

@dataclass
class LegalCitation:
    """একটি আইনি উদ্ধৃতি — certainty grade বহনকারী"""
    cite: str                       # হুবহু উদ্ধৃতি
    certainty: str = "P"
    instrument: str = ""            # কোন আইন/বিধিমালা/SRO
    section: str = ""               # ধারা/বিধি নম্বর
    module: str = ""                # KB module
    note: str = ""

    def render(self) -> str:
        """প্রতিবেদনে বসানোর রূপ"""
        out = self.cite
        if not out.endswith(Certainty.mark(self.certainty)):
            out = f"{out} {Certainty.mark(self.certainty)}"
        if self.certainty.upper().startswith("P"):
            out += " [প্রাথমিক উৎস যাচাই সাপেক্ষে]"
        return out


# ==========================================================
# Temporal Resolver — কাল-নির্ণয়
# ==========================================================

CUSTOMS_ACT_2023_EFFECTIVE = date(2024, 6, 6)
CUSTOMS_ACT_2023_SRO = "এসআরও নং ১৫৩-আইন/২০২৪, তারিখ ২৮-০৫-২০২৪"
VAT_CADENCE_SWITCH = date(2026, 7, 1)
BONDING_REGIME_SWITCH = date(2026, 7, 1)


@dataclass
class TemporalResolution:
    """একটি ঘটনার জন্য প্রযোজ্য আইনি সংস্করণ"""
    event_date: Optional[date]
    regime: str = ""                # customs_2023 | customs_1969 | dual
    instrument: str = ""
    basis: str = ""
    segments: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve_temporal(
    event_date: Optional[date] = None,
    period_from: Optional[date] = None,
    period_to: Optional[date] = None,
) -> TemporalResolution:
    """
    ★ ঘটনার তারিখ অনুযায়ী প্রযোজ্য আইনের সংস্করণ নির্ণয় করে।

    KB Module 13 (Temporal Resolver) ও Module 14 (ঐতিহাসিক রেজিম) অনুযায়ী।
    """
    cut = CUSTOMS_ACT_2023_EFFECTIVE

    if event_date:
        if event_date >= cut:
            return TemporalResolution(
                event_date=event_date, regime="customs_2023",
                instrument="কাস্টমস আইন, ২০২৩",
                basis=(
                    f"ঘটনার তারিখ {bn_date(event_date)} — "
                    f"{bn_date(cut)} বা তৎপরবর্তী হওয়ায় কাস্টমস "
                    f"আইন, ২০২৩ প্রযোজ্য ({CUSTOMS_ACT_2023_SRO}) "
                    f"{Certainty.mark('V')}"
                ),
            )
        return TemporalResolution(
            event_date=event_date, regime="customs_1969",
            instrument="Customs Act, 1969 (একাদশ অধ্যায়, ধারা ৮৪–১১৯)",
            basis=(
                f"ঘটনার তারিখ {bn_date(event_date)} — "
                f"{bn_date(cut)} এর পূর্বে হওয়ায় Customs Act, "
                f"1969 প্রযোজ্য {Certainty.mark('V')}"
            ),
        )

    # --- মেয়াদভিত্তিক ---
    if period_from and period_to:
        if period_to < cut:
            return TemporalResolution(
                event_date=None, regime="customs_1969",
                instrument="Customs Act, 1969",
                basis="সম্পূর্ণ নিরীক্ষা মেয়াদ কাস্টমস আইন ২০২৩ কার্যকরের পূর্বে",
            )
        if period_from >= cut:
            return TemporalResolution(
                event_date=None, regime="customs_2023",
                instrument="কাস্টমস আইন, ২০২৩",
                basis="সম্পূর্ণ নিরীক্ষা মেয়াদ কাস্টমস আইন ২০২৩ কার্যকরের পরে",
            )
        # ★ দ্বৈত রেজিম — খণ্ডভিত্তিক পৃথক finding আবশ্যক
        from datetime import timedelta
        res = TemporalResolution(
            event_date=None, regime="dual",
            instrument="Customs Act 1969 + কাস্টমস আইন ২০২৩",
            basis=(
                f"নিরীক্ষা মেয়াদ কাস্টমস আইন ২০২৩ কার্যকরের তারিখ "
                f"({bn_date(cut)}) অতিক্রম করেছে — খণ্ডভিত্তিক "
                f"পৃথক উপ-finding প্রস্তুত করতে হবে"
            ),
            segments=[
                {
                    "খণ্ড": "১",
                    "শুরু": period_from.isoformat(),
                    "শেষ": (cut - timedelta(days=1)).isoformat(),
                    "আইন": "Customs Act, 1969 (ধারা ৮৪–১১৯)",
                },
                {
                    "খণ্ড": "২",
                    "শুরু": cut.isoformat(),
                    "শেষ": period_to.isoformat(),
                    "আইন": "কাস্টমস আইন, ২০২৩",
                },
            ],
            warnings=[
                "⚠ এক বাক্যে দুই রেজিমের ধারা মিশ্রিত করা নিষিদ্ধ "
                "(KB Module 13)। প্রতিটি খণ্ডের জন্য পৃথক আইনি উদ্ধৃতি দিন।"
            ],
        )
        return res

    return TemporalResolution(
        event_date=None, regime="unknown",
        basis="তারিখ শনাক্ত করা যায়নি — [যাচাই করুন]",
        warnings=["⚠ ঘটনার তারিখ ছাড়া প্রযোজ্য আইনি সংস্করণ নির্ধারণ সম্ভব নয়"],
    )


# ==========================================================
# তামাদি (Limitation)
# ==========================================================

LIMITATION_YEARS_2023 = 3       # ধারা ২০৪(১) — ধারা ২০৩ নোটিশের শেষ সীমা
LIMITATION_NOTE_1969 = "ধারা ৩২ (১৯৬৯) — তামাদি-স্তর ভিন্ন; Module 14 দেখুন"


def limitation_note(
    event_date: Optional[date], regime: str = "customs_2023",
    fraud_alleged: bool = False,
) -> str:
    """★ প্রতিটি finding-এ বাধ্যতামূলক তামাদি-নোট"""
    if not event_date:
        return "তামাদি-নোট: ঘটনার তারিখ অনুপস্থিত — [যাচাই করুন]"

    if regime == "customs_1969":
        base = (
            f"তামাদি-নোট: ঘটনার তারিখ {bn_date(event_date)}; "
            f"{LIMITATION_NOTE_1969}"
        )
    else:
        deadline = date(
            event_date.year + LIMITATION_YEARS_2023,
            event_date.month, event_date.day,
        )
        base = (
            f"তামাদি-নোট: ঘটনার তারিখ {bn_date(event_date)} "
            f"+ ৩ বছর = {bn_date(deadline)} — কাস্টমস আইন, ২০২৩ এর "
            f"ধারা ২০৩ অনুযায়ী নোটিশ জারির শেষ সীমা [ধারা ২০৪(১)] "
            f"{Certainty.mark('V')}"
        )

    if fraud_alleged:
        base += (
            " জালিয়াতির দাবিতে ধারা ৩৩(৪) এর ব্যতিক্রম উদ্ধৃত হলে "
            "জালিয়াতির উপাদান পৃথকভাবে প্রমাণ-তালিকাভুক্ত করতে হবে।"
        )
    return base


# ==========================================================
# Finding সংযোজক — চার ধাপের কাঠামো
# ==========================================================

@dataclass
class StructuredFinding:
    """
    ★ KB-নির্দেশিত অভিন্ন finding কাঠামো।

    identify → quantify → cite law → state consequence
    + Defensibility-নোট + তামাদি-নোট
    """
    serial: int = 0
    title: str = ""

    identify: str = ""              # কী, কোথায়, কোন মেয়াদ, কোন দলিল-জোড়ায়
    quantify: str = ""              # পরিমাণ/অঙ্ক — টেবিল-রেফসহ
    citations: list[LegalCitation] = field(default_factory=list)
    applicable_version: str = ""    # প্রযোজ্য-সংস্করণ (বাধ্যতামূলক)
    consequence: str = ""           # শুল্ক-কর-সুদ-জরিমানা বা প্রশাসনিক সুপারিশ

    defensibility: str = ""
    limitation: str = ""

    test_id: str = ""               # কোন test থেকে (T-01…T-13)
    severity: str = "medium"
    is_supplementary: bool = False  # প্রশাসনিক/সম্পূরক পর্যবেক্ষণ কিনা
    amount: float = 0.0

    def render(self) -> str:
        """প্রতিবেদনে বসানোর সম্পূর্ণ রূপ (চলিত ভাষা)"""
        L: list[str] = [f"অনিয়ম নং {self.serial}: {self.title}", ""]
        L.append(f"১। শনাক্তকরণ: {self.identify}")
        L.append(f"২। পরিমাপ: {self.quantify}")

        L.append("৩। আইনি ভিত্তি:")
        if self.citations:
            for c in self.citations:
                L.append(f"    • {c.render()}")
        else:
            L.append("    • [যাচাই করুন] — KB-তে উদ্ধৃতি পাওয়া যায়নি")

        L.append(f"৩ক। প্রযোজ্য সংস্করণ: {self.applicable_version or '[যাচাই করুন]'}")
        L.append(f"৪। পরিণতি: {self.consequence}")

        if self.is_supplementary:
            L.append("    [সম্পূরক পর্যবেক্ষণ — রাজস্ব দাবি নয়]")

        L.append("")
        L.append(f"Defensibility-নোট: {self.defensibility or 'মূল্যায়ন প্রয়োজন'}")
        L.append(self.limitation or "তামাদি-নোট: [যাচাই করুন]")
        return "\n".join(L)

    @property
    def scn_ready(self) -> bool:
        """SCN-এ ব্যবহারযোগ্য কিনা — সব উদ্ধৃতি 【V】 হতে হবে"""
        return bool(self.citations) and all(
            Certainty.usable_in_scn(c.certainty) for c in self.citations
        )


# ==========================================================
# KB Loader
# ==========================================================

@dataclass
class AuditTest:
    """Audit Test Library-র একটি test"""
    id: str
    name: str
    inputs: list[str] = field(default_factory=list)
    formula: str = ""
    formulas: dict = field(default_factory=dict)
    checks: list[str] = field(default_factory=list)
    threshold: Any = None
    law_refs: list[LegalCitation] = field(default_factory=list)
    consequence: str = ""
    severity: str = "medium"
    module: str = ""


class KnowledgeBase:
    """
    ★ ১৫টি KB ফাইল থেকে ইঞ্জিনের জন্য জ্ঞান লোড করে।

    ব্যবহার:
        kb = KnowledgeBase("/mnt/project")
        kb.load()
        test = kb.get_test("T04A_entitlement_ceiling")
        cites = kb.find_citations("এককালীন বন্ডিং ক্যাপাসিটি")
    """

    def __init__(self, kb_dir: str | Path):
        self.dir = Path(kb_dir)
        self.tests: dict[str, AuditTest] = {}
        self.instruments: list[dict] = []
        self.constraints: dict = {}
        self.linguistic: dict[str, dict] = {}
        self.documents: dict[str, str] = {}     # module → পূর্ণ পাঠ
        self.version = ""
        self.build_date = ""
        self.notes: list[str] = []

    # ------------------------------------------------------
    def load(self) -> "KnowledgeBase":
        self._load_rules_json()
        self._load_markdown_docs()
        self._load_linguistic_layer()
        logger.success(
            f"KB লোড সম্পন্ন — {len(self.tests)}টি test, "
            f"{len(self.instruments)}টি instrument, "
            f"{len(self.documents)}টি দলিল"
        )
        return self

    # ------------------------------------------------------
    def _load_rules_json(self):
        """08_RULES_ENGINE.json — machine-readable রুল"""
        files = sorted(self.dir.glob("08_RULES_ENGINE*.json"))
        if not files:
            self.notes.append("⚠ 08_RULES_ENGINE.json পাওয়া যায়নি")
            return

        d = json.loads(files[-1].read_text(encoding="utf-8"))
        self.version = d.get("kb_version", "")
        self.build_date = d.get("build_date", "")
        self.constraints = d.get("global_constraints", {}) or {}

        for r in d.get("rules", []) or []:
            self.tests[r["id"]] = AuditTest(
                id=r["id"], name=r.get("name", ""),
                inputs=r.get("inputs", []) or [],
                formula=r.get("formula", "") or "",
                formulas=r.get("formulas", {}) or {},
                checks=r.get("checks", []) or [],
                threshold=r.get("threshold") or r.get("thresholds"),
                law_refs=self._parse_law_refs(r.get("law_ref")),
                consequence=r.get("consequence", "") or "",
                severity=r.get("severity", "medium") or "medium",
                module="08",
            )

        tr = d.get("temporal_registry", {}) or {}
        self.instruments = tr.get("instruments", []) or []

    @staticmethod
    def _parse_law_refs(raw) -> list[LegalCitation]:
        """law_ref একাধিক আকারে থাকতে পারে — সব সামলাও"""
        out: list[LegalCitation] = []
        if not raw:
            return out
        if isinstance(raw, str):
            g = "V" if "【V】" in raw else ("E" if "【E】" in raw else "P")
            return [LegalCitation(cite=raw, certainty=g)]
        if isinstance(raw, dict):
            raw = [raw]
        for item in raw:
            if isinstance(item, dict):
                out.append(LegalCitation(
                    cite=item.get("cite", ""),
                    certainty=(item.get("certainty", "P") or "P")[:1].upper(),
                ))
            else:
                out.append(LegalCitation(cite=str(item), certainty="P"))
        return out

    # ------------------------------------------------------
    def _load_markdown_docs(self):
        """০০–১৪ markdown দলিল পাঠ সংরক্ষণ"""
        for f in sorted(self.dir.glob("*.md")):
            m = re.match(r"^(\d{2})_", f.name)
            key = m.group(1) if m else f.stem
            try:
                self.documents[key] = f.read_text(encoding="utf-8")
            except Exception as e:
                self.notes.append(f"⚠ {f.name} পড়া যায়নি: {e}")

    # ------------------------------------------------------
    def _load_linguistic_layer(self):
        """Module 00-এর ভাষাগত সূক্ষ্মতা সারণি"""
        doc = self.documents.get("00", "")
        if not doc:
            return
        sec = doc.split("Linguistic Precision Layer")
        if len(sec) < 2:
            return
        for line in sec[1].splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3 or cells[0].startswith("---") or "শব্দ" in cells[0]:
                continue
            term = re.sub(r"\*\*", "", cells[0]).split("(")[0].strip()
            if term:
                self.linguistic[term] = {
                    "আইনি অর্থ": cells[1],
                    "ভুল-প্রয়োগ ঝুঁকি": cells[2] if len(cells) > 2 else "",
                }

    # ------------------------------------------------------
    # অনুসন্ধান
    # ------------------------------------------------------
    def get_test(self, test_id: str) -> Optional[AuditTest]:
        return self.tests.get(test_id)

    def find_tests(self, keyword: str) -> list[AuditTest]:
        k = (keyword or "").lower()
        return [
            t for t in self.tests.values()
            if k in t.id.lower() or k in t.name.lower()
            or k in t.formula.lower() or k in str(t.formulas).lower()
        ]

    def find_citations(self, query: str, limit: int = 12) -> list[LegalCitation]:
        """
        ★ প্রশ্নের সাথে প্রাসঙ্গিক আইনি উদ্ধৃতি খুঁজে দেয়।

        কেবল KB-তে বিদ্যমান উদ্ধৃতি ফেরত দেয় — কখনো বানায় না।
        """
        terms = [t for t in re.split(r"\s+", (query or "").strip()) if len(t) > 1]
        if not terms:
            return []

        out: list[LegalCitation] = []
        seen: set[str] = set()

        def _add(c: LegalCitation) -> bool:
            key = re.sub(r"\s+", "", c.cite)
            if not c.cite or key in seen:
                return False
            seen.add(key)
            out.append(c)
            return True

        # ১) test-এর law_ref থেকে
        for t in self.tests.values():
            blob = f"{t.name} {t.formula} {t.formulas} {t.checks}".lower()
            if any(x.lower() in blob for x in terms):
                for c in t.law_refs:
                    c.module = t.module
                    _add(c)

        # ২) markdown দলিল থেকে ধারা/বিধি/SRO উদ্ধৃতি
        pat = re.compile(
            r"(ধারা\s*[\d০-৯]+[^\s。|]{0,18}"
            r"|বিধি\s*[\d০-৯]+[^\s。|]{0,18}"
            r"|(?:এস\.?আর\.?ও|SRO)\s*নং?\s*[^\s,;।|]{2,40})"
            r"[^|\n]{0,80}?(【[VEP]】)?"
        )
        for mod, doc in self.documents.items():
            for line in doc.splitlines():
                low = line.lower()
                if not any(x.lower() in low for x in terms):
                    continue
                # লাইনের certainty grade নির্ণয় — নিকটতম চিহ্ন
                line_grade = (
                    "V" if "【V" in line else
                    "E" if "【E" in line else
                    "P" if "【P" in line else "P"
                )
                for m in pat.finditer(line):
                    cite = m.group(0).strip(" —-|*:)")
                    # শেষে অসম্পূর্ণ বন্ধনী/চিহ্ন পরিষ্কার
                    cite = re.sub(r"[\(\)\*:,।]+$", "", cite).strip()
                    if len(cite) < 6 or cite in seen:
                        continue
                    ctx = self._nearest_context(line, m.start())
                    # ★ প্রাসঙ্গিকতা যাচাই — প্রসঙ্গে অনুসন্ধান-শব্দ থাকতে হবে
                    if not any(x.lower() in ctx.lower() for x in terms):
                        continue
                    if _add(LegalCitation(
                        cite=cite, certainty=line_grade, module=mod, note=ctx,
                    )) and len(out) >= limit:
                        return out
        return out[:limit]

    @staticmethod
    def _nearest_context(line: str, pos: int, width: int = 110) -> str:
        """উদ্ধৃতির আশপাশের প্রসঙ্গ — নিরীক্ষক যাচাই করতে পারবেন"""
        a = max(0, pos - width // 2)
        return re.sub(r"\s+", " ", line[a:a + width]).strip(" |*")

    def search_docs(self, query: str, context_chars: int = 320,
                    limit: int = 8) -> list[dict]:
        """KB দলিলে পাঠ্য অনুসন্ধান — উৎস উল্লেখসহ"""
        terms = [t for t in re.split(r"\s+", (query or "").strip()) if len(t) > 1]
        if not terms:
            return []
        hits: list[dict] = []
        for mod, doc in sorted(self.documents.items()):
            for m in re.finditer(re.escape(terms[0]), doc):
                s = max(0, m.start() - context_chars // 2)
                snippet = doc[s:s + context_chars].replace("\n", " ")
                hits.append({
                    "module": mod,
                    "অংশ": snippet,
                })
                if len(hits) >= limit:
                    return hits
        return hits

    # ------------------------------------------------------
    def check_term(self, term: str) -> Optional[dict]:
        """ভাষাগত সূক্ষ্মতা যাচাই — 'খালাস' বনাম 'ছাড়' ইত্যাদি"""
        for k, v in self.linguistic.items():
            if term.strip() in k or k in term:
                return {"শব্দ": k, **v}
        return None

    # ------------------------------------------------------
    def summary(self) -> dict:
        return {
            "KB সংস্করণ": self.version or "—",
            "নির্মাণ তারিখ": self.build_date or "—",
            "Audit Test সংখ্যা": len(self.tests),
            "Test তালিকা": sorted(self.tests.keys()),
            "Instrument সংখ্যা": len(self.instruments),
            "দলিল সংখ্যা": len(self.documents),
            "ভাষাগত পরিভাষা": len(self.linguistic),
            "কঠোর নিষেধাজ্ঞা": self.constraints.get("never_fabricate", []),
            "Finding কাঠামো": self.constraints.get("finding_structure", []),
            "টীকা": self.notes,
        }


__all__ = [
    "Certainty", "LegalCitation", "StructuredFinding",
    "AuditTest", "KnowledgeBase",
    "TemporalResolution", "resolve_temporal", "limitation_note",
    "CUSTOMS_ACT_2023_EFFECTIVE", "CUSTOMS_ACT_2023_SRO",
]
