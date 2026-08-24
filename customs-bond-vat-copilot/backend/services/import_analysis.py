"""
Import Analysis Engine — আমদানি বিশ্লেষণ ইঞ্জিন
================================================

মূল কাজ:
  পূর্ববর্তী নিরীক্ষায় জারিকৃত "প্রাপ্যতা শীট" (Entitlement) এর সাথে
  প্রকৃত আমদানির (AIS/IM-4/IM-7) তুলনা করে অসঙ্গতি বের করা।

নীতি:
  ★ সহনসীমা শূন্য — প্রাপ্যতার চেয়ে এক এককও বেশি হলে ফ্ল্যাগ
  ★ মিলকরণ দুই স্তরে — কাঁচামাল ভিত্তিক ও ক্লাস্টার ভিত্তিক
  ★ প্রাপ্যতা মেয়াদ-নির্দিষ্ট — কলামে উল্লিখিত মেয়াদের আমদানিই গণনায়

আউটপুট:
  ১. অতিরিক্ত আমদানি শীট (Excess Import Sheet)
  ২. অননুমোদিত পণ্য শীট (Unauthorized Item Sheet)
  ৩. প্রাপ্যতা ব্যবহার শীট (Utilization Sheet)
  ৪. ঝুঁকি ফ্ল্যাগ তালিকা
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, Any

import pandas as pd
import numpy as np

from ai.matcher import (
    ItemMatcher, MatchCandidate, MatchResult,
    detect_cluster, normalize, DEFAULT_CLUSTERS, is_machinery,
)
from services.assessment import assess_excess, assess_full, assess_bill, TaxBreakdown
from services.bond_register import RegisterDecision, SKIP_NOTE
from services.capacity_ledger import (
    KG_PER_MT, WarehouseCapacity, compute_warehouse_capacity,
    OneTimeBondingCapacity, compute_one_time_capacity,
    LedgerEvent, CapacityLedgerResult, build_capacity_ledger,
    BreachAssessment,
)
from services.unit_extractor import UnitExtractor, UnitExtractionResult
from services.bonding_rules import (
    resolve_capacity, check_capacity_limit, determine_regime,
    split_audit_period, PeriodSegment, NEW_REGIME_DATE,
    CapacityRegime, BANK_GUARANTEE_NOTE,
)
from utils.logger import logger


# ==========================================================
# ধ্রুবক
# ==========================================================

TOLERANCE = 0.0   # ★ শূন্য সহনসীমা — ব্যবহারকারীর নির্দেশ অনুযায়ী

VAT_RATE_DEFAULT = 15.0
AT_RATE_DEFAULT = 5.0
AIT_RATE_DEFAULT = 5.0


# ==========================================================
# ডেটা কাঠামো
# ==========================================================

@dataclass
class EntitlementMember:
    """ক্লাস্টারভুক্ত একটি কাঁচামাল — নাম ও এইচ.এস কোড"""
    hs_code: Optional[str] = None
    item_name: str = ""
    commercial_name: str = ""
    row_number: Optional[int] = None


@dataclass
class EntitlementRow:
    """
    প্রাপ্যতা শীটের একটি প্রাপ্যতা-একক।

    ইহা হইতে পারে —
      ক) একটিমাত্র কাঁচামাল (members-এ একটি সদস্য), অথবা
      খ) ★ একটি ক্লাস্টার — একাধিক কাঁচামালের নাম ও এইচ.এস কোড উল্লেখ
         থাকিবে, কিন্তু প্রাপ্যতার পরিমাণ একত্রে একটিই দেওয়া থাকিবে।

    ক্লাস্টার ইঞ্জিন নিজে তৈরি করে না — প্রাপ্যতা শীটে যেভাবে
    উল্লেখ থাকে হুবহু সেভাবেই গ্রহণ করে।
    """
    row_id: int
    serial_no: str = ""
    hs_code: Optional[str] = None          # প্রধান/প্রথম এইচ.এস কোড
    item_name: str = ""
    commercial_name: str = ""
    cluster: Optional[str] = None          # তথ্যমূলক শ্রেণী (মিলকরণে ব্যবহৃত নয়)

    # ★ ক্লাস্টার তথ্য — প্রাপ্যতা শীট হইতে প্রাপ্ত
    is_cluster: bool = False
    cluster_label: str = ""
    members: list[EntitlementMember] = field(default_factory=list)

    # ★ মূল কলাম — নির্দিষ্ট মেয়াদের জন্য প্রদত্ত/প্রস্তাবিত প্রাপ্যতা
    entitled_quantity: float = 0.0
    unit: str = ""

    # ★ বর্ধিত প্রাপ্যতা [বিধি ৮] — নিরীক্ষা চলাকালে ৩ মাস মেয়াদ বৃদ্ধির প্রাপ্যতা।
    #   ০ হইলে ধরে নেওয়া হয় entitled_quantity-তেই folded (নমুনা শীটের মত);
    #   পৃথক দেওয়া থাকিলে মোট অনুমোদিত = entitled_quantity + extended_entitlement।
    extended_entitlement: float = 0.0

    period_from: Optional[date] = None
    period_to: Optional[date] = None
    period_label: str = ""

    unit_price: float = 0.0
    entitled_value_usd: float = 0.0

    # ★ পূর্ববর্তী নিরীক্ষার সমাপনী মজুত = চলতি মেয়াদের প্রারম্ভিক জের
    opening_stock: float = 0.0

    # ★ এই আইটেম/ক্লাস্টারের এককালীন বন্ডিং ক্যাপাসিটি (শীটে থাকিলে)
    bonding_capacity_qty: float = 0.0

    # ★ মেশিনের বার্ষিক উৎপাদন ক্ষমতা — বিধি ১১(১) যাচাইয়ের জন্য
    capacity_100: float = 0.0
    capacity_80: float = 0.0
    capacity_60: float = 0.0
    warehouse_capacity: float = 0.0

    duty_rate: float = 0.0
    vat_rate: float = VAT_RATE_DEFAULT
    at_rate: float = AT_RATE_DEFAULT
    rd_rate: float = 0.0
    sd_rate: float = 0.0
    ait_rate: float = AIT_RATE_DEFAULT

    def __post_init__(self):
        # সদস্য তালিকা খালি হলে নিজেকেই একমাত্র সদস্য ধরো
        if not self.members:
            self.members = [EntitlementMember(
                hs_code=self.hs_code,
                item_name=self.item_name,
                commercial_name=self.commercial_name,
            )]
        if not self.hs_code and self.members:
            self.hs_code = self.members[0].hs_code
        if not self.item_name and self.members:
            self.item_name = self.members[0].item_name

    @property
    def effective_entitled_quantity(self) -> float:
        """মোট অনুমোদিত প্রাপ্যতা = মূল + বর্ধিত [বিধি ৮] (অতিরিক্ত হিসাবের সীমা)"""
        return (self.entitled_quantity or 0.0) + (self.extended_entitlement or 0.0)

    @property
    def all_hs_codes(self) -> list[str]:
        """এই প্রাপ্যতা-এককের অধীন সকল এইচ.এস কোড"""
        return [m.hs_code for m in self.members if m.hs_code]

    @property
    def all_names(self) -> list[str]:
        """এই প্রাপ্যতা-এককের অধীন সকল কাঁচামালের নাম"""
        out = []
        for m in self.members:
            if m.item_name:
                out.append(m.item_name)
            if m.commercial_name and m.commercial_name != m.item_name:
                out.append(m.commercial_name)
        return out

    @property
    def display_name(self) -> str:
        """প্রতিবেদনে দেখানোর নাম"""
        if self.is_cluster:
            base = self.cluster_label or (
                self.members[0].item_name if self.members else "ক্লাস্টার"
            )
            return f"ক্লাস্টার: {base} ইত্যাদি ({len(self.members)}টি কাঁচামাল)"
        return self.item_name


@dataclass
class ImportRow:
    """আমদানি বিলের একটি সারি"""
    row_id: int
    bill_number: str = ""
    bill_date: Optional[date] = None
    # ★ বন্ড রেজিস্টার (তফসিল-১) হইতে প্রাপ্ত ইন্টু-বন্ড তারিখ — প্রবেশক্রম নির্ণয়ে
    #   ব্যবহৃত (FIFO নয়)। রেজিস্টার না থাকিলে None → bill_date fallback (আনুমানিক)।
    into_bond_date: Optional[date] = None
    bill_type: str = "IM-4"

    hs_code: Optional[str] = None
    item_name: str = ""
    commercial_name: str = ""

    quantity: float = 0.0
    unit: str = ""

    # ★ দুই পরিমাণ কলাম
    qty_target_unit: Optional[float] = None   # প্রাপ্যতা শীটের এককে
    target_unit: str = ""
    qty_kg: Optional[float] = None            # কেজিতে — ক্যাপাসিটির জন্য
    unit_source: str = ""                     # কোথা হইতে পাওয়া গেল
    unit_flag: str = ""                       # যাচাইয়ের প্রয়োজন হইলে
    unit_price: float = 0.0
    value_usd: float = 0.0
    value_bdt: float = 0.0
    exchange_rate: float = 0.0

    duty_rate: float = 0.0
    vat_rate: float = VAT_RATE_DEFAULT

    # ★ MIS-এ উল্লিখিত শুল্ক-কর (বন্ড সুবিধা বাতিলে সম্পূর্ণটাই দাবিযোগ্য)
    duty_paid: float = 0.0
    vat_paid: float = 0.0
    rd_paid: float = 0.0
    sd_paid: float = 0.0
    at_paid: float = 0.0
    ait_paid: float = 0.0
    total_tax: float = 0.0

    supplier: str = ""
    country: str = ""

    # বিশ্লেষণের পর পূরণ হয়
    cluster: Optional[str] = None
    matched_entitlement_id: Optional[int] = None
    match_score: float = 0.0
    match_method: str = "none"
    match_explanation: str = ""

    # ★ পণ্যের ধরন
    is_machinery_item: bool = False
    machinery_reason: str = ""
    source_type: str = "import"   # import | local_purchase

    def __post_init__(self):
        if self.cluster is None:
            self.cluster, _ = detect_cluster(
                self.item_name or self.commercial_name, self.hs_code
            )
        if not self.is_machinery_item:
            self.is_machinery_item, self.machinery_reason = is_machinery(
                self.item_name or self.commercial_name, self.hs_code
            )


@dataclass
class ExcessRecord:
    """অতিরিক্ত আমদানির একটি রেকর্ড — নির্ধারিত শীটে যাবে"""
    serial: int
    hs_code: str
    item_name: str
    entitlement_item: str
    cluster: str
    period_label: str

    entitled_quantity: float
    imported_quantity: float
    excess_quantity: float
    excess_pct: float
    unit: str

    # সংশ্লিষ্ট বিল
    bill_count: int
    bill_numbers: str
    excess_bills: str          # কোন বিল থেকে অতিরিক্ত শুরু

    # মূল্য ও রাজস্ব
    avg_unit_price_usd: float
    excess_value_usd: float
    excess_value_bdt: float
    exchange_rate: float

    duty_rate: float
    vat_rate: float
    at_rate: float
    rd_rate: float
    sd_rate: float
    ait_rate: float

    duty_involved: float
    vat_involved: float
    at_involved: float
    rd_involved: float
    sd_involved: float
    ait_involved: float
    total_revenue_impact: float
    assessment_basis: str
    bank_guarantee_note: str

    # ব্যাখ্যা
    match_method: str
    match_confidence: float
    remarks: str


@dataclass
class UnauthorizedRecord:
    """প্রাপ্যতায় নেই এমন আমদানি"""
    serial: int
    hs_code: str
    item_name: str
    cluster: str
    bill_count: int
    bill_numbers: str
    total_quantity: float
    unit: str
    total_value_usd: float
    total_value_bdt: float

    # ★ শুল্কায়ন — বন্ড সুবিধা বাতিল করে সম্পূর্ণ শুল্ক-কর দাবি
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    total_revenue_impact: float
    assessment_basis: str

    nearest_match: str
    nearest_score: float
    remarks: str


@dataclass
class MachineryRecord:
    """
    মেশিনারিজ ও যন্ত্রাংশ — পৃথক তালিকা

    নিয়ম: প্রাপ্যতা শীটে না থাকলেও মেশিনারিজকে অননুমোদিত ধরা হবে না,
          কারণ মূলধনী যন্ত্রপাতি ভিন্ন অনুমোদন প্রক্রিয়ায় আমদানি হয়।
    """
    serial: int
    hs_code: str
    item_name: str
    bill_count: int
    bill_numbers: str
    total_quantity: float
    unit: str
    total_value_usd: float
    total_value_bdt: float
    duty_paid: float
    vat_paid: float
    reason: str
    remarks: str


@dataclass
class BondingCapacityRecord:
    """
    এককালীন বন্ডিং ক্যাপাসিটি যাচাই — আইটেমভিত্তিক

    ভিত্তি:  ধারণকৃত মজুত = প্রারম্ভিক জের + মেয়াদে সকল প্রবেশ
             (প্রারম্ভিক জের = বিগত নিরীক্ষার সমাপনী মজুত)

    এখানে ভোগ বিয়োগ হয় না — কারণ বন্ডিং ক্যাপাসিটি নিয়ন্ত্রণ করে
    ওয়্যারহাউসে কী পরিমাণ কাঁচামাল প্রবেশ বা ধারণ করা যাবে।
    """
    serial: int
    hs_code: str
    item_name: str
    cluster: str
    unit: str

    opening_stock: float
    import_entry: float
    local_entry: float
    total_entry: float

    bonding_capacity: float
    capacity_regime: str
    capacity_formula: str
    capacity_source: str
    capacity_legal_basis: str
    held_stock: float            # প্রারম্ভিক জের + সব প্রবেশ
    peak_date: str
    peak_bill: str

    excess_over_capacity: float
    excess_pct: float
    breach_date: str
    breach_bill: str

    # ★ নিরীক্ষাধীন মেয়াদের সমাপনী মজুত (ভোগ জানা থাকলে)
    consumption: float
    closing_stock: float
    closing_stock_basis: str

    # ★ শুল্কায়ন — ক্যাপাসিটির অতিরিক্ত অংশে বন্ড সুবিধা বাতিল
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    total_revenue_impact: float
    assessment_basis: str

    # ★ বিধি ১১(১) — উৎপাদন ক্ষমতার ৮০% সীমা যাচাই
    capacity_100: float
    capacity_80_limit: float
    entitlement_plus_opening: float
    limit_excess: float
    limit_status: str
    limit_remarks: str

    bank_guarantee_note: str

    status: str
    calculation_basis: str
    remarks: str


@dataclass
class BondingCapacityValueRecord:
    """এককালীন বন্ডিং ক্যাপাসিটি যাচাই — সামগ্রিক মূল্যভিত্তিক"""
    capacity_value_bdt: float = 0.0
    capacity_value_usd: float = 0.0
    opening_stock_value_bdt: float = 0.0
    total_entry_value_bdt: float = 0.0
    held_value_bdt: float = 0.0
    peak_date: str = ""
    peak_bill: str = ""
    breach_date: str = ""
    breach_bill: str = ""
    excess_value_bdt: float = 0.0
    excess_pct: float = 0.0
    status: str = "প্রযোজ্য নয়"
    calculation_basis: str = ""
    remarks: str = ""


@dataclass
class ClusterExcessRecord:
    """
    ★ ক্লাস্টারভিত্তিক অতিরিক্ত আমদানি

    প্রাপ্যতা কাঁচামাল অথবা কাঁচামালের ক্লাস্টার — উভয় ভিত্তিতেই দেওয়া হয়।
    তাই আইটেমভিত্তিক যাচাইয়ের পাশাপাশি ক্লাস্টারভিত্তিক যাচাইও প্রয়োজন;
    কারণ প্রতিটি আইটেম আলাদাভাবে সীমার মধ্যে থাকলেও ক্লাস্টারের
    সমষ্টি সীমা অতিক্রম করতে পারে।
    """
    serial: int
    cluster_code: str
    cluster_name: str
    hs_codes: str
    items_in_cluster: int
    unit: str

    entitled_quantity: float
    imported_quantity: float
    local_quantity: float
    total_quantity: float
    excess_quantity: float
    excess_pct: float

    bill_count: int
    bill_numbers: str
    excess_bills: str

    # শুল্কায়ন
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    source_vat_demanded: float
    total_revenue_impact: float
    assessment_basis: str

    status: str
    remarks: str


@dataclass
class CapacityBreachRecord:
    """
    ★ দাবি ৩ — এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন (ঘটনাভিত্তিক)

    প্রতিটি লঙ্ঘন-ঘটনার জন্য পৃথক সারি। দ্বৈত শুল্কায়ন পরিহারের জন্য
    পূর্বে শুল্কায়িত ও এখনও মজুত পরিমাণ বাদ দেওয়া হইয়াছে।
    """
    serial: int
    breach_date: str
    trigger_bill: str

    balance_kg: float
    capacity_kg: float
    gross_excess_kg: float
    shielded_kg: float
    assessable_kg: float

    allocation_detail: str      # কোন বিলের কত অংশ

    # শুল্কায়ন
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    source_vat_demanded: float
    total_revenue_impact: float
    assessment_basis: str

    capacity_formula: str
    capacity_regime: str
    legal_basis: str
    bank_guarantee_note: str
    remarks: str


@dataclass
class CapacityLimitRecord:
    """
    ★ বিধি ১১(১) লঙ্ঘন — দাবিনামা

    ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ এর বিধি ১১(১) অনুযায়ী
    নির্ধারিত বার্ষিক আমদানি প্রাপ্যতা ও পূর্ববর্তী মেয়াদের সমাপনী
    জেরসহ একত্রে বার্ষিক উৎপাদন ক্ষমতার ৮০% এর অতিরিক্ত হইতে পারিবে না।
    """
    serial: int
    hs_code: str
    item_name: str
    unit: str

    capacity_100: float
    limit_80: float
    entitled_quantity: float
    opening_stock: float
    entitlement_plus_opening: float
    excess_over_limit: float
    excess_pct: float

    # প্রকৃত ধারণকৃত — শুল্কায়নের ভিত্তি
    actual_entry: float
    actual_held: float
    assessable_excess: float

    bill_count: int
    bill_numbers: str
    excess_bills: str

    # শুল্কায়ন
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    total_revenue_impact: float
    assessment_basis: str

    legal_basis: str
    demand_proposal: str
    remarks: str


@dataclass
class UtilizationRecord:
    """প্রাপ্যতা ব্যবহারের হিসাব"""
    serial: int
    hs_code: str
    entitlement_item: str
    cluster: str
    period_label: str
    entitled_quantity: float          # মোট অনুমোদিত (মূল + বর্ধিত [বিধি ৮])
    imported_quantity: float
    balance_quantity: float
    utilization_pct: float
    unit: str
    bill_count: int
    status: str   # অতিরিক্ত | সম্পূর্ণ | আংশিক | অব্যবহৃত
    extended_quantity: float = 0.0    # ইহার মধ্যে বর্ধিত প্রাপ্যতা [বিধি ৮] অংশ


@dataclass
class PostPeriodRecord:
    """
    ★ দাবি ৫ — নিরীক্ষা মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি

    নিরীক্ষা মেয়াদ (প্রাপ্যতার period_to) শেষ হইবার পর, নূতন প্রাপ্যতা/UP
    অনুমোদনের পূর্বে, কোনো বৈধ প্রাপ্যতা বা প্রত্যয়নপত্র ব্যতীত যে আমদানি ও
    স্থানীয় ক্রয় হয় — তাহার সম্পূর্ণ শুল্ক-কর দাবিযোগ্য।

    আইনি ভিত্তি: এসআরও ২১৪-আইন/২০২৪ — বিধি ৫, ৯ ও ১২ লঙ্ঘন।
    কর-উপাদান: আমদানিতে পূর্ণ BE (CD+RD+SD+VAT+AT+AIT); স্থানীয় ক্রয়ে ১৫%
    উৎসে মূসক।
    """
    serial: int
    source: str            # "আমদানি (IM-4/IM-7)" | "স্থানীয় ক্রয়"
    hs_code: str
    item_name: str
    bill_count: int
    bill_numbers: str
    total_quantity: float
    unit: str
    total_value_usd: float
    total_value_bdt: float
    assessable_value_bdt: float
    cd_demanded: float
    rd_demanded: float
    sd_demanded: float
    vat_demanded: float
    at_demanded: float
    ait_demanded: float
    total_revenue_impact: float
    assessment_basis: str
    period_window: str
    legal_basis: str
    remarks: str


@dataclass
class Rule8Observation:
    """
    ★ বিধি ৮ — বর্ধিত প্রাপ্যতা ও বিয়োজন সংক্রান্ত পর্যবেক্ষণ (দাবি নহে)

    নিরীক্ষা চলাকালে পূর্ববর্তী প্রাপ্যতার মেয়াদ ৩ মাস বৃদ্ধি করা যায়; বর্ধিত
    পরিমাণ মোট অনুমোদিত প্রাপ্যতায় যোগ হয়। তবে নূতন প্রাপ্যতা নির্ধারণের সময়
    বর্ধিত সময়ে ব্যবহৃত পরিমাণ বিয়োজন করিতে হইবে। ব্যবহৃত পরিমাণ প্রতিষ্ঠানের
    স্ব-ঘোষণা — ইঞ্জিন স্বয়ংক্রিয়ভাবে গণনা করে না; নিরীক্ষক ঘোষণা তলব করিয়া
    বন্ড রেজিস্টারের (তফসিল-১) সহিত মিলাইয়া যাচাই করিবেন।
    """
    serial: int
    entitlement_item: str
    base_entitlement: float
    extended_entitlement: float
    combined_entitlement: float
    unit: str
    instruction: str
    legal_basis: str
    scope: str = "item"          # item | overall


@dataclass
class ImportAnalysisResult:
    """সম্পূর্ণ বিশ্লেষণ ফলাফল"""
    excess_records: list[ExcessRecord] = field(default_factory=list)
    cluster_excess_records: list[ClusterExcessRecord] = field(default_factory=list)
    unauthorized_records: list[UnauthorizedRecord] = field(default_factory=list)
    post_period_records: list[PostPeriodRecord] = field(default_factory=list)
    rule8_observations: list[Rule8Observation] = field(default_factory=list)
    machinery_records: list[MachineryRecord] = field(default_factory=list)
    bonding_records: list[BondingCapacityRecord] = field(default_factory=list)
    capacity_limit_records: list[CapacityLimitRecord] = field(default_factory=list)
    capacity_breach_records: list[CapacityBreachRecord] = field(default_factory=list)
    capacity_ledger: Any = None          # CapacityLedgerResult
    one_time_capacity: Any = None        # OneTimeBondingCapacity
    bonding_value: BondingCapacityValueRecord = field(
        default_factory=BondingCapacityValueRecord
    )
    utilization_records: list[UtilizationRecord] = field(default_factory=list)
    unmatched_imports: list[dict] = field(default_factory=list)
    low_confidence_matches: list[dict] = field(default_factory=list)

    # সারসংক্ষেপ
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def _ledger_frame(self) -> pd.DataFrame:
        """সময়ানুক্রমিক মজুত খতিয়ান — DataFrame আকারে"""
        lg = self.capacity_ledger
        if not lg or not getattr(lg, "points", None):
            return pd.DataFrame()
        cap = lg.capacity.capacity_kg if lg.capacity else 0.0
        return pd.DataFrame([{
            "তারিখ": p.point_date.strftime("%d.%m.%Y"),
            "সূত্র (বিল/চালান)": p.reference,
            "ইন্টু-বন্ড (কেজি)": round(p.into_bond_kg, 3),
            "এক্স-বন্ড (কেজি)": round(p.ex_bond_kg, 3),
            "স্থিতি (কেজি)": round(p.balance_kg, 3),
            "ক্যাপাসিটি (কেজি)": round(cap, 3),
            "অতিরিক্ত (কেজি)": round(p.excess_kg, 3),
            "অবস্থা": "সীমা অতিক্রম" if p.exceeds else "সীমার মধ্যে",
        } for p in lg.points])

    def to_excel_frames(self) -> dict[str, pd.DataFrame]:
        """Excel এ লেখার জন্য DataFrame গুলো"""
        frames = {
            "অতিরিক্ত আমদানি": pd.DataFrame([asdict(r) for r in self.excess_records]),
            "ক্লাস্টারভিত্তিক অতিরিক্ত": pd.DataFrame(
                [asdict(r) for r in self.cluster_excess_records]
            ),
            "অননুমোদিত এইচএস কোড": pd.DataFrame(
                [asdict(r) for r in self.unauthorized_records]
            ),
            "মেয়াদোত্তর আমদানি (দাবি ৫)": pd.DataFrame(
                [asdict(r) for r in self.post_period_records]
            ),
            "বিধি ৮ বর্ধিত প্রাপ্যতা": pd.DataFrame(
                [asdict(r) for r in self.rule8_observations]
            ),
            "বন্ডিং ক্যাপাসিটি": pd.DataFrame(
                [asdict(r) for r in self.capacity_breach_records]
            ),
            "মজুত খতিয়ান": self._ledger_frame(),
            "উৎপাদন ক্ষমতার ৮০% সীমা": pd.DataFrame(
                [asdict(r) for r in self.capacity_limit_records]
            ),
            "মেশিনারিজ ও যন্ত্রাংশ": pd.DataFrame(
                [asdict(r) for r in self.machinery_records]
            ),
            "প্রাপ্যতা ব্যবহার": pd.DataFrame([asdict(r) for r in self.utilization_records]),
            "যাচাই প্রয়োজন": pd.DataFrame(self.low_confidence_matches),
        }
        return frames


# ==========================================================
# মূল ইঞ্জিন
# ==========================================================

class ImportAnalysisEngine:
    """
    প্রাপ্যতা বনাম আমদানি বিশ্লেষণ।

    ব্যবহার:
        engine = ImportAnalysisEngine(entitlements, imports)
        result = engine.analyze()
    """

    LOW_CONFIDENCE_THRESHOLD = 0.80   # এর নিচে হলে মানুষের যাচাই প্রয়োজন

    def __init__(
        self,
        entitlements: list[EntitlementRow],
        imports: list[ImportRow],
        dictionary: dict[str, str] | None = None,
        tolerance: float = TOLERANCE,
        enforce_period: bool = True,
        strict_hs: bool | None = None,
        exclude_machinery: bool = True,
        bonding_capacity_value_bdt: float = 0.0,
        bonding_capacity_value_usd: float = 0.0,
        local_purchases: list[ImportRow] | None = None,
        consumption_map: dict[int, float] | None = None,
        register_decision: RegisterDecision | None = None,
        warehouse_capacity_mt: float = 0.0,
        warehouse_dims: dict | None = None,
        ledger_events: list | None = None,
        next_entitlement_date: date | None = None,
        bond_license_capacity_mt: float = 0.0,
        extension_applies: bool = False,
    ):
        self.entitlements = entitlements
        self.imports = imports
        self.local_purchases = local_purchases or []
        # ★ আইটেমভিত্তিক ভোগ (Module-2 হতে আসবে) — সমাপনী মজুত নির্ণয়ে ব্যবহৃত
        self.consumption_map = consumption_map or {}
        # ★ কনজাম্পশন রেজিস্টার (তফসিল-১) সংক্রান্ত নিরীক্ষকের সিদ্ধান্ত
        self.register = register_decision or RegisterDecision()
        # ★ ওয়্যারহাউসের ধারণক্ষমতা (মেট্রিক টন) — সামগ্রিক
        self.warehouse_capacity_mt = warehouse_capacity_mt
        # ★ বন্ড লাইসেন্সে উল্লিখিত অনুমোদিত ধারণক্ষমতা (মে.টন) — তৃতীয় উৎস,
        #   দেওয়া থাকিলে মাপ/প্রদত্ত মানের চেয়ে অগ্রাধিকার পায় (নিরীক্ষক নির্দেশ)।
        self.bond_license_capacity_mt = bond_license_capacity_mt
        # ওয়্যারহাউসের মাপ (ফুটে) — ধারণক্ষমতা নির্ণয়ে
        self.warehouse_dims = warehouse_dims or {}
        # তফসিল-১ রেজিস্টার হইতে প্রাপ্ত ঘটনাবলি
        self.ledger_events = ledger_events or []
        # ★ নূতন প্রাপ্যতা/UP অনুমোদনের তারিখ — মেয়াদোত্তর দাবির উর্ধ্বসীমা।
        #   period_to-এর পর, এই তারিখের পূর্ব পর্যন্ত আমদানি = দাবি ৫।
        #   None হইলে period_to-এর পরের সকল বিল দাবিতে ধরা হয় (সতর্কতাসহ)।
        self.next_entitlement_date = next_entitlement_date
        # ★ বিধি ৮ — নিরীক্ষায় প্রাপ্যতার মেয়াদ বৃদ্ধি প্রযোজ্য কিনা (নিরীক্ষক flag)।
        #   True হইলে সর্বদা বিয়োজন-যাচাই পর্যবেক্ষণ দেওয়া হয়।
        self.extension_applies = extension_applies
        # একক নিষ্কাশক
        self.unit_extractor = UnitExtractor()
        self.tolerance = tolerance
        self.enforce_period = enforce_period
        self.exclude_machinery = exclude_machinery
        self.dictionary = dictionary or {}
        self.bonding_capacity_value_bdt = bonding_capacity_value_bdt
        self.bonding_capacity_value_usd = bonding_capacity_value_usd

        # ★ কঠোর মোড: নাম ও HS উভয় প্রাপ্যতা শীটে না থাকলে অননুমোদিত।
        #   প্রাপ্যতা শীটে সব সারিতে HS কোড থাকলে কঠোর মোড স্বয়ংক্রিয় চালু হয়।
        #   ক্লাস্টারভিত্তিক প্রাপ্যতা (HS ছাড়া সারি) থাকলে শিথিল মোড।
        if strict_hs is None:
            with_hs = sum(1 for e in entitlements if e.all_hs_codes)
            strict_hs = bool(entitlements) and with_hs / len(entitlements) >= 0.9
        self.strict_hs = strict_hs

        # Matcher প্রস্তুত
        candidates = [
            MatchCandidate(
                id=e.row_id,
                name=e.display_name,
                hs_code=e.hs_code,
                cluster=None,                      # স্বয়ংক্রিয় ক্লাস্টার নিষ্ক্রিয়
                hs_codes=tuple(e.all_hs_codes),    # ★ ক্লাস্টারের সব এইচ.এস কোড
                member_names=tuple(e.all_names),   # ★ ক্লাস্টারের সব নাম
                is_cluster=e.is_cluster,
            )
            for e in self.entitlements
        ]
        self.matcher = ItemMatcher(candidates, dictionary=self.dictionary)
        self._ent_by_id = {e.row_id: e for e in self.entitlements}

    # ------------------------------------------------------
    def analyze(self) -> ImportAnalysisResult:
        """সম্পূর্ণ বিশ্লেষণ চালাও"""
        result = ImportAnalysisResult()

        logger.info(
            f"বিশ্লেষণ শুরু — প্রাপ্যতা: {len(self.entitlements)} আইটেম, "
            f"আমদানি: {len(self.imports)} সারি, স্থানীয় ক্রয়: {len(self.local_purchases)}, "
            f"সহনসীমা: {self.tolerance:.0%}, "
            f"মোড: {'কঠোর (HS+নাম)' if self.strict_hs else 'শিথিল (ক্লাস্টারসহ)'}"
        )

        # ধাপ ০: ★ আমদানি ফাইলটি সঠিক মেয়াদের কিনা যাচাই
        self._validate_period_coverage(result)

        # ধাপ ০ক: ★ বন্ড রেজিস্টার (তফসিল-১) হইতে ইন্টু-বন্ড তারিখ প্রয়োগ —
        #   অতিরিক্ত আমদানির প্রবেশক্রম রেজিস্টার-ভিত্তিক (FIFO নহে)
        self._apply_register_into_dates(result)

        # ধাপ ০.৫: ★ মেয়াদোত্তর বিল পৃথক করা — এগুলো দাবি ৫-এ যাইবে, এবং
        #   excess/অননুমোদিত/ক্যাপাসিটি হিসাব হইতে বাদ থাকিবে (দ্বৈত দাবি রোধ)।
        post_period_imports = [r for r in self.imports if self._is_post_period(r)]
        post_period_local = [r for r in self.local_purchases if self._is_post_period(r)]
        period_imports = [r for r in self.imports if not self._is_post_period(r)]
        period_local = [r for r in self.local_purchases if not self._is_post_period(r)]

        # ধাপ ১: প্রতিটি আমদানি সারি শ্রেণীবদ্ধ ও মিলকরণ
        matched_groups: dict[int, list[ImportRow]] = {}
        unmatched: list[ImportRow] = []
        machinery: list[ImportRow] = []

        for imp in period_imports:
            name = imp.item_name or imp.commercial_name

            # --- ক) মেশিনারিজ? তাহলে পৃথক তালিকায় ---
            if self.exclude_machinery and imp.is_machinery_item:
                machinery.append(imp)
                imp.match_method = "machinery"
                imp.match_explanation = imp.machinery_reason
                continue

            # --- খ) প্রাপ্যতার সাথে মিলকরণ ---
            # কঠোর মোডে ক্লাস্টার-ভিত্তিক মিল গ্রহণযোগ্য নয়
            m: MatchResult = self.matcher.match(
                name, imp.hs_code,
                allow_cluster=False,   # ★ ইঞ্জিন নিজে ক্লাস্টার তৈরি করে না
                require_exact_hs=self.strict_hs,
            )

            imp.match_score = m.score
            imp.match_method = m.method
            imp.match_explanation = m.explanation

            if m.matched and m.target_id is not None:
                imp.matched_entitlement_id = m.target_id
                matched_groups.setdefault(m.target_id, []).append(imp)
                self._resolve_units(imp, self._ent_by_id[m.target_id], result)

                if m.score < self.LOW_CONFIDENCE_THRESHOLD:
                    ent = self._ent_by_id[m.target_id]
                    result.low_confidence_matches.append({
                        "বিল নং": imp.bill_number,
                        "আমদানি পণ্য": name,
                        "আমদানি HS": imp.hs_code or "",
                        "মিলকৃত প্রাপ্যতা": ent.item_name,
                        "প্রাপ্যতা HS": ent.hs_code or "",
                        "মিলের ধরন": m.method,
                        "আস্থা (%)": round(m.score * 100, 1),
                        "ব্যাখ্যা": m.explanation,
                        "বিকল্প": "; ".join(
                            f"{a['name']} ({a['score']:.0%})" for a in m.alternatives
                        ),
                    })
            else:
                unmatched.append(imp)
                result.unmatched_imports.append({
                    "বিল নং": imp.bill_number,
                    "তারিখ": str(imp.bill_date or ""),
                    "HS কোড": imp.hs_code or "",
                    "পণ্যের নাম": name,
                    "পরিমাণ": imp.quantity,
                    "একক": imp.unit,
                    "মূল্য (USD)": imp.value_usd,
                    "ব্যাখ্যা": m.explanation,
                    "নিকটতম সম্ভাবনা": "; ".join(
                        f"{a['name']} ({a['score']:.0%})" for a in m.alternatives
                    ) or "কিছুই পাওয়া যায়নি",
                })

        # ধাপ ২: স্থানীয় ক্রয়ও প্রাপ্যতার সাথে মেলাও (বন্ডিং ক্যাপাসিটির জন্য)
        local_groups: dict[int, list[ImportRow]] = {}
        for lp in period_local:
            lp.source_type = "local_purchase"
            if self.exclude_machinery and lp.is_machinery_item:
                continue
            m = self.matcher.match(
                lp.item_name or lp.commercial_name, lp.hs_code,
                allow_cluster=False,   # ★ ইঞ্জিন নিজে ক্লাস্টার তৈরি করে না
                require_exact_hs=self.strict_hs,
            )
            lp.match_score, lp.match_method = m.score, m.method
            lp.match_explanation = m.explanation
            if m.matched and m.target_id is not None:
                lp.matched_entitlement_id = m.target_id
                local_groups.setdefault(m.target_id, []).append(lp)
            else:
                # ★ প্রাপ্যতাবহির্ভূত স্থানীয় ক্রয়ও অননুমোদিত
                unmatched.append(lp)
                result.unmatched_imports.append({
                    "চালান নং": lp.bill_number,
                    "তারিখ": str(lp.bill_date or ""),
                    "HS কোড": lp.hs_code or "",
                    "পণ্যের নাম": lp.item_name or lp.commercial_name,
                    "পরিমাণ": lp.quantity,
                    "একক": lp.unit,
                    "উৎস": "স্থানীয় ক্রয়",
                    "ব্যাখ্যা": m.explanation,
                })

        # ধাপ ৩: অতিরিক্ত আমদানি ও প্রাপ্যতা ব্যবহার
        self._build_excess_and_utilization(matched_groups, result)

        # ধাপ ৪: অননুমোদিত এইচএস কোড
        self._build_unauthorized(unmatched, result)

        # ধাপ ৪.৫: ★ দাবি ৫ — মেয়াদোত্তর প্রাপ্যতা ব্যতীত আমদানি
        self._build_post_period(post_period_imports, post_period_local, result)

        # ধাপ ৪.৬: ★ বিধি ৮ — বর্ধিত প্রাপ্যতা ও বিয়োজন পর্যবেক্ষণ
        self._build_rule8_observations(result)

        # ধাপ ৫: মেশিনারিজ তালিকা
        self._build_machinery(machinery, result)

        # ধাপ ৬: ★ এককালীন বন্ডিং ক্যাপাসিটি যাচাই
        self._check_bonding_capacity(matched_groups, local_groups, result)

        # ধাপ ৭: সারসংক্ষেপ
        self._build_summary(result)

        logger.info(
            f"বিশ্লেষণ সম্পন্ন — অতিরিক্ত: {len(result.excess_records)}, "
            f"অননুমোদিত: {len(result.unauthorized_records)}, "
            f"মেশিনারিজ: {len(result.machinery_records)}, "
            f"ক্যাপাসিটি লঙ্ঘন: {sum(1 for r in result.bonding_records if r.excess_over_capacity > 0)}"
        )
        return result

    # ------------------------------------------------------
    def _validate_period_coverage(self, result: ImportAnalysisResult):
        """
        ★ আমদানি ফাইলটি প্রাপ্যতার মেয়াদের সাথে মেলে কিনা যাচাই

        প্রাপ্যতার মেয়াদ = বর্তমান নিরীক্ষার মেয়াদ।
        আমদানি ফাইলে যদি অধিকাংশ বিল এই মেয়াদের বাইরে হয়,
        তবে সম্ভবত ভুল ফাইল বা ভুল প্রাপ্যতা শীট আপলোড হয়েছে।
        """
        p_from = next((e.period_from for e in self.entitlements if e.period_from), None)
        p_to = next((e.period_to for e in self.entitlements if e.period_to), None)

        if not p_from or not p_to:
            result.warnings.append(
                "⚠ প্রাপ্যতার মেয়াদ শনাক্ত হয়নি — সকল আমদানি বিল "
                "গণনায় অন্তর্ভুক্ত হয়েছে। ফলাফল যাচাই করুন।"
            )
            return

        dated = [r for r in self.imports if r.bill_date]
        if not dated:
            result.warnings.append("⚠ আমদানি ফাইলে কোনো বিলের তারিখ পাওয়া যায়নি।")
            return

        inside = [r for r in dated if p_from <= r.bill_date <= p_to]
        outside = len(dated) - len(inside)
        coverage = len(inside) / len(dated)

        first, last = min(r.bill_date for r in dated), max(r.bill_date for r in dated)

        if coverage < 0.5:
            result.warnings.append(
                f"⛔ গুরুতর: আমদানি ফাইলের {outside}টি বিল "
                f"({(1-coverage):.0%}) প্রাপ্যতার মেয়াদ "
                f"({p_from.strftime('%d.%m.%Y')} — {p_to.strftime('%d.%m.%Y')}) "
                f"এর বাইরে। ফাইলের বিল-তারিখের পরিসর: "
                f"{first.strftime('%d.%m.%Y')} — {last.strftime('%d.%m.%Y')}। "
                f"সম্ভবত ভুল মেয়াদের প্রাপ্যতা শীট বা আমদানি ফাইল আপলোড হয়েছে — "
                f"অনুগ্রহ করে যাচাই করুন।"
            )
        elif outside:
            result.warnings.append(
                f"ℹ আমদানি ফাইলের {outside}টি বিল প্রাপ্যতার মেয়াদের বাইরে; "
                f"সেগুলো প্রাপ্যতা-ব্যবহারের হিসাবে অন্তর্ভুক্ত হয়নি।"
            )
        else:
            result.warnings.append(
                f"✓ আমদানি ফাইলের সকল বিল ({len(dated)}টি) প্রাপ্যতার মেয়াদের "
                f"({p_from.strftime('%d.%m.%Y')} — {p_to.strftime('%d.%m.%Y')}) মধ্যে।"
            )

    # ------------------------------------------------------
    def _in_period(self, imp: ImportRow, ent: EntitlementRow) -> bool:
        """আমদানিটি প্রাপ্যতার মেয়াদের ভেতরে কিনা"""
        if not self.enforce_period:
            return True
        if not imp.bill_date:
            return True   # তারিখ না থাকলে বাদ দেওয়া হবে না
        if ent.period_from and imp.bill_date < ent.period_from:
            return False
        if ent.period_to and imp.bill_date > ent.period_to:
            return False
        return True

    # ------------------------------------------------------
    def _apply_register_into_dates(self, result: ImportAnalysisResult):
        """
        ★ বন্ড রেজিস্টার (তফসিল-১) হইতে প্রতিটি বিলের ইন্টু-বন্ড তারিখ AIS সারিতে
        প্রয়োগ করে — অতিরিক্ত আমদানির প্রবেশক্রম FIFO নয়, রেজিস্টার-ভিত্তিক হয়।
        রেজিস্টার না থাকিলে বিল অব এন্ট্রির তারিখ ব্যবহৃত হয় (আনুমানিক)।
        """
        if not self.ledger_events:
            result.warnings.append(
                "ℹ বন্ড রেজিস্টার (তফসিল-১) দেওয়া হয় নাই — অতিরিক্ত আমদানির "
                "প্রবেশক্রম বিল অব এন্ট্রির তারিখ অনুযায়ী (আনুমানিক) নির্ণীত। "
                "রেজিস্টার প্রদান করিলে ইন্টু-বন্ড তারিখে নির্ভুল হইবে।"
            )
            return

        into_by_ref: dict[str, date] = {}
        for ev in self.ledger_events:
            if getattr(ev, "kind", "") == "into_bond" and ev.reference and ev.event_date:
                cur = into_by_ref.get(ev.reference)
                if cur is None or ev.event_date < cur:
                    into_by_ref[ev.reference] = ev.event_date

        applied = 0
        for r in self.imports:
            d = into_by_ref.get(r.bill_number)
            if d:
                r.into_bond_date = d
                applied += 1

        result.warnings.append(
            f"✓ বন্ড রেজিস্টার (তফসিল-১) হইতে {applied}টি বিলের ইন্টু-বন্ড তারিখ "
            f"প্রয়োগ করা হইয়াছে — অতিরিক্ত আমদানির প্রবেশক্রম রেজিস্টার-ভিত্তিক "
            f"(FIFO অনুমান নহে)।"
        )

    # ------------------------------------------------------
    def _audit_period_end(self) -> date | None:
        """নিরীক্ষা মেয়াদের সমাপ্তি (প্রাপ্যতা শীটের period_to)"""
        return next((e.period_to for e in self.entitlements if e.period_to), None)

    def _is_post_period(self, row: ImportRow) -> bool:
        """
        ★ বিলটি মেয়াদোত্তর (দাবি ৫) কিনা।

        সত্য যখন — বিল-তারিখ নিরীক্ষা মেয়াদের শেষ (period_to)-এর পরে, এবং
        (নূতন প্রাপ্যতার তারিখ দেওয়া থাকিলে) তাহার পূর্বে। মেয়াদ-পূর্ব বিল
        (period_from-এর আগে) মেয়াদোত্তর নহে — উহা পূর্ববর্তী নিরীক্ষার আওতাধীন।
        """
        p_to = self._audit_period_end()
        if not p_to or not row.bill_date:
            return False
        if row.bill_date <= p_to:
            return False
        nxt = self.next_entitlement_date
        if nxt and row.bill_date >= nxt:
            return False   # নূতন প্রাপ্যতায় আচ্ছাদিত — দাবি ৫-এর বাইরে
        return True

    # ------------------------------------------------------
    def _build_excess_and_utilization(
        self, groups: dict[int, list[ImportRow]], result: ImportAnalysisResult
    ):
        """প্রতিটি প্রাপ্যতা আইটেমের বিপরীতে হিসাব"""
        excess_serial = 0
        util_serial = 0

        for ent in self.entitlements:
            util_serial += 1
            all_rows = groups.get(ent.row_id, [])

            # মেয়াদ যাচাই
            in_period = [r for r in all_rows if self._in_period(r, ent)]
            out_period = [r for r in all_rows if not self._in_period(r, ent)]

            if out_period:
                before = [r for r in out_period if r.bill_date and ent.period_from
                          and r.bill_date < ent.period_from]
                after = [r for r in out_period if r.bill_date and ent.period_to
                         and r.bill_date > ent.period_to]
                if before:
                    result.warnings.append(
                        f"'{ent.item_name[:40]}' — {len(before)}টি বিল প্রাপ্যতার "
                        f"মেয়াদ শুরুর ({ent.period_from.strftime('%d.%m.%Y')}) পূর্বের; "
                        f"ইহা পূর্ববর্তী প্রাপ্যতার আওতাধীন বিধায় চলতি হিসাবে "
                        f"অন্তর্ভুক্ত হয়নি। বিল: "
                        f"{', '.join(r.bill_number for r in before[:5])}"
                    )
                if after:
                    result.warnings.append(
                        f"'{ent.item_name[:40]}' — {len(after)}টি বিল প্রাপ্যতার "
                        f"মেয়াদ শেষের ({ent.period_to.strftime('%d.%m.%Y')}) পরের; "
                        f"ইহা পরবর্তী প্রাপ্যতার আওতাধীন বিধায় চলতি হিসাবে "
                        f"অন্তর্ভুক্ত হয়নি। বিল: "
                        f"{', '.join(r.bill_number for r in after[:5])}"
                    )

            imported_qty = sum(r.quantity or 0 for r in in_period)
            # ★ মোট অনুমোদিত = মূল + বর্ধিত [বিধি ৮]; সীমা এই মোটের বিপরীতে
            entitled_qty = ent.effective_entitled_quantity
            allowed_qty = entitled_qty * (1 + self.tolerance)
            balance = entitled_qty - imported_qty

            # --- ব্যবহার রেকর্ড ---
            util_pct = (imported_qty / entitled_qty * 100) if entitled_qty else 0.0
            if imported_qty > allowed_qty:
                status = "অতিরিক্ত"
            elif entitled_qty and imported_qty >= entitled_qty * 0.99:
                status = "সম্পূর্ণ ব্যবহৃত"
            elif imported_qty > 0:
                status = "আংশিক ব্যবহৃত"
            else:
                status = "অব্যবহৃত"

            result.utilization_records.append(UtilizationRecord(
                serial=util_serial,
                hs_code=ent.hs_code or "",
                entitlement_item=ent.display_name,
                cluster=ent.cluster_label if ent.is_cluster else "",
                period_label=ent.period_label,
                entitled_quantity=round(entitled_qty, 3),
                imported_quantity=round(imported_qty, 3),
                balance_quantity=round(balance, 3),
                utilization_pct=round(util_pct, 2),
                unit=ent.unit or (in_period[0].unit if in_period else ""),
                bill_count=len(in_period),
                status=status,
                extended_quantity=round(ent.extended_entitlement or 0.0, 3),
            ))

            # --- অতিরিক্ত আমদানি ---
            if entitled_qty > 0 and imported_qty > allowed_qty:
                excess_serial += 1
                excess_qty = imported_qty - entitled_qty
                excess_pct = (excess_qty / entitled_qty * 100)

                rec = self._make_excess_record(
                    excess_serial, ent, in_period, imported_qty, excess_qty, excess_pct
                )
                result.excess_records.append(rec)

    # ------------------------------------------------------
    def _make_excess_record(
        self,
        serial: int,
        ent: EntitlementRow,
        rows: list[ImportRow],
        imported_qty: float,
        excess_qty: float,
        excess_pct: float,
    ) -> ExcessRecord:
        """একটি অতিরিক্ত আমদানি রেকর্ড তৈরি করো — রাজস্ব হিসাবসহ"""

        # ★ সীমা = মোট অনুমোদিত (মূল + বর্ধিত [বিধি ৮])
        limit_qty = ent.effective_entitled_quantity

        # প্রবেশক্রম (into-bond register তারিখ; না থাকিলে BE তারিখ) অনুযায়ী
        sorted_rows = sorted(rows, key=lambda r: (r.into_bond_date or r.bill_date or date.min))
        running = 0.0
        excess_bill_list: list[str] = []
        for r in sorted_rows:
            prev = running
            running += r.quantity or 0
            if running > limit_qty:
                over = running - max(prev, limit_qty)
                excess_bill_list.append(f"{r.bill_number} ({over:,.0f} {r.unit or ent.unit})")

        # গড় একক মূল্য — তথ্যের জন্য
        total_val = sum(r.value_usd or 0 for r in rows)
        total_qty = sum(r.quantity or 0 for r in rows) or 1
        avg_price = total_val / total_qty if total_qty else (ent.unit_price or 0)

        rates = [r.exchange_rate for r in rows if r.exchange_rate]
        ex_rate = float(np.mean(rates)) if rates else 0.0

        excess_val_usd = excess_qty * avg_price

        # === ★ শুল্কায়ন — বন্ড সুবিধা বাতিল করে MIS/BE-এর সম্পূর্ণ শুল্ক-কর ===
        tb = assess_excess(rows, limit=limit_qty)
        excess_val_bdt = tb.assessable_value

        # তথ্যমূলক করহার
        duty_rate = self._pick_rate([r.duty_rate for r in rows], ent.duty_rate)
        vat_rate = self._pick_rate([r.vat_rate for r in rows], ent.vat_rate or VAT_RATE_DEFAULT)
        at_rate = ent.at_rate or AT_RATE_DEFAULT
        rd_rate = ent.rd_rate or 0.0
        sd_rate = ent.sd_rate or 0.0
        ait_rate = ent.ait_rate or AIT_RATE_DEFAULT

        # --- মন্তব্য ---
        remarks = (
            (f"প্রাপ্যতা শীটে একত্রে প্রাপ্যতাপ্রাপ্ত {len(ent.members)}টি "
             f"কাঁচামালের ক্লাস্টার (এইচ.এস কোড: "
             f"{', '.join(ent.all_hs_codes)}) এর বিপরীতে প্রদত্ত "
             if ent.is_cluster else "প্রাপ্যতা ")
            + f"{limit_qty:,.0f} {ent.unit} "
            + (f"(মূল {ent.entitled_quantity:,.0f} + বর্ধিত [বিধি ৮] "
               f"{ent.extended_entitlement:,.0f}) " if ent.extended_entitlement else "")
            + f"({ent.period_label or 'মেয়াদ উল্লেখ নেই'}) এর বিপরীতে "
            f"{imported_qty:,.0f} {ent.unit} আমদানি — "
            f"{excess_qty:,.0f} {ent.unit} ({excess_pct:.1f}%) অতিরিক্ত। "
            f"{tb.calculation_note}"
        )

        method = rows[0].match_method if rows else "unknown"
        conf = float(np.mean([r.match_score for r in rows])) if rows else 0.0
        if method == "cluster":
            remarks += " [ক্লাস্টার ভিত্তিতে মিলকৃত — যাচাই বাঞ্ছনীয়]"

        return ExcessRecord(
            serial=serial,
            hs_code=(", ".join(ent.all_hs_codes) if ent.is_cluster else (ent.hs_code or "")),
            item_name=", ".join(sorted({(r.item_name or "")[:60] for r in rows}))[:250],
            entitlement_item=ent.display_name,
            cluster=ent.cluster_label if ent.is_cluster else "",
            period_label=ent.period_label,
            entitled_quantity=round(limit_qty, 3),
            imported_quantity=round(imported_qty, 3),
            excess_quantity=round(excess_qty, 3),
            excess_pct=round(excess_pct, 2),
            unit=ent.unit or (rows[0].unit if rows else ""),
            bill_count=len(rows),
            bill_numbers=", ".join(r.bill_number for r in sorted_rows),
            excess_bills="; ".join(excess_bill_list),
            avg_unit_price_usd=round(avg_price, 4),
            excess_value_usd=round(excess_val_usd, 2),
            excess_value_bdt=round(excess_val_bdt, 2),
            exchange_rate=round(ex_rate, 2),
            duty_rate=duty_rate, vat_rate=vat_rate, at_rate=at_rate,
            rd_rate=rd_rate, sd_rate=sd_rate, ait_rate=ait_rate,
            duty_involved=tb.cd,
            vat_involved=tb.vat,
            at_involved=tb.at,
            rd_involved=tb.rd,
            sd_involved=tb.sd,
            ait_involved=tb.ait,
            total_revenue_impact=tb.total,
            assessment_basis=tb.basis,
            bank_guarantee_note=BANK_GUARANTEE_NOTE,
            match_method=method,
            match_confidence=round(conf, 3),
            remarks=remarks,
        )

    # ------------------------------------------------------
    @staticmethod
    def _pick_rate(values: list[float], fallback: float) -> float:
        """বিল থেকে করহার নাও; না পেলে প্রাপ্যতা শীটের হার"""
        vals = [v for v in values if v and v > 0]
        return float(np.median(vals)) if vals else (fallback or 0.0)

    # ------------------------------------------------------
    def _build_unauthorized(
        self, unmatched: list[ImportRow], result: ImportAnalysisResult
    ):
        """প্রাপ্যতায় নেই এমন আমদানি — HS কোড ভিত্তিক একত্রিত"""
        groups: dict[tuple, list[ImportRow]] = {}
        for r in unmatched:
            key = (r.hs_code or "", normalize(r.item_name)[:60])
            groups.setdefault(key, []).append(r)

        serial = 0
        for (hs, _), rows in sorted(
            groups.items(), key=lambda kv: -sum(x.value_usd or 0 for x in kv[1])
        ):
            serial += 1
            qty = sum(r.quantity or 0 for r in rows)
            val_usd = sum(r.value_usd or 0 for r in rows)
            val_bdt = sum(r.value_bdt or 0 for r in rows)

            # === ★ শুল্কায়ন — সম্পূর্ণ আমদানিতে বন্ড সুবিধা বাতিল ===
            tb = assess_full(rows)

            # নিকটতম সম্ভাব্য প্রাপ্যতা
            m = self.matcher.match(rows[0].item_name, rows[0].hs_code, allow_cluster=False)
            near_name, near_score = "", 0.0
            if m.alternatives:
                near_name = m.alternatives[0]["name"]
                near_score = m.alternatives[0]["score"]

            cluster = rows[0].cluster or ""
            remarks = (
                f"এই পণ্যটির নাম ও এইচ.এস কোড কোনোটিই প্রাপ্যতা শীটে "
                f"অন্তর্ভুক্ত নয়। HS {hs or '—'} এর বিপরীতে {len(rows)}টি বিলে "
                f"{qty:,.0f} {rows[0].unit} আমদানি করা হয়েছে। "
            )
            if near_name:
                remarks += f"নিকটতম সম্ভাব্য প্রাপ্যতা: '{near_name}' ({near_score:.0%})। "
            remarks += (
                "মেশিনারিজ ব্যতীত প্রাপ্যতা শীটবহির্ভূত আমদানি হওয়ায় "
                "ইহা অননুমোদিত এইচ.এস কোড ব্যবহার করে আমদানি হিসেবে গণ্য। "
                + tb.calculation_note
            )

            result.unauthorized_records.append(UnauthorizedRecord(
                serial=serial,
                hs_code=hs,
                item_name=", ".join(sorted({(r.item_name or "")[:60] for r in rows}))[:250],
                cluster=cluster,
                bill_count=len(rows),
                bill_numbers=", ".join(r.bill_number for r in rows),
                total_quantity=round(qty, 3),
                unit=rows[0].unit or "",
                total_value_usd=round(val_usd, 2),
                total_value_bdt=round(val_bdt, 2),
                assessable_value_bdt=tb.assessable_value,
                cd_demanded=tb.cd,
                rd_demanded=tb.rd,
                sd_demanded=tb.sd,
                vat_demanded=tb.vat,
                at_demanded=tb.at,
                ait_demanded=tb.ait,
                total_revenue_impact=tb.total,
                assessment_basis=tb.basis,
                nearest_match=near_name,
                nearest_score=round(near_score, 3),
                remarks=remarks,
            ))

    # ------------------------------------------------------
    POST_PERIOD_LEGAL_BASIS = (
        "এসআরও ২১৪-আইন/২০২৪/৬৬/কাস্টমস — বিধি ৫, ৯ ও ১২ "
        "(নিরীক্ষা মেয়াদ সমাপনান্তে প্রাপ্যতা/প্রত্যয়নপত্র ব্যতীত আমদানি)"
    )

    def _build_post_period(
        self,
        imports: list[ImportRow],
        local_purchases: list[ImportRow],
        result: ImportAnalysisResult,
    ):
        """
        ★ দাবি ৫ — নিরীক্ষা মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি

        period_to-এর পর (এবং নূতন প্রাপ্যতার তারিখ থাকিলে তাহার পূর্বে)
        যে সকল আমদানি ও স্থানীয় ক্রয় কোনো বৈধ প্রাপ্যতা/প্রত্যয়নপত্র ছাড়াই
        হইয়াছে — তাহার সম্পূর্ণ শুল্ক-কর দাবিযোগ্য।
        """
        rows = list(imports) + list(local_purchases)
        if not rows:
            return

        p_to = self._audit_period_end()
        nxt = self.next_entitlement_date
        window = (
            (f"{p_to.strftime('%d.%m.%Y')}-এর পর" if p_to else "মেয়াদ সমাপ্তির পর")
            + (f" — {nxt.strftime('%d.%m.%Y')}-এর পূর্ব"
               if nxt else " (নূতন প্রাপ্যতার তারিখ পর্যন্ত)")
        )

        if nxt is None:
            result.warnings.append(
                "⚠ নূতন প্রাপ্যতা/UP অনুমোদনের তারিখ প্রদান করা হয় নাই — "
                "নিরীক্ষা মেয়াদ (period_to) সমাপ্তির পরের সকল বিল 'দাবি ৫ — "
                "মেয়াদোত্তর'-এ অন্তর্ভুক্ত হইয়াছে। বৈধ নূতন প্রাপ্যতায় আচ্ছাদিত "
                "বিল থাকিলে অনুগ্রহ করে নূতন প্রাপ্যতার তারিখ প্রদান করুন।"
            )

        # উৎস ও পণ্য অনুসারে একত্রীকরণ
        groups: dict[tuple, list[ImportRow]] = {}
        for r in rows:
            is_local = getattr(r, "source_type", "import") == "local_purchase"
            src = "স্থানীয় ক্রয়" if is_local else "আমদানি (IM-4/IM-7)"
            key = (src, r.hs_code or "", normalize(r.item_name)[:60])
            groups.setdefault(key, []).append(r)

        serial = 0
        for (src, hs, _), grows in sorted(
            groups.items(), key=lambda kv: -sum(x.value_usd or 0 for x in kv[1])
        ):
            serial += 1
            qty = sum(r.quantity or 0 for r in grows)
            val_usd = sum(r.value_usd or 0 for r in grows)
            val_bdt = sum(r.value_bdt or 0 for r in grows)

            # ★ সম্পূর্ণ শুল্কায়ন — আমদানিতে পূর্ণ BE, স্থানীয় ক্রয়ে ১৫% উৎসে মূসক
            tb = assess_full(grows)

            remarks = (
                f"নিরীক্ষা মেয়াদ ({p_to.strftime('%d.%m.%Y') if p_to else '—'}) "
                f"সমাপ্তির পর, নূতন প্রাপ্যতা অনুমোদনের পূর্বে, কোনো বৈধ প্রাপ্যতা "
                f"বা প্রত্যয়নপত্র ব্যতীত {src} বাবদ HS {hs or '—'} এর বিপরীতে "
                f"{len(grows)}টি বিলে {qty:,.3f} {grows[0].unit} সংগ্রহ করা "
                f"হইয়াছে (সময়কাল: {window})। বন্ড সুবিধায় শুল্কমুক্ত সংগ্রহের "
                f"বৈধতা না থাকায় সম্পূর্ণ শুল্ক-কর দাবিযোগ্য। "
                + tb.calculation_note + " " + BANK_GUARANTEE_NOTE
            )

            result.post_period_records.append(PostPeriodRecord(
                serial=serial,
                source=src,
                hs_code=hs,
                item_name=", ".join(sorted({(r.item_name or "")[:60] for r in grows}))[:250],
                bill_count=len(grows),
                bill_numbers=", ".join(r.bill_number for r in grows),
                total_quantity=round(qty, 3),
                unit=grows[0].unit or "",
                total_value_usd=round(val_usd, 2),
                total_value_bdt=round(val_bdt, 2),
                assessable_value_bdt=tb.assessable_value,
                cd_demanded=tb.cd,
                rd_demanded=tb.rd,
                sd_demanded=tb.sd,
                vat_demanded=tb.vat,
                at_demanded=tb.at,
                ait_demanded=tb.ait,
                total_revenue_impact=tb.total,
                assessment_basis=tb.basis,
                period_window=window,
                legal_basis=self.POST_PERIOD_LEGAL_BASIS,
                remarks=remarks,
            ))

        logger.info(
            f"মেয়াদোত্তর দাবি (দাবি ৫) — {len(result.post_period_records)}টি রেকর্ড, "
            f"মোট দাবি {sum(r.total_revenue_impact for r in result.post_period_records):,.0f} টাকা"
        )

    # ------------------------------------------------------
    RULE8_LEGAL_BASIS = (
        "বার্ষিক আমদানি-প্রাপ্যতা নির্ধারণ বিধিমালা, ২০২৪ [এসআরও ২১৪-আইন/২০২৪] — "
        "বিধি ৮ (নিরীক্ষাধীন অবস্থায় প্রাপ্যতার মেয়াদ ৩ মাস বৃদ্ধি) সহপঠিত "
        "বর্ধিত সময়ে ব্যবহৃত পরিমাণের বিয়োজন"
    )
    RULE8_INSTRUCTION = (
        "নিরীক্ষা চলাকালে বিধি ৮ অনুযায়ী পূর্ববর্তী প্রাপ্যতার মেয়াদ ৩ মাস বৃদ্ধি "
        "প্রযোজ্য; বর্ধিত পরিমাণ মোট অনুমোদিত প্রাপ্যতায় যুক্ত হইয়াছে। তবে বর্ধিত "
        "সময়ে ব্যবহৃত কাঁচামালের পরিমাণ প্রতিষ্ঠানের স্ব-ঘোষণা — ইঞ্জিন উহা "
        "স্বয়ংক্রিয়ভাবে গণনা করে না। নিরীক্ষক (১) প্রতিষ্ঠানের নিকট বর্ধিত সময়ের "
        "ব্যবহৃত পরিমাণের ঘোষণা তলব করিবেন; (২) উহা বন্ড রেজিস্টার (তফসিল-১) ও "
        "সংশ্লিষ্ট দলিলের সহিত মিলাইয়া যাচাই করিবেন; (৩) নূতন প্রাপ্যতা নির্ধারণের "
        "সময় ঐ পরিমাণ বিয়োজন হইয়াছে কিনা নিশ্চিত করিবেন — বিয়োজন না হইলে "
        "পর্যবেক্ষণ হিসাবে লিপিবদ্ধ করিবেন।"
    )

    def _build_rule8_observations(self, result: ImportAnalysisResult):
        """
        ★ বিধি ৮ — বর্ধিত প্রাপ্যতা ও বিয়োজন যাচাই পর্যবেক্ষণ (দাবি নহে)।

        যখন নিরীক্ষক extension_applies flag দেন, অথবা কোনো প্রাপ্যতা-এককে বর্ধিত
        প্রাপ্যতা (extended_entitlement) দেওয়া থাকে — তখন বিয়োজন-যাচাই নির্দেশ দেয়।
        """
        items_ext = [e for e in self.entitlements if (e.extended_entitlement or 0) > 0]
        if not items_ext and not self.extension_applies:
            return

        # সামগ্রিক নির্দেশ
        result.rule8_observations.append(Rule8Observation(
            serial=0, entitlement_item="সামগ্রিক",
            base_entitlement=0.0, extended_entitlement=0.0, combined_entitlement=0.0,
            unit="", instruction=self.RULE8_INSTRUCTION,
            legal_basis=self.RULE8_LEGAL_BASIS, scope="overall",
        ))

        # আইটেমভিত্তিক (যেখানে বর্ধিত পরিমাণ জানা আছে)
        for i, e in enumerate(items_ext, start=1):
            result.rule8_observations.append(Rule8Observation(
                serial=i, entitlement_item=e.display_name,
                base_entitlement=round(e.entitled_quantity or 0.0, 3),
                extended_entitlement=round(e.extended_entitlement or 0.0, 3),
                combined_entitlement=round(e.effective_entitled_quantity, 3),
                unit=e.unit,
                instruction=(
                    "এই এককের মোট অনুমোদিত প্রাপ্যতায় বর্ধিত প্রাপ্যতা [বিধি ৮] "
                    "অন্তর্ভুক্ত। বর্ধিত সময়ে ব্যবহৃত পরিমাণ প্রতিষ্ঠানের ঘোষণা "
                    "হইতে লইয়া বন্ড রেজিস্টারে যাচাই ও বিয়োজন নিশ্চিত করুন।"
                ),
                legal_basis=self.RULE8_LEGAL_BASIS, scope="item",
            ))

        result.warnings.append("বিধি ৮ (বর্ধিত প্রাপ্যতা): " + self.RULE8_INSTRUCTION)
        logger.info(f"বিধি ৮ পর্যবেক্ষণ — {len(result.rule8_observations)}টি")

    # ------------------------------------------------------
    def _build_cluster_excess(
        self,
        import_groups: dict[int, list[ImportRow]],
        local_groups: dict[int, list[ImportRow]],
        result: ImportAnalysisResult,
    ):
        """
        ★ ক্লাস্টারভিত্তিক অতিরিক্ত আমদানি যাচাই

        প্রাপ্যতা কাঁচামাল অথবা কাঁচামালের ক্লাস্টার ভিত্তিতে দেওয়া হয়।
        প্রতিটি আইটেম পৃথকভাবে সীমার মধ্যে থাকলেও ক্লাস্টারের সমষ্টি
        সীমা অতিক্রম করতে পারে — সেটিও আপত্তিযোগ্য।
        """
        from ai.matcher import DEFAULT_CLUSTERS
        cluster_names = {c.code: c.name_bn for c in DEFAULT_CLUSTERS}

        # ক্লাস্টার অনুযায়ী প্রাপ্যতা ও প্রবেশ গোষ্ঠীবদ্ধ করো
        by_cluster: dict[str, dict] = {}
        for ent in self.entitlements:
            code = ent.cluster
            if not code:
                continue
            g = by_cluster.setdefault(code, {
                "entitled": 0.0, "units": set(), "hs": set(),
                "items": 0, "imports": [], "locals": [],
            })
            g["entitled"] += ent.entitled_quantity or 0.0
            g["items"] += 1
            if ent.unit:
                g["units"].add(ent.unit.upper())
            if ent.hs_code:
                g["hs"].add(ent.hs_code)
            g["imports"].extend(
                r for r in import_groups.get(ent.row_id, []) if self._in_period(r, ent)
            )
            g["locals"].extend(
                r for r in local_groups.get(ent.row_id, []) if self._in_period(r, ent)
            )

        serial = 0
        for code, g in sorted(by_cluster.items()):
            # একই ক্লাস্টারে একাধিক আইটেম না থাকলে আইটেমভিত্তিক যাচাইই যথেষ্ট
            if g["items"] < 2:
                continue

            # একক ভিন্ন হলে যোগ করা অর্থহীন — সতর্ক করে বাদ দাও
            if len(g["units"]) > 1:
                result.warnings.append(
                    f"ক্লাস্টার '{cluster_names.get(code, code)}' — একাধিক একক "
                    f"({', '.join(sorted(g['units']))}) থাকায় ক্লাস্টারভিত্তিক "
                    f"যোগফল নির্ণয় করা হয়নি; আইটেমভিত্তিক যাচাই প্রযোজ্য।"
                )
                continue

            unit = next(iter(g["units"])) if g["units"] else ""
            entitled = g["entitled"]
            imp_qty = sum(r.quantity or 0 for r in g["imports"])
            loc_qty = sum(r.quantity or 0 for r in g["locals"])
            total_qty = imp_qty + loc_qty

            if entitled <= 0 or total_qty <= entitled * (1 + self.tolerance):
                continue

            serial += 1
            excess = total_qty - entitled
            excess_pct = excess / entitled * 100

            all_rows = g["imports"] + g["locals"]
            tb = assess_excess(all_rows, limit=entitled)

            # উৎসে মূসক আলাদা করে দেখাও
            src_vat = sum(
                d.get("দাবিকৃত উৎসে মূসক (৳)", 0.0) for d in tb.bill_details
            )

            excess_bills = "; ".join(
                f"{d.get('বিল নং') or d.get('চালান নং')} "
                f"({d['আপত্তিকৃত পরিমাণ']:,.0f} {d['একক']})"
                for d in tb.bill_details
            )

            remarks = (
                f"'{cluster_names.get(code, code)}' ক্লাস্টারভুক্ত {g['items']}টি "
                f"কাঁচামালের বিপরীতে মোট প্রাপ্যতা {entitled:,.0f} {unit}। "
                f"নিরীক্ষাধীন মেয়াদে আমদানি {imp_qty:,.0f} + স্থানীয় ক্রয় "
                f"{loc_qty:,.0f} = {total_qty:,.0f} {unit} — "
                f"{excess:,.0f} {unit} ({excess_pct:.1f}%) অতিরিক্ত। "
                f"{tb.calculation_note}"
            )
            if src_vat > 0:
                remarks += (
                    f" স্থানীয় ক্রয় সংশ্লিষ্ট অংশে ১৫% হারে উৎসে মূসক "
                    f"৳{src_vat:,.0f} দাবি করা হইল।"
                )

            result.cluster_excess_records.append(ClusterExcessRecord(
                serial=serial,
                cluster_code=code,
                cluster_name=cluster_names.get(code, code),
                hs_codes=", ".join(sorted(g["hs"])),
                items_in_cluster=g["items"],
                unit=unit,
                entitled_quantity=round(entitled, 3),
                imported_quantity=round(imp_qty, 3),
                local_quantity=round(loc_qty, 3),
                total_quantity=round(total_qty, 3),
                excess_quantity=round(excess, 3),
                excess_pct=round(excess_pct, 2),
                bill_count=len(all_rows),
                bill_numbers=", ".join(r.bill_number for r in all_rows),
                excess_bills=excess_bills,
                assessable_value_bdt=tb.assessable_value,
                cd_demanded=tb.cd, rd_demanded=tb.rd, sd_demanded=tb.sd,
                vat_demanded=tb.vat, at_demanded=tb.at, ait_demanded=tb.ait,
                source_vat_demanded=round(src_vat, 2),
                total_revenue_impact=tb.total,
                assessment_basis=tb.basis,
                status="সীমা অতিক্রম",
                remarks=remarks,
            ))

    # ------------------------------------------------------
    def _build_machinery(
        self, machinery: list[ImportRow], result: ImportAnalysisResult
    ):
        """মেশিনারিজ ও যন্ত্রাংশ — পৃথক তালিকা, অননুমোদিত নয়"""
        groups: dict[tuple, list[ImportRow]] = {}
        for r in machinery:
            key = (r.hs_code or "", normalize(r.item_name)[:60])
            groups.setdefault(key, []).append(r)

        serial = 0
        for (hs, _), rows in sorted(
            groups.items(), key=lambda kv: -sum(x.value_usd or 0 for x in kv[1])
        ):
            serial += 1
            result.machinery_records.append(MachineryRecord(
                serial=serial,
                hs_code=hs,
                item_name=", ".join(sorted({(r.item_name or "")[:60] for r in rows}))[:250],
                bill_count=len(rows),
                bill_numbers=", ".join(r.bill_number for r in rows),
                total_quantity=round(sum(r.quantity or 0 for r in rows), 3),
                unit=rows[0].unit or "",
                total_value_usd=round(sum(r.value_usd or 0 for r in rows), 2),
                total_value_bdt=round(sum(r.value_bdt or 0 for r in rows), 2),
                duty_paid=round(sum(r.duty_paid or 0 for r in rows), 2),
                vat_paid=round(sum(r.vat_paid or 0 for r in rows), 2),
                reason=rows[0].machinery_reason,
                remarks=(
                    "মূলধনী যন্ত্রপাতি/যন্ত্রাংশ হিসেবে চিহ্নিত। "
                    "প্রাপ্যতা শীটে অন্তর্ভুক্ত না থাকলেও অননুমোদিত আমদানি "
                    "হিসেবে গণ্য হয়নি। তবে সংশ্লিষ্ট অনুমোদন/এসআরও সুবিধার "
                    "শর্ত পৃথকভাবে যাচাই করা প্রয়োজন।"
                ),
            ))

    # ------------------------------------------------------
    def _check_bonding_capacity(
        self,
        import_groups: dict[int, list[ImportRow]],
        local_groups: dict[int, list[ImportRow]],
        result: ImportAnalysisResult,
    ):
        """
        ★ দাবি ৩ — এককালীন বন্ডিং ক্যাপাসিটি যাচাই (সামগ্রিক, কেজিতে)

        এসআরও ২০৯/২০২৪ বিধি ৭(৩) ও এসআরও ২১৪/২০২৪ বিধি ১৫:
            ক্যাপাসিটি = min( প্রাপ্যতা ÷ ৩ , ওয়্যারহাউসের ধারণক্ষমতা )
            প্রাপ্যতা  = শীটে প্রদত্ত পরিমাণ (মজুত বাদে) + প্রারম্ভিক মজুত

        ০১.০৭.২০২৬ হইতে: ক্যাপাসিটি = ওয়্যারহাউসের ধারণক্ষমতা

        যাচাই সামগ্রিক — সকল কাঁচামালের সমষ্টি (কেজিতে) কোনো মুহূর্তে
        ক্যাপাসিটি অতিক্রম করিতে পারিবে না।
        """
        # ★★ কনজাম্পশন রেজিস্টার না থাকিলে যাচাই স্থগিত ★★
        if not self.register.can_check_capacity:
            result.bonding_value.status = "যাচাই স্থগিত"
            result.bonding_value.remarks = self.register.note
            result.warnings.append("ℹ " + self.register.note)
            logger.info(
                "কনজাম্পশন রেজিস্টার অনুপস্থিত — এককালীন বন্ডিং ক্যাপাসিটি "
                "সংক্রান্ত ফাইন্ডিংস প্রদান করা হইল না"
            )
            return

        # --- মেয়াদ ও পদ্ধতি ---
        p_from = next((e.period_from for e in self.entitlements if e.period_from), None)
        p_to = next((e.period_to for e in self.entitlements if e.period_to), None)
        segments = split_audit_period(p_from, p_to)
        regime = "new" if segments[-1].regime == CapacityRegime.NEW else "old"
        if len(segments) > 1:
            result.warnings.append(
                f"ℹ নিরীক্ষা মেয়াদ নিয়ম পরিবর্তনের তারিখ "
                f"({NEW_REGIME_DATE.strftime('%d.%m.%Y')}) অতিক্রম করায় "
                + "; ".join(f"{sg.label} [{sg.display}]" for sg in segments)
                + " — খণ্ডভিত্তিক ক্যাপাসিটি প্রয়োগ করা হইয়াছে।"
            )

        # --- সামগ্রিক প্রাপ্যতা ও প্রারম্ভিক মজুত (কেজিতে) ---
        sheet_kg = sum(self._to_kg_entitlement(e) for e in self.entitlements)
        opening_kg = sum(self._to_kg_opening(e) for e in self.entitlements)

        # --- ওয়্যারহাউসের ধারণক্ষমতা ---
        wh = compute_warehouse_capacity(
            length_ft=self.warehouse_dims.get("length", 0.0),
            width_ft=self.warehouse_dims.get("width", 0.0),
            height_ft=self.warehouse_dims.get("height", 0.0),
            volume_cft=self.warehouse_dims.get("volume", 0.0),
            given_capacity_mt=self.warehouse_capacity_mt,
            bond_license_capacity_mt=self.bond_license_capacity_mt,
        )

        cap = compute_one_time_capacity(
            entitlement_sheet_kg=sheet_kg,
            opening_stock_kg=opening_kg,
            warehouse_capacity_kg=wh.capacity_kg,
            regime=regime,
        )
        result.one_time_capacity = cap
        for n in cap.notes:
            result.warnings.append(n)

        if cap.capacity_kg <= 0:
            result.bonding_value.status = "যাচাই সম্ভব হয় নাই"
            result.bonding_value.remarks = (
                "এককালীন বন্ডিং ক্যাপাসিটি নির্ণয় করা যায় নাই। "
                + " ".join(cap.notes)
            )
            return

        # --- খতিয়ানের ঘটনাবলি ---
        events = self._build_ledger_events(import_groups, local_groups)
        if not events:
            result.warnings.append(
                "⚠ বন্ড রেজিস্টার হইতে কোনো ইন্টু-বন্ড/এক্স-বন্ড ঘটনা "
                "পাওয়া যায় নাই — ক্যাপাসিটি যাচাই সম্পন্ন হয় নাই।"
            )
            return

        ledger = build_capacity_ledger(events, opening_kg, cap, wh)
        result.capacity_ledger = ledger
        result.warnings.extend(ledger.warnings)

        # --- প্রতিটি লঙ্ঘনের শুল্কায়ন ---
        self._assess_breaches(ledger, cap, result)

        # --- সামগ্রিক অবস্থা ---
        bv = result.bonding_value
        bv.status = ledger.status
        bv.remarks = ledger.remarks
        bv.calculation_basis = cap.formula

    # ------------------------------------------------------
    def _resolve_units(self, imp: ImportRow, ent, result: ImportAnalysisResult):
        """
        ★ আমদানির পরিমাণে দুইটি কলাম প্রস্তুত করো —
          ১) প্রাপ্যতা শীটের এককে  ২) কেজিতে
        """
        r = self.unit_extractor.extract(
            description=imp.item_name or imp.commercial_name,
            mis_qty=imp.quantity, mis_unit=imp.unit,
            mis_qty_kg=imp.qty_kg, target_unit=ent.unit,
            bill_number=imp.bill_number,
        )
        imp.target_unit = r.target_unit
        imp.qty_target_unit = r.target_qty
        imp.qty_kg = r.qty_kg
        imp.unit_source = f"{r.target_source}/{r.kg_source}"

        # প্রাপ্যতার এককে পরিমাণ পাওয়া গেলে সেটিই তুলনার ভিত্তি
        if r.target_qty is not None:
            imp.quantity = float(r.target_qty)
            imp.unit = r.target_unit or imp.unit

        if r.needs_review:
            imp.unit_flag = r.flag_reason
            result.low_confidence_matches.append({
                "বিল নং": imp.bill_number,
                "আমদানি পণ্য": (imp.item_name or "")[:70],
                "আমদানি HS": imp.hs_code or "",
                "মিলকৃত প্রাপ্যতা": ent.display_name[:50],
                "প্রাপ্যতা HS": ent.hs_code or "",
                "মিলের ধরন": "একক নিষ্কাশন",
                "আস্থা (%)": 0.0,
                "ব্যাখ্যা": r.flag_reason,
                "বিকল্প": r.explanation,
            })

    # ------------------------------------------------------
    def _to_kg_entitlement(self, ent) -> float:
        """প্রাপ্যতা শীটের পরিমাণ কেজিতে (একক কেজি/মে.টন হইলে)"""
        u = (ent.unit or "").upper()
        q = ent.entitled_quantity or 0.0
        if u in ("KG", "KGS"):
            return q
        if u in ("MT", "M/TON", "TON"):
            return q * KG_PER_MT
        return 0.0

    def _to_kg_opening(self, ent) -> float:
        u = (ent.unit or "").upper()
        q = ent.opening_stock or 0.0
        if u in ("KG", "KGS"):
            return q
        if u in ("MT", "M/TON", "TON"):
            return q * KG_PER_MT
        return 0.0

    # ------------------------------------------------------
    def _build_ledger_events(self, import_groups, local_groups) -> list:
        """
        খতিয়ানের ঘটনাবলি প্রস্তুত করো।

        অগ্রাধিকার: বন্ড রেজিস্টার (তফসিল-১) হইতে প্রাপ্ত ঘটনা;
        না থাকিলে আমদানি ও স্থানীয় ক্রয়ের সারি হইতে (কেবল প্রবেশ)।
        """
        if self.ledger_events:
            return list(self.ledger_events)

        events = []
        seen = set()
        for grp in (import_groups, local_groups):
            for rows in grp.values():
                for r in rows:
                    key = (r.bill_number, r.row_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    kg = r.qty_kg
                    if not kg or kg <= 0 or not r.bill_date:
                        continue
                    events.append(LedgerEvent(
                        event_date=r.bill_date, kind="into_bond",
                        hs_code=r.hs_code or "", item_name=r.item_name or "",
                        qty_kg=float(kg), reference=r.bill_number,
                        row_number=r.row_id, source_row=r,
                    ))
        return events

    # ------------------------------------------------------
    def _assess_breaches(self, ledger, cap, result: ImportAnalysisResult):
        """প্রতিটি লঙ্ঘন-ঘটনার শুল্কায়ন করিয়া রেকর্ড তৈরি করো"""
        for ba in ledger.assessments:
            tb = TaxBreakdown()
            details = []
            src_vat = 0.0

            for al in ba.allocations:
                row = al.get("source_row")
                prop = al.get("proportion") or 0.0
                if row is not None and prop > 0:
                    part = assess_bill(row, prop)
                    tb = tb + part
                    if getattr(row, "source_type", "") == "local_purchase":
                        src_vat += part.vat
                details.append(
                    f"{al['reference']} ({al['date']}) — বিলের "
                    f"{al['bill_qty_kg']:,.0f} কেজির মধ্যে "
                    f"{al['assessed_kg']:,.0f} কেজি ({prop*100:.2f}%)"
                )
            tb.round_all()

            result.capacity_breach_records.append(CapacityBreachRecord(
                serial=ba.seq,
                breach_date=ba.breach_date.strftime("%d.%m.%Y"),
                trigger_bill=ba.trigger_reference,
                balance_kg=ba.balance_kg,
                capacity_kg=ba.capacity_kg,
                gross_excess_kg=ba.gross_excess_kg,
                shielded_kg=ba.shielded_kg,
                assessable_kg=ba.assessable_kg,
                allocation_detail="; ".join(details),
                assessable_value_bdt=tb.assessable_value,
                cd_demanded=tb.cd, rd_demanded=tb.rd, sd_demanded=tb.sd,
                vat_demanded=tb.vat, at_demanded=tb.at, ait_demanded=tb.ait,
                source_vat_demanded=round(src_vat, 2),
                total_revenue_impact=tb.total,
                assessment_basis=tb.basis or "প্রযোজ্য নয়",
                capacity_formula=cap.formula,
                capacity_regime=cap.regime,
                legal_basis=cap.legal_basis,
                bank_guarantee_note=BANK_GUARANTEE_NOTE,
                remarks=ba.remarks,
            ))

    # ------------------------------------------------------
    def _add_limit_record(self, ent, chk, rows: list, result):
        """★ বিধি ১১(১) লঙ্ঘন — শুল্কায়নসহ দাবিনামা রেকর্ড তৈরি"""
        serial = len(result.capacity_limit_records) + 1

        # সীমার অতিরিক্ত প্রকৃত অংশে শুল্কায়ন
        if chk.assessable_excess > 0 and rows:
            tb = assess_excess(
                rows, limit=chk.limit_applied, opening_stock=ent.opening_stock or 0.0
            )
            excess_bills = "; ".join(
                f"{d.get('বিল নং') or d.get('চালান নং')} "
                f"({d['আপত্তিকৃত পরিমাণ']:,.0f} {d['একক']})"
                for d in tb.bill_details
            )
        else:
            tb = TaxBreakdown()
            excess_bills = ""

        result.capacity_limit_records.append(CapacityLimitRecord(
            serial=serial,
            hs_code=", ".join(ent.all_hs_codes) if ent.is_cluster else (ent.hs_code or ""),
            item_name=ent.display_name,
            unit=ent.unit,
            capacity_100=round(chk.capacity_100, 3),
            limit_80=round(chk.limit_applied, 3),
            entitled_quantity=round(chk.entitled_quantity, 3),
            opening_stock=round(chk.opening_stock, 3),
            entitlement_plus_opening=round(chk.combined, 3),
            excess_over_limit=round(chk.excess_over_limit, 3),
            excess_pct=round(chk.excess_pct, 2),
            actual_entry=round(chk.actual_held - chk.opening_stock, 3),
            actual_held=round(chk.actual_held, 3),
            assessable_excess=round(chk.assessable_excess, 3),
            bill_count=len(rows),
            bill_numbers=", ".join(r.bill_number for r in rows),
            excess_bills=excess_bills,
            assessable_value_bdt=tb.assessable_value,
            cd_demanded=tb.cd, rd_demanded=tb.rd, sd_demanded=tb.sd,
            vat_demanded=tb.vat, at_demanded=tb.at, ait_demanded=tb.ait,
            total_revenue_impact=tb.total,
            assessment_basis=tb.basis or "প্রযোজ্য নয়",
            legal_basis=chk.legal_basis,
            demand_proposal=chk.demand_proposal,
            remarks=chk.remarks + " " + tb.calculation_note,
        ))
        result.warnings.append(f"⛔ বিধি ১১(১) লঙ্ঘন — {chk.remarks}")

    # ------------------------------------------------------
    def _check_capacity_by_value(
        self, events: list[tuple[date, float, str]], result: ImportAnalysisResult
    ):
        """সামগ্রিক মূল্যভিত্তিক এককালীন বন্ডিং ক্যাপাসিটি যাচাই"""
        cap_bdt = self.bonding_capacity_value_bdt
        cap_usd = self.bonding_capacity_value_usd

        rec = result.bonding_value
        rec.capacity_value_bdt = cap_bdt
        rec.capacity_value_usd = cap_usd
        rec.calculation_basis = (
            "প্রারম্ভিক মজুতের মূল্য (বিগত নিরীক্ষার সমাপনী মজুত) "
            "+ নিরীক্ষাধীন মেয়াদে সকল প্রবেশের মূল্য"
        )

        if cap_bdt <= 0:
            rec.status = "প্রযোজ্য নয়"
            rec.remarks = (
                "প্রাপ্যতা শীটে মূল্যভিত্তিক এককালীন বন্ডিং ক্যাপাসিটি "
                "উল্লেখ পাওয়া যায়নি; আইটেমভিত্তিক যাচাই প্রযোজ্য।"
            )
            return

        opening_val = sum(
            (e.opening_stock or 0) * (e.unit_price or 0) for e in self.entitlements
        )
        # আনুমানিক টাকায় রূপান্তর — গড় বিনিময় হার
        rates = [r.exchange_rate for r in self.imports if r.exchange_rate]
        avg_rate = float(np.mean(rates)) if rates else 0.0
        opening_val_bdt = opening_val * avg_rate

        # ধারণকৃত মূল্য = প্রারম্ভিক মজুতের মূল্য + মেয়াদে সকল প্রবেশের মূল্য
        peak = opening_val_bdt + sum(v for _, v, _ in events)
        running, peak_date, peak_bill = opening_val_bdt, "প্রারম্ভিক", "—"
        for d, val, bill in sorted(events, key=lambda x: x[0]):
            running += val
            peak_date, peak_bill = d.strftime("%d.%m.%Y"), bill
            if running > cap_bdt and rec.breach_bill == "":
                rec.breach_date, rec.breach_bill = peak_date, bill

        excess = max(0.0, peak - cap_bdt)
        rec.opening_stock_value_bdt = round(opening_val_bdt, 2)
        rec.total_entry_value_bdt = round(sum(v for _, v, _ in events), 2)
        rec.held_value_bdt = round(peak, 2)
        rec.peak_date = peak_date
        rec.peak_bill = peak_bill
        rec.excess_value_bdt = round(excess, 2)
        rec.excess_pct = round(excess / cap_bdt * 100, 2) if cap_bdt else 0.0
        rec.status = "সীমা অতিক্রম" if excess > 0 else "সীমার মধ্যে"

        if excess > 0:
            rec.remarks = (
                f"এককালীন বন্ডিং ক্যাপাসিটি ৳{cap_bdt:,.0f} হলেও "
                f"ধারণকৃত মজুতের মূল্য দাঁড়ায় ৳{peak:,.0f} — "
                f"৳{excess:,.0f} ({rec.excess_pct:.1f}%) অতিরিক্ত। "
                f"ইহা বন্ড লাইসেন্সের শর্ত লঙ্ঘন হিসেবে অডিট আপত্তিযোগ্য।"
            )
        else:
            rec.remarks = (
                f"ধারণকৃত মজুতের মূল্য ৳{peak:,.0f} — "
                f"ক্যাপাসিটি ৳{cap_bdt:,.0f} এর মধ্যে সীমাবদ্ধ।"
            )

    # ------------------------------------------------------
    def _build_summary(self, result: ImportAnalysisResult):
        """সারসংক্ষেপ পরিসংখ্যান"""
        ex = result.excess_records
        un = result.unauthorized_records
        pp = result.post_period_records
        ut = result.utilization_records
        cx = result.cluster_excess_records
        cl = result.capacity_limit_records
        mc = result.machinery_records
        bc = result.bonding_records
        cb = result.capacity_breach_records
        breaches = cb

        result.summary = {
            "মিলকরণ মোড": "কঠোর (নাম + এইচএস)" if self.strict_hs else "শিথিল (ক্লাস্টারসহ)",
            "প্রাপ্যতা আইটেম সংখ্যা": len(self.entitlements),
            "আমদানি সারি সংখ্যা": len(self.imports),
            "স্থানীয় ক্রয় সারি": len(self.local_purchases),
            "মিলকৃত সারি": len(self.imports) - len(result.unmatched_imports) - len(mc),
            "মিলবিহীন সারি": len(result.unmatched_imports),

            "অতিরিক্ত আমদানি আইটেম": len(ex),
            "ক্লাস্টারভিত্তিক অতিরিক্ত": len(cx),
            "অতিরিক্ত আমদানির মূল্য (USD)": round(sum(r.excess_value_usd for r in ex), 2),
            "অতিরিক্ত আমদানির মূল্য (BDT)": round(sum(r.excess_value_bdt for r in ex), 2),
            "অতিরিক্ত আমদানিজনিত রাজস্ব (BDT)": round(
                sum(r.total_revenue_impact for r in ex), 2
            ),

            "অননুমোদিত এইচএস কোড সংখ্যা": len(un),
            "অননুমোদিত আমদানির মূল্য (USD)": round(sum(r.total_value_usd for r in un), 2),
            "অননুমোদিত আমদানির মূল্য (BDT)": round(sum(r.total_value_bdt for r in un), 2),
            "অননুমোদিত আমদানিজনিত দাবি (BDT)": round(
                sum(r.total_revenue_impact for r in un), 2
            ),

            "মেশিনারিজ আইটেম (আপত্তির বাইরে)": len(mc),
            "মেশিনারিজ আমদানির মূল্য (USD)": round(sum(r.total_value_usd for r in mc), 2),


            "ক্যাপাসিটি লঙ্ঘনকারী আইটেম": len(breaches),
            "বিধি ১১(১) লঙ্ঘনকারী আইটেম": len(cl),
            "ক্যাপাসিটি লঙ্ঘনজনিত দাবি (BDT)": round(
                sum(r.total_revenue_impact for r in breaches), 2
            ),
            "মূল্যভিত্তিক ক্যাপাসিটি অবস্থা": result.bonding_value.status,
            "কনজাম্পশন রেজিস্টার (তফসিল-১)": (
                "পাওয়া গিয়াছে" if self.register.can_check_capacity
                else ("নিরীক্ষক এড়াইয়া গিয়াছেন" if self.register.skipped
                      else "পাওয়া যায় নাই")
            ),

            "সম্পূর্ণ ব্যবহৃত আইটেম": sum(1 for r in ut if r.status == "সম্পূর্ণ ব্যবহৃত"),
            "আংশিক ব্যবহৃত আইটেম": sum(1 for r in ut if r.status == "আংশিক ব্যবহৃত"),
            "অব্যবহৃত আইটেম": sum(1 for r in ut if r.status == "অব্যবহৃত"),

            "যাচাই প্রয়োজন (কম আস্থা)": len(result.low_confidence_matches),

            # ★ তিনটি পৃথক দাবি
            "দাবি ১ — অননুমোদিত এইচএস কোড (BDT)": round(
                sum(r.total_revenue_impact for r in un), 2
            ),
            "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)": round(
                sum(r.total_revenue_impact for r in ex)
                + sum(r.total_revenue_impact for r in cx), 2
            ),
            "দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত (BDT)": round(
                sum(r.total_revenue_impact for r in cb), 2
            ),
            "ক্যাপাসিটি লঙ্ঘন-ঘটনা সংখ্যা": len(cb),
            "মোট শুল্কায়নযোগ্য অতিরিক্ত (কেজি)": round(
                sum(r.assessable_kg for r in cb), 3
            ),
            "দাবি ৪ — উৎপাদন ক্ষমতার ৮০% সীমা লঙ্ঘন [বিধি ১১(১)] (BDT)": round(
                sum(r.total_revenue_impact for r in cl), 2
            ),
            "দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি (BDT)": round(
                sum(r.total_revenue_impact for r in pp), 2
            ),
            "মেয়াদোত্তর দাবি-রেকর্ড সংখ্যা": len(pp),
            "বিধি ৮ বর্ধিত-প্রাপ্যতা পর্যবেক্ষণ (দাবি নহে)": len(result.rule8_observations),
            "সর্বমোট রাজস্ব দাবি (BDT)": round(
                sum(r.total_revenue_impact for r in un)
                + sum(r.total_revenue_impact for r in ex)
                + sum(r.total_revenue_impact for r in cx)
                + sum(r.total_revenue_impact for r in breaches)
                + sum(r.total_revenue_impact for r in cl)
                + sum(r.total_revenue_impact for r in pp), 2
            ),
            "ইহার মধ্যে উৎসে মূসক (স্থানীয় ক্রয়) (BDT)": round(
                sum(r.source_vat_demanded for r in cx), 2
            ),
        }


__all__ = [
    "ImportAnalysisEngine", "ImportAnalysisResult",
    "EntitlementRow", "ImportRow",
    "ExcessRecord", "UnauthorizedRecord", "UtilizationRecord",
    "PostPeriodRecord", "Rule8Observation",
    "TOLERANCE",
]
