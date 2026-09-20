"""
Unit Extractor — পণ্যের বর্ণনা হইতে বিকল্প এককে পরিমাণ নিষ্কাশন
==================================================================

প্রেক্ষাপট:
    MIS/বিল অব এন্ট্রিতে কাঁচামালের পরিমাণ **কেজিতে** সর্বদা থাকে।
    কিন্তু প্রাপ্যতা শীটে একক ভিন্ন হইতে পারে (গজ, মিটার, পিস, ডজন)।

    সেই ক্ষেত্রে তুলনা করিতে হইলে বিল অব এন্ট্রির **পণ্যের বর্ণনা** হইতে
    ঐ ভিন্ন এককে পরিমাণ নিষ্কাশন করিতে হইবে।

ফলাফল — আমদানির পরিমাণে দুইটি কলাম:
    কলাম ১ : প্রাপ্যতা শীটের এককে পরিমাণ  (দাবি ২ ও ৪ এর জন্য)
    কলাম ২ : কেজিতে পরিমাণ                (দাবি ৩ — ক্যাপাসিটির জন্য)

বর্ণনায় ঐ একক না পাওয়া গেলে ফ্ল্যাগ দেওয়া হয় — নিরীক্ষক যাচাই করিবেন।
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


# ==========================================================
# এককের প্রতিশব্দ
# ==========================================================

UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "KG": ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms",
           "কেজি", "কিলো", "কিলোগ্রাম"),
    "MT": ("mt", "m/ton", "m.ton", "metric ton", "metric tons", "ton", "tons",
           "মে.টন", "মেট্রিক টন", "টন"),
    "YDS": ("yds", "yd", "yard", "yards", "y/d", "গজ"),
    "MTR": ("mtr", "mtrs", "m", "meter", "meters", "metre", "metres",
            "lm", "linear meter", "মিটার"),
    "PCS": ("pcs", "pc", "piece", "pieces", "nos", "no.", "unit", "units",
            "পিস", "সংখ্যা"),
    "DOZ": ("doz", "dz", "dozen", "dozens", "ডজন"),
    "SET": ("set", "sets", "সেট"),
    "LTR": ("ltr", "l", "lit", "litre", "liter", "litres", "liters", "লিটার"),
    "SQM": ("sqm", "sq.m", "sq m", "square meter", "square metre", "বর্গমিটার"),
    "ROLL": ("roll", "rolls", "রোল"),
    "CONE": ("cone", "cones", "কোন"),
    "BAG": ("bag", "bags", "ব্যাগ", "বস্তা"),
}

# উল্টো ম্যাপ
_ALIAS_TO_UNIT: dict[str, str] = {}
for canon, aliases in UNIT_ALIASES.items():
    for a in aliases:
        _ALIAS_TO_UNIT[a.lower()] = canon

# দীর্ঘতম প্রতিশব্দ আগে — "kilogram" যেন "kg" এর আগে মেলে
_ALIAS_SORTED = sorted(_ALIAS_TO_UNIT.keys(), key=len, reverse=True)

_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_unit(text: str | None) -> Optional[str]:
    """একক স্বাভাবিকীকরণ — 'Yards' → 'YDS'"""
    if not text:
        return None
    s = unicodedata.normalize("NFKC", str(text)).strip().lower()
    s = re.sub(r"[^\w\u0980-\u09FF./]", "", s)
    return _ALIAS_TO_UNIT.get(s)


# ==========================================================
# নিষ্কাশনের ফলাফল
# ==========================================================

@dataclass
class ExtractedQuantity:
    """বর্ণনা হইতে নিষ্কাশিত একটি পরিমাণ"""
    value: float
    unit: str
    matched_text: str = ""
    position: int = 0


@dataclass
class UnitExtractionResult:
    """একটি আমদানি সারির একক-নিষ্কাশনের ফলাফল — Explainable"""
    # কলাম ১ — প্রাপ্যতা শীটের এককে
    target_unit: str = ""
    target_qty: Optional[float] = None
    target_source: str = ""      # mis_column | description | converted | missing

    # কলাম ২ — কেজিতে
    qty_kg: Optional[float] = None
    kg_source: str = ""

    # সব নিষ্কাশিত পরিমাণ
    all_found: list[ExtractedQuantity] = field(default_factory=list)

    # যাচাইয়ের প্রয়োজন
    needs_review: bool = False
    flag_reason: str = ""
    explanation: str = ""


# ==========================================================
# বর্ণনা হইতে পরিমাণ নিষ্কাশন
# ==========================================================

# সংখ্যা + একক প্যাটার্ন — "45,000 YDS", "১২০০০ গজ", "3500.5 Mtr"
_QTY_PATTERN = re.compile(
    r"(\d[\d,\.]*)\s*"
    r"([A-Za-z\u0980-\u09FF][A-Za-z\u0980-\u09FF\.\/]{0,14})",
    flags=re.UNICODE,
)

# একক + সংখ্যা (উল্টো ক্রম) — "YDS: 45,000", "গজ ১২০০০"
_UNIT_FIRST_PATTERN = re.compile(
    r"([A-Za-z\u0980-\u09FF][A-Za-z\u0980-\u09FF\.\/]{0,14})"
    r"\s*[:=\-]?\s*(\d[\d,\.]*)",
    flags=re.UNICODE,
)


def _to_float(s: str) -> Optional[float]:
    """'45,000.5' → 45000.5"""
    s = s.translate(_BN_DIGITS).replace(",", "").strip(" .")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_quantities(description: str | None) -> list[ExtractedQuantity]:
    """
    পণ্যের বর্ণনা হইতে সকল (পরিমাণ + একক) জোড়া নিষ্কাশন করো।

    উদাহরণ:
        "Grey Cotton Fabric 45,000 YDS (12,500 KG) 58/60 inch"
        → [45000 YDS, 12500 KG]
    """
    if not description:
        return []

    text = unicodedata.normalize("NFKC", str(description))
    found: list[ExtractedQuantity] = []
    seen: set[tuple[float, str]] = set()

    for pat, num_first in ((_QTY_PATTERN, True), (_UNIT_FIRST_PATTERN, False)):
        for m in pat.finditer(text):
            raw_num = m.group(1) if num_first else m.group(2)
            raw_unit = m.group(2) if num_first else m.group(1)

            unit = normalize_unit(raw_unit)
            if not unit:
                continue
            val = _to_float(raw_num)
            if val is None or val <= 0:
                continue

            key = (val, unit)
            if key in seen:
                continue
            seen.add(key)
            found.append(ExtractedQuantity(
                value=val, unit=unit,
                matched_text=m.group(0).strip(), position=m.start(),
            ))

    found.sort(key=lambda q: q.position)
    return found


# ==========================================================
# মূল নিষ্কাশক
# ==========================================================

class UnitExtractor:
    """
    আমদানি সারির জন্য দুইটি পরিমাণ-কলাম প্রস্তুত করে।

    ব্যবহার:
        ex = UnitExtractor()
        r = ex.extract(
            description="Grey Cotton Fabric 45,000 YDS (12,500 KG)",
            mis_qty=12500, mis_unit="KG",
            target_unit="YDS",
        )
        r.target_qty  → 45000.0   (প্রাপ্যতা শীটের এককে)
        r.qty_kg      → 12500.0   (ক্যাপাসিটির জন্য)
    """

    def extract(
        self,
        description: str | None,
        mis_qty: Optional[float] = None,
        mis_unit: str | None = None,
        mis_qty_kg: Optional[float] = None,
        target_unit: str | None = None,
        bill_number: str = "",
    ) -> UnitExtractionResult:
        """
        mis_qty / mis_unit : MIS-এ থাকা মূল পরিমাণ ও একক
        mis_qty_kg         : MIS-এ পৃথক কেজি কলাম থাকিলে
        target_unit        : প্রাপ্যতা শীটের একক
        """
        tgt = normalize_unit(target_unit) or (target_unit or "").upper()
        mu = normalize_unit(mis_unit) or (mis_unit or "").upper()

        res = UnitExtractionResult(target_unit=tgt)
        res.all_found = extract_quantities(description)

        # ===== কলাম ২: কেজিতে পরিমাণ =====
        if mis_qty_kg and mis_qty_kg > 0:
            res.qty_kg = float(mis_qty_kg)
            res.kg_source = "mis_column"
        elif mu == "KG" and mis_qty:
            res.qty_kg = float(mis_qty)
            res.kg_source = "mis_column"
        elif mu == "MT" and mis_qty:
            res.qty_kg = float(mis_qty) * 1000.0
            res.kg_source = "converted"
        else:
            kg_found = next((q for q in res.all_found if q.unit == "KG"), None)
            mt_found = next((q for q in res.all_found if q.unit == "MT"), None)
            if kg_found:
                res.qty_kg = kg_found.value
                res.kg_source = "description"
            elif mt_found:
                res.qty_kg = mt_found.value * 1000.0
                res.kg_source = "description"

        # ===== কলাম ১: প্রাপ্যতা শীটের এককে পরিমাণ =====
        if not tgt:
            res.target_qty = mis_qty
            res.target_source = "mis_column"
        elif mu and mu == tgt and mis_qty:
            # MIS ও প্রাপ্যতার একক অভিন্ন — সরাসরি
            res.target_qty = float(mis_qty)
            res.target_source = "mis_column"
        else:
            # ★ বর্ণনা হইতে ঐ ভিন্ন এককে পরিমাণ খোঁজো
            hit = next((q for q in res.all_found if q.unit == tgt), None)
            if hit:
                res.target_qty = hit.value
                res.target_source = "description"
            else:
                # ডজন↔পিস এর মতো নিশ্চিত রূপান্তর
                conv = self._safe_convert(res.all_found, mis_qty, mu, tgt)
                if conv is not None:
                    res.target_qty = conv
                    res.target_source = "converted"
                else:
                    res.target_source = "missing"
                    res.needs_review = True
                    res.flag_reason = (
                        f"প্রাপ্যতা শীটের একক '{tgt}' কিন্তু বিল অব এন্ট্রিতে "
                        f"একক '{mu or '—'}'; পণ্যের বর্ণনায় '{tgt}' এককে "
                        f"পরিমাণ উল্লেখ পাওয়া যায় নাই। নিরীক্ষক কর্তৃক "
                        f"হাতে যাচাই আবশ্যক।"
                    )

        # ===== ব্যাখ্যা =====
        res.explanation = self._explain(res, mis_qty, mu, bill_number)

        # কেজি না পাইলে ক্যাপাসিটি যাচাই ব্যাহত হইবে
        if res.qty_kg is None:
            res.needs_review = True
            extra = (
                "কেজি এককে পরিমাণ পাওয়া যায় নাই — এককালীন বন্ডিং "
                "ক্যাপাসিটি যাচাই ব্যাহত হইবে।"
            )
            res.flag_reason = (res.flag_reason + " " + extra).strip()

        return res

    # ------------------------------------------------------
    @staticmethod
    def _safe_convert(
        found: list[ExtractedQuantity],
        mis_qty: Optional[float],
        from_unit: str,
        to_unit: str,
    ) -> Optional[float]:
        """
        কেবল নিশ্চিত (পণ্য-নিরপেক্ষ) রূপান্তর করো।

        গজ↔মিটার, ডজন↔পিস — নিরাপদ।
        কেজি↔গজ ইত্যাদি পণ্য-নির্ভর, তাই করা হয় না।
        """
        SAFE = {
            ("YDS", "MTR"): 0.9144, ("MTR", "YDS"): 1.09361,
            ("DOZ", "PCS"): 12.0, ("PCS", "DOZ"): 1 / 12.0,
            ("MT", "KG"): 1000.0, ("KG", "MT"): 0.001,
            ("LTR", "ML"): 1000.0,
        }
        # বর্ণনায় পাওয়া অন্য একক হইতে
        for q in found:
            f = SAFE.get((q.unit, to_unit))
            if f:
                return q.value * f
        # MIS এর একক হইতে
        if mis_qty and from_unit:
            f = SAFE.get((from_unit, to_unit))
            if f:
                return mis_qty * f
        return None

    # ------------------------------------------------------
    @staticmethod
    def _explain(
        res: UnitExtractionResult,
        mis_qty: Optional[float],
        mis_unit: str,
        bill_number: str,
    ) -> str:
        prefix = f"বিল {bill_number}: " if bill_number else ""

        src_label = {
            "mis_column": "এমআইএস কলাম হইতে",
            "description": "পণ্যের বর্ণনা হইতে নিষ্কাশিত",
            "converted": "নিশ্চিত একক-রূপান্তরের মাধ্যমে",
            "missing": "পাওয়া যায় নাই",
        }

        parts: list[str] = []
        if res.target_qty is not None:
            parts.append(
                f"প্রাপ্যতার এককে ({res.target_unit}) পরিমাণ "
                f"{res.target_qty:,.3f} — {src_label.get(res.target_source, '')}"
            )
        else:
            parts.append(
                f"প্রাপ্যতার এককে ({res.target_unit}) পরিমাণ নির্ধারণ করা যায় নাই"
            )

        if res.qty_kg is not None:
            parts.append(
                f"কেজিতে {res.qty_kg:,.3f} — {src_label.get(res.kg_source, '')}"
            )
        else:
            parts.append("কেজিতে পরিমাণ পাওয়া যায় নাই")

        if res.all_found:
            found_txt = ", ".join(
                f"{q.value:,.0f} {q.unit}" for q in res.all_found
            )
            parts.append(f"বর্ণনায় প্রাপ্ত: {found_txt}")

        return prefix + "; ".join(parts) + "।"


__all__ = [
    "UnitExtractor", "UnitExtractionResult", "ExtractedQuantity",
    "extract_quantities", "normalize_unit", "UNIT_ALIASES",
]
