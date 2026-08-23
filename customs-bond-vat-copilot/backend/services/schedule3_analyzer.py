"""
Schedule-3 Analyzer — বার্ষিক আমদানি-রপ্তানি বিবরণী বিশ্লেষণ
================================================================

উৎস: এসআরও নং ২১২-আইন/২০২৪/৬৪/কাস্টমস — **তফসিল-৩** [বিধি ১৩ দ্রষ্টব্য]
      "সরাসরি ও প্রচ্ছন্ন রপ্তানিমুখী (পোশাক শিল্প ব্যতীত) শিল্প প্রতিষ্ঠান
       (ওয়্যারহাউস পদ্ধতির আওতায় সাময়িক আমদানি, ওয়্যারহাউস পরিচালনা ও
       কার্যপদ্ধতি) বিধিমালা, ২০২৪"  【V — গেজেট-পাঠ】

তফসিল-৩ এ দুটি ছক আছে:
    ছক-ক : সরাসরি রপ্তানিমুখী প্রতিষ্ঠানের বার্ষিক আমদানি-রপ্তানি বিবরণী
    ছক-খ : প্রচ্ছন্ন রপ্তানিমুখী প্রতিষ্ঠানের বার্ষিক আমদানি-রপ্তানি বিবরণী

★ এই মডিউল ছক-ক (সরাসরি) কে কেন্দ্র করে গঠিত; ছক-খ পৃথকভাবে সমর্থিত।

এই বিবরণী কেন গুরুত্বপূর্ণ:
    ইহা একটিমাত্র দলিলে **ছয়টি প্রবাহ** একত্রে ধারণ করে —
    রপ্তানি আদেশ → UP অনুমোদন → আমদানি → স্থানীয় সংগ্রহ →
    রপ্তানি → মূল্য প্রত্যাবাসন।
    ফলে প্রতিটি সারিতেই **আন্তঃপ্রবাহ অসঙ্গতি** ধরা পড়ে।
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Optional

from utils.logger import logger


# ==========================================================
# ছক-ক : সরাসরি রপ্তানিমুখী — ১৭ কলাম
# ==========================================================

SCHEDULE_3A_COLUMNS: list[tuple[str, str, str]] = [
    # (কলাম নং, শিরোনাম, গোষ্ঠী)
    ("১",  "সেলস কন্ট্রাক্ট / রপ্তানি এলসি", "রপ্তানি আদেশ"),
    ("২",  "ইউপি নং ও তারিখ", "অনুমোদন"),
    ("৩",  "ইউপিতে অনুমোদিত কাঁচামালের বিবরণ ও পরিমাণ", "অনুমোদন"),

    ("৪",  "এলসি নং ও তারিখ", "আমদানিকৃত কাঁচামাল"),
    ("৫",  "কাঁচামালের বর্ণনা", "আমদানিকৃত কাঁচামাল"),
    ("৬",  "মূল্য", "আমদানিকৃত কাঁচামাল"),
    ("৭",  "পরিমাণ (কেজি ও সংখ্যা)", "আমদানিকৃত কাঁচামাল"),

    ("৮",  "বিবি এলসি নং ও তারিখ", "স্থানীয় উৎস"),
    ("৯",  "কাঁচামালের বর্ণনা", "স্থানীয় উৎস"),
    ("১০", "মূল্য", "স্থানীয় উৎস"),
    ("১১", "পরিমাণ (কেজি ও সংখ্যা)", "স্থানীয় উৎস"),

    ("১২", "শিপিং বিল নং ও তারিখ", "রপ্তানি"),
    ("১৩", "রপ্তানিকৃত পণ্যের পরিমাণ (কেজি ও সংখ্যা)", "রপ্তানি"),
    ("১৪", "মজুদ পণ্যের পরিমাণ (কেজি ও সংখ্যা)", "মজুদ"),
    ("১৫", "মোট রপ্তানি মূল্য", "মূল্য"),
    ("১৬", "প্রত্যাবাসিত মূল্য", "মূল্য"),
    ("১৭", "মন্তব্য", "—"),
]

# ==========================================================
# ছক-খ : প্রচ্ছন্ন রপ্তানিমুখী — ১৭ কলাম
# ==========================================================

SCHEDULE_3B_COLUMNS: list[tuple[str, str, str]] = [
    ("১",  "ইউপি নং ও তারিখ", "অনুমোদন"),
    ("২",  "বিবিএলসি নং", "অনুমোদন"),
    ("৩",  "ইউপিতে অনুমোদিত কাঁচামালের বিবরণ ও পরিমাণ", "অনুমোদন"),
    ("৪",  "এলসি নং ও তারিখ", "আমদানিকৃত কাঁচামাল"),
    ("৫",  "কাঁচামালের বর্ণনা", "আমদানিকৃত কাঁচামাল"),
    ("৬",  "মূল্য", "আমদানিকৃত কাঁচামাল"),
    ("৭",  "পরিমাণ", "আমদানিকৃত কাঁচামাল"),
    ("৮",  "বিবিএলসি / মূসক চালান নং ও তারিখ", "স্থানীয় উৎস"),
    ("৯",  "কাঁচামালের বর্ণনা", "স্থানীয় উৎস"),
    ("১০", "মূল্য", "স্থানীয় উৎস"),
    ("১১", "পরিমাণ", "স্থানীয় উৎস"),
    ("১২", "উৎপাদিত পণ্যের বিবরণ", "সরবরাহ"),
    ("১৩", "সরবরাহকৃত পণ্যের পরিমাণ", "সরবরাহ"),
    ("১৪", "সরবরাহ গ্রহীতার নাম ও ঠিকানা", "সরবরাহ"),
    ("১৫", "মোট রপ্তানি মূল্য", "মূল্য"),
    ("১৬", "প্রত্যাবাসিত মূল্য", "মূল্য"),
    ("১৭", "মন্তব্য", "—"),
]


# ==========================================================
# একটি সারির উপস্থাপন
# ==========================================================

@dataclass
class Schedule3Row:
    """তফসিল-৩ ছক-ক এর একটি সারি"""
    row_no: int = 0

    # রপ্তানি আদেশ ও অনুমোদন (কলাম ১–৩)
    sales_contract: str = ""
    up_number: str = ""
    up_date: Optional[date] = None
    up_approved_desc: str = ""
    up_approved_qty: float = 0.0

    # আমদানিকৃত কাঁচামাল (কলাম ৪–৭)
    import_lc: str = ""
    import_lc_date: Optional[date] = None
    import_desc: str = ""
    import_value: float = 0.0
    import_qty_kg: float = 0.0
    import_qty_pcs: float = 0.0

    # স্থানীয় উৎস (কলাম ৮–১১)
    local_bblc: str = ""
    local_bblc_date: Optional[date] = None
    local_desc: str = ""
    local_value: float = 0.0
    local_qty_kg: float = 0.0
    local_qty_pcs: float = 0.0

    # রপ্তানি ও মজুদ (কলাম ১২–১৪)
    shipping_bill: str = ""
    shipping_bill_date: Optional[date] = None
    export_qty_kg: float = 0.0
    export_qty_pcs: float = 0.0
    stock_qty_kg: float = 0.0
    stock_qty_pcs: float = 0.0

    # মূল্য (কলাম ১৫–১৭)
    export_value: float = 0.0
    repatriated_value: float = 0.0
    remarks: str = ""

    # গণনাকৃত
    @property
    def total_input_kg(self) -> float:
        """মোট কাঁচামাল = আমদানি + স্থানীয়"""
        return (self.import_qty_kg or 0) + (self.local_qty_kg or 0)

    @property
    def total_input_value(self) -> float:
        return (self.import_value or 0) + (self.local_value or 0)

    @property
    def unrepatriated(self) -> float:
        return max(0.0, (self.export_value or 0) - (self.repatriated_value or 0))


# ==========================================================
# বিশ্লেষণের ফলাফল
# ==========================================================

@dataclass
class Schedule3Issue:
    """তফসিল-৩ বিশ্লেষণে প্রাপ্ত একটি অসঙ্গতি"""
    row_no: int
    check_id: str
    title: str
    columns: str                # কোন কলামসমূহ জড়িত
    detail: str
    severity: str = "medium"
    test_ref: str = ""          # KB Audit Test
    legal_ref: str = ""
    certainty: str = "V"
    amount: float = 0.0


@dataclass
class Schedule3Result:
    rows: int = 0
    issues: list[Schedule3Issue] = field(default_factory=list)
    totals: dict[str, float] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ==========================================================
# ★ বিশ্লেষক — ১১টি আন্তঃকলাম যাচাই
# ==========================================================

class Schedule3Analyzer:
    """
    তফসিল-৩ ছক-ক বিশ্লেষণ করে ১১টি যাচাই চালায়।

    প্রতিটি যাচাই KB-র Audit Test-এর সাথে সংযুক্ত।
    """

    # সহনসীমা
    INPUT_OUTPUT_TOLERANCE = 0.005      # ০.৫% — T-01 এর সমান
    REPATRIATION_DAYS = 120             # T-08
    MIN_VALUE_ADDITION = 15.0           # T-06 [SRO ২১২ বিধি ১০(৮)]

    def __init__(self, rows: list[Schedule3Row], period_from: Optional[date] = None,
                 period_to: Optional[date] = None):
        self.rows = rows
        self.period_from = period_from
        self.period_to = period_to

    # ------------------------------------------------------
    def analyze(self) -> Schedule3Result:
        res = Schedule3Result(rows=len(self.rows))

        for r in self.rows:
            self._check_up_ceiling(r, res)          # ১
            self._check_material_balance(r, res)    # ২
            self._check_up_before_import(r, res)    # ৩
            self._check_export_without_up(r, res)   # ৪
            self._check_repatriation(r, res)        # ৫
            self._check_value_addition(r, res)      # ৬
            self._check_description_match(r, res)   # ৭
            self._check_local_documents(r, res)     # ৮
            self._check_negative_stock(r, res)      # ৯
            self._check_export_without_input(r, res)  # ১০
            self._check_missing_shipping(r, res)    # ১১

        self._build_totals(res)
        self._build_summary(res)
        return res

    # ------------------------------------------------------
    # যাচাই ১ — ইউপি অনুমোদিত পরিমাণ অতিক্রম
    # ------------------------------------------------------
    def _check_up_ceiling(self, r: Schedule3Row, res: Schedule3Result):
        if r.up_approved_qty <= 0:
            return
        used = r.total_input_kg
        if used > r.up_approved_qty * (1 + self.INPUT_OUTPUT_TOLERANCE):
            excess = used - r.up_approved_qty
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-01",
                title="ইউপিতে অনুমোদিত পরিমাণের অতিরিক্ত কাঁচামাল সংগ্রহ",
                columns="৩ বনাম ৭+১১",
                detail=(
                    f"ইউপি {r.up_number} এ অনুমোদিত {r.up_approved_qty:,.3f} কেজি; "
                    f"প্রকৃতপক্ষে আমদানি {r.import_qty_kg:,.3f} + স্থানীয় "
                    f"{r.local_qty_kg:,.3f} = {used:,.3f} কেজি — অতিরিক্ত "
                    f"{excess:,.3f} কেজি ({excess/r.up_approved_qty*100:.2f}%)।"
                ),
                severity="high", test_ref="T-04",
                legal_ref=(
                    "এসআরও ২১২-আইন/২০২৪/৬৪ — ইউপি অনুমোদনের শর্ত; "
                    "কাস্টমস আইন, ২০২৩ ধারা ১২(৪)(ক)"
                ),
                amount=excess,
            ))

    # ------------------------------------------------------
    # যাচাই ২ — কাঁচামালের ভারসাম্য
    # ------------------------------------------------------
    def _check_material_balance(self, r: Schedule3Row, res: Schedule3Result):
        """
        মোট প্রাপ্তি = রপ্তানিতে ব্যবহৃত + মজুদ (+ অনুমোদিত অপচয়)

        তফসিল-৩ এ অপচয়ের কলাম নেই — তাই ফাঁক থাকলে ইউপির সহগ-ছক
        (তফসিল-২ ক্রমিক ১২) এর সাথে মিলিয়ে দেখতে হবে।
        """
        received = r.total_input_kg
        if received <= 0:
            return
        accounted = (r.export_qty_kg or 0) + (r.stock_qty_kg or 0)
        gap = received - accounted
        if abs(gap) <= received * self.INPUT_OUTPUT_TOLERANCE:
            return

        if gap > 0:
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-02",
                title="কাঁচামালের হিসাবে ঘাটতি — অপ্রদত্ত পরিমাণ",
                columns="৭+১১ বনাম ১৩+১৪",
                detail=(
                    f"মোট প্রাপ্তি {received:,.3f} কেজি; রপ্তানিতে ব্যবহৃত "
                    f"{r.export_qty_kg:,.3f} + মজুদ {r.stock_qty_kg:,.3f} = "
                    f"{accounted:,.3f} কেজি। হিসাব-বহির্ভূত {gap:,.3f} কেজি। "
                    f"ইউপির সহগ-ছক অনুযায়ী অনুমোদিত অপচয় বাদ দিয়ে অবশিষ্ট "
                    f"পরিমাণের ব্যাখ্যা তলব করা প্রয়োজন।"
                ),
                severity="high", test_ref="T-01",
                legal_ref=(
                    "কাস্টমস আইন, ২০২৩ ধারা ১২৬(গ) [হিসাব-অপ্রদত্ত পণ্য] "
                    "সহপঠিত ধারা ১২৮ [রেকর্ড সংরক্ষণের দায়]"
                ),
                amount=gap,
            ))
        else:
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-02খ",
                title="প্রাপ্তির অতিরিক্ত ব্যবহার — রেজিস্টারে অসঙ্গতি",
                columns="৭+১১ বনাম ১৩+১৪",
                detail=(
                    f"রপ্তানি ও মজুদের যোগফল {accounted:,.3f} কেজি প্রাপ্তি "
                    f"{received:,.3f} কেজির চেয়ে {abs(gap):,.3f} কেজি বেশি — "
                    f"অঘোষিত উৎস হতে কাঁচামাল সংগ্রহের সম্ভাবনা।"
                ),
                severity="high", test_ref="T-01",
                legal_ref="কাস্টমস আইন, ২০২৩ ধারা ১২৮",
                amount=abs(gap),
            ))

    # ------------------------------------------------------
    # যাচাই ৩ — ইউপির পূর্বে আমদানি
    # ------------------------------------------------------
    def _check_up_before_import(self, r: Schedule3Row, res: Schedule3Result):
        if not (r.up_date and r.import_lc_date):
            return
        if r.import_lc_date < r.up_date:
            days = (r.up_date - r.import_lc_date).days
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-03",
                title="ইউপি অনুমোদনের পূর্বে আমদানি এলসি স্থাপন",
                columns="২ বনাম ৪",
                detail=(
                    f"আমদানি এলসি {r.import_lc} তারিখ "
                    f"{r.import_lc_date.strftime('%d-%m-%Y')}; ইউপি "
                    f"{r.up_number} অনুমোদন {r.up_date.strftime('%d-%m-%Y')} — "
                    f"{days} দিন পূর্বে এলসি স্থাপিত। ইউপি ব্যতিরেকে বন্ড "
                    f"সুবিধায় আমদানির সূচনা যথাযথ কিনা যাচাই আবশ্যক।"
                ),
                severity="medium", test_ref="T-04",
                legal_ref="এসআরও ২১২-আইন/২০২৪/৬৪ — ইউপি পদ্ধতি",
                certainty="E",
            ))

    # ------------------------------------------------------
    # যাচাই ৪ — ইউপি ব্যতিরেকে রপ্তানি
    # ------------------------------------------------------
    def _check_export_without_up(self, r: Schedule3Row, res: Schedule3Result):
        if (r.export_qty_kg or r.export_value) and not r.up_number.strip():
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-04",
                title="ইউপি নম্বর উল্লেখ ব্যতিরেকে রপ্তানি",
                columns="২ বনাম ১২–১৩",
                detail=(
                    f"শিপিং বিল {r.shipping_bill or '—'} এর বিপরীতে "
                    f"{r.export_qty_kg:,.3f} কেজি রপ্তানি দেখানো হয়েছে, কিন্তু "
                    f"সংশ্লিষ্ট ইউপি নম্বর উল্লেখ নেই।"
                ),
                severity="high", test_ref="T-04",
                legal_ref="এসআরও ২১২-আইন/২০২৪/৬৪ — ইউপি ব্যতীত খালাস নিষিদ্ধ",
            ))

    # ------------------------------------------------------
    # যাচাই ৫ — মূল্য প্রত্যাবাসন
    # ------------------------------------------------------
    def _check_repatriation(self, r: Schedule3Row, res: Schedule3Result):
        if (r.export_value or 0) <= 0:
            return
        gap = r.unrepatriated
        if gap <= 0.01:
            return

        overdue_txt = ""
        if r.shipping_bill_date:
            from datetime import timedelta
            due = r.shipping_bill_date + timedelta(days=self.REPATRIATION_DAYS)
            today = self.period_to or date.today()
            if today > due:
                overdue_txt = (
                    f" জাহাজীকরণ {r.shipping_bill_date.strftime('%d-%m-%Y')} "
                    f"হতে {self.REPATRIATION_DAYS} দিনের সময়সীমা "
                    f"{due.strftime('%d-%m-%Y')} অতিক্রান্ত "
                    f"({(today - due).days} দিন)।"
                )

        res.issues.append(Schedule3Issue(
            row_no=r.row_no, check_id="S3-05",
            title="রপ্তানি মূল্য অপ্রত্যাবাসিত",
            columns="১৫ বনাম ১৬",
            detail=(
                f"মোট রপ্তানি মূল্য {r.export_value:,.2f}; প্রত্যাবাসিত "
                f"{r.repatriated_value:,.2f}; অপ্রত্যাবাসিত {gap:,.2f} "
                f"({gap/r.export_value*100:.2f}%)।" + overdue_txt
            ),
            severity="medium", test_ref="T-08",
            legal_ref=(
                "FERA 1947 [প্রত্যাবাসন-দায়] সহপঠিত GFET; "
                "লিয়েন ব্যাংকের Force Loan Certificate তলব করুন"
            ),
            certainty="E", amount=gap,
        ))

    # ------------------------------------------------------
    # যাচাই ৬ — মূল্য সংযোজনের হার
    # ------------------------------------------------------
    def _check_value_addition(self, r: Schedule3Row, res: Schedule3Result):
        """
        ★ T-06 — SRO ২১২ বিধি ১০(৮): ইউপিতে মূল্য সংযোজনের হার উল্লেখ
        বাধ্যতামূলক এবং তা ১৫% এর কম হবে না।

        VA% = (রপ্তানি FOB − ব্যবহৃত কাঁচামালের আমদানি মূল্য) ÷ রপ্তানি FOB × ১০০
        """
        fob = r.export_value or 0
        inp = r.total_input_value or 0
        if fob <= 0 or inp <= 0:
            return

        va = (fob - inp) / fob * 100
        if va >= self.MIN_VALUE_ADDITION:
            return

        res.issues.append(Schedule3Issue(
            row_no=r.row_no, check_id="S3-06",
            title="মূল্য সংযোজনের হার বিধিবদ্ধ ন্যূনতম সীমার নিচে",
            columns="৬+১০ বনাম ১৫",
            detail=(
                f"রপ্তানি মূল্য {fob:,.2f}; ব্যবহৃত কাঁচামালের মূল্য "
                f"(আমদানি {r.import_value:,.2f} + স্থানীয় {r.local_value:,.2f}) "
                f"= {inp:,.2f}। মূল্য সংযোজনের হার {va:.2f}% — বিধিবদ্ধ "
                f"ন্যূনতম {self.MIN_VALUE_ADDITION:.0f}% এর চেয়ে "
                f"{self.MIN_VALUE_ADDITION - va:.2f} শতাংশ বিন্দু কম।"
            ),
            severity="high", test_ref="T-06",
            legal_ref=(
                "এসআরও ২১২-আইন/২০২৪/৬৪ — বিধি ১০(৮) [ইউপিতে মূল্য সংযোজনের "
                "হার উল্লেখ বাধ্যতামূলক, ১৫% এর কম নয়]; গণনার বিধিবদ্ধ স্থান: "
                "তফসিল-২ ক্রমিক ১৪(ঘ)"
            ),
        ))

    # ------------------------------------------------------
    # যাচাই ৭ — পণ্যের বর্ণনার অসঙ্গতি
    # ------------------------------------------------------
    def _check_description_match(self, r: Schedule3Row, res: Schedule3Result):
        if not (r.up_approved_desc and (r.import_desc or r.local_desc)):
            return
        from ai.matcher import normalize
        up = set(normalize(r.up_approved_desc).split())
        got = set(normalize(f"{r.import_desc} {r.local_desc}").split())
        if not up or not got:
            return
        overlap = len(up & got) / max(1, len(up))
        if overlap < 0.34:
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-07",
                title="ইউপিতে অনুমোদিত কাঁচামালের সাথে সংগৃহীত কাঁচামালের বর্ণনার অমিল",
                columns="৩ বনাম ৫/৯",
                detail=(
                    f"ইউপিতে অনুমোদিত: «{r.up_approved_desc[:70]}»; "
                    f"সংগৃহীত: «{(r.import_desc or r.local_desc)[:70]}» — "
                    f"শব্দগত মিল কেবল {overlap*100:.0f}%। অনুমোদিত কাঁচামালের "
                    f"পরিবর্তে ভিন্ন পণ্য সংগ্রহ করা হয়েছে কিনা যাচাই করুন।"
                ),
                severity="medium", test_ref="T-04",
                legal_ref="এসআরও ২১২-আইন/২০২৪/৬৪ — ইউপিতে বর্ণিত পণ্যই খালাসযোগ্য",
                certainty="E",
            ))

    # ------------------------------------------------------
    # যাচাই ৮ — স্থানীয় সংগ্রহের দলিল
    # ------------------------------------------------------
    def _check_local_documents(self, r: Schedule3Row, res: Schedule3Result):
        """
        ★ তফসিল-২ ক্রমিক ১৫(গ): স্থানীয় সংগ্রহ বিবিএলসি-তে হতে হবে
        এবং মূসক চালান দাখিল করতে হবে।
        """
        if (r.local_qty_kg or r.local_value) and not r.local_bblc.strip():
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-08",
                title="স্থানীয় উৎস হতে সংগৃহীত কাঁচামালের বিবিএলসি/মূসক চালান অনুপস্থিত",
                columns="৮ বনাম ১০–১১",
                detail=(
                    f"স্থানীয় উৎস হতে {r.local_qty_kg:,.3f} কেজি "
                    f"(মূল্য {r.local_value:,.2f}) সংগ্রহ দেখানো হলেও "
                    f"বিবিএলসি নম্বর ও তারিখ উল্লেখ নেই। বন্ড সুবিধায় "
                    f"স্থানীয় সংগ্রহের বৈধতা প্রশ্নবিদ্ধ।"
                ),
                severity="high", test_ref="T-12",
                legal_ref=(
                    "এসআরও ২১২-আইন/২০২৪/৬৪ — তফসিল-২ ক্রমিক ১৫(গ) "
                    "[স্থানীয় সংগ্রহ বিবিএলসি-তে + মূসক চালান দাখিল]; "
                    "উৎসে মূসক কর্তনের বাধ্যবাধকতা যাচাই করুন"
                ),
                amount=r.local_value,
            ))

    # ------------------------------------------------------
    # যাচাই ৯ — ঋণাত্মক মজুদ
    # ------------------------------------------------------
    def _check_negative_stock(self, r: Schedule3Row, res: Schedule3Result):
        if (r.stock_qty_kg or 0) < 0:
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-09",
                title="ঋণাত্মক মজুদ — বিবরণীতে অসত্যতা",
                columns="১৪",
                detail=(
                    f"মজুদ পণ্যের পরিমাণ {r.stock_qty_kg:,.3f} কেজি — "
                    f"ঋণাত্মক মজুদ বাস্তবে অসম্ভব; রেজিস্টার ও বিবরণীর "
                    f"সত্যতা যাচাই আবশ্যক।"
                ),
                severity="high", test_ref="T-01",
                legal_ref="কাস্টমস আইন, ২০২৩ ধারা ১২৮",
            ))

    # ------------------------------------------------------
    # যাচাই ১০ — কাঁচামাল ব্যতীত রপ্তানি
    # ------------------------------------------------------
    def _check_export_without_input(self, r: Schedule3Row, res: Schedule3Result):
        if (r.export_qty_kg or 0) > 0 and r.total_input_kg <= 0:
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-10",
                title="কাঁচামাল সংগ্রহের হিসাব ব্যতিরেকে রপ্তানি",
                columns="৭+১১ বনাম ১৩",
                detail=(
                    f"{r.export_qty_kg:,.3f} কেজি রপ্তানি দেখানো হয়েছে, কিন্তু "
                    f"আমদানি বা স্থানীয় সংগ্রহ কোনোটিই উল্লেখ নেই। পূর্ববর্তী "
                    f"মেয়াদের জের হতে ব্যবহৃত হলে তা মন্তব্য কলামে উল্লেখ থাকা "
                    f"প্রয়োজন।"
                ),
                severity="medium", test_ref="T-01",
                legal_ref="কাস্টমস আইন, ২০২৩ ধারা ১২৮",
            ))

    # ------------------------------------------------------
    # যাচাই ১১ — শিপিং বিল অনুপস্থিত
    # ------------------------------------------------------
    def _check_missing_shipping(self, r: Schedule3Row, res: Schedule3Result):
        if (r.export_value or 0) > 0 and not r.shipping_bill.strip():
            res.issues.append(Schedule3Issue(
                row_no=r.row_no, check_id="S3-11",
                title="রপ্তানি মূল্য উল্লেখ থাকলেও শিপিং বিল নম্বর অনুপস্থিত",
                columns="১২ বনাম ১৫",
                detail=(
                    f"রপ্তানি মূল্য {r.export_value:,.2f} উল্লেখ থাকলেও শিপিং "
                    f"বিল (বিল অব এক্সপোর্ট) নম্বর ও তারিখ নেই। শূন্যহার "
                    f"সুবিধার দলিলগত ভিত্তি অসম্পূর্ণ।"
                ),
                severity="medium", test_ref="T-13",
                legal_ref=(
                    "মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২ ধারা ২১ "
                    "[শূন্যহার সরবরাহের দলিল]"
                ),
            ))

    # ------------------------------------------------------
    def _build_totals(self, res: Schedule3Result):
        t = {
            "মোট ইউপি অনুমোদিত (কেজি)": sum(r.up_approved_qty for r in self.rows),
            "মোট আমদানি (কেজি)": sum(r.import_qty_kg for r in self.rows),
            "মোট স্থানীয় সংগ্রহ (কেজি)": sum(r.local_qty_kg for r in self.rows),
            "মোট কাঁচামাল প্রাপ্তি (কেজি)": sum(r.total_input_kg for r in self.rows),
            "মোট রপ্তানি (কেজি)": sum(r.export_qty_kg for r in self.rows),
            "মোট মজুদ (কেজি)": sum(r.stock_qty_kg for r in self.rows),
            "মোট আমদানি মূল্য": sum(r.import_value for r in self.rows),
            "মোট স্থানীয় মূল্য": sum(r.local_value for r in self.rows),
            "মোট রপ্তানি মূল্য": sum(r.export_value for r in self.rows),
            "মোট প্রত্যাবাসিত মূল্য": sum(r.repatriated_value for r in self.rows),
            "মোট অপ্রত্যাবাসিত": sum(r.unrepatriated for r in self.rows),
        }
        # সামগ্রিক মূল্য সংযোজন
        fob = t["মোট রপ্তানি মূল্য"]
        inp = t["মোট আমদানি মূল্য"] + t["মোট স্থানীয় মূল্য"]
        t["সামগ্রিক মূল্য সংযোজনের হার (%)"] = (
            round((fob - inp) / fob * 100, 2) if fob else 0.0
        )
        # ভারসাম্য
        t["হিসাব-বহির্ভূত (কেজি)"] = round(
            t["মোট কাঁচামাল প্রাপ্তি (কেজি)"]
            - t["মোট রপ্তানি (কেজি)"] - t["মোট মজুদ (কেজি)"], 3
        )
        res.totals = {k: round(v, 3) if isinstance(v, float) else v
                      for k, v in t.items()}

    # ------------------------------------------------------
    def _build_summary(self, res: Schedule3Result):
        by_sev: dict[str, int] = {}
        by_check: dict[str, int] = {}
        for i in res.issues:
            by_sev[i.severity] = by_sev.get(i.severity, 0) + 1
            by_check[i.check_id] = by_check.get(i.check_id, 0) + 1

        va = res.totals.get("সামগ্রিক মূল্য সংযোজনের হার (%)", 0)
        res.summary = {
            "বিবরণী": "তফসিল-৩ ছক-ক (সরাসরি রপ্তানিমুখী)",
            "আইনি ভিত্তি": (
                "এসআরও নং ২১২-আইন/২০২৪/৬৪/কাস্টমস — তফসিল-৩ "
                "[বিধি ১৩ দ্রষ্টব্য] 【V】"
            ),
            "সারি সংখ্যা": res.rows,
            "মোট অসঙ্গতি": len(res.issues),
            "গুরুত্ব অনুযায়ী": by_sev,
            "যাচাই অনুযায়ী": by_check,
            "সামগ্রিক মূল্য সংযোজনের হার": f"{va:.2f}%",
            "মূল্য সংযোজন সীমার মধ্যে": va >= self.MIN_VALUE_ADDITION,
        }
        if va and va < self.MIN_VALUE_ADDITION:
            res.warnings.append(
                f"⛔ সামগ্রিক মূল্য সংযোজনের হার {va:.2f}% — বিধিবদ্ধ ন্যূনতম "
                f"{self.MIN_VALUE_ADDITION:.0f}% এর নিচে [এসআরও ২১২ বিধি ১০(৮)]"
            )
        gap = res.totals.get("হিসাব-বহির্ভূত (কেজি)", 0)
        if abs(gap) > 0.001:
            res.warnings.append(
                f"⚠ সামগ্রিকভাবে {gap:,.3f} কেজি কাঁচামাল হিসাব-বহির্ভূত — "
                f"ইউপির সহগ-ছক (তফসিল-২ ক্রমিক ১২) অনুযায়ী অনুমোদিত অপচয়ের "
                f"সাথে মিলিয়ে যাচাই করুন"
            )


__all__ = [
    "SCHEDULE_3A_COLUMNS", "SCHEDULE_3B_COLUMNS",
    "Schedule3Row", "Schedule3Issue", "Schedule3Result", "Schedule3Analyzer",
]
