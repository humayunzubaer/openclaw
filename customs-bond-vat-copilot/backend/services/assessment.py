"""
Assessment Engine — শুল্কায়ন ইঞ্জিন
=====================================

নীতি (ব্যবহারকারী কর্তৃক নির্ধারিত):

  অননুমোদিত এইচ.এস কোডে আমদানি, প্রাপ্যতার অতিরিক্ত আমদানি, অথবা
  বন্ডিং ক্যাপাসিটির অতিরিক্ত মজুত — এই তিন ক্ষেত্রেই সংশ্লিষ্ট
  আমদানির অংশের **বন্ড সুবিধা বাতিল** করে সেই Bill of Entry-তে
  উল্লিখিত (MIS হতে প্রাপ্ত) **সম্পূর্ণ শুল্ক-কর** দাবি করতে হবে।

গণনার ভিত্তি:
  ১) প্রাধান্য — MIS/BE-তে উল্লিখিত প্রকৃত শুল্ক-কর অঙ্ক
  ২) অংশবিশেষ হলে — সেই বিলের অনুপাতে (আপত্তিকৃত পরিমাণ ÷ বিলের পরিমাণ)
  ৩) MIS-এ অঙ্ক না থাকলে — করহার হতে ক্যাসকেড পদ্ধতিতে গণনা

অতিরিক্ত আমদানির ক্ষেত্রে বিল বাছাই:
  বিলগুলো তারিখক্রমে প্রাপ্যতা পূরণ করে; প্রাপ্যতা অতিক্রমের পর যে
  বিলগুলো আসে, সেগুলোর অতিরিক্ত অংশই আপত্তিযোগ্য। ইহা আইনগতভাবে
  সর্বাধিক সমর্থনযোগ্য পদ্ধতি (FIFO)।
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

import numpy as np


# ==========================================================
# ফলাফল কাঠামো
# ==========================================================

@dataclass
class TaxBreakdown:
    """শুল্ক-করের বিভাজন — সব অঙ্ক টাকায়"""
    assessable_value: float = 0.0
    cd: float = 0.0      # Customs Duty
    rd: float = 0.0      # Regulatory Duty
    sd: float = 0.0      # Supplementary Duty
    vat: float = 0.0     # Value Added Tax
    at: float = 0.0      # Advance Tax
    ait: float = 0.0     # Advance Income Tax
    total: float = 0.0

    # ব্যাখ্যা
    basis: str = ""              # "MIS/BE ভিত্তিক" | "করহার ভিত্তিক"
    bill_details: list[dict] = field(default_factory=list)
    calculation_note: str = ""

    def __add__(self, other: "TaxBreakdown") -> "TaxBreakdown":
        out = TaxBreakdown(
            assessable_value=self.assessable_value + other.assessable_value,
            cd=self.cd + other.cd, rd=self.rd + other.rd, sd=self.sd + other.sd,
            vat=self.vat + other.vat, at=self.at + other.at, ait=self.ait + other.ait,
            total=self.total + other.total,
            basis=self.basis or other.basis,
        )
        out.bill_details = self.bill_details + other.bill_details
        return out

    def round_all(self, nd: int = 2) -> "TaxBreakdown":
        for f in ("assessable_value", "cd", "rd", "sd", "vat", "at", "ait", "total"):
            setattr(self, f, round(getattr(self, f), nd))
        return self


# ==========================================================
# একটি বিলের (আংশিক) শুল্কায়ন
# ==========================================================

# উৎসে মূসক হার — স্থানীয় ক্রয়ে বিধিভঙ্গের ক্ষেত্রে প্রযোজ্য
SOURCE_VAT_RATE = 15.0


def assess_bill(row, proportion: float = 1.0) -> TaxBreakdown:
    """
    একটি আমদানি বিলের (বা তার অংশের) শুল্ক-কর নির্ণয়।

    proportion : ১.০ মানে পুরো বিল; ০.৩ মানে বিলের ৩০% অংশ।

    ★ স্থানীয় ক্রয়ের ক্ষেত্রে আমদানি শুল্ক প্রযোজ্য নয় —
      বিধিভঙ্গ হলে ১৫% উৎসে মূসক দাবি করা হয়।
    """
    p = max(0.0, min(1.0, proportion))

    av_full = (row.value_bdt or 0.0) or (
        (row.value_usd or 0.0) * (row.exchange_rate or 0.0)
    )

    # === ★ স্থানীয় ক্রয় — ১৫% উৎসে মূসক ===
    if getattr(row, "source_type", "import") == "local_purchase":
        av = av_full * p
        vat = av * SOURCE_VAT_RATE / 100
        tb = TaxBreakdown(
            assessable_value=av,
            vat=vat,
            total=vat,
            basis=f"স্থানীয় ক্রয় — {SOURCE_VAT_RATE:.0f}% উৎসে মূসক",
        )
        tb.bill_details.append({
            "চালান নং": row.bill_number,
            "তারিখ": row.bill_date.strftime("%d.%m.%Y") if row.bill_date else "",
            "চালানের পরিমাণ": round(row.quantity or 0, 3),
            "আপত্তিকৃত পরিমাণ": round((row.quantity or 0) * p, 3),
            "একক": row.unit,
            "অনুপাত (%)": round(p * 100, 2),
            "ক্রয়মূল্য (৳)": round(av, 2),
            "দাবিকৃত উৎসে মূসক (৳)": round(vat, 2),
        })
        return tb

    # --- MIS/BE-তে উল্লিখিত অঙ্ক আছে কিনা ---
    mis_cd = (row.duty_paid or 0.0)
    mis_rd = (row.rd_paid or 0.0)
    mis_sd = (row.sd_paid or 0.0)
    mis_vat = (row.vat_paid or 0.0)
    mis_at = (row.at_paid or 0.0)
    mis_ait = (row.ait_paid or 0.0)
    mis_sum = mis_cd + mis_rd + mis_sd + mis_vat + mis_at + mis_ait
    mis_total = (row.total_tax or 0.0)

    if mis_sum > 0 or mis_total > 0:
        # --- পদ্ধতি ১: MIS/BE ভিত্তিক (অগ্রাধিকার) ---
        if mis_sum <= 0 and mis_total > 0:
            # শুধু মোট অঙ্ক আছে, বিভাজন নেই
            tb = TaxBreakdown(
                assessable_value=av_full * p,
                total=mis_total * p,
                basis="MIS/BE ভিত্তিক (মোট অঙ্ক)",
            )
        else:
            total = mis_total if mis_total > 0 else mis_sum
            tb = TaxBreakdown(
                assessable_value=av_full * p,
                cd=mis_cd * p, rd=mis_rd * p, sd=mis_sd * p,
                vat=mis_vat * p, at=mis_at * p, ait=mis_ait * p,
                total=total * p,
                basis="MIS/BE ভিত্তিক",
            )
    else:
        # --- পদ্ধতি ২: করহার হতে ক্যাসকেড গণনা (fallback) ---
        av = av_full * p
        cd = av * (row.duty_rate or 0.0) / 100
        rd = av * (getattr(row, "rd_rate", 0.0) or 0.0) / 100
        sd = (av + cd + rd) * (getattr(row, "sd_rate", 0.0) or 0.0) / 100
        vat = (av + cd + rd + sd) * (row.vat_rate or 0.0) / 100
        at = av * (getattr(row, "at_rate", 5.0) or 0.0) / 100
        ait = av * (getattr(row, "ait_rate", 5.0) or 0.0) / 100
        tb = TaxBreakdown(
            assessable_value=av, cd=cd, rd=rd, sd=sd, vat=vat, at=at, ait=ait,
            total=cd + rd + sd + vat + at + ait,
            basis="করহার ভিত্তিক (MIS-এ অঙ্ক অনুপস্থিত)",
        )

    tb.bill_details.append({
        "বিল নং": row.bill_number,
        "তারিখ": row.bill_date.strftime("%d.%m.%Y") if row.bill_date else "",
        "বিলের পরিমাণ": round(row.quantity or 0, 3),
        "আপত্তিকৃত পরিমাণ": round((row.quantity or 0) * p, 3),
        "একক": row.unit,
        "অনুপাত (%)": round(p * 100, 2),
        "শুল্কায়িত মূল্য (৳)": round(tb.assessable_value, 2),
        "দাবিকৃত শুল্ক-কর (৳)": round(tb.total, 2),
    })
    return tb


# ==========================================================
# FIFO ভিত্তিতে অতিরিক্ত অংশ নির্ধারণ
# ==========================================================

def allocate_excess_fifo(
    rows: Iterable, limit: float
) -> list[tuple[Any, float, float]]:
    """
    তারিখক্রমে বিলগুলো সীমা (প্রাপ্যতা/ক্যাপাসিটি) পূরণ করে।
    সীমা অতিক্রমের পর যে অংশ আসে সেটিই আপত্তিযোগ্য।

    ফেরত: [(বিল, অতিরিক্ত পরিমাণ, অনুপাত), ...]
    """
    ordered = sorted(rows, key=lambda r: (r.bill_date or date.min, r.bill_number))
    out: list[tuple[Any, float, float]] = []
    running = 0.0

    for r in ordered:
        qty = r.quantity or 0.0
        if qty <= 0:
            continue
        before, after = running, running + qty
        running = after

        if after <= limit:
            continue                      # সম্পূর্ণ সীমার মধ্যে
        excess_in_bill = after - max(before, limit)
        excess_in_bill = min(excess_in_bill, qty)
        proportion = excess_in_bill / qty if qty else 0.0
        out.append((r, excess_in_bill, proportion))

    return out


# ==========================================================
# উচ্চস্তরের শুল্কায়ন ফাংশন
# ==========================================================

def assess_excess(rows: Iterable, limit: float, opening_stock: float = 0.0) -> TaxBreakdown:
    """
    সীমার অতিরিক্ত অংশের শুল্কায়ন (অতিরিক্ত আমদানি / ক্যাপাসিটি লঙ্ঘন)।

    opening_stock থাকলে সীমা থেকে বাদ দেওয়া হয় — কারণ প্রারম্ভিক জের
    ইতিমধ্যেই ওয়্যারহাউসে আছে, নতুন প্রবেশের জন্য অবশিষ্ট সীমা কম।
    """
    effective_limit = max(0.0, limit - (opening_stock or 0.0))
    allocations = allocate_excess_fifo(rows, effective_limit)

    total = TaxBreakdown()
    for row, excess_qty, prop in allocations:
        total = total + assess_bill(row, prop)

    if allocations:
        bills = ", ".join(r.bill_number for r, _, _ in allocations)
        total.calculation_note = (
            f"তারিখক্রমে সীমা ({effective_limit:,.0f}) পূরণের পর "
            f"{len(allocations)}টি বিলের অতিরিক্ত অংশে বন্ড সুবিধা বাতিল করে "
            f"সংশ্লিষ্ট বিল অব এন্ট্রিতে উল্লিখিত সম্পূর্ণ শুল্ক-কর দাবি করা হইল। "
            f"সংশ্লিষ্ট বিল: {bills}।"
        )
    return total.round_all()


def assess_full(rows: Iterable) -> TaxBreakdown:
    """
    সম্পূর্ণ আমদানির শুল্কায়ন (অননুমোদিত এইচ.এস কোডের ক্ষেত্রে)।
    """
    total = TaxBreakdown()
    for row in rows:
        total = total + assess_bill(row, 1.0)

    if total.total > 0:
        bills = ", ".join(getattr(r, "bill_number", "") for r in rows)
        total.calculation_note = (
            f"প্রাপ্যতা শীটবহির্ভূত পণ্য হওয়ায় সংশ্লিষ্ট আমদানির সম্পূর্ণ "
            f"অংশে বন্ড সুবিধা বাতিল করে বিল অব এন্ট্রিতে উল্লিখিত "
            f"সম্পূর্ণ শুল্ক-কর দাবি করা হইল। সংশ্লিষ্ট বিল: {bills}।"
        )
    return total.round_all()


__all__ = [
    "TaxBreakdown", "assess_bill", "assess_excess", "assess_full",
    "allocate_excess_fifo",
]
