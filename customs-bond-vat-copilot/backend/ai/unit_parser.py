"""
Unit Parser — একক নিষ্কাশন ও সমন্বয়
=====================================

সমস্যা:
    প্রাপ্যতা শীটে একক এক রকম (যেমন YDS), MIS-এ আমদানির একক ভিন্ন (যেমন KG)।
    আবার এককালীন বন্ডিং ক্যাপাসিটি মেট্রিক টনে — সামগ্রিক যাচাইয়ের জন্য
    সকল কাঁচামালকে কেজিতে আনিতে হয়।

সমাধান (ব্যবহারকারী কর্তৃক নির্ধারিত পদ্ধতি):
    আমদানিকৃত কাঁচামালের পরিমাণে দুইটি কলাম থাকিবে —

    কলাম ১ : প্রাপ্যতা শীটের একক অনুযায়ী পরিমাণ
             → MIS-এর বিল অব এন্ট্রিতে পণ্যের বর্ণনা হইতে নিষ্কাশিত
             → না পাওয়া গেলে ফ্ল্যাগ দিয়া নিরীক্ষককে যাচাই করিতে বলা হইবে

    কলাম ২ : কেজি এককে পরিমাণ
             → সামগ্রিক এককালীন বন্ডিং ক্যাপাসিটি যাচাইয়ের ভিত্তি
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


# ==========================================================
# একক নামের প্রতিশব্দ
# ==========================================================

UNIT_ALIASES: dict[str, str] = {
    # ওজন
    "kg": "KG", "kgs": "KG", "kg.": "KG", "kilo": "KG", "kilos": "KG",
    "kilogram": "KG", "kilograms": "KG", "kilogramme": "KG",
    "কেজি": "KG", "কিলোগ্রাম": "KG", "কিলো": "KG",
    "mt": "MT", "m/t": "MT", "m.ton": "MT", "mton": "MT",
    "ton": "MT", "tons": "MT", "tonne": "MT", "tonnes": "MT",
    "metric ton": "MT", "metric tons": "MT", "metricton": "MT",
    "মেট্রিক টন": "MT", "মে টন": "MT", "মে.টন": "MT", "টন": "MT",
    "gm": "GM", "gms": "GM", "gram": "GM", "grams": "GM", "গ্রাম": "GM",
    "lb": "LBS", "lbs": "LBS", "pound": "LBS", "pounds": "LBS",
    # দৈর্ঘ্য
    "yds": "YDS", "yd": "YDS", "yard": "YDS", "yards": "YDS",
    "yrd": "YDS", "গজ": "YDS",
    "mtr": "MTR", "mtrs": "MTR", "meter": "MTR", "meters": "MTR",
    "metre": "MTR", "metres": "MTR", "মিটার": "MTR",
    "ft": "FT", "feet": "FT", "foot": "FT", "ফুট": "FT",
    "inch": "INCH", "inches": "INCH", "ইঞ্চি": "INCH",
    # সংখ্যা
    "pcs": "PCS", "pc": "PCS", "piece": "PCS", "pieces": "PCS",
    "nos": "PCS", "no": "PCS", "nos.": "PCS", "unit": "PCS", "units": "PCS",
    "পিস": "PCS", "সংখ্যা": "PCS",
    "doz": "DOZ", "dz": "DOZ", "dzn": "DOZ", "dozen": "DOZ", "dozens": "DOZ",
    "ডজন": "DOZ",
    "gross": "GROSS", "grs": "GROSS",
    "set": "SET", "sets": "SET", "সেট": "SET",
    "pair": "PAIR", "pairs": "PAIR", "prs": "PAIR", "জোড়া": "PAIR",
    # আয়তন
    "ltr": "LTR", "ltrs": "LTR", "liter": "LTR", "liters": "LTR",
    "litre": "LTR", "litres": "LTR", "লিটার": "LTR",
    "ml": "ML", "mls": "ML",
    # ক্ষেত্র
    "sqm": "SQM", "sq.m": "SQM", "sq m": "SQM", "square meter": "SQM",
    "sqyd": "SQYD", "sq.yd": "SQYD", "square yard": "SQYD",
    # প্যাকেজিং
    "roll": "ROLL", "rolls": "ROLL", "রোল": "ROLL",
    "cone": "CONE", "cones": "CONE", "কোন": "CONE",
    "bag": "BAG", "bags": "BAG", "ব্যাগ": "BAG",
    "ctn": "CTN", "carton": "CTN", "cartons": "CTN", "কার্টন": "CTN",
    "drum": "DRUM", "drums": "DRUM", "ড্রাম": "DRUM",
    "bale": "BALE", "bales": "BALE", "বেল": "BALE",
    "box": "BOX", "boxes": "BOX",
}

# ==========================================================
# নিশ্চিত একক রূপান্তর (পণ্যনিরপেক্ষ)
# ==========================================================
CONVERSIONS: dict[tuple[str, str], float] = {
    # ওজন
    ("MT", "KG"): 1000.0,      ("KG", "MT"): 0.001,
    ("GM", "KG"): 0.001,       ("KG", "GM"): 1000.0,
    ("LBS", "KG"): 0.45359237, ("KG", "LBS"): 2.20462262,
    ("MT", "LBS"): 2204.62262, ("LBS", "MT"): 0.00045359237,
    # দৈর্ঘ্য
    ("YDS", "MTR"): 0.9144,    ("MTR", "YDS"): 1.0936133,
    ("FT", "MTR"): 0.3048,     ("MTR", "FT"): 3.2808399,
    ("YDS", "FT"): 3.0,        ("FT", "YDS"): 1 / 3,
    ("INCH", "FT"): 1 / 12,    ("FT", "INCH"): 12.0,
    # সংখ্যা
    ("DOZ", "PCS"): 12.0,      ("PCS", "DOZ"): 1 / 12,
    ("GROSS", "PCS"): 144.0,   ("PCS", "GROSS"): 1 / 144,
    ("GROSS", "DOZ"): 12.0,    ("DOZ", "GROSS"): 1 / 12,
    ("PAIR", "PCS"): 2.0,      ("PCS", "PAIR"): 0.5,
    # আয়তন
    ("LTR", "ML"): 1000.0,     ("ML", "LTR"): 0.001,
}

# ওজনভিত্তিক একক — সামগ্রিক ক্যাপাসিটি যাচাইয়ে সরাসরি ব্যবহারযোগ্য
WEIGHT_UNITS = {"KG", "MT", "GM", "LBS"}


def normalize_unit(raw: str | None) -> Optional[str]:
    """একক স্বাভাবিকীকরণ — 'Kgs.' → 'KG'"""
    if not raw:
        return None
    s = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    s = re.sub(r"[()\[\]{}]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .,;:-/")
    if not s:
        return None
    if s in UNIT_ALIASES:
        return UNIT_ALIASES[s]
    # যুক্ত রূপ — "kgs" এর ভেতরে "kg"
    compact = re.sub(r"[\s.]", "", s)
    if compact in UNIT_ALIASES:
        return UNIT_ALIASES[compact]
    # দীর্ঘতম প্রতিশব্দ আগে
    for alias in sorted(UNIT_ALIASES, key=len, reverse=True):
        if len(alias) < 2:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", s):
            return UNIT_ALIASES[alias]
    return s.upper()[:12]


# ==========================================================
# বর্ণনা হইতে পরিমাণ নিষ্কাশন
# ==========================================================

_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# "45,000 YDS" | "12000.50 KG" | "৫০০০ কেজি" | "YDS 45000"
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_PATTERNS = [
    rf"{_NUM}\s*([A-Za-z\u0980-\u09FF./]{{1,18}})",     # সংখ্যা তারপর একক
    rf"([A-Za-z\u0980-\u09FF./]{{1,18}})\s*[:=]?\s*{_NUM}",  # একক তারপর সংখ্যা
]


def extract_quantities(text: str | None) -> dict[str, float]:
    """
    পণ্যের বর্ণনা হইতে সকল (পরিমাণ, একক) জোড়া নিষ্কাশন করো।

    ইনপুট  : "Grey Cotton Fabric 45,000 YDS / 12500 KGS (GSM 180)"
    আউটপুট : {"YDS": 45000.0, "KG": 12500.0}

    একই একক একাধিকবার থাকিলে বৃহত্তম মান গ্রহণ করা হয়।
    """
    out: dict[str, float] = {}
    if not text:
        return out

    s = unicodedata.normalize("NFKC", str(text)).translate(_BN_DIGITS)

    for pat in _PATTERNS:
        for m in re.finditer(pat, s):
            g1, g2 = m.group(1), m.group(2)
            # কোনটি সংখ্যা তা নির্ণয় করো
            if re.match(r"^\d", g1):
                num_s, unit_s = g1, g2
            else:
                num_s, unit_s = g2, g1
            try:
                val = float(num_s.replace(",", ""))
            except ValueError:
                continue
            if val <= 0:
                continue

            u = normalize_unit(unit_s)
            # শুধু পরিচিত একক গ্রহণ করো — GSM, DIA ইত্যাদি বাদ
            if not u or u not in set(UNIT_ALIASES.values()):
                continue
            # একই একক পুনরাবৃত্ত হইলে বৃহত্তম
            if val > out.get(u, 0.0):
                out[u] = val

    return out


def convert(qty: float, from_unit: str, to_unit: str) -> Optional[float]:
    """নিশ্চিত রূপান্তর — সম্ভব না হইলে None"""
    if qty is None:
        return None
    f, t = normalize_unit(from_unit), normalize_unit(to_unit)
    if not f or not t:
        return None
    if f == t:
        return float(qty)
    if (f, t) in CONVERSIONS:
        return float(qty) * CONVERSIONS[(f, t)]
    # দুই ধাপে (যেমন MT → KG → LBS)
    for mid in ("KG", "MTR", "PCS"):
        if (f, mid) in CONVERSIONS and (mid, t) in CONVERSIONS:
            return float(qty) * CONVERSIONS[(f, mid)] * CONVERSIONS[(mid, t)]
    return None


# ==========================================================
# সমন্বয়ের ফলাফল
# ==========================================================

@dataclass
class UnitResolution:
    """একটি আমদানি সারির পরিমাণ সমন্বয়ের ফলাফল — Explainable"""
    quantity: Optional[float] = None
    unit: str = ""
    method: str = "none"
    # same_unit | from_description | converted | none
    source_text: str = ""
    explanation: str = ""
    needs_review: bool = False

    @property
    def ok(self) -> bool:
        return self.quantity is not None


def resolve_quantity(
    row_quantity: Optional[float],
    row_unit: Optional[str],
    target_unit: str,
    description: str | None = None,
    extra_text: str | None = None,
) -> UnitResolution:
    """
    একটি আমদানি সারির পরিমাণ লক্ষ্য এককে রূপান্তর করো।

    স্তরক্রম:
      ১) আমদানির একক ও লক্ষ্য একক একই → সরাসরি
      ২) বিল অব এন্ট্রির পণ্যের বর্ণনায় লক্ষ্য এককে পরিমাণ উল্লেখ আছে → তাহাই
      ৩) নিশ্চিত রূপান্তর সম্ভব (KG↔MT, DOZ↔PCS ইত্যাদি) → রূপান্তর
      ৪) কোনোটিই নয় → ফ্ল্যাগ, নিরীক্ষকের যাচাই প্রয়োজন
    """
    tgt = normalize_unit(target_unit)
    src = normalize_unit(row_unit)
    res = UnitResolution(unit=tgt or "")

    if not tgt:
        res.explanation = "লক্ষ্য একক নির্ধারিত নাই।"
        res.needs_review = True
        return res

    # ===== স্তর ১: একই একক =====
    if src and src == tgt and row_quantity is not None:
        res.quantity = float(row_quantity)
        res.method = "same_unit"
        res.explanation = f"আমদানির একক ({src}) প্রাপ্যতার এককের সহিত অভিন্ন।"
        return res

    # ===== স্তর ২: বর্ণনা হইতে নিষ্কাশন =====
    combined = " | ".join(t for t in (description, extra_text) if t)
    if combined:
        found = extract_quantities(combined)
        if tgt in found:
            res.quantity = found[tgt]
            res.method = "from_description"
            res.source_text = combined[:200]
            res.explanation = (
                f"বিল অব এন্ট্রির পণ্যের বর্ণনা হইতে {tgt} এককে পরিমাণ "
                f"{found[tgt]:,.3f} নিষ্কাশিত হইয়াছে।"
            )
            return res
        # বর্ণনার অন্য একক হইতে রূপান্তর
        for u, q in found.items():
            conv = convert(q, u, tgt)
            if conv is not None:
                res.quantity = conv
                res.method = "from_description"
                res.source_text = combined[:200]
                res.explanation = (
                    f"বর্ণনা হইতে {q:,.3f} {u} পাওয়া গিয়াছে; "
                    f"রূপান্তর করিয়া {conv:,.3f} {tgt} নির্ণীত।"
                )
                return res

    # ===== স্তর ৩: নিশ্চিত রূপান্তর =====
    if src and row_quantity is not None:
        conv = convert(row_quantity, src, tgt)
        if conv is not None:
            res.quantity = conv
            res.method = "converted"
            factor = conv / row_quantity if row_quantity else 0
            res.explanation = (
                f"{row_quantity:,.3f} {src} → {conv:,.3f} {tgt} "
                f"(রূপান্তর হার {factor:.6g})।"
            )
            return res

    # ===== স্তর ৪: সম্ভব নয় =====
    res.method = "none"
    res.needs_review = True
    res.explanation = (
        f"আমদানির একক ({src or 'অজ্ঞাত'}) হইতে {tgt} এককে পরিমাণ নির্ণয় "
        f"করা যায় নাই। বিল অব এন্ট্রির পণ্যের বর্ণনায়ও {tgt} এককে পরিমাণ "
        f"উল্লেখ পাওয়া যায় নাই। ★ নিরীক্ষক কর্তৃক হাতে যাচাই আবশ্যক।"
    )
    return res


__all__ = [
    "UNIT_ALIASES", "CONVERSIONS", "WEIGHT_UNITS",
    "normalize_unit", "extract_quantities", "convert",
    "UnitResolution", "resolve_quantity",
]
