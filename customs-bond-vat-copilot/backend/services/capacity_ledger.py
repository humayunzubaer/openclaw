"""
Capacity Ledger — সময়ানুক্রমিক মজুত খতিয়ান ও এককালীন বন্ডিং ক্যাপাসিটি
==========================================================================

★ এককালীন বন্ডিং ক্যাপাসিটির সঠিক সূত্র (আইনানুযায়ী):

    এসআরও ২০৯/২০২৪ — বিধি ৭(৩) এবং এসআরও ২১৪/২০২৪ — বিধি ১৫:

        এককালীন বন্ডিং ক্যাপাসিটি
            = min( প্রাপ্যতা ÷ ৩ , ওয়্যারহাউসের ধারণক্ষমতা )

    যেখানে —
        প্রাপ্যতা = প্রাপ্যতা শীটে প্রদত্ত পরিমাণ (মজুত বাদে) + প্রারম্ভিক মজুত
                    উদাহরণ: ৯০ + ১০ = ১০০ মে.টন → ক্যাপাসিটি = min(৩৩.৩৩, ধারণক্ষমতা)

        ধারণক্ষমতা = [{(আয়তন − আয়তনের ১০%) ÷ ১৩৬০} × ১২] মে.টন
                     [এসআরও ২০৯/২০২৪ — বিধি ৭(২)]

    ★ ০১.০৭.২০২৬ হইতে সংশোধিত নিয়ম:
        এককালীন বন্ডিং ক্যাপাসিটি = ওয়্যারহাউসের ধারণক্ষমতা

★ যাচাই সামগ্রিক — আইটেমভিত্তিক নহে:

    "কোনো সময়েই ওয়্যারহাউসে এককালীন মজুদ কাঁচামালের পরিমাণ..."
    [এসআরও ২১৪/২০২৪ — বিধি ১৫]

    অর্থাৎ সকল কাঁচামালের সমষ্টি (কেজি/মে.টনে) যেকোনো মুহূর্তে
    ক্যাপাসিটি অতিক্রম করিতে পারিবে না।
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Any

import numpy as np
import pandas as pd

from engines.excel_engine import ExcelEngine, clean_number, clean_hs_code
from utils.logger import logger


# ==========================================================
# ধ্রুবক
# ==========================================================

KG_PER_MT = 1000.0
CONTAINER_VOLUME_CFT = 1360.0     # ২০ ফুট কন্টেইনারের আয়তন (ঘনফুট)
CONTAINER_CAPACITY_MT = 12.0      # ২০ ফুট কন্টেইনারের ধারণক্ষমতা (মে.টন)
CIRCULATION_DEDUCTION = 0.10      # লোক চলাচল ও ওঠানো-নামানোর জন্য ১০%

ENTITLEMENT_DIVISOR = 3.0         # প্রাপ্যতার এক-তৃতীয়াংশ


# ==========================================================
# ওয়্যারহাউসের ধারণক্ষমতা নির্ণয়
# ==========================================================

@dataclass
class WarehouseCapacity:
    """ওয়্যারহাউসের ধারণক্ষমতা — এসআরও ২০৯/২০২৪, বিধি ৭(১)–(২)"""
    length_ft: float = 0.0
    width_ft: float = 0.0
    height_ft: float = 0.0
    volume_cft: float = 0.0
    usable_cft: float = 0.0
    capacity_mt: float = 0.0
    bond_license_mt: float = 0.0  # ★ বন্ড লাইসেন্সে উল্লিখিত ধারণক্ষমতা (যদি থাকে)
    source: str = ""              # bond_license | measured | given | missing
    formula: str = ""
    legal_basis: str = (
        "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ "
        "[এসআরও ২০৯-আইন/২০২৪] — বিধি ৭(১) ও ৭(২)"
    )

    @property
    def capacity_kg(self) -> float:
        return self.capacity_mt * KG_PER_MT


def compute_warehouse_capacity(
    length_ft: float = 0.0,
    width_ft: float = 0.0,
    height_ft: float = 0.0,
    volume_cft: float = 0.0,
    given_capacity_mt: float = 0.0,
    bond_license_capacity_mt: float = 0.0,
) -> WarehouseCapacity:
    """
    ওয়্যারহাউসের ধারণক্ষমতা নির্ণয় করো।

    উৎস (অগ্রাধিকার-ক্রম):
      ১) ★ বন্ড লাইসেন্সে উল্লিখিত অনুমোদিত ধারণক্ষমতা — অফিশিয়াল, তাই
         মাপ/প্রদত্ত মান থাকিলেও ইহাই চূড়ান্ত (নিরীক্ষক নির্দেশ; Case-B
         নমুনায় ৩,৪০০ মে.টন এভাবেই গৃহীত)।
      ২) সরাসরি প্রদত্ত ধারণক্ষমতা (মাপ না থাকিলে)।
      ৩) ওয়্যারহাউসের মাপ হইতে গণনা:
         [{(আয়তন − আয়তনের ১০%) ÷ ১৩৬০} × ১২] মেট্রিক টন।

    একাধিক উৎস ভিন্ন মান দিলে সতর্কতা যুক্ত হয় — নিরীক্ষক যাচাই করিবেন।
    """
    wc = WarehouseCapacity(
        length_ft=length_ft, width_ft=width_ft, height_ft=height_ft,
        bond_license_mt=bond_license_capacity_mt,
    )

    # আয়তন ও পরিমাপকৃত ধারণক্ষমতা (মাপ থাকিলে) — চূড়ান্ত বা ক্রস-চেক উভয়ে ব্যবহৃত
    if volume_cft > 0:
        wc.volume_cft = volume_cft
    elif length_ft and width_ft and height_ft:
        wc.volume_cft = length_ft * width_ft * height_ft

    measured_mt = 0.0
    if wc.volume_cft > 0:
        wc.usable_cft = wc.volume_cft * (1 - CIRCULATION_DEDUCTION)
        measured_mt = (wc.usable_cft / CONTAINER_VOLUME_CFT) * CONTAINER_CAPACITY_MT

    def _crosscheck(chosen_mt: float) -> str:
        others = []
        if measured_mt > 0 and abs(measured_mt - chosen_mt) > max(0.5, chosen_mt * 0.02):
            others.append(f"পরিমাপকৃত {measured_mt:,.3f}")
        if given_capacity_mt > 0 and abs(given_capacity_mt - chosen_mt) > max(0.5, chosen_mt * 0.02):
            others.append(f"প্রদত্ত {given_capacity_mt:,.3f}")
        if others:
            return " | ⚠ ভিন্ন মান বিদ্যমান: " + ", ".join(others) + " মে.টন — যাচাই আবশ্যক"
        return ""

    # ===== অগ্রাধিকার ১ — বন্ড লাইসেন্স =====
    if bond_license_capacity_mt > 0:
        wc.capacity_mt = bond_license_capacity_mt
        wc.source = "bond_license"
        wc.formula = (
            f"বন্ড লাইসেন্সে উল্লিখিত অনুমোদিত ধারণক্ষমতা "
            f"= {bond_license_capacity_mt:,.3f} মে.টন"
            + _crosscheck(bond_license_capacity_mt)
        )
        return wc

    # ===== অগ্রাধিকার ২ — সরাসরি প্রদত্ত (মাপ না থাকিলে) =====
    if given_capacity_mt > 0 and measured_mt <= 0:
        wc.capacity_mt = given_capacity_mt
        wc.source = "given"
        wc.formula = f"প্রদত্ত ধারণক্ষমতা {given_capacity_mt:,.3f} মে.টন"
        return wc

    # ===== অগ্রাধিকার ৩ — ওয়্যারহাউসের মাপ হইতে গণনা =====
    if measured_mt > 0:
        wc.capacity_mt = measured_mt
        wc.source = "measured"
        wc.formula = (
            f"[{{({wc.volume_cft:,.0f} − {wc.volume_cft:,.0f}×১০%) "
            f"÷ {CONTAINER_VOLUME_CFT:,.0f}}} × {CONTAINER_CAPACITY_MT:g}] "
            f"= {wc.capacity_mt:,.3f} মে.টন"
        )
        if given_capacity_mt > 0:
            diff = wc.capacity_mt - given_capacity_mt
            if abs(diff) > max(0.5, wc.capacity_mt * 0.02):
                wc.formula += (
                    f" | ⚠ প্রদত্ত মান {given_capacity_mt:,.3f} মে.টন — "
                    f"পার্থক্য {diff:+,.3f} মে.টন, যাচাই আবশ্যক"
                )
        return wc

    # ===== কিছুই পাওয়া যায় নাই =====
    wc.source = "missing"
    wc.formula = (
        "ওয়্যারহাউসের মাপ, প্রদত্ত ধারণক্ষমতা বা বন্ড লাইসেন্সের ধারণক্ষমতা "
        "— কোনোটিই পাওয়া যায় নাই"
    )
    return wc


# ==========================================================
# এককালীন বন্ডিং ক্যাপাসিটি নির্ণয়
# ==========================================================

@dataclass
class OneTimeBondingCapacity:
    """সামগ্রিক এককালীন বন্ডিং ক্যাপাসিটি — কেজিতে"""
    entitlement_sheet_kg: float = 0.0     # শীটে প্রদত্ত (মজুত বাদে)
    opening_stock_kg: float = 0.0         # প্রারম্ভিক মজুত
    total_entitlement_kg: float = 0.0     # প্রকৃত প্রাপ্যতা = শীট + মজুত
    one_third_kg: float = 0.0             # প্রাপ্যতা ÷ ৩

    warehouse_capacity_kg: float = 0.0
    capacity_kg: float = 0.0              # চূড়ান্ত ক্যাপাসিটি
    binding_constraint: str = ""          # কোনটি কম হইল
    regime: str = "old"                   # old | new
    formula: str = ""
    legal_basis: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def capacity_mt(self) -> float:
        return self.capacity_kg / KG_PER_MT


def compute_one_time_capacity(
    entitlement_sheet_kg: float,
    opening_stock_kg: float,
    warehouse_capacity_kg: float,
    regime: str = "old",
) -> OneTimeBondingCapacity:
    """
    সামগ্রিক এককালীন বন্ডিং ক্যাপাসিটি নির্ণয়।

    পুরাতন নিয়ম : min( (শীটের প্রাপ্যতা + প্রারম্ভিক মজুত) ÷ ৩ , ধারণক্ষমতা )
    নূতন নিয়ম   : ধারণক্ষমতা          [০১.০৭.২০২৬ হইতে]
    """
    c = OneTimeBondingCapacity(
        entitlement_sheet_kg=entitlement_sheet_kg,
        opening_stock_kg=opening_stock_kg,
        total_entitlement_kg=entitlement_sheet_kg + opening_stock_kg,
        warehouse_capacity_kg=warehouse_capacity_kg,
        regime=regime,
    )
    c.one_third_kg = c.total_entitlement_kg / ENTITLEMENT_DIVISOR

    # ===== নূতন নিয়ম =====
    if regime == "new":
        c.capacity_kg = warehouse_capacity_kg
        c.binding_constraint = "ওয়্যারহাউসের ধারণক্ষমতা"
        c.legal_basis = (
            "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ (সংশোধিত, "
            "০১.০৭.২০২৬ হইতে কার্যকর) — এককালীন বন্ডিং ক্যাপাসিটি "
            "= ওয়্যারহাউসের ধারণক্ষমতা"
        )
        c.formula = (
            f"ওয়্যারহাউসের ধারণক্ষমতা = {warehouse_capacity_kg:,.0f} কেজি "
            f"({warehouse_capacity_kg/KG_PER_MT:,.3f} মে.টন)"
        )
        if warehouse_capacity_kg <= 0:
            c.notes.append(
                "⚠ ওয়্যারহাউসের ধারণক্ষমতা পাওয়া যায় নাই — "
                "নূতন নিয়মে ক্যাপাসিটি নির্ণয় সম্ভব হয় নাই।"
            )
        return c

    # ===== পুরাতন নিয়ম =====
    c.legal_basis = (
        "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ [এসআরও ২০৯-আইন/২০২৪] — "
        "বিধি ৭(৩) সহপঠিত বার্ষিক আমদানি প্রাপ্যতা নির্ধারণ বিধিমালা, ২০২৪ "
        "[এসআরও ২১৪-আইন/২০২৪] — বিধি ১৫ "
        "[\"নির্ধারিত বার্ষিক আমদানি-প্রাপ্যতার এক তৃতীয়াংশ অথবা গুদামের "
        "অনুমোদিত ধারণ ক্ষমতা এই দুই এর মধ্যে যাহা কম\"]"
    )

    candidates: list[tuple[float, str]] = []
    if c.one_third_kg > 0:
        candidates.append((c.one_third_kg, "প্রাপ্যতার এক-তৃতীয়াংশ"))
    if warehouse_capacity_kg > 0:
        candidates.append((warehouse_capacity_kg, "ওয়্যারহাউসের ধারণক্ষমতা"))

    if not candidates:
        c.notes.append(
            "⚠ প্রাপ্যতা ও ধারণক্ষমতা কোনোটিই পাওয়া যায় নাই — "
            "ক্যাপাসিটি নির্ণয় সম্ভব হয় নাই।"
        )
        return c

    c.capacity_kg, c.binding_constraint = min(candidates, key=lambda x: x[0])

    c.formula = (
        f"প্রাপ্যতা = শীটে প্রদত্ত {entitlement_sheet_kg:,.0f} "
        f"+ প্রারম্ভিক মজুত {opening_stock_kg:,.0f} "
        f"= {c.total_entitlement_kg:,.0f} কেজি; "
        f"এক-তৃতীয়াংশ = {c.one_third_kg:,.0f} কেজি; "
        f"ধারণক্ষমতা = {warehouse_capacity_kg:,.0f} কেজি; "
        f"min → {c.capacity_kg:,.0f} কেজি ({c.capacity_mt:,.3f} মে.টন) "
        f"[নির্ধারক: {c.binding_constraint}]"
    )

    if warehouse_capacity_kg <= 0:
        c.notes.append(
            "⚠ ওয়্যারহাউসের ধারণক্ষমতা পাওয়া যায় নাই; কেবল প্রাপ্যতার "
            "এক-তৃতীয়াংশ বিবেচনা করা হইয়াছে। ধারণক্ষমতা ইহার চেয়ে কম "
            "হইলে প্রকৃত ক্যাপাসিটি আরও কম হইবে।"
        )
    return c


# ==========================================================
# বন্ড রেজিস্টার হইতে সময়ানুক্রমিক খতিয়ান
# ==========================================================

@dataclass
class LedgerEvent:
    """
    খতিয়ানের একটি ঘটনা — প্রবেশ বা উত্তোলন।

    ★ তফসিল-১ এ প্রতিটি সারিতে একই সঙ্গে ইন্টু-বন্ড (কলাম ১১) ও
      এক্স-বন্ড (কলাম ১৩–১৪) লিপিবদ্ধ থাকে। ফলে কোন প্রবেশ হইতে
      কী পরিমাণ উত্তোলন হইল তাহা রেজিস্টারেই সংযুক্ত — ইঞ্জিনকে
      FIFO/LIFO অনুমান করিতে হয় না।
    """
    event_date: date
    kind: str                  # into_bond | ex_bond
    hs_code: str = ""
    item_name: str = ""
    qty_kg: float = 0.0
    reference: str = ""        # বিল অব এন্ট্রি / চালান
    row_number: int = 0        # ★ রেজিস্টারের সারি নম্বর — সংযোগসূত্র
    source_row: Any = None     # সংশ্লিষ্ট ImportRow — শুল্কায়নের জন্য
    # ★ তফসিল-১ কলাম ৩ — কাস্টম হাউস হইতে ছাড়করণের (ASYCUDA Exit Note) তারিখ।
    #   ইন্টু-বন্ড ঘটনায় প্রযোজ্য; বিধি ৮ এর বিলম্ব-যাচাইয়ে ব্যবহৃত।
    release_date: Optional[date] = None


@dataclass
class LedgerPoint:
    """খতিয়ানের একটি বিন্দু — কোনো তারিখের স্থিতি"""
    point_date: date
    into_bond_kg: float
    ex_bond_kg: float
    balance_kg: float
    reference: str
    exceeds: bool = False
    excess_kg: float = 0.0


@dataclass
class BreachAssessment:
    """
    ★ একটি লঙ্ঘন-ঘটনার শুল্কায়নযোগ্য অংশ

    নীতি (ব্যবহারকারী কর্তৃক নির্ধারিত):
      • যে বিলসমূহ সীমা ছাড়াইতে ভূমিকা রাখিয়াছে সেগুলির অতিরিক্ত অংশে শুল্কায়ন
      • বৎসরে যতবার লঙ্ঘন হইবে ততবারই শুল্কায়ন
      • তবে যে পরিমাণের উপর একবার শুল্কায়ন হইয়াছে, সেই পরিমাণের উপর
        পুনরায় শুল্কায়ন করা যাইবে না (যতক্ষণ উহা ওয়্যারহাউসে বিদ্যমান)
    """
    seq: int
    breach_date: date
    trigger_reference: str
    balance_kg: float
    capacity_kg: float
    gross_excess_kg: float         # মোট অতিরিক্ত
    shielded_kg: float             # পূর্বে শুল্কায়িত ও এখনও মজুত
    assessable_kg: float           # এইবার নূতন শুল্কায়নযোগ্য
    allocations: list[dict] = field(default_factory=list)
    remarks: str = ""


def allocate_breach_assessments(
    events: list[LedgerEvent],
    opening_kg: float,
    capacity_kg: float,
) -> list[BreachAssessment]:
    """
    ★ সময়ানুক্রমে হাঁটিয়া প্রতিটি লঙ্ঘনের শুল্কায়নযোগ্য অংশ নির্ণয় করো।

    ঢাল (shield) ব্যবস্থা:
        পূর্বে শুল্কায়িত পরিমাণ যতক্ষণ ওয়্যারহাউসে বিদ্যমান, ততক্ষণ উহা
        পুনঃশুল্কায়ন হইতে সুরক্ষিত। উত্তোলনের ফলে মজুত সীমার নিচে নামিলে
        ঢালও হ্রাস পায় — তখন নূতন প্রবেশে পুনরায় শুল্কায়ন প্রযোজ্য।
    """
    ordered = sorted(events, key=lambda e: (e.event_date, e.kind == "ex_bond"))

    balance = opening_kg
    shield = max(0.0, opening_kg - capacity_kg)
    out: list[BreachAssessment] = []

    # ওয়্যারহাউসে বিদ্যমান প্রবেশসমূহ — রেজিস্টারের সারি নম্বর দিয়া সূচিত
    stack: list[dict] = []
    by_row: dict[int, dict] = {}

    if opening_kg > 0:
        entry = {
            "reference": "প্রারম্ভিক জের", "remaining": opening_kg,
            "original": opening_kg, "event": None, "row": 0,
        }
        stack.append(entry)
        by_row[0] = entry

    for ev in ordered:
        if ev.kind == "into_bond":
            balance += ev.qty_kg
            entry = {
                "reference": ev.reference, "remaining": ev.qty_kg,
                "original": ev.qty_kg, "event": ev, "row": ev.row_number,
            }
            stack.append(entry)
            if ev.row_number:
                by_row[ev.row_number] = entry

            excess = balance - capacity_kg
            if excess <= 0:
                shield = 0.0
                continue

            assessable = excess - shield
            if assessable <= 0.001:
                continue    # সম্পূর্ণ অতিরিক্ত পূর্বেই শুল্কায়িত

            # --- দায়ারোপ: যে বিল সীমা ছাড়াইল সে-ই প্রথম দায়ী ---
            need = assessable
            allocations: list[dict] = []
            for e in reversed(stack):
                if need <= 0.001:
                    break
                if e["remaining"] <= 0:
                    continue
                take = min(e["remaining"], need)
                need -= take
                src = e["event"]
                allocations.append({
                    "reference": e["reference"],
                    "date": src.event_date.strftime("%d.%m.%Y") if src else "—",
                    "bill_qty_kg": round(e["original"], 3),
                    "assessed_kg": round(take, 3),
                    "proportion": (
                        round(take / e["original"], 6) if e["original"] else 0.0
                    ),
                    "hs_code": src.hs_code if src else "",
                    "item_name": src.item_name if src else "",
                    "source_row": getattr(src, "source_row", None) if src else None,
                })

            bill_list = ", ".join(
                f"{a['reference']} ({a['assessed_kg']:,.0f} কেজি)"
                for a in allocations
            )
            out.append(BreachAssessment(
                seq=len(out) + 1,
                breach_date=ev.event_date,
                trigger_reference=ev.reference,
                balance_kg=round(balance, 3),
                capacity_kg=round(capacity_kg, 3),
                gross_excess_kg=round(excess, 3),
                shielded_kg=round(shield, 3),
                assessable_kg=round(assessable, 3),
                allocations=allocations,
                remarks=(
                    f"{ev.event_date.strftime('%d.%m.%Y')} তারিখে বিল "
                    f"{ev.reference} ইন্টু-বন্ড হইবার পর ওয়্যারহাউসে মজুত "
                    f"{balance:,.0f} কেজি — এককালীন বন্ডিং ক্যাপাসিটি "
                    f"{capacity_kg:,.0f} কেজি অপেক্ষা {excess:,.0f} কেজি অধিক। "
                    + (f"ইহার মধ্যে {shield:,.0f} কেজি পূর্বেই শুল্কায়িত হইয়াছে "
                       f"বিধায় পুনঃশুল্কায়ন হইতে বাদ দেওয়া হইল। "
                       if shield > 0.001 else "")
                    + f"নূতন শুল্কায়নযোগ্য পরিমাণ {assessable:,.0f} কেজি — "
                    f"সংশ্লিষ্ট বিল: {bill_list}।"
                ),
            ))
            shield = excess

        else:  # ex_bond
            balance -= ev.qty_kg
            shield = min(shield, max(0.0, balance - capacity_kg))

            # ★ রেজিস্টারের সারি-সংযোগ অনুযায়ী বিয়োজন —
            #   কোন প্রবেশ হইতে বাহির হইল তাহা তফসিল-১ এ লিপিবদ্ধ থাকে
            linked = by_row.get(ev.row_number)
            need = ev.qty_kg
            if linked is not None and linked["remaining"] > 0:
                take = min(linked["remaining"], need)
                linked["remaining"] -= take
                need -= take

            # সারি-সংযোগে না মিলিলে (রেজিস্টার অসম্পূর্ণ) — একই বিল নম্বর দেখো
            if need > 0.001:
                for e in stack:
                    if need <= 0.001:
                        break
                    if e["remaining"] > 0 and e["reference"] == ev.reference:
                        take = min(e["remaining"], need)
                        e["remaining"] -= take
                        need -= take

            # তবুও অবশিষ্ট থাকিলে প্রবেশক্রমে (রেজিস্টারে স্পষ্ট নহে)
            if need > 0.001:
                for e in stack:
                    if need <= 0.001:
                        break
                    if e["remaining"] > 0:
                        take = min(e["remaining"], need)
                        e["remaining"] -= take
                        need -= take

            stack = [e for e in stack if e["remaining"] > 0.001]

    return out


@dataclass
class CapacityLedgerResult:
    """সময়ানুক্রমিক ক্যাপাসিটি যাচাইয়ের ফলাফল"""
    capacity: OneTimeBondingCapacity = field(
        default_factory=OneTimeBondingCapacity
    )
    warehouse: WarehouseCapacity = field(default_factory=WarehouseCapacity)

    opening_kg: float = 0.0
    total_into_bond_kg: float = 0.0
    total_ex_bond_kg: float = 0.0
    closing_kg: float = 0.0

    peak_balance_kg: float = 0.0
    peak_date: Optional[date] = None
    peak_reference: str = ""

    breach_count: int = 0
    first_breach_date: Optional[date] = None
    first_breach_reference: str = ""
    max_excess_kg: float = 0.0
    max_excess_date: Optional[date] = None

    points: list[LedgerPoint] = field(default_factory=list)
    breach_points: list[LedgerPoint] = field(default_factory=list)
    assessments: list[BreachAssessment] = field(default_factory=list)
    total_assessable_kg: float = 0.0

    status: str = "যাচাই হয় নাই"
    remarks: str = ""
    warnings: list[str] = field(default_factory=list)


def build_capacity_ledger(
    events: list[LedgerEvent],
    opening_kg: float,
    capacity: OneTimeBondingCapacity,
    warehouse: WarehouseCapacity | None = None,
) -> CapacityLedgerResult:
    """
    ★ সময়ানুক্রমিক মজুত খতিয়ান তৈরি করিয়া প্রতিটি মুহূর্তে
      এককালীন বন্ডিং ক্যাপাসিটি যাচাই করো।

    মজুত(t) = প্রারম্ভিক জের + ইন্টু-বন্ড(t পর্যন্ত) − এক্স-বন্ড(t পর্যন্ত)
    """
    res = CapacityLedgerResult(
        capacity=capacity,
        warehouse=warehouse or WarehouseCapacity(),
        opening_kg=opening_kg,
    )

    cap_kg = capacity.capacity_kg
    if cap_kg <= 0:
        res.status = "যাচাই সম্ভব হয় নাই"
        res.remarks = (
            "এককালীন বন্ডিং ক্যাপাসিটি নির্ণয় করা যায় নাই। "
            + " ".join(capacity.notes)
        )
        return res

    ordered = sorted(events, key=lambda e: (e.event_date, e.kind == "ex_bond"))
    balance = opening_kg
    res.peak_balance_kg = balance
    res.peak_date = ordered[0].event_date if ordered else None
    res.peak_reference = "প্রারম্ভিক জের"

    # প্রারম্ভিক জেরই সীমা ছাড়াইলে
    if balance > cap_kg:
        p = LedgerPoint(
            point_date=res.peak_date or date.today(),
            into_bond_kg=0.0, ex_bond_kg=0.0, balance_kg=balance,
            reference="প্রারম্ভিক জের", exceeds=True,
            excess_kg=balance - cap_kg,
        )
        res.points.append(p)
        res.breach_points.append(p)
        res.first_breach_date = p.point_date
        res.first_breach_reference = "প্রারম্ভিক জের"

    for ev in ordered:
        into = ev.qty_kg if ev.kind == "into_bond" else 0.0
        out = ev.qty_kg if ev.kind == "ex_bond" else 0.0
        balance = balance + into - out

        res.total_into_bond_kg += into
        res.total_ex_bond_kg += out

        exceeds = balance > cap_kg
        excess = max(0.0, balance - cap_kg)

        point = LedgerPoint(
            point_date=ev.event_date,
            into_bond_kg=into, ex_bond_kg=out,
            balance_kg=balance, reference=ev.reference,
            exceeds=exceeds, excess_kg=excess,
        )
        res.points.append(point)

        if balance > res.peak_balance_kg:
            res.peak_balance_kg = balance
            res.peak_date = ev.event_date
            res.peak_reference = ev.reference

        if exceeds:
            res.breach_count += 1
            res.breach_points.append(point)
            if res.first_breach_date is None:
                res.first_breach_date = ev.event_date
                res.first_breach_reference = ev.reference
            if excess > res.max_excess_kg:
                res.max_excess_kg = excess
                res.max_excess_date = ev.event_date

    res.closing_kg = balance

    # ★ প্রতিটি লঙ্ঘনের শুল্কায়নযোগ্য অংশ নির্ণয় (দ্বৈত শুল্কায়ন পরিহারসহ)
    res.assessments = allocate_breach_assessments(ordered, opening_kg, cap_kg)
    res.total_assessable_kg = round(
        sum(a.assessable_kg for a in res.assessments), 3
    )

    # --- ফলাফল ---
    if res.breach_count > 0:
        res.status = "সীমা অতিক্রম"
        res.remarks = (
            f"নিরীক্ষাধীন মেয়াদে এককালীন বন্ডিং ক্যাপাসিটি "
            f"{cap_kg:,.0f} কেজি ({capacity.capacity_mt:,.3f} মে.টন) — "
            f"[{capacity.formula}]। "
            f"বন্ড রেজিস্টার (তফসিল-১) অনুযায়ী সময়ানুক্রমিক মজুত খতিয়ান "
            f"বিশ্লেষণে দেখা যায়, {res.breach_count} বার উক্ত সীমা অতিক্রান্ত "
            f"হইয়াছে। সর্বোচ্চ মজুত "
            f"{res.peak_balance_kg:,.0f} কেজি "
            f"({res.peak_balance_kg/KG_PER_MT:,.3f} মে.টন) — "
            f"তারিখ {res.peak_date.strftime('%d.%m.%Y') if res.peak_date else '—'}, "
            f"সূত্র: {res.peak_reference}। প্রথম লঙ্ঘন "
            f"{res.first_breach_date.strftime('%d.%m.%Y') if res.first_breach_date else '—'} "
            f"তারিখে ({res.first_breach_reference})। সর্বাধিক অতিরিক্ত "
            f"{res.max_excess_kg:,.0f} কেজি। "
            f"ইহা এসআরও ২১২-আইন/২০২৪ এর বিধি ৬(১) এর শর্ত "
            f"[\"এককালীন বন্ডিং ক্যাপাসিটির অতিরিক্ত পণ্য আমদানি করা যাইবে না\"] "
            f"এবং এসআরও ২১৪-আইন/২০২৪ এর বিধি ১৫ এর সুস্পষ্ট লঙ্ঘন।"
        )
    else:
        res.status = "সীমার মধ্যে"
        res.remarks = (
            f"সময়ানুক্রমিক মজুত খতিয়ান অনুযায়ী সর্বোচ্চ মজুত "
            f"{res.peak_balance_kg:,.0f} কেজি "
            f"({res.peak_balance_kg/KG_PER_MT:,.3f} মে.টন) — "
            f"এককালীন বন্ডিং ক্যাপাসিটি {cap_kg:,.0f} কেজি এর মধ্যে "
            f"সীমাবদ্ধ। কোনো লঙ্ঘন পাওয়া যায় নাই।"
        )

    return res


# ==========================================================
# তফসিল-১ রেজিস্টার পাঠক
# ==========================================================

class BondRegisterReader:
    """
    তফসিল-১ অনুযায়ী পূরণকৃত বন্ড রেজিস্টার পড়িয়া
    ইন্টু-বন্ড ও এক্স-বন্ড ঘটনাবলি নিষ্কাশন করে।
    """

    # তফসিল-১ এর কলাম শনাক্তকরণের সংকেতশব্দ
    COL_HINTS = {
        "be_no": ["বিল অব এন্ট্রি", "b/e", "be no", "বিই"],
        "hs_code": ["এইচএস", "এইচ.এস", "hs code", "hs"],
        "item_name": ["বাণিজ্যিক বর্ণনা", "পণ্যের", "description"],
        "qty_kg": ["কেজি", "kg", "kilogram"],
        "qty_meter": ["মিটার", "meter", "mtr"],
        "qty_yard": ["গজ", "yard", "yds"],
        "release_date": ["ছাড়করণ", "এক্সিট নোট", "exit note", "ছাড়কর"],
        "into_date": ["ইন্টু বন্ড", "into bond", "ইন্টু-বন্ড"],
        "ex_date": ["এক্স বন্ড", "ex bond", "এক্স-বন্ড", "এি বন্ড"],
        "ex_qty": ["এক্সবন্ডকৃত", "এিবন্ডকৃত", "ex bond qty", "উত্তোলন"],
        "closing": ["সমাপনী মজুদ", "সমাপনী", "closing"],
    }

    def __init__(self, verbose: bool = True):
        self.excel = ExcelEngine(verbose=verbose)
        self.notes: list[str] = []

    # ------------------------------------------------------
    def read(self, file_path: str | Path) -> list[LedgerEvent]:
        """রেজিস্টার পড়িয়া ঘটনাবলি ফেরত দাও"""
        res = self.excel.read(file_path)
        if res.errors:
            raise ValueError("; ".join(res.errors))

        # সবচেয়ে বড় শীট বাছাই (রেজিস্টার সাধারণত মূল শীট)
        best, best_rows = None, -1
        for prof in res.sheets:
            df = res.dataframes.get(prof.sheet_name)
            if df is None:
                continue
            if len(df) > best_rows:
                best, best_rows = prof.sheet_name, len(df)
        if not best:
            raise ValueError("বন্ড রেজিস্টারে পাঠযোগ্য শীট পাওয়া যায় নাই")

        df = self.excel.get_clean_data(res.get_sheet(best))
        # ★ ExcelEngine হেডারকে canonical নামে (bill_date, quantity …) রূপান্তর
        #   করে, ফলে তফসিল-১ এর বাংলা শিরোনাম হারাইয়া যায়। তাই মূল হেডার-পাঠ
        #   অবস্থানসহ পুনরায় লইয়া সেই অনুযায়ী কলাম শনাক্ত করা হয়।
        prof = next((sp for sp in res.sheets if sp.sheet_name == best), None)
        orig = self._original_headers(file_path, prof)
        positions = getattr(prof, "column_positions", None) if prof else None
        cols = self._map_columns(df.columns, orig, positions)
        # ★ "বিল অব এন্ট্রি নম্বর ও তারিখ" কলামটি canonical `bill_date` হইয়া
        #   যাওয়ায় নম্বরের পাঠ্যমান তারিখ-রূপান্তরে হারাইয়া যায়; তাই মূল শীট
        #   হইতে অবস্থান ধরিয়া উহা পুনরুদ্ধার করা হয়।
        raw_sheet = self._raw_sheet(file_path, prof)
        be_pos = (positions or {}).get(cols.get("be_no", ""), None)
        self.notes.append(f"রেজিস্টার শীট: '{best}' | শনাক্তকৃত কলাম: {list(cols.keys())}")

        missing = [k for k in ("qty_kg",) if k not in cols]
        if missing:
            self.notes.append(
                "⚠ কেজি এককে পরিমাণের কলাম শনাক্ত করা যায় নাই — "
                "সামগ্রিক ক্যাপাসিটি যাচাই ব্যাহত হইবে।"
            )

        events: list[LedgerEvent] = []
        for idx, row in df.iterrows():
            hs = clean_hs_code(row.get(cols.get("hs_code", ""), None))
            name = self._s(row.get(cols.get("item_name", ""), None))
            ref = self._s(row.get(cols.get("be_no", ""), None))
            if not ref and raw_sheet is not None and be_pos is not None:
                ref = self._raw_text(raw_sheet, row.get("_raw_row"), be_pos)
            qty_kg = clean_number(row.get(cols.get("qty_kg", ""), None)) or 0.0

            # --- ইন্টু বন্ড ---
            into_date = self._as_date(row.get(cols.get("into_date", ""), None))
            rel_date = self._as_date(row.get(cols.get("release_date", ""), None))
            if into_date and qty_kg > 0:
                events.append(LedgerEvent(
                    event_date=into_date, kind="into_bond",
                    hs_code=hs or "", item_name=name,
                    qty_kg=qty_kg, reference=ref or f"সারি {idx+1}",
                    row_number=int(idx) + 1,
                    release_date=rel_date,
                ))

            # --- এক্স বন্ড ---
            ex_date = self._as_date(row.get(cols.get("ex_date", ""), None))
            ex_qty = clean_number(row.get(cols.get("ex_qty", ""), None)) or 0.0
            if ex_date and ex_qty > 0:
                events.append(LedgerEvent(
                    event_date=ex_date, kind="ex_bond",
                    hs_code=hs or "", item_name=name,
                    qty_kg=ex_qty, reference=ref or f"সারি {idx+1}",
                    row_number=int(idx) + 1,   # ★ একই সারি — প্রবেশের সহিত সংযুক্ত
                ))

        into_n = sum(1 for e in events if e.kind == "into_bond")
        ex_n = len(events) - into_n
        logger.info(
            f"বন্ড রেজিস্টার পড়া হইয়াছে: {into_n} ইন্টু-বন্ড, {ex_n} এক্স-বন্ড"
        )
        if ex_n == 0:
            self.notes.append(
                "⚠ কোনো এক্স-বন্ড (উত্তোলন) তথ্য পাওয়া যায় নাই। "
                "উত্তোলন ব্যতীত মজুত ক্রমবর্ধমান দেখাইবে — যাচাই আবশ্যক।"
            )
        return events

    # ------------------------------------------------------
    def _original_headers(self, file_path, profile) -> dict[int, str]:
        """হেডার-সারির মূল (অ-রূপান্তরিত) পাঠ — কলাম-অবস্থান অনুযায়ী"""
        if profile is None or profile.header_row is None:
            return {}
        try:
            path = str(file_path)
            if path.lower().endswith(".csv"):
                raw = pd.read_csv(path, header=None,
                                  nrows=profile.header_row + 1, dtype=str)
            else:
                raw = pd.read_excel(path, sheet_name=profile.sheet_name,
                                    header=None, nrows=profile.header_row + 1)
        except Exception:  # noqa: BLE001
            return {}
        if profile.header_row >= len(raw):
            return {}
        row = raw.iloc[profile.header_row]
        out: dict[int, str] = {}
        for i, v in enumerate(row):
            txt = "" if v is None else str(v).strip()
            if txt and txt.lower() != "nan":
                out[i] = txt
        return out

    @staticmethod
    def _raw_text(raw_sheet, raw_row, pos) -> str:
        """মূল শীটের একটি ঘর হইতে পাঠ্যমান"""
        try:
            r = int(raw_row)
        except (TypeError, ValueError):
            return ""
        if r < 0 or r >= len(raw_sheet) or pos >= raw_sheet.shape[1]:
            return ""
        v = raw_sheet.iat[r, pos]
        txt = "" if v is None else str(v).strip()
        return "" if txt.lower() in ("nan", "nat") else txt

    def _raw_sheet(self, file_path, profile):
        """হেডার-বিহীন মূল শীট — coercion-পূর্ব পাঠ্যমান উদ্ধারের জন্য"""
        if profile is None:
            return None
        try:
            path = str(file_path)
            if path.lower().endswith(".csv"):
                return pd.read_csv(path, header=None, dtype=object)
            return pd.read_excel(path, sheet_name=profile.sheet_name,
                                 header=None, dtype=object)
        except Exception:  # noqa: BLE001
            return None

    def _map_columns(
        self, columns, orig_by_pos: dict[int, str] | None = None,
        positions: dict[str, int] | None = None,
    ) -> dict[str, str]:
        """
        তফসিল-১ এর কলাম শনাক্ত করো।

        প্রথমে বর্তমান কলাম-নামে মিলকরণ; না মিলিলে হেডারের **মূল পাঠ**
        (অবস্থানসহ) দেখিয়া মিলানো হয় — কারণ ExcelEngine বাংলা শিরোনামকে
        canonical নামে রূপান্তর করিয়া ফেলে।
        """
        out: dict[str, str] = {}
        cols = [str(c) for c in columns]

        def _hit(text: str, hints) -> bool:
            low = text.lower()
            return any(h in low or h in text for h in hints)

        # ধাপ ১ — বর্তমান কলাম-নাম
        for key, hints in self.COL_HINTS.items():
            for col in cols:
                if _hit(col, hints):
                    out.setdefault(key, col)
                    break

        # ধাপ ২ — মূল হেডার-পাঠ (অবস্থান → বর্তমান নাম)
        if orig_by_pos and positions:
            pos_to_name = {v: k for k, v in positions.items()}
            taken = set(out.values())
            for key, hints in self.COL_HINTS.items():
                if key in out:
                    continue
                for pos, text in orig_by_pos.items():
                    if not _hit(text, hints):
                        continue
                    name = pos_to_name.get(pos)
                    if name and name in cols and name not in taken:
                        out[key] = name
                        taken.add(name)
                        break
        return out

    # ------------------------------------------------------
    @staticmethod
    def _as_date(v) -> Optional[date]:
        if v is None:
            return None
        if isinstance(v, pd.Timestamp):
            return v.date()
        if isinstance(v, date):
            return v
        try:
            ts = pd.to_datetime(v, errors="coerce", dayfirst=True)
            return ts.date() if pd.notna(ts) else None
        except Exception:
            return None

    @staticmethod
    def _s(v) -> str:
        if v is None:
            return ""
        if isinstance(v, float) and np.isnan(v):
            return ""
        s = str(v).strip()
        return "" if s.lower() in {"nan", "none", "nat"} else s


__all__ = [
    "KG_PER_MT", "WarehouseCapacity", "compute_warehouse_capacity",
    "OneTimeBondingCapacity", "compute_one_time_capacity",
    "LedgerEvent", "LedgerPoint", "CapacityLedgerResult",
    "build_capacity_ledger", "BondRegisterReader",
    "BreachAssessment", "allocate_breach_assessments",
]
