"""
Bonding Capacity Rules — এককালীন বন্ডিং ক্যাপাসিটি নির্ণয়
============================================================

★ সময়ভিত্তিক দুইটি পদ্ধতি (ব্যবহারকারী কর্তৃক নির্ধারিত):

    পদ্ধতি ক — পুরাতন নিয়ম (নিরীক্ষা মেয়াদ ০১.০৭.২০২৬ এর পূর্বে সমাপ্ত):
        এককালীন বন্ডিং ক্যাপাসিটি = (মোট প্রাপ্যতা + মজুত) ÷ ৩

    পদ্ধতি খ — নূতন নিয়ম (নিরীক্ষা মেয়াদ ০১.০৭.২০২৬ বা তৎপরবর্তীতে আরম্ভ):
        এককালীন বন্ডিং ক্যাপাসিটি = প্রতিষ্ঠানের ওয়্যারহাউসের ধারণ ক্ষমতা

আইনি ভিত্তি:
    ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ — বিধি ৫
    এসআরও ২১২/২০২৪ — বিধি ৫ ও ৬(১)
    ["এককালীন বিন্ডিং ক্যাপাসিটির অতিরিক্ত পণ্য আমদানি করা যাইবে না"]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


# ★ নূতন নিয়ম কার্যকর হইবার তারিখ
NEW_REGIME_DATE = date(2026, 7, 1)

# পুরাতন নিয়মের ভাজক
OLD_REGIME_DIVISOR = 3.0


class CapacityRegime:
    OLD = "old"          # (প্রাপ্যতা + মজুত) ÷ ৩
    NEW = "new"          # ওয়্যারহাউসের ধারণ ক্ষমতা
    STRADDLE = "straddle"  # মেয়াদ কাট-অফ তারিখ অতিক্রম করিয়াছে


@dataclass
class CapacityResolution:
    """একটি প্রাপ্যতা-এককের ক্যাপাসিটি নির্ণয়ের ফলাফল — ব্যাখ্যাসহ"""
    capacity: float = 0.0
    regime: str = CapacityRegime.OLD
    formula: str = ""
    source: str = ""              # computed | sheet | warehouse_input
    sheet_value: float = 0.0      # প্রাপ্যতা শীটে উল্লিখিত মান (যদি থাকে)
    discrepancy: float = 0.0      # গণনা ও শীটের পার্থক্য
    legal_basis: str = ""
    note: str = ""


@dataclass
class PeriodSegment:
    """
    নিরীক্ষা মেয়াদের একটি খণ্ড।

    মেয়াদ যদি ০১.০৭.২০২৬ অতিক্রম করে, তবে দুইটি খণ্ডে বিভক্ত হইবে —
    প্রতিটি খণ্ডে পৃথক পদ্ধতিতে এককালীন বন্ডিং ক্যাপাসিটি নির্ণীত হইবে।
    """
    seq: int
    date_from: date
    date_to: date
    regime: str
    label: str = ""
    legal_note: str = ""

    @property
    def display(self) -> str:
        return (
            f"{self.date_from.strftime('%d.%m.%Y')} — "
            f"{self.date_to.strftime('%d.%m.%Y')}"
        )

    def contains(self, d: Optional[date]) -> bool:
        if not d:
            return True
        return self.date_from <= d <= self.date_to


def split_audit_period(
    period_from: Optional[date], period_to: Optional[date]
) -> list[PeriodSegment]:
    """
    ★ নিরীক্ষা মেয়াদকে নিয়ম পরিবর্তনের তারিখ অনুযায়ী খণ্ডে বিভক্ত করো।

    উদাহরণ: ০১.০১.২০২৬ — ৩১.১২.২০২৬
        খণ্ড ১ : ০১.০১.২০২৬ — ৩০.০৬.২০২৬  (পুরাতন নিয়ম)
        খণ্ড ২ : ০১.০৭.২০২৬ — ৩১.১২.২০২৬  (নূতন নিয়ম)
    """
    from datetime import timedelta

    if not period_from or not period_to:
        return [PeriodSegment(
            seq=1,
            date_from=period_from or date(1900, 1, 1),
            date_to=period_to or date(2999, 12, 31),
            regime=CapacityRegime.OLD,
            label="সম্পূর্ণ মেয়াদ",
            legal_note="মেয়াদ শনাক্ত না হওয়ায় পুরাতন নিয়ম প্রয়োগ করা হইল।",
        )]

    # সম্পূর্ণ মেয়াদ কাট-অফের পূর্বে
    if period_to < NEW_REGIME_DATE:
        return [PeriodSegment(
            seq=1, date_from=period_from, date_to=period_to,
            regime=CapacityRegime.OLD, label="সম্পূর্ণ মেয়াদ",
            legal_note=(
                f"সম্পূর্ণ নিরীক্ষা মেয়াদ {NEW_REGIME_DATE.strftime('%d.%m.%Y')} "
                f"এর পূর্বে হওয়ায় পুরাতন নিয়ম [(প্রাপ্যতা + মজুত) ÷ ৩] প্রযোজ্য।"
            ),
        )]

    # সম্পূর্ণ মেয়াদ কাট-অফের পরে
    if period_from >= NEW_REGIME_DATE:
        return [PeriodSegment(
            seq=1, date_from=period_from, date_to=period_to,
            regime=CapacityRegime.NEW, label="সম্পূর্ণ মেয়াদ",
            legal_note=(
                f"সম্পূর্ণ নিরীক্ষা মেয়াদ {NEW_REGIME_DATE.strftime('%d.%m.%Y')} "
                f"বা তৎপরবর্তী হওয়ায় নূতন নিয়ম "
                f"(ক্যাপাসিটি = ওয়্যারহাউসের ধারণ ক্ষমতা) প্রযোজ্য।"
            ),
        )]

    # ★ ছেদকারী মেয়াদ — দুই খণ্ডে বিভাজন
    cutoff_prev = NEW_REGIME_DATE - timedelta(days=1)
    return [
        PeriodSegment(
            seq=1, date_from=period_from, date_to=cutoff_prev,
            regime=CapacityRegime.OLD, label="খণ্ড-১ (পুরাতন নিয়ম)",
            legal_note=(
                f"নিরীক্ষা মেয়াদের এই অংশ ({period_from.strftime('%d.%m.%Y')} — "
                f"{cutoff_prev.strftime('%d.%m.%Y')}) নিয়ম পরিবর্তনের তারিখের "
                f"পূর্বে হওয়ায় পুরাতন নিয়ম [(প্রাপ্যতা + মজুত) ÷ ৩] প্রযোজ্য।"
            ),
        ),
        PeriodSegment(
            seq=2, date_from=NEW_REGIME_DATE, date_to=period_to,
            regime=CapacityRegime.NEW, label="খণ্ড-২ (নূতন নিয়ম)",
            legal_note=(
                f"নিরীক্ষা মেয়াদের এই অংশ ({NEW_REGIME_DATE.strftime('%d.%m.%Y')} — "
                f"{period_to.strftime('%d.%m.%Y')}) নিয়ম পরিবর্তনের তারিখ বা "
                f"তৎপরবর্তী হওয়ায় নূতন নিয়ম "
                f"(ক্যাপাসিটি = ওয়্যারহাউসের ধারণ ক্ষমতা) প্রযোজ্য।"
            ),
        ),
    ]


def determine_regime(
    period_from: Optional[date], period_to: Optional[date]
) -> tuple[str, str]:
    """
    নিরীক্ষা মেয়াদ অনুযায়ী কোন পদ্ধতি প্রযোজ্য নির্ণয় করো।
    ফেরত: (regime, ব্যাখ্যা)
    """
    if period_from and period_from >= NEW_REGIME_DATE:
        return CapacityRegime.NEW, (
            f"নিরীক্ষা মেয়াদ আরম্ভ {period_from.strftime('%d.%m.%Y')} — "
            f"{NEW_REGIME_DATE.strftime('%d.%m.%Y')} বা তৎপরবর্তী হওয়ায় "
            f"নূতন নিয়ম প্রযোজ্য (ক্যাপাসিটি = ওয়্যারহাউসের ধারণ ক্ষমতা)।"
        )

    if period_to and period_to < NEW_REGIME_DATE:
        return CapacityRegime.OLD, (
            f"নিরীক্ষা মেয়াদ সমাপ্ত {period_to.strftime('%d.%m.%Y')} — "
            f"{NEW_REGIME_DATE.strftime('%d.%m.%Y')} এর পূর্বে হওয়ায় "
            f"পুরাতন নিয়ম প্রযোজ্য [(প্রাপ্যতা + মজুত) ÷ ৩]।"
        )

    if period_from and period_to:
        return CapacityRegime.STRADDLE, (
            f"⚠ নিরীক্ষা মেয়াদ ({period_from.strftime('%d.%m.%Y')} — "
            f"{period_to.strftime('%d.%m.%Y')}) নিয়ম পরিবর্তনের তারিখ "
            f"{NEW_REGIME_DATE.strftime('%d.%m.%Y')} অতিক্রম করিয়াছে। "
            f"সতর্কতার সহিত পুরাতন নিয়ম প্রয়োগ করা হইল — "
            f"নিরীক্ষক কর্তৃক যাচাই আবশ্যক।"
        )

    return CapacityRegime.OLD, (
        "নিরীক্ষা মেয়াদ শনাক্ত না হওয়ায় পুরাতন নিয়ম "
        "[(প্রাপ্যতা + মজুত) ÷ ৩] প্রয়োগ করা হইল।"
    )


def resolve_capacity(
    entitled_quantity: float,
    opening_stock: float,
    period_from: Optional[date],
    period_to: Optional[date],
    sheet_capacity: float = 0.0,
    warehouse_capacity: float = 0.0,
    prefer_sheet: bool = False,
) -> CapacityResolution:
    """
    একটি প্রাপ্যতা-এককের এককালীন বন্ডিং ক্যাপাসিটি নির্ণয় করো।

    entitled_quantity  : ঐ এককের মোট প্রাপ্যতা
    opening_stock      : প্রারম্ভিক জের (বিগত নিরীক্ষার সমাপনী মজুত)
    sheet_capacity     : প্রাপ্যতা শীটে উল্লিখিত ক্যাপাসিটি (যদি থাকে)
    warehouse_capacity : ওয়্যারহাউসের ধারণ ক্ষমতা (নূতন নিয়মে প্রয়োজন)
    prefer_sheet       : শীটের মান থাকিলে তাহাই চূড়ান্ত ধরিবে কিনা
    """
    regime, reason = determine_regime(period_from, period_to)
    res = CapacityResolution(regime=regime, sheet_value=sheet_capacity, note=reason)

    # ===== নূতন নিয়ম =====
    if regime == CapacityRegime.NEW:
        res.legal_basis = (
            "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ (সংশোধিত) — "
            "এককালীন বন্ডিং ক্যাপাসিটি = ওয়্যারহাউসের ধারণ ক্ষমতা"
        )
        if warehouse_capacity > 0:
            res.capacity = warehouse_capacity
            res.source = "warehouse_input"
            res.formula = "ওয়্যারহাউসের ধারণ ক্ষমতা"
        elif sheet_capacity > 0:
            res.capacity = sheet_capacity
            res.source = "sheet"
            res.formula = "প্রাপ্যতা শীটে উল্লিখিত ধারণ ক্ষমতা"
            res.note += (
                " ওয়্যারহাউসের ধারণ ক্ষমতা পৃথকভাবে প্রদান করা হয় নাই; "
                "প্রাপ্যতা শীটের মান ব্যবহৃত হইল।"
            )
        else:
            res.capacity = 0.0
            res.source = "missing"
            res.note += (
                " ⚠ ওয়্যারহাউসের ধারণ ক্ষমতা পাওয়া যায় নাই — "
                "ক্যাপাসিটি যাচাই সম্ভব হয় নাই।"
            )
        return res

    # ===== পুরাতন নিয়ম (ও straddle) =====
    computed = (entitled_quantity + opening_stock) / OLD_REGIME_DIVISOR
    res.legal_basis = (
        "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ — বিধি ৫ "
        "(এককালীন বন্ডিং ক্যাপাসিটি নির্ধারণ)"
    )
    res.formula = (
        f"(প্রাপ্যতা {entitled_quantity:,.0f} + মজুত {opening_stock:,.0f}) ÷ 3 "
        f"= {computed:,.0f}"
    )

    if prefer_sheet and sheet_capacity > 0:
        res.capacity = sheet_capacity
        res.source = "sheet"
    else:
        res.capacity = computed
        res.source = "computed"

    # শীটের মানের সহিত পার্থক্য থাকিলে সতর্ক করো
    if sheet_capacity > 0:
        res.discrepancy = round(computed - sheet_capacity, 3)
        if abs(res.discrepancy) > max(1.0, computed * 0.01):
            res.note += (
                f" ⚠ গণনাকৃত ক্যাপাসিটি ({computed:,.0f}) এবং প্রাপ্যতা শীটে "
                f"উল্লিখিত ক্যাপাসিটি ({sheet_capacity:,.0f}) এর মধ্যে "
                f"{abs(res.discrepancy):,.0f} পার্থক্য বিদ্যমান — যাচাই আবশ্যক।"
            )

    return res


# ==========================================================
# বার্ষিক উৎপাদন ক্ষমতা সংক্রান্ত যাচাই — বিধি ১১(১)
# ==========================================================

@dataclass
class CapacityLimitCheck:
    """
    বিধি ১১(১) যাচাই:
      নির্ধারিত বার্ষিক আমদানি প্রাপ্যতা + পূর্ববর্তী মেয়াদের মজুদ কাঁচামালের
      সমাপনী জেরসহ একত্রে প্রতিষ্ঠানের বার্ষিক উৎপাদন ক্ষমতার শতকরা ৮০ ভাগের
      অতিরিক্ত হইতে পারিবে না।
    """
    entitled_quantity: float = 0.0
    opening_stock: float = 0.0
    combined: float = 0.0

    capacity_100: float = 0.0
    capacity_80: float = 0.0
    capacity_60: float = 0.0

    limit_applied: float = 0.0
    excess_over_limit: float = 0.0
    excess_pct: float = 0.0
    utilization_of_capacity_pct: float = 0.0

    # ★ শুল্কায়নযোগ্য অতিরিক্ত — প্রকৃত প্রবেশের ভিত্তিতে
    actual_held: float = 0.0          # প্রারম্ভিক জের + প্রকৃত প্রবেশ
    assessable_excess: float = 0.0    # সীমার অতিরিক্ত প্রকৃত পরিমাণ

    status: str = "প্রযোজ্য নয়"
    legal_basis: str = ""
    remarks: str = ""
    demand_proposal: str = ""


def check_capacity_limit(
    entitled_quantity: float,
    opening_stock: float,
    capacity_100: float = 0.0,
    capacity_80: float = 0.0,
    capacity_60: float = 0.0,
    unit: str = "",
    item_label: str = "",
    actual_entry: float = 0.0,
) -> CapacityLimitCheck:
    """
    বিধি ১১(১) অনুযায়ী ৮০% সীমা যাচাই করো।

    প্রাপ্যতা শীটে মেশিনের উৎপাদন ক্ষমতার ১০০% / ৮০% / ৬০% কলাম থাকে —
    সেখান হইতে সীমা গ্রহণ করা হয়।
    """
    chk = CapacityLimitCheck(
        entitled_quantity=entitled_quantity,
        opening_stock=opening_stock,
        combined=entitled_quantity + opening_stock,
        capacity_100=capacity_100,
        capacity_80=capacity_80,
        capacity_60=capacity_60,
        legal_basis=(
            "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ — বিধি ১২(১) "
            "[\"কোনো ক্ষেত্রেই তাহা সংশ্লিষ্ট মেয়াদে মোট আমদানির পরিমাণ ও "
            "পূর্ববর্তী মেয়াদের মজুদ কাঁচামালের জেরসহ একত্রে প্রতিষ্ঠানের বার্ষিক "
            "উৎপাদন ক্ষমতার শতকরা ৮০ (আশি) ভাগের অতিরিক্ত হইবে না\"] "
            "সহপঠিত বিধি ১১(১) [প্রাপ্যতা নির্ধারণে ৮০% সীমা]"
        ),
    )

    # সীমা নির্ধারণ — ৮০% কলাম থাকিলে তাহাই; নতুবা ১০০% এর ৮০%
    limit = capacity_80 or (capacity_100 * 0.80 if capacity_100 else 0.0)
    chk.limit_applied = limit

    if limit <= 0:
        chk.status = "প্রযোজ্য নয়"
        chk.remarks = (
            "প্রাপ্যতা শীটে মেশিনের উৎপাদন ক্ষমতা সংক্রান্ত তথ্য "
            "পাওয়া যায় নাই বিধায় বিধি ১১(১) অনুযায়ী যাচাই করা সম্ভব হয় নাই।"
        )
        return chk

    chk.utilization_of_capacity_pct = (
        chk.combined / capacity_100 * 100 if capacity_100 else 0.0
    )

    # প্রকৃত ধারণকৃত পরিমাণ — শুল্কায়নের ভিত্তি
    chk.actual_held = opening_stock + actual_entry
    chk.assessable_excess = max(0.0, chk.actual_held - limit)

    if chk.combined > limit:
        chk.excess_over_limit = chk.combined - limit
        chk.excess_pct = chk.excess_over_limit / limit * 100
        chk.status = "সীমা অতিক্রম"
        chk.remarks = (
            f"{item_label + ' — ' if item_label else ''}"
            f"নির্ধারিত বার্ষিক আমদানি প্রাপ্যতা {entitled_quantity:,.0f} {unit} "
            f"এবং পূর্ববর্তী মেয়াদের সমাপনী জের {opening_stock:,.0f} {unit} "
            f"একত্রে {chk.combined:,.0f} {unit} — যাহা মেশিনের বার্ষিক উৎপাদন "
            f"ক্ষমতার ৮০% ({limit:,.0f} {unit}) অপেক্ষা "
            f"{chk.excess_over_limit:,.0f} {unit} ({chk.excess_pct:.1f}%) অধিক — "
            f"যাহা বিধি ১১(১) অনুযায়ী প্রাপ্যতা নির্ধারণের সীমা লঙ্ঘন "
            f"(নিরীক্ষা পর্যবেক্ষণ)।"
        )
        # ★ দাবিনামা জারির প্রস্তাব
        if chk.assessable_excess > 0:
            chk.demand_proposal = (
                f"প্রতিষ্ঠানের ওয়্যারহাউসে প্রকৃতপক্ষে ধারণকৃত "
                f"{chk.actual_held:,.0f} {unit} (প্রারম্ভিক জের {opening_stock:,.0f} "
                f"+ মেয়াদে প্রবেশ {actual_entry:,.0f}) মেশিনের বার্ষিক উৎপাদন "
                f"ক্ষমতার ৮০% ({limit:,.0f} {unit}) অপেক্ষা "
                f"{chk.assessable_excess:,.0f} {unit} অধিক। "
                f"ইহা ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ এর বিধি ১২(১) এর "
                f"সুস্পষ্ট লঙ্ঘন। উক্ত অতিরিক্ত {chk.assessable_excess:,.0f} {unit} "
                f"কাঁচামালের বন্ড সুবিধা বাতিলপূর্বক সংশ্লিষ্ট বিল অব এন্ট্রিতে "
                f"উল্লিখিত সম্পূর্ণ শুল্ক-কর আদায়ের নিমিত্ত কাস্টমস আইন, ২০২৩ "
                f"এর ধারা ২৩৮ অনুযায়ী দাবিনামা জারির প্রস্তাব করা হইল।"
            )
        else:
            chk.demand_proposal = (
                f"তবে নিরীক্ষাধীন মেয়াদে প্রকৃতপক্ষে ধারণকৃত পরিমাণ "
                f"({chk.actual_held:,.0f} {unit}) ৮০% সীমার মধ্যে থাকায় "
                f"শুল্কায়নযোগ্য অতিরিক্ত পাওয়া যায় নাই। প্রাপ্যতা নির্ধারণে "
                f"ত্রুটি রহিয়াছে বিধায় প্রাপ্যতা পুনঃনির্ধারণের সুপারিশ করা হইল।"
            )
    else:
        chk.status = "সীমার মধ্যে"
        chk.remarks = (
            f"প্রাপ্যতা ও প্রারম্ভিক জের একত্রে {chk.combined:,.0f} {unit} — "
            f"উৎপাদন ক্ষমতার ৮০% সীমা ({limit:,.0f} {unit}) এর মধ্যে সীমাবদ্ধ "
            f"(ক্ষমতার {chk.utilization_of_capacity_pct:.1f}%)।"
        )

    return chk


# ==========================================================
# ব্যাংক গ্যারান্টি সংক্রান্ত টীকা — বিধি ১২
# ==========================================================

BANK_GUARANTEE_NOTE = (
    "★ শর্তসাপেক্ষ: ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ এর বিধি ১২(১) "
    "অনুযায়ী নির্ধারিত বার্ষিক আমদানি প্রাপ্যতার অতিরিক্ত কাঁচামাল প্রযোজ্য "
    "শুল্ক-করাদির সমপরিমাণ অর্থের নিঃশর্ত ও অব্যাহত ব্যাংক গ্যারান্টির বিপরীতে "
    "বন্ডের আওতায় খালাস গ্রহণের সুযোগ রহিয়াছে। প্রতিষ্ঠান কর্তৃপক্ষ উক্ত "
    "ব্যাংক গ্যারান্টির বিপরীতে আমদানির জন্য কমিশনার অব কাস্টমস (বন্ড) এর "
    "অনুমোদন উপস্থাপন করিতে পারিলে এই শুল্কায়ন দাবিনামায় অন্তর্ভুক্ত করা হইবে না।"
)


# ==========================================================
# ★ বিয়োজনের শর্তে আমদানি প্রাপ্যতা (Provisional entitlement)
# ==========================================================
#
# নিরীক্ষা চলাকালে প্রতিষ্ঠান **আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা** হইতে বিয়োজনের
# শর্তে সাময়িক আমদানি প্রাপ্যতা গ্রহণ করিতে পারে। উক্ত সাময়িক প্রাপ্যতা আগামী
# মেয়াদের সম্ভাব্য প্রাপ্যতার —
#
#     • ০১.০৭.২০২৬ এর পূর্বে  : এক-তৃতীয়াংশ (÷ ৩) এর অধিক হইবে না
#     • ০১.০৭.২০২৬ ও তৎপরবর্তী : এক-চতুর্থাংশ (÷ ৪) এর অধিক হইবে না
#
# সীমা লঙ্ঘিত হইলে অতিরিক্ত অংশ বৈধ প্রাপ্যতা নহে — উহার বিপরীতে আমদানিকৃত
# কাঁচামাল **প্রাপ্যতার অতিরিক্ত আমদানি** হিসাবে শুল্কায়নযোগ্য এবং মতামত ও
# প্রস্তাবনায় দাবিনামা জারির প্রস্তাব করিতে হইবে।

PROVISIONAL_OLD_DIVISOR = 3.0   # ০১.০৭.২০২৬ এর পূর্বে — এক-তৃতীয়াংশ
PROVISIONAL_NEW_DIVISOR = 4.0   # ০১.০৭.২০২৬ ও তৎপরবর্তী — এক-চতুর্থাংশ

PROVISIONAL_LEGAL_BASIS = (
    "বার্ষিক আমদানি-প্রাপ্যতা নির্ধারণ বিধিমালা, ২০২৪ [এসআরও ২১৪-আইন/২০২৪] — "
    "নিরীক্ষাধীন অবস্থায় আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা হইতে বিয়োজনের শর্তে "
    "গৃহীত সাময়িক আমদানি প্রাপ্যতার ঊর্ধ্বসীমা "
    "(০১.০৭.২০২৬ এর পূর্বে এক-তৃতীয়াংশ; উক্ত তারিখ ও তৎপরবর্তী এক-চতুর্থাংশ)"
)

PROVISIONAL_DEMAND_PROPOSAL = (
    "বিয়োজনের শর্তে গৃহীত সাময়িক আমদানি প্রাপ্যতা নির্ধারিত ঊর্ধ্বসীমা অতিক্রম "
    "করিয়াছে। সীমাতিরিক্ত অংশ বৈধ প্রাপ্যতা নহে বিধায় উহার বিপরীতে আমদানিকৃত "
    "কাঁচামালের উপর প্রাপ্যতার অতিরিক্ত আমদানি হিসাবে শুল্ক-কর আরোপপূর্বক "
    "কাস্টমস আইন, ২০২৩ এর ধারা ২৩৮ অনুযায়ী দাবিনামা জারির প্রস্তাব করা হইল।"
)


@dataclass
class ProvisionalEntitlementCheck:
    """বিয়োজনের শর্তে গৃহীত সাময়িক প্রাপ্যতার সীমা যাচাই"""
    next_period_probable: float      # আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা
    provisional_taken: float         # বিয়োজনের শর্তে গৃহীত পরিমাণ
    divisor: float                   # ৩ (পুরাতন) বা ৪ (নূতন)
    allowed_cap: float               # সম্ভাব্য প্রাপ্যতা ÷ divisor
    excess_quantity: float           # সীমার অতিরিক্ত (০ হইলে লঙ্ঘন নাই)
    excess_pct: float
    regime: str                      # CapacityRegime.OLD | NEW
    reference_date: Optional[date]
    unit: str
    violated: bool
    legal_basis: str
    explanation: str
    demand_proposal: str


def resolve_provisional_divisor(
    reference_date: Optional[date],
) -> tuple[float, str, str]:
    """
    বিয়োজনের শর্তে প্রাপ্যতার ভাজক নির্ণয় — তারিখভিত্তিক দুইটি সূত্র।

    reference_date : সাময়িক প্রাপ্যতা গ্রহণ/অনুমোদনের তারিখ।
    ফেরত: (divisor, regime, ব্যাখ্যা)
    """
    if reference_date and reference_date >= NEW_REGIME_DATE:
        return PROVISIONAL_NEW_DIVISOR, CapacityRegime.NEW, (
            f"সাময়িক প্রাপ্যতার তারিখ {reference_date.strftime('%d.%m.%Y')} — "
            f"{NEW_REGIME_DATE.strftime('%d.%m.%Y')} বা তৎপরবর্তী হওয়ায় নূতন সূত্র "
            f"প্রযোজ্য (আগামী মেয়াদের সম্ভাব্য প্রাপ্যতার এক-চতুর্থাংশ)।"
        )

    if reference_date:
        return PROVISIONAL_OLD_DIVISOR, CapacityRegime.OLD, (
            f"সাময়িক প্রাপ্যতার তারিখ {reference_date.strftime('%d.%m.%Y')} — "
            f"{NEW_REGIME_DATE.strftime('%d.%m.%Y')} এর পূর্বে হওয়ায় পুরাতন সূত্র "
            f"প্রযোজ্য (আগামী মেয়াদের সম্ভাব্য প্রাপ্যতার এক-তৃতীয়াংশ)।"
        )

    return PROVISIONAL_OLD_DIVISOR, CapacityRegime.OLD, (
        "⚠ সাময়িক প্রাপ্যতা গ্রহণের তারিখ শনাক্ত হয় নাই — সতর্কতার সহিত পুরাতন "
        "সূত্র (এক-তৃতীয়াংশ) প্রয়োগ করা হইল; নিরীক্ষক কর্তৃক তারিখ যাচাই আবশ্যক।"
    )


def check_provisional_entitlement(
    next_period_probable: float,
    provisional_taken: float,
    reference_date: Optional[date] = None,
    unit: str = "",
) -> ProvisionalEntitlementCheck:
    """
    ★ বিয়োজনের শর্তে গৃহীত সাময়িক আমদানি প্রাপ্যতা নির্ধারিত সীমার মধ্যে কি না।

    সীমা = আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা ÷ (৩ বা ৪ — তারিখভিত্তিক)।
    """
    probable = max(0.0, next_period_probable or 0.0)
    taken = max(0.0, provisional_taken or 0.0)
    divisor, regime, why = resolve_provisional_divisor(reference_date)

    cap = probable / divisor if probable > 0 else 0.0
    excess = max(0.0, taken - cap)
    violated = excess > 0 and probable > 0
    excess_pct = (excess / cap * 100) if cap > 0 else 0.0

    frac = "এক-চতুর্থাংশ" if divisor == PROVISIONAL_NEW_DIVISOR else "এক-তৃতীয়াংশ"
    if probable <= 0:
        explanation = (
            "আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা প্রদত্ত হয় নাই — সীমা নির্ণয় সম্ভব "
            "নহে। নিরীক্ষক সম্ভাব্য প্রাপ্যতার ছক তলব করিয়া যাচাই করিবেন।"
        )
    elif violated:
        explanation = (
            f"{why} সম্ভাব্য প্রাপ্যতা {probable:,.3f} {unit} এর {frac} = "
            f"{cap:,.3f} {unit} সর্বোচ্চ গ্রহণযোগ্য; প্রতিষ্ঠান গ্রহণ করিয়াছে "
            f"{taken:,.3f} {unit} — সীমার অতিরিক্ত {excess:,.3f} {unit} "
            f"({excess_pct:.1f}%)।"
        )
    else:
        explanation = (
            f"{why} সম্ভাব্য প্রাপ্যতা {probable:,.3f} {unit} এর {frac} = "
            f"{cap:,.3f} {unit}; গৃহীত {taken:,.3f} {unit} — সীমার মধ্যে।"
        )

    return ProvisionalEntitlementCheck(
        next_period_probable=round(probable, 3),
        provisional_taken=round(taken, 3),
        divisor=divisor,
        allowed_cap=round(cap, 3),
        excess_quantity=round(excess, 3),
        excess_pct=round(excess_pct, 2),
        regime=regime,
        reference_date=reference_date,
        unit=unit,
        violated=violated,
        legal_basis=PROVISIONAL_LEGAL_BASIS,
        explanation=explanation,
        demand_proposal=PROVISIONAL_DEMAND_PROPOSAL if violated else "",
    )


__all__ = [
    "NEW_REGIME_DATE", "OLD_REGIME_DIVISOR", "CapacityRegime",
    "PeriodSegment", "split_audit_period",
    "CapacityResolution", "determine_regime", "resolve_capacity",
    "CapacityLimitCheck", "check_capacity_limit", "BANK_GUARANTEE_NOTE",
    "PROVISIONAL_OLD_DIVISOR", "PROVISIONAL_NEW_DIVISOR",
    "PROVISIONAL_LEGAL_BASIS", "PROVISIONAL_DEMAND_PROPOSAL",
    "ProvisionalEntitlementCheck", "resolve_provisional_divisor",
    "check_provisional_entitlement",
]
