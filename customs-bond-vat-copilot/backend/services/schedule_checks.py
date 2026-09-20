"""
তফসিল-ভিত্তিক যাচাই (এসআরও ২১২/২০২৪)
======================================

তফসিল-১ (বন্ড রেজিস্টার) ও তফসিল-২ (ইউপি ফরম) হইতে সরাসরি উদ্ভূত তিনটি
যাচাই — রপ্তানি-পক্ষের কোনো তথ্য ব্যতীতই সম্পন্ন হয়:

    ১. ছাড়করণ → ইন্টু-বন্ড বিলম্ব          [বিধি ৮]   — তফসিল-১ কলাম ৩ ↔ ১১
    ২. সহগের মেয়াদ ও সমজাতীয় সহগের সীমা  [বিধি ৯]   — তফসিল-২ (ইউপি)
    ৩. ইউপির গাণিতিক যোগফল                 (গাণিতিক)  — তফসিল-২ লাইন আইটেম

★ আইনি সংখ্যা:
    বিধি ৮ — ASYCUDA Exit Note ইস্যুর তারিখ হইতে **৫ দিনের** মধ্যে ওয়্যারহাউসে
    প্রবেশ; যুক্তিসংগত কারণে কমিশনার সর্বোচ্চ **৭ দিন** পর্যন্ত বর্ধিত করিতে
    পারেন। 【V】
    বিধি ৯ — নিজস্ব সহগ না পাইলে সমজাতীয় সহগের ভিত্তিতে সর্বোচ্চ **৩০ দিন**
    পর্যন্ত ইউপি ইস্যু করা যায়। 【V】

★ সহগের বৈধতার মেয়াদ ইঞ্জিন নিজে অনুমান করে না — DEDO অনুমোদনপত্রে উল্লিখিত
  মেয়াদ (হইতে/পর্যন্ত) নিরীক্ষক সরবরাহ করিবেন। মেয়াদ না দিলে "তথ্য অসম্পূর্ণ"
  হিসাবে চিহ্নিত হয়, অনুমিত কোনো মেয়াদ বসানো হয় না।
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional, Sequence

from utils.logger import logger


# ==========================================================
# আইনি ধ্রুবক 【V】
# ==========================================================

INTO_BOND_BASE_DAYS = 5          # বিধি ৮ — ছাড়করণ হইতে ৫ দিন
INTO_BOND_MAX_EXTENSION = 7      # বিধি ৮ — কমিশনার সর্বোচ্চ +৭ দিন
SIMILAR_COEFFICIENT_MAX_DAYS = 30  # বিধি ৯ — সমজাতীয় সহগে সর্বোচ্চ ৩০ দিন

RULE8_LEGAL_BASIS = (
    "এসআরও ২১২-আইন/২০২৪/৬৪/কাস্টমস — বিধি ৮: পণ্যচালান ছাড়করণের "
    "(ASYCUDA Exit Note) তারিখ হইতে ৫ (পাঁচ) দিনের মধ্যে ওয়্যারহাউসে ইন্টু-বন্ড "
    "করিতে হইবে; যুক্তিসংগত কারণে কমিশনার সর্বোচ্চ ৭ (সাত) দিন পর্যন্ত সময় "
    "বর্ধিত করিতে পারিবেন।"
)

RULE9_LEGAL_BASIS = (
    "এসআরও ২১২-আইন/২০২৪/৬৪/কাস্টমস — বিধি ৯: ইউটিলাইজেশন পারমিশন "
    "পরিদপ্তর (DEDO) কর্তৃক অনুমোদিত বৈধ সহগের ভিত্তিতে ইস্যু করিতে হইবে; "
    "নিজস্ব সহগ প্রাপ্তিতে বিলম্ব হইলে সমজাতীয় সহগের ভিত্তিতে সর্বোচ্চ "
    "৩০ (ত্রিশ) দিন পর্যন্ত ইউপি ইস্যু করা যাইবে।"
)

UP_ARITHMETIC_LEGAL_BASIS = (
    "এসআরও ২১২-আইন/২০২৪/৬৪/কাস্টমস — তফসিল-২ (ইউপি ফরম্যাট): ইউপিতে "
    "ঘোষিত মোট পরিমাণ লাইন আইটেমসমূহের প্রকৃত যোগফলের সহিত সামঞ্জস্যপূর্ণ "
    "হইতে হইবে। ঘোষিত মোট অধিক হইলে উদ্বৃত্ত অংশ অনুমোদন-বহির্ভূত প্রাপ্যতা।"
)


def _as_date(v: Any) -> Optional[date]:
    """তারিখ-সদৃশ মান হইতে date নিষ্কাশন"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    txt = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ==========================================================
# ১. ছাড়করণ → ইন্টু-বন্ড বিলম্ব [বিধি ৮]
# ==========================================================

@dataclass
class IntoBondDelayRecord:
    """তফসিল-১ কলাম ৩ ↔ ১১ — ছাড়করণ হইতে ইন্টু-বন্ডের ব্যবধান"""
    serial: int
    row_number: int
    reference: str            # বিল অব এন্ট্রি নং
    hs_code: str
    item_name: str
    release_date: str         # কলাম ৩ — এক্সিট নোটের তারিখ
    into_bond_date: str       # কলাম ১১
    quantity_kg: float
    delay_days: int           # ইন্টু-বন্ড − ছাড়করণ
    allowed_days: int         # ৫ (+ কমিশনার-বর্ধিত)
    excess_days: int
    status: str               # সীমার মধ্যে | সীমা অতিক্রম | ক্রম-বিপর্যয় | তথ্য অসম্পূর্ণ
    legal_basis: str
    remarks: str


def check_into_bond_delay(
    events: Sequence[Any],
    commissioner_extension_days: int = 0,
) -> list[IntoBondDelayRecord]:
    """
    ★ বিধি ৮ — ছাড়করণের তারিখ হইতে ইন্টু-বন্ডের ব্যবধান যাচাই।

    events : বন্ড রেজিস্টার হইতে প্রাপ্ত LedgerEvent তালিকা (into_bond ঘটনায়
             `release_date` থাকিলে যাচাই সম্ভব)।
    commissioner_extension_days : কমিশনার কর্তৃক বর্ধিত দিন (০–৭)। নিরীক্ষক
             অনুমোদনপত্র দেখিয়া দিবেন; সীমার অধিক দিলে ৭-এ সীমাবদ্ধ হয়।
    """
    ext = max(0, min(int(commissioner_extension_days or 0), INTO_BOND_MAX_EXTENSION))
    if int(commissioner_extension_days or 0) > INTO_BOND_MAX_EXTENSION:
        logger.warning(
            f"কমিশনার-বর্ধিত দিন {commissioner_extension_days} — বিধিবদ্ধ সর্বোচ্চ "
            f"{INTO_BOND_MAX_EXTENSION}; {INTO_BOND_MAX_EXTENSION} দিন ধরা হইল।"
        )
    allowed = INTO_BOND_BASE_DAYS + ext

    out: list[IntoBondDelayRecord] = []
    serial = 0
    for ev in events:
        if getattr(ev, "kind", "") != "into_bond":
            continue
        into_d = getattr(ev, "event_date", None)
        rel_d = getattr(ev, "release_date", None)
        if not into_d:
            continue

        serial += 1
        qty = round(_f(getattr(ev, "qty_kg", 0.0)), 3)
        ref = getattr(ev, "reference", "") or ""
        base = dict(
            serial=serial,
            row_number=int(getattr(ev, "row_number", 0) or 0),
            reference=ref,
            hs_code=getattr(ev, "hs_code", "") or "",
            item_name=getattr(ev, "item_name", "") or "",
            into_bond_date=into_d.strftime("%d.%m.%Y"),
            quantity_kg=qty,
            allowed_days=allowed,
            legal_basis=RULE8_LEGAL_BASIS,
        )

        if not rel_d:
            out.append(IntoBondDelayRecord(
                release_date="", delay_days=0, excess_days=0,
                status="তথ্য অসম্পূর্ণ",
                remarks="তফসিল-১ কলাম ৩ (ছাড়করণ/এক্সিট নোটের তারিখ) পাওয়া "
                        "যায় নাই — বিলম্ব যাচাই করা যায় নাই। নিরীক্ষক সংশ্লিষ্ট "
                        "বিল অব এন্ট্রির এক্সিট নোট তলব করিয়া মিলাইবেন।",
                **base,
            ))
            continue

        delay = (into_d - rel_d).days
        rel_txt = rel_d.strftime("%d.%m.%Y")

        if delay < 0:
            out.append(IntoBondDelayRecord(
                release_date=rel_txt, delay_days=delay, excess_days=0,
                status="ক্রম-বিপর্যয়",
                remarks=f"ইন্টু-বন্ডের তারিখ ({base['into_bond_date']}) ছাড়করণের "
                        f"তারিখের ({rel_txt}) পূর্বে — রেজিস্টারের ভুক্তি "
                        "অসঙ্গতিপূর্ণ। মূল দলিলের সহিত মিলাইয়া সংশোধন তলব করুন।",
                **base,
            ))
            continue

        excess = max(0, delay - allowed)
        if excess > 0:
            ext_txt = (f" (মূল ৫ দিন + কমিশনার-বর্ধিত {ext} দিন)" if ext else "")
            remarks = (
                f"ছাড়করণ {rel_txt} হইতে ইন্টু-বন্ড {base['into_bond_date']} — "
                f"{delay} দিন, অনুমোদিত {allowed} দিন{ext_txt}; "
                f"{excess} দিন বিলম্ব। বিধি ৮ লঙ্ঘিত — বিলম্বের কারণ ও "
                "কমিশনারের সময়-বর্ধিতকরণ আদেশ (থাকিলে) তলব করুন।"
            )
            status = "সীমা অতিক্রম"
        else:
            remarks = (
                f"ছাড়করণ {rel_txt} হইতে ইন্টু-বন্ড {base['into_bond_date']} — "
                f"{delay} দিন; অনুমোদিত {allowed} দিনের মধ্যে।"
            )
            status = "সীমার মধ্যে"

        out.append(IntoBondDelayRecord(
            release_date=rel_txt, delay_days=delay, excess_days=excess,
            status=status, remarks=remarks, **base,
        ))

    breaches = sum(1 for r in out if r.status == "সীমা অতিক্রম")
    logger.info(
        f"বিধি ৮ ইন্টু-বন্ড বিলম্ব যাচাই — {len(out)}টি প্রবেশ, "
        f"{breaches}টি সীমা অতিক্রম"
    )
    return out


# ==========================================================
# ২. সহগের মেয়াদ [বিধি ৯]
# ==========================================================

@dataclass
class CoefficientValidityRecord:
    """ইউপি ইস্যুর তারিখে DEDO সহগ বৈধ ছিল কি না"""
    serial: int
    up_no: str
    up_issue_date: str
    coefficient_ref: str
    valid_from: str
    valid_to: str
    status: str          # বৈধ | মেয়াদোত্তীর্ণ | মেয়াদপূর্ব | সমজাতীয়-সীমা অতিক্রম
                         # | তথ্য অসম্পূর্ণ
    days_expired: int    # মেয়াদ শেষের কত দিন পর ইস্যু (ধনাত্মক হইলে লঙ্ঘন)
    legal_basis: str
    remarks: str


def check_coefficient_validity(
    ups: Sequence[dict],
) -> list[CoefficientValidityRecord]:
    """
    ★ বিধি ৯ — প্রতিটি ইউপি ইস্যুর তারিখে সহগ বৈধ ছিল কি না।

    ups : প্রতিটি ইউপির তথ্য —
        up_no, issue_date, coefficient_ref,
        valid_from, valid_to            (DEDO অনুমোদনপত্র হইতে),
        similar_coefficient (bool)      — সমজাতীয় সহগে ইস্যু কি না,
        similar_since (date)            — সমজাতীয় সহগ প্রয়োগ আরম্ভের তারিখ

    সহগের মেয়াদ ইঞ্জিন অনুমান করে না — না দিলে "তথ্য অসম্পূর্ণ"।
    """
    out: list[CoefficientValidityRecord] = []
    for i, u in enumerate(ups or [], start=1):
        issue = _as_date(u.get("issue_date"))
        v_from = _as_date(u.get("valid_from"))
        v_to = _as_date(u.get("valid_to"))
        up_no = str(u.get("up_no", "") or "")
        ref = str(u.get("coefficient_ref", "") or "")
        similar = bool(u.get("similar_coefficient"))
        since = _as_date(u.get("similar_since"))

        base = dict(
            serial=i, up_no=up_no,
            up_issue_date=issue.strftime("%d.%m.%Y") if issue else "",
            coefficient_ref=ref,
            valid_from=v_from.strftime("%d.%m.%Y") if v_from else "",
            valid_to=v_to.strftime("%d.%m.%Y") if v_to else "",
            legal_basis=RULE9_LEGAL_BASIS,
        )

        # --- সমজাতীয় সহগের ৩০-দিন সীমা ---
        if similar:
            if not (issue and since):
                out.append(CoefficientValidityRecord(
                    status="তথ্য অসম্পূর্ণ", days_expired=0,
                    remarks="সমজাতীয় সহগে ইস্যু বলিয়া চিহ্নিত, কিন্তু ইউপি "
                            "ইস্যুর তারিখ বা সমজাতীয় সহগ প্রয়োগের সূচনা-তারিখ "
                            "পাওয়া যায় নাই — ৩০ দিনের সীমা যাচাই করা যায় নাই।",
                    **base,
                ))
                continue
            used = (issue - since).days
            over = used - SIMILAR_COEFFICIENT_MAX_DAYS
            if over > 0:
                out.append(CoefficientValidityRecord(
                    status="সমজাতীয়-সীমা অতিক্রম", days_expired=over,
                    remarks=f"সমজাতীয় সহগ প্রয়োগ আরম্ভ {since.strftime('%d.%m.%Y')} "
                            f"হইতে {used} দিন পর ইউপি ইস্যু — বিধিবদ্ধ সর্বোচ্চ "
                            f"{SIMILAR_COEFFICIENT_MAX_DAYS} দিন; {over} দিন "
                            "অতিক্রান্ত। নিজস্ব সহগ প্রাপ্তির নথি তলব করুন।",
                    **base,
                ))
                continue
            out.append(CoefficientValidityRecord(
                status="বৈধ", days_expired=0,
                remarks=f"সমজাতীয় সহগে ইস্যু — প্রয়োগ আরম্ভ হইতে {used} দিন, "
                        f"{SIMILAR_COEFFICIENT_MAX_DAYS} দিনের সীমার মধ্যে।",
                **base,
            ))
            continue

        # --- নিজস্ব সহগের মেয়াদ ---
        if not issue or not (v_from or v_to):
            out.append(CoefficientValidityRecord(
                status="তথ্য অসম্পূর্ণ", days_expired=0,
                remarks="ইউপি ইস্যুর তারিখ অথবা সহগের বৈধতার মেয়াদ পাওয়া যায় "
                        "নাই। DEDO অনুমোদনপত্র তলব করিয়া মেয়াদ যাচাই করুন — "
                        "ইঞ্জিন কোনো অনুমিত মেয়াদ প্রয়োগ করে না।",
                **base,
            ))
            continue

        if v_to and issue > v_to:
            gap = (issue - v_to).days
            out.append(CoefficientValidityRecord(
                status="মেয়াদোত্তীর্ণ", days_expired=gap,
                remarks=f"সহগের মেয়াদ {v_to.strftime('%d.%m.%Y')} তারিখে উত্তীর্ণ "
                        f"হইলেও ইউপি ইস্যু হইয়াছে {issue.strftime('%d.%m.%Y')} — "
                        f"{gap} দিন পর। মেয়াদোত্তীর্ণ সহগের ভিত্তিতে ইস্যুকৃত "
                        "ইউপি বিধি ৯ এর লঙ্ঘন; উক্ত ইউপির বিপরীতে ছাড়কৃত "
                        "কাঁচামালের প্রাপ্যতা পুনর্নির্ধারণ ও শুল্কায়ন বিবেচ্য।",
                **base,
            ))
            continue

        if v_from and issue < v_from:
            gap = (v_from - issue).days
            out.append(CoefficientValidityRecord(
                status="মেয়াদপূর্ব", days_expired=gap,
                remarks=f"সহগ কার্যকর হইবার ({v_from.strftime('%d.%m.%Y')}) "
                        f"{gap} দিন পূর্বেই ইউপি ইস্যু হইয়াছে — সহগের "
                        "প্রযোজ্যতা যাচাই করুন।",
                **base,
            ))
            continue

        out.append(CoefficientValidityRecord(
            status="বৈধ", days_expired=0,
            remarks="ইউপি ইস্যুর তারিখে সহগ বৈধ ছিল।",
            **base,
        ))

    bad = sum(1 for r in out
              if r.status in ("মেয়াদোত্তীর্ণ", "সমজাতীয়-সীমা অতিক্রম"))
    logger.info(f"বিধি ৯ সহগ-মেয়াদ যাচাই — {len(out)}টি ইউপি, {bad}টি লঙ্ঘন")
    return out


# ==========================================================
# ৩. ইউপির গাণিতিক যোগফল
# ==========================================================

@dataclass
class UPArithmeticRecord:
    """ইউপিতে ঘোষিত মোট বনাম লাইন আইটেমের প্রকৃত যোগফল"""
    serial: int
    up_no: str
    unit: str
    line_count: int
    declared_total: float     # ইউপিতে ঘোষিত মোট
    computed_total: float     # লাইন আইটেমের যোগফল
    difference: float         # ঘোষিত − প্রকৃত
    difference_pct: float
    status: str               # মিল আছে | ঘোষিত অধিক | ঘোষিত কম | তথ্য অসম্পূর্ণ
    legal_basis: str
    remarks: str


def check_up_arithmetic(
    ups: Sequence[dict],
    tolerance: float = 0.0,
) -> list[UPArithmeticRecord]:
    """
    ★ ইউপির গাণিতিক নির্ভুলতা — ঘোষিত মোট বনাম লাইন আইটেমের যোগফল।

    ups : প্রতিটি ইউপির তথ্য — up_no, declared_total, line_items (list[float]),
          unit (ঐচ্ছিক)।
    tolerance : গ্রহণযোগ্য পার্থক্য (এককে)। ডিফল্ট শূন্য — নিরীক্ষকের
          শূন্য-সহনসীমা নীতির সহিত সঙ্গতিপূর্ণ; ভগ্নাংশজনিত সামান্য
          পার্থক্যের জন্য নিরীক্ষক মান দিতে পারেন।
    """
    tol = max(0.0, _f(tolerance))
    out: list[UPArithmeticRecord] = []
    for i, u in enumerate(ups or [], start=1):
        up_no = str(u.get("up_no", "") or "")
        unit = str(u.get("unit", "") or "")
        items = [_f(x) for x in (u.get("line_items") or [])]
        declared = _f(u.get("declared_total"))
        computed = round(sum(items), 6)
        diff = round(declared - computed, 6)
        pct = (diff / computed * 100) if computed else 0.0

        base = dict(
            serial=i, up_no=up_no, unit=unit, line_count=len(items),
            declared_total=round(declared, 3),
            computed_total=round(computed, 3),
            difference=round(diff, 3),
            difference_pct=round(pct, 2),
            legal_basis=UP_ARITHMETIC_LEGAL_BASIS,
        )

        if not items or declared <= 0:
            out.append(UPArithmeticRecord(
                status="তথ্য অসম্পূর্ণ",
                remarks="লাইন আইটেমের পরিমাণ অথবা ঘোষিত মোট পাওয়া যায় নাই — "
                        "যোগফল মিলানো যায় নাই। ইউপির সংশ্লিষ্ট পৃষ্ঠা তলব করুন।",
                **base,
            ))
            continue

        if abs(diff) <= tol:
            out.append(UPArithmeticRecord(
                status="মিল আছে",
                remarks=f"{len(items)}টি লাইন আইটেমের যোগফল {computed:,.3f} "
                        f"{unit} — ঘোষিত মোটের সহিত সঙ্গতিপূর্ণ।",
                **base,
            ))
        elif diff > 0:
            out.append(UPArithmeticRecord(
                status="ঘোষিত অধিক",
                remarks=f"ইউপিতে ঘোষিত মোট {declared:,.3f} {unit} হইলেও "
                        f"{len(items)}টি লাইন আইটেমের প্রকৃত যোগফল "
                        f"{computed:,.3f} {unit} — ঘোষিত মোট {diff:,.3f} {unit} "
                        f"({pct:+.2f}%) অধিক। উদ্বৃত্ত অংশ অনুমোদন-বহির্ভূত "
                        "প্রাপ্যতা; প্রাপ্যতা শিটের মোট হইতে হুবহু গ্রহণ করা "
                        "হইয়াছে কি না মিলাইয়া দেখুন।",
                **base,
            ))
        else:
            out.append(UPArithmeticRecord(
                status="ঘোষিত কম",
                remarks=f"ঘোষিত মোট {declared:,.3f} {unit} লাইন আইটেমের যোগফল "
                        f"{computed:,.3f} {unit} অপেক্ষা {abs(diff):,.3f} {unit} "
                        "কম — ভুক্তি-ত্রুটি অথবা অলিখিত আইটেম আছে কি না যাচাই করুন।",
                **base,
            ))

    over = sum(1 for r in out if r.status == "ঘোষিত অধিক")
    logger.info(f"ইউপি গাণিতিক যাচাই — {len(out)}টি ইউপি, {over}টি ঘোষিত অধিক")
    return out


__all__ = [
    "INTO_BOND_BASE_DAYS", "INTO_BOND_MAX_EXTENSION",
    "SIMILAR_COEFFICIENT_MAX_DAYS",
    "RULE8_LEGAL_BASIS", "RULE9_LEGAL_BASIS", "UP_ARITHMETIC_LEGAL_BASIS",
    "IntoBondDelayRecord", "check_into_bond_delay",
    "CoefficientValidityRecord", "check_coefficient_validity",
    "UPArithmeticRecord", "check_up_arithmetic",
]
