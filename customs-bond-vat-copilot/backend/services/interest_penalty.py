"""
Interest & Penalty — কাস্টমস আইন, ২০২৩ অনুযায়ী সুদ ও জরিমানা
================================================================

★ সুদের বিধিবদ্ধ ভিত্তি — **কাস্টমস আইন, ২০২৩ এর ধারা ৩২** 【V】

    (ক) সাধারণ বিলম্ব: পরিশোধ ১০ দিনের মধ্যে; বিলম্বে
        **বার্ষিক ১০% সরল সুদ**

    (খ) ছাড়-পরবর্তী বকেয়া (post-clearance demand):
        **মাসিক ১%** — নিষ্পন্নাধীন সময়সহ **অনধিক ২৪ মাস**;
        বোর্ড গুরুতর ক্ষতিতে সুদ-আরোপ হইতে বিরত থাকিতে পারে

★★ কাল-নিয়ম (Module 13):
    SCN-এ কোন হার প্রযোজ্য তাহা **ঘটনার তারিখ-ভিত্তিক** নির্বাচন
    করিতে হইবে — নিরীক্ষার তারিখ নয়।

    ঘটনা ০৬-০৬-২০২৪ এর পূর্বে হইলে Customs Act 1969 এর
    সংশ্লিষ্ট ধারা প্রযোজ্য 【P — হার যাচাই আবশ্যক】।

মূসক-পার্শ্বে: মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২ — **ধারা ১২৭**
    বকেয়া মূসকে **মাসিক ১%** 【E — হার যাচাই আবশ্যক】
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _bd(d: Optional[date]) -> str:
    return d.strftime("%d-%m-%Y").translate(_BN) if d else "—"

# কাল-সীমা
CUSTOMS_ACT_2023_EFFECTIVE = date(2024, 6, 6)

# ধারা ৩২ — হার
SIMPLE_INTEREST_ANNUAL_PCT = 10.0     # বার্ষিক ১০% সরল সুদ
POST_CLEARANCE_MONTHLY_PCT = 1.0      # মাসিক ১%
MAX_INTEREST_MONTHS = 24              # অনধিক ২৪ মাস
PAYMENT_GRACE_DAYS = 10               # পরিশোধের সময়সীমা

# মূসক-পার্শ্ব
VAT_INTEREST_MONTHLY_PCT = 1.0        # ধারা ১২৭ 【E】


class InterestBasis:
    """সুদ গণনার ভিত্তি"""
    SIMPLE_ANNUAL = "simple_annual"        # ধারা ৩২ — বার্ষিক ১০%
    POST_CLEARANCE = "post_clearance"      # ধারা ৩২ — মাসিক ১%
    VAT_MONTHLY = "vat_monthly"            # মূসক আইন ধারা ১২৭
    NONE = "none"


@dataclass
class InterestResult:
    """সুদ গণনার ফলাফল — সম্পূর্ণ ব্যাখ্যাসহ"""
    principal: float = 0.0
    basis: str = InterestBasis.POST_CLEARANCE

    from_date: Optional[date] = None
    to_date: Optional[date] = None
    days: int = 0
    months: float = 0.0
    months_applied: float = 0.0        # ২৪ মাস সীমা প্রয়োগের পর

    rate_label: str = ""
    interest: float = 0.0
    total: float = 0.0

    capped: bool = False
    legal_ref: str = ""
    formula: str = ""
    certainty: str = "V"
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        """প্রতিবেদনে বসানোর রূপ — প্রমিত চলিত ভাষা"""
        from knowledge.report_style import _indian_group, number_to_bangla_words
        L = [
            f"সুদ গণনা: মূল দাবি {_indian_group(self.principal)} টাকা; "
            f"সময়কাল {_bd(self.from_date)} "
            f"থেকে {_bd(self.to_date)} "
            f"({str(self.days).translate(_BN)} দিন = {self.months:.2f} মাস)।",
            f"হার: {self.rate_label}। {self.formula}",
            f"সুদ: {_indian_group(self.interest)} টাকা "
            f"({number_to_bangla_words(self.interest)} টাকা)।",
            f"মূল দাবিসহ সর্বমোট: {_indian_group(self.total)} টাকা।",
            f"আইনি ভিত্তি: {self.legal_ref}",
        ]
        if self.capped:
            L.append(
                f"★ সুদ গণনায় সর্বোচ্চ {MAX_INTEREST_MONTHS} মাসের সীমা "
                f"প্রয়োগ করা হয়েছে [ধারা ৩২]।"
            )
        L.extend(self.notes)
        return "\n".join(L)


# ==========================================================
# সুদ গণনা
# ==========================================================

def compute_interest(
    principal: float,
    from_date: Optional[date],
    to_date: Optional[date] = None,
    basis: str = InterestBasis.POST_CLEARANCE,
    event_date: Optional[date] = None,
    apply_cap: bool = True,
) -> InterestResult:
    """
    ★ কাস্টমস আইন, ২০২৩ এর ধারা ৩২ অনুযায়ী সুদ গণনা।

    principal   : মূল দাবির অঙ্ক
    from_date   : সুদ গণনার সূচনা (সাধারণত ছাড়ের তারিখ বা পরিশোধের
                  সময়সীমা অতিক্রান্ত হইবার তারিখ)
    to_date     : সুদ গণনার শেষ (ডিফল্ট: আজ)
    basis       : কোন হার প্রযোজ্য
    event_date  : করযোগ্য ঘটনার তারিখ — কাল-নিয়ম যাচাইয়ের জন্য
    """
    r = InterestResult(principal=principal, basis=basis)
    r.from_date = from_date
    r.to_date = to_date or date.today()

    # ---- কাল-নিয়ম যাচাই ----
    ev = event_date or from_date
    if ev and ev < CUSTOMS_ACT_2023_EFFECTIVE:
        r.certainty = "P"
        r.notes.append(
            f"⚠ ঘটনার তারিখ {_bd(ev)} — কাস্টমস আইন, ২০২৩ "
            f"কার্যকর হইবার ({_bd(CUSTOMS_ACT_2023_EFFECTIVE)}) "
            f"পূর্বে। Customs Act, 1969 এর সুদ-বিধান প্রযোজ্য হইতে পারে — "
            f"[যাচাই করুন]। এখানে ২০২৩ আইনের হার প্রয়োগ করা হইয়াছে; "
            f"SCN জারির পূর্বে সংশোধন আবশ্যক।"
        )

    if not from_date or principal <= 0:
        r.notes.append("সুদ গণনার জন্য মূল দাবি ও সূচনা-তারিখ আবশ্যক।")
        r.total = principal
        return r

    r.days = max(0, (r.to_date - from_date).days)
    r.months = r.days / 30.4375        # গড় মাস

    # ---- হার প্রয়োগ ----
    if basis == InterestBasis.SIMPLE_ANNUAL:
        r.rate_label = f"বার্ষিক {SIMPLE_INTEREST_ANNUAL_PCT:g}% সরল সুদ"
        r.months_applied = r.months
        r.interest = principal * SIMPLE_INTEREST_ANNUAL_PCT / 100 * (r.days / 365)
        r.formula = (
            f"{principal:,.2f} × {SIMPLE_INTEREST_ANNUAL_PCT:g}% × "
            f"({str(r.days).translate(_BN)} ÷ ৩৬৫) = {r.interest:,.2f}"
        )
        r.legal_ref = (
            "কাস্টমস আইন, ২০২৩ — ধারা ৩২ [পরিশোধ ১০ দিনের মধ্যে; "
            "বিলম্বে বার্ষিক ১০% সরল সুদ] 【V】"
        )

    elif basis == InterestBasis.POST_CLEARANCE:
        m = r.months
        if apply_cap and m > MAX_INTEREST_MONTHS:
            m = float(MAX_INTEREST_MONTHS)
            r.capped = True
        r.months_applied = m
        r.rate_label = f"মাসিক {POST_CLEARANCE_MONTHLY_PCT:g}%"
        r.interest = principal * POST_CLEARANCE_MONTHLY_PCT / 100 * m
        r.formula = (
            f"{principal:,.2f} × {POST_CLEARANCE_MONTHLY_PCT:g}% × "
            f"{m:.2f} মাস = {r.interest:,.2f}"
        )
        r.legal_ref = (
            "কাস্টমস আইন, ২০২৩ — ধারা ৩২ [ছাড়-পরবর্তী বকেয়ায় মাসিক ১%; "
            "নিষ্পন্নাধীন সময়সহ অনধিক ২৪ মাস] 【V】"
        )
        r.notes.append(
            "★ বোর্ড গুরুতর ক্ষতির ক্ষেত্রে সুদ আরোপ হইতে বিরত থাকিতে "
            "পারে [ধারা ৩২]।"
        )

    elif basis == InterestBasis.VAT_MONTHLY:
        m = r.months
        if apply_cap and m > MAX_INTEREST_MONTHS:
            m = float(MAX_INTEREST_MONTHS)
            r.capped = True
        r.months_applied = m
        r.rate_label = f"মাসিক {VAT_INTEREST_MONTHLY_PCT:g}%"
        r.interest = principal * VAT_INTEREST_MONTHLY_PCT / 100 * m
        r.formula = (
            f"{principal:,.2f} × {VAT_INTEREST_MONTHLY_PCT:g}% × "
            f"{m:.2f} মাস = {r.interest:,.2f}"
        )
        r.legal_ref = (
            "মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২ — ধারা ১২৭ "
            "[বকেয়া মূসকে মাসিক সুদ] 【E — হার যাচাই আবশ্যক】"
        )
        r.certainty = "E"

    else:
        r.rate_label = "সুদ প্রযোজ্য নয়"
        r.legal_ref = "—"

    r.interest = round(r.interest, 2)
    r.total = round(principal + r.interest, 2)
    return r


# ==========================================================
# ★ প্রত্যাবাসন-ব্যর্থতায় দাবি — এসআরও ২১৩ বিধি ১১(৭)
# ==========================================================

def repatriation_demand(
    export_value_fc: float,
    repatriated_fc: float,
    exchange_rate: float,
    shipment_date: Optional[date],
    as_on: Optional[date] = None,
    grace_days: int = 120,
) -> dict:
    """
    ★ পোশাক শিল্পে রপ্তানিমূল্য প্রত্যাবাসিত না হইলে সরাসরি রাজস্ব দাবি।

    এসআরও ২১৩-আইন/২০২৪/৬৫ — বিধি ১১(৭):
    "নির্ধারিত বা বর্ধিত সময়ের মধ্যে রপ্তানিমূল্য দেশে প্রত্যাবাসিত না
    হইলে, কমিশনার অব কাস্টমস বন্ড … রপ্তানিমূল্যের সমপরিমাণ বাংলাদেশি
    মুদ্রা রপ্তানিকারকের নিকট দাবি করিবেন এবং এইরূপ দাবীকৃত অর্থ
    প্রতিষ্ঠান সুদসহ পরিশোধ করিবেন।"
    """
    as_on = as_on or date.today()
    unrepatriated_fc = max(0.0, (export_value_fc or 0) - (repatriated_fc or 0))
    principal_bdt = round(unrepatriated_fc * (exchange_rate or 0), 2)

    out: dict = {
        "রপ্তানি মূল্য (বৈদেশিক মুদ্রা)": round(export_value_fc or 0, 2),
        "প্রত্যাবাসিত (বৈদেশিক মুদ্রা)": round(repatriated_fc or 0, 2),
        "অপ্রত্যাবাসিত (বৈদেশিক মুদ্রা)": round(unrepatriated_fc, 2),
        "বিনিময় হার": exchange_rate,
        "দাবির মূল অঙ্ক (টাকা)": principal_bdt,
        "আইনি ভিত্তি": (
            "এসআরও নং ২১৩-আইন/২০২৪/৬৫/কাস্টমস — বিধি ১১(৬) ও ১১(৭) 【V】"
        ),
    }

    if unrepatriated_fc <= 0:
        out["অবস্থা"] = "সম্পূর্ণ প্রত্যাবাসিত — দাবি প্রযোজ্য নয়"
        return out

    if not shipment_date:
        out["অবস্থা"] = "জাহাজীকরণের তারিখ অনুপস্থিত — [যাচাই করুন]"
        return out

    due = shipment_date + timedelta(days=grace_days)
    out["জাহাজীকরণের তারিখ"] = _bd(shipment_date)
    out["প্রত্যাবাসনের শেষ সীমা"] = _bd(due)

    if as_on <= due:
        out["অবস্থা"] = (
            f"সময়সীমা ({grace_days} দিন) এখনো অতিক্রান্ত হয় নাই — "
            f"দাবি অকালপক্ব"
        )
        return out

    overdue = (as_on - due).days
    out["অবস্থা"] = f"সময়সীমা {overdue} দিন অতিক্রান্ত"
    out["অতিক্রান্ত দিন"] = overdue

    ir = compute_interest(
        principal=principal_bdt, from_date=due, to_date=as_on,
        basis=InterestBasis.POST_CLEARANCE, event_date=shipment_date,
    )
    out["সুদ (টাকা)"] = ir.interest
    out["সুদের হার"] = ir.rate_label
    out["সুদের সময়কাল (মাস)"] = round(ir.months_applied, 2)
    out["সর্বমোট দাবি (টাকা)"] = ir.total
    out["সুদের আইনি ভিত্তি"] = ir.legal_ref
    if ir.capped:
        out["টীকা"] = f"সুদ {MAX_INTEREST_MONTHS} মাসে সীমাবদ্ধ [ধারা ৩২]"

    out["দাবির বিবরণ"] = (
        f"বিল অব এক্সপোর্টের বিপরীতে {unrepatriated_fc:,.2f} বৈদেশিক মুদ্রা "
        f"জাহাজীকরণের {grace_days} দিনের মধ্যে প্রত্যাবাসিত হয় নাই। "
        f"এসআরও ২১৩ এর বিধি ১১(৭) অনুযায়ী রপ্তানিমূল্যের সমপরিমাণ "
        f"বাংলাদেশি মুদ্রা {principal_bdt:,.2f} টাকা সুদসহ আদায়যোগ্য।"
    )
    return out


# ==========================================================
# জরিমানা — সংশ্লিষ্ট ধারা-মানচিত্র
# ==========================================================
# ★ জরিমানার অঙ্ক ন্যায়নির্ণয়নকারী কর্তৃপক্ষের বিবেচনাধীন।
#   ইঞ্জিন কেবল প্রযোজ্য ধারা নির্দেশ করে — অঙ্ক নির্ধারণ করে না।

PENALTY_SECTIONS: list[dict] = [
    {
        "ধারা": "কাস্টমস আইন, ২০২৩ — ধারা ২৩৮",
        "বিষয": "দাবিনামা ও জরিমানা আরোপ",
        "বিষয়": "দাবিনামা জারি ও জরিমানা আরোপের সাধারণ ক্ষমতা",
        "প্রয়োগ": "বন্ড সুবিধার অপব্যবহারজনিত দাবিতে",
        "certainty": "V",
    },
    {
        "ধারা": "কাস্টমস আইন, ২০২৩ — ধারা ২০৩",
        "বিষয়": "কারণ দর্শানো নোটিশ (SCN)",
        "প্রয়োগ": "দাবি প্রতিষ্ঠার পূর্বশর্ত; তামাদি ধারা ২০৪(১) — ৩ বছর",
        "certainty": "V",
    },
    {
        "ধারা": "কাস্টমস আইন, ২০২৩ — ধারা ৩৩",
        "বিষয়": "অসত্য ঘোষণা/দলিল/যোগসাজশে শুল্ক কম-আরোপ",
        "প্রয়োগ": "★ ধারা ৩৩(৪) — এই নোটিশে কোনো তামাদি নাই",
        "certainty": "V",
    },
    {
        "ধারা": "কাস্টমস আইন, ২০২৩ — ধারা ১২৬",
        "বিষয়": "ওয়্যারহাউস হইতে অবৈধ অপসারণ ও হিসাব-অপ্রদত্ত পণ্য",
        "প্রয়োগ": "১২৬(ক) অবৈধ অপসারণ; ১২৬(গ) হিসাব-অপ্রদত্ত",
        "certainty": "V",
    },
    {
        "ধারা": "মূসক আইন, ২০১২ — ধারা ৮৫",
        "বিষয়": "ব্যর্থতা ও অনিয়মে জরিমানা",
        "প্রয়োগ": "দাখিলপত্র-সংক্রান্ত ত্রুটিতে; ক্রমিকভিত্তিক",
        "certainty": "V",
    },
]


def penalty_guidance(finding_kind: str = "") -> dict:
    """
    ★ জরিমানার অঙ্ক নির্ধারণ করা হয় না — কেবল প্রযোজ্য ধারা নির্দেশিত।

    কারণ: জরিমানা ন্যায়নির্ণয়নকারী কর্তৃপক্ষের বিবেচনাধীন; নিরীক্ষা
    প্রতিবেদনে অঙ্ক নির্ধারণ করিলে তাহা এখতিয়ার-বহির্ভূত হইবে।
    """
    return {
        "নীতি": (
            "নিরীক্ষা প্রতিবেদনে জরিমানার অঙ্ক নির্ধারণ করা হয় না। "
            "প্রতিবেদনে কেবল রাজস্ব দাবি ও প্রযোজ্য সুদ উপস্থাপিত হয়; "
            "জরিমানা ন্যায়নির্ণয়নকারী কর্তৃপক্ষের বিবেচনাধীন বিষয়।"
        ),
        "প্রযোজ্য ধারাসমূহ": PENALTY_SECTIONS,
        "সুপারিশের ভাষা": (
            "…আদায়ের লক্ষ্যে প্রতিষ্ঠান বরাবর কারণ দর্শানো নোটিশ জারি "
            "করা যেতে পারে।"
        ),
    }


__all__ = [
    "InterestBasis", "InterestResult", "compute_interest",
    "repatriation_demand", "penalty_guidance", "PENALTY_SECTIONS",
    "SIMPLE_INTEREST_ANNUAL_PCT", "POST_CLEARANCE_MONTHLY_PCT",
    "MAX_INTEREST_MONTHS", "VAT_INTEREST_MONTHLY_PCT",
]
