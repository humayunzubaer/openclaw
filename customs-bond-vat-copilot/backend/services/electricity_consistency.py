"""
বিদ্যুৎ-উৎপাদন সামঞ্জস্য যাচাই (C5)
====================================

নিরীক্ষক-নিশ্চিত পদ্ধতি (Patch Notes v4.9):
    মূল যাচাই = **প্রকৃত বিদ্যুৎ-ব্যয়/একক উৎপাদ** বনাম প্রতিষ্ঠানের **মূসক-৪.৩**
    (উপকরণ-উৎপাদ সহগ ঘোষণা)-এ উল্লিখিত **ঘোষিত হার**। পূর্ববর্তী মেয়াদের সাথে
    তুলনা নয় (সেটা কেবল সহায়ক তথ্য)।

★ থ্রেশহোল্ড নীতি:
    ±সহনসীমা (default ১৫%) **নিরীক্ষক-নির্ধারিত — কোনো SRO/গেজেট সংখ্যা নয়**।
    প্রতিষ্ঠান-নির্দিষ্ট বা VAT Audit Manual নির্দেশিকা থাকিলে `threshold_pct`
    প্যারামিটার দিয়া সেই মান বসাইতে হইবে। তাই certainty = 【E】 (estimated),
    আইনি দাবি নয় — নিরীক্ষা-পর্যবেক্ষণ ও তদন্ত-সূচক।

বোনাস: T-02 frozen-note detector — একাধিক মাসে হুবহু একই বিদ্যুৎ-বিল অস্বাভাবিক
(সম্ভাব্য বানানো/frozen নোট); পৃথকভাবে flag হয়।
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import logger


ELECTRICITY_METHOD_BASIS = (
    "মূল যাচাই: প্রকৃত বিদ্যুৎ-ব্যয়/একক উৎপাদ বনাম প্রতিষ্ঠানের মূসক-৪.৩ "
    "(উপকরণ-উৎপাদ সহগ ঘোষণা)-এ ঘোষিত হার। ±সহনসীমা নিরীক্ষক-নির্ধারিত "
    "(SRO সংখ্যা নহে) — প্রতিষ্ঠান/VAT Audit Manual নির্দেশিকা থাকিলে সেই মান "
    "প্রযোজ্য। 【E】"
)

# নিরীক্ষক-নির্ধারিত সূচনা-সহনসীমা (আইনি নহে)
DEFAULT_THRESHOLD_PCT = 15.0


@dataclass
class FrozenNoteFlag:
    """T-02 — একাধিক মাসে হুবহু একই বিল (frozen/বানানো সন্দেহ)"""
    suspected: bool
    repeated_value: float
    repeat_count: int
    total_months: int
    remark: str


@dataclass
class ElectricityConsistencyResult:
    """বিদ্যুৎ-উৎপাদন সামঞ্জস্য যাচাইয়ের ফলাফল"""
    declared_rate_per_unit: float     # মূসক-৪.৩ ঘোষিত ৳/একক উৎপাদ
    actual_rate_per_unit: float       # প্রকৃত ৳/একক = মোট বিদ্যুৎ-ব্যয় ÷ উৎপাদিত একক
    total_electricity_cost: float
    produced_units: float
    unit: str
    deviation_pct: float              # (actual − declared) ÷ declared × ১০০
    threshold_pct: float
    within_tolerance: bool
    direction: str                    # "স্ফীত" | "হ্রাস" | "সঙ্গতিপূর্ণ"
    certainty: str
    basis: str
    remarks: str
    frozen_note: Optional[FrozenNoteFlag] = None
    warnings: list[str] = field(default_factory=list)


def detect_frozen_note(
    monthly_costs: list[float] | None,
    min_months: int = 3,
    repeat_fraction: float = 0.5,
) -> Optional[FrozenNoteFlag]:
    """
    T-02 frozen-note সনাক্তকরণ — মাসিক বিদ্যুৎ-বিলে হুবহু পুনরাবৃত্ত মান।

    monthly_costs না থাকিলে বা মাস < min_months হইলে None (যাচাই সম্ভব নহে)।
    সবচেয়ে ঘনঘন মানটি যদি মোট মাসের `repeat_fraction` অংশ বা বেশি হয় → সন্দেহ।
    """
    vals = [c for c in (monthly_costs or []) if c is not None]
    if len(vals) < min_months:
        return None
    rounded = [round(float(v), 2) for v in vals]
    value, count = Counter(rounded).most_common(1)[0]
    suspected = count >= max(2, int(len(rounded) * repeat_fraction)) and count >= 2
    remark = (
        f"{len(rounded)} মাসের মধ্যে {count} মাসে হুবহু ৳{value:,.2f} — frozen/বানানো "
        "নোট সন্দেহ; মূল বিদ্যুৎ-বিল ও মিটার রিডিং তলব করুন।"
        if suspected else
        f"{len(rounded)} মাসের বিলে অস্বাভাবিক পুনরাবৃত্তি নাই।"
    )
    return FrozenNoteFlag(
        suspected=suspected, repeated_value=value, repeat_count=count,
        total_months=len(rounded), remark=remark,
    )


def check_electricity_consistency(
    declared_rate_per_unit: float,
    total_electricity_cost: float,
    produced_units: float,
    unit: str = "কেজি",
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    monthly_costs: list[float] | None = None,
) -> ElectricityConsistencyResult:
    """
    ★ C5 — বিদ্যুৎ-উৎপাদন সামঞ্জস্য।

    declared_rate_per_unit : মূসক-৪.৩ ঘোষিত বিদ্যুৎ-ব্যয় ৳/একক উৎপাদ
    total_electricity_cost : অডিট মেয়াদে প্রকৃত মোট বিদ্যুৎ-ব্যয় (৳)
    produced_units         : অডিট মেয়াদে মোট উৎপাদিত একক
    threshold_pct          : নিরীক্ষক-নির্ধারিত সহনসীমা (default ১৫%; SRO নহে)
    monthly_costs          : (ঐচ্ছিক) মাসিক বিল — T-02 frozen-note যাচাইয়ে
    """
    warnings: list[str] = []
    frozen = detect_frozen_note(monthly_costs)

    if produced_units <= 0:
        warnings.append("উৎপাদিত একক ০/অজানা — প্রকৃত হার গণনা সম্ভব নহে; উৎপাদন-লগ তলব করুন।")
        actual_rate = 0.0
    else:
        actual_rate = total_electricity_cost / produced_units

    if declared_rate_per_unit <= 0:
        warnings.append("মূসক-৪.৩ ঘোষিত হার ০/অজানা — সামঞ্জস্য যাচাই সম্ভব নহে; মূসক-৪.৩ তলব করুন।")
        deviation = 0.0
        within = True
        direction = "সঙ্গতিপূর্ণ"
    else:
        deviation = (actual_rate - declared_rate_per_unit) / declared_rate_per_unit * 100
        within = abs(deviation) <= threshold_pct
        if within:
            direction = "সঙ্গতিপূর্ণ"
        elif deviation > 0:
            direction = "স্ফীত"          # প্রকৃত > ঘোষিত (সম্ভাব্য কম-ঘোষিত উৎপাদন/অতি-ভোগ)
        else:
            direction = "হ্রাস"          # প্রকৃত < ঘোষিত (সম্ভাব্য অতি-ঘোষিত উৎপাদন)

    if not within:
        remarks = (
            f"প্রকৃত বিদ্যুৎ-ব্যয় ৳{actual_rate:,.2f}/{unit} বনাম মূসক-৪.৩ ঘোষিত "
            f"৳{declared_rate_per_unit:,.2f}/{unit} — বিচ্যুতি {deviation:+.1f}% "
            f"({direction}), নিরীক্ষক-সহনসীমা ±{threshold_pct:.0f}% অতিক্রান্ত। "
            "উৎপাদন-হিসাব ও বিদ্যুৎ-বিল মিলাইয়া ব্যাখ্যা তলব করুন।"
        )
    else:
        remarks = (
            f"প্রকৃত ৳{actual_rate:,.2f}/{unit} বনাম ঘোষিত ৳{declared_rate_per_unit:,.2f}"
            f"/{unit} — বিচ্যুতি {deviation:+.1f}%, সহনসীমা ±{threshold_pct:.0f}%-এর মধ্যে।"
        )

    if frozen and frozen.suspected:
        warnings.append(frozen.remark)

    logger.info(
        f"C5 বিদ্যুৎ-সামঞ্জস্য: বিচ্যুতি {deviation:+.1f}% "
        f"({'সীমার মধ্যে' if within else 'সীমা অতিক্রম'})"
    )

    return ElectricityConsistencyResult(
        declared_rate_per_unit=round(declared_rate_per_unit, 4),
        actual_rate_per_unit=round(actual_rate, 4),
        total_electricity_cost=round(total_electricity_cost, 2),
        produced_units=round(produced_units, 3),
        unit=unit,
        deviation_pct=round(deviation, 2),
        threshold_pct=threshold_pct,
        within_tolerance=within,
        direction=direction,
        certainty="【E】",
        basis=ELECTRICITY_METHOD_BASIS,
        remarks=remarks,
        frozen_note=frozen,
        warnings=warnings,
    )
