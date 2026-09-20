"""
Data Loader — Excel থেকে বিশ্লেষণযোগ্য ডেটায় রূপান্তর
========================================================

কাজ:
  ১. প্রাপ্যতা শীট পড়ো → EntitlementRow তালিকা
  ২. AIS আমদানি শীট পড়ো → ImportRow তালিকা
  ৩. প্রাপ্যতার মেয়াদ (যেমন "০১.০১.২০২৫ থেকে ৩১.১২.২০২৫") স্বয়ংক্রিয় শনাক্ত
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from engines.excel_engine import ExcelEngine, clean_number, clean_hs_code
from services.import_analysis import EntitlementRow, EntitlementMember, ImportRow
from utils.logger import logger


# ==========================================================
# মেয়াদ শনাক্তকরণ
# ==========================================================

_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# তারিখের ধরন: 01.01.2025 | 01/01/2025 | 01-01-2025
_DATE_PATTERN = r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})"

# "থেকে ... পর্যন্ত" বা "from ... to"
_RANGE_PATTERNS = [
    rf"{_DATE_PATTERN}\s*(?:থেকে|হইতে|to|till|until|—|–|-)\s*{_DATE_PATTERN}",
]


def _parse_one_date(d: str, m: str, y: str) -> Optional[date]:
    try:
        day, month, year = int(d), int(m), int(y)
        if year < 100:
            year += 2000
        # দিন-মাস উল্টানো থাকলে সংশোধন
        if day > 12 and month > 12:
            return None
        if month > 12 >= day:
            day, month = month, day
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def parse_period(text: str | None) -> tuple[Optional[date], Optional[date], str]:
    """
    প্রাপ্যতার মেয়াদ বের করো।

    ইনপুট  : "০১.০১.২০২৫ থেকে ৩১.১২.২০২৫ পর্যন্ত সময়ের জন্য প্রদত্ত আমদানি প্রাপ্যতা"
    আউটপুট : (date(2025,1,1), date(2025,12,31), "01.01.2025 — 31.12.2025")
    """
    if not text:
        return None, None, ""

    s = str(text).translate(_BN_DIGITS)
    s = re.sub(r"\s+", " ", s)

    for pat in _RANGE_PATTERNS:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            g = m.groups()
            d1 = _parse_one_date(g[0], g[1], g[2])
            d2 = _parse_one_date(g[3], g[4], g[5])
            if d1 and d2:
                label = f"{d1.strftime('%d.%m.%Y')} — {d2.strftime('%d.%m.%Y')}"
                return d1, d2, label

    # একটিমাত্র তারিখ পেলে — বছর ধরে নাও
    dates = re.findall(_DATE_PATTERN, s)
    if len(dates) >= 2:
        d1 = _parse_one_date(*dates[0])
        d2 = _parse_one_date(*dates[1])
        if d1 and d2:
            return d1, d2, f"{d1.strftime('%d.%m.%Y')} — {d2.strftime('%d.%m.%Y')}"

    # শুধু বছর উল্লেখ থাকলে (যেমন "2024-25")
    ym = re.search(r"(20\d{2})\s*[-–/]\s*(\d{2,4})", s)
    if ym:
        y1 = int(ym.group(1))
        y2raw = ym.group(2)
        y2 = int(y2raw) if len(y2raw) == 4 else 2000 + int(y2raw)
        # বাংলাদেশ অর্থবছর: জুলাই–জুন
        return date(y1, 7, 1), date(y2, 6, 30), f"{y1}-{str(y2)[-2:]} (অর্থবছর)"

    return None, None, str(text)[:80]


def parse_bonding_capacity(texts: list[str]) -> dict:
    """
    প্রাপ্যতা শীট থেকে এককালীন বন্ডিং ক্যাপাসিটি বের করো।

    যেসব লেখা খুঁজবে:
      "এককালীন বন্ডিং ক্যাপাসিটি: ৳ ৫,০০,০০,০০০"
      "One time bonding capacity: USD 500,000"
      "বন্ডিং ক্যাপাসিটি — টাকা ৪,৫০,০০,০০০/-"
    """
    out = {"value_bdt": 0.0, "value_usd": 0.0, "source_text": ""}

    keywords = ["বন্ডিং ক্যাপাসিটি", "বন্ড ক্ষমতা", "ধারণক্ষমতা",
                "bonding capacity", "bond capacity", "warehouse capacity"]

    for raw in texts:
        s = str(raw)
        low = s.lower()
        if not any(k in low or k in s for k in keywords):
            continue

        norm = s.translate(_BN_DIGITS)
        # সংখ্যা বের করো (কমা সহ)
        nums = re.findall(r"[\d,]+(?:\.\d+)?", norm)
        values = []
        for n in nums:
            try:
                v = float(n.replace(",", ""))
                if v >= 1000:      # ক্যাপাসিটি সাধারণত বড় সংখ্যা
                    values.append(v)
            except ValueError:
                continue
        if not values:
            continue

        amount = max(values)
        is_usd = any(t in low for t in ["usd", "us$", "dollar", "ডলার", "$"])
        is_bdt = any(t in low for t in ["৳", "tk", "taka", "টাকা", "bdt"])

        if is_usd and not is_bdt:
            out["value_usd"] = amount
        else:
            out["value_bdt"] = amount
        out["source_text"] = s.strip()[:200]
        break

    return out


# ==========================================================
# মেয়াদের ধরন শনাক্তকরণ
# ==========================================================
#
# প্রাপ্যতা শীটে সাধারণত দুই ধরনের তারিখ থাকে:
#
#   ১) পূর্ববর্তী নিরীক্ষা মেয়াদ  — যেমন ০১.০১.২০২৪ – ৩১.১২.২০২৪
#      (যে নিরীক্ষা শেষে এই শীট জারি হয়েছে)
#
#   ২) প্রাপ্যতার মেয়াদ           — যেমন ০১.০১.২০২৫ – ৩১.১২.২০২৫
#      (এই সময়ে প্রতিষ্ঠান আমদানির বৈধতা পেয়েছে)
#
# ★ বর্তমান নিরীক্ষার মেয়াদ = প্রাপ্যতার মেয়াদ
#   কাজেই ইঞ্জিনকে অবশ্যই দুটি আলাদা করতে হবে।

_ENTITLEMENT_MARKERS = (
    "প্রাপ্যতা", "প্রদত্ত", "প্রস্তাবিত", "আমদানির জন্য", "বৈধতা",
    "entitlement", "entitled", "allowed", "permitted", "validity",
)

_AUDIT_MARKERS = (
    "নিরীক্ষা মেয়াদ", "নিরীক্ষাকাল", "নিরীক্ষার মেয়াদ", "নিরীক্ষা সম্পন্ন",
    "নিরীক্ষাধীন মেয়াদ", "পূর্ববর্তী নিরীক্ষা", "অডিট মেয়াদ",
    "audit period", "audited period", "period audited", "previous audit",
)


def classify_period_text(text: str | None) -> tuple[str, Optional[date], Optional[date], str]:
    """
    একটি লেখা থেকে মেয়াদ বের করে তার ধরন নির্ণয় করো।

    ফেরত: (ধরন, শুরু, শেষ, লেবেল)
    ধরন: "entitlement" | "audit" | "unknown"
    """
    if not text:
        return "unknown", None, None, ""

    s = str(text)
    low = s.lower()
    d_from, d_to, label = parse_period(s)
    if not d_from:
        return "unknown", None, None, ""

    has_audit = any(m in low or m in s for m in _AUDIT_MARKERS)
    has_ent = any(m in low or m in s for m in _ENTITLEMENT_MARKERS)

    if has_ent and not has_audit:
        kind = "entitlement"
    elif has_audit and not has_ent:
        kind = "audit"
    elif has_ent and has_audit:
        # দুটোই আছে — যেটি আগে উল্লেখ, সেটিই মূল বিষয়
        pos_ent = min((s.find(m) for m in _ENTITLEMENT_MARKERS if m in s), default=10**6)
        pos_aud = min((s.find(m) for m in _AUDIT_MARKERS if m in s), default=10**6)
        kind = "entitlement" if pos_ent <= pos_aud else "audit"
    else:
        kind = "unknown"

    return kind, d_from, d_to, label


@dataclass
class PeriodInfo:
    """প্রাপ্যতা শীট থেকে প্রাপ্ত সময়ক্রম"""
    # ★ প্রাপ্যতার মেয়াদ = বর্তমান নিরীক্ষার মেয়াদ
    entitlement_from: Optional[date] = None
    entitlement_to: Optional[date] = None
    entitlement_label: str = ""
    entitlement_source: str = ""

    # পূর্ববর্তী নিরীক্ষার মেয়াদ (যে নিরীক্ষা শেষে শীটটি জারি হয়েছে)
    prev_audit_from: Optional[date] = None
    prev_audit_to: Optional[date] = None
    prev_audit_label: str = ""

    notes: list[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []

    @property
    def audit_from(self) -> Optional[date]:
        """বর্তমান নিরীক্ষার শুরু = প্রাপ্যতার শুরু"""
        return self.entitlement_from

    @property
    def audit_to(self) -> Optional[date]:
        """বর্তমান নিরীক্ষার শেষ = প্রাপ্যতার শেষ"""
        return self.entitlement_to

    def validate(self) -> list[str]:
        """সময়ক্রমের যৌক্তিকতা যাচাই করো"""
        issues: list[str] = []

        if not self.entitlement_from or not self.entitlement_to:
            issues.append(
                "⚠ প্রাপ্যতার মেয়াদ শনাক্ত করা যায়নি — "
                "মেয়াদভিত্তিক যাচাই নিষ্ক্রিয় থাকবে।"
            )
            return issues

        if self.entitlement_to <= self.entitlement_from:
            issues.append("⚠ প্রাপ্যতার শেষ তারিখ শুরুর তারিখের আগে বা সমান।")

        if self.prev_audit_to:
            gap = (self.entitlement_from - self.prev_audit_to).days
            if gap < 0:
                issues.append(
                    f"⚠ পূর্ববর্তী নিরীক্ষা মেয়াদ ({self.prev_audit_label}) এবং "
                    f"প্রাপ্যতার মেয়াদ ({self.entitlement_label}) পরস্পর ছেদ করছে — "
                    f"শীটটি সঠিক কিনা যাচাই করুন।"
                )
            elif gap > 31:
                issues.append(
                    f"⚠ পূর্ববর্তী নিরীক্ষা শেষ ({self.prev_audit_to.strftime('%d.%m.%Y')}) "
                    f"ও প্রাপ্যতা শুরুর ({self.entitlement_from.strftime('%d.%m.%Y')}) "
                    f"মধ্যে {gap} দিনের ব্যবধান — শীটটি সঠিক মেয়াদের কিনা যাচাই করুন।"
                )
            else:
                issues.append(
                    f"✓ সময়ক্রম সঙ্গতিপূর্ণ — পূর্ববর্তী নিরীক্ষা "
                    f"({self.prev_audit_label}) শেষে প্রাপ্যতা প্রদান "
                    f"({self.entitlement_label})।"
                )

        return issues


def detect_entitlement_groups(
    df: pd.DataFrame,
    qty_col: str,
    profile,
) -> list[list[int]]:
    """
    ★ প্রাপ্যতা শীটে উল্লিখিত ক্লাস্টার শনাক্ত করো।

    ইঞ্জিন নিজে ক্লাস্টার তৈরি করে না — শীটে যেভাবে লেখা আছে
    হুবহু সেভাবেই গোষ্ঠী নির্ণয় করে।

    যেসব চিহ্ন দেখে বোঝা যায় একাধিক কাঁচামাল একত্রে প্রাপ্যতা পেয়েছে:

      ১) প্রাপ্যতার কলামে Merged Cell — ৪টি সারি জুড়ে একটিই ঘর
      ২) পরপর কয়েকটি সারিতে প্রাপ্যতা খালি, তারপর একটি সারিতে মান
      ৩) 'ক্লাস্টার' নামে আলাদা কলাম, যাতে একই লেবেল পুনরাবৃত্ত

    ফেরত: [[df সারি সূচক, ...], ...] — প্রতিটি ভেতরের তালিকা একটি গোষ্ঠী
    """
    n = len(df)
    if n == 0:
        return []

    used: set[int] = set()
    groups: list[list[int]] = []

    # raw Excel সারি → df সূচক মানচিত্র
    raw_to_idx: dict[int, int] = {}
    if "_raw_row" in df.columns:
        for idx, raw in enumerate(df["_raw_row"].tolist()):
            try:
                raw_to_idx[int(raw)] = idx
            except (TypeError, ValueError):
                continue

    # ---------- চিহ্ন ১: Merged Cell ----------
    qty_pos = profile.column_positions.get(qty_col) if profile else None
    if qty_pos is not None and raw_to_idx:
        for mr in (profile.merged_parsed or []):
            if mr["col_start"] != qty_pos or mr["col_end"] != qty_pos:
                continue
            if mr["row_end"] <= mr["row_start"]:
                continue
            member_idx = [
                raw_to_idx[r] for r in range(mr["row_start"], mr["row_end"] + 1)
                if r in raw_to_idx
            ]
            member_idx = [i for i in member_idx if i not in used]
            if len(member_idx) >= 2:
                groups.append(sorted(member_idx))
                used.update(member_idx)

    # ---------- চিহ্ন ২: 'ক্লাস্টার' কলামে একই লেবেল ----------
    cluster_col = None
    for cand in ("cluster", "ক্লাস্টার", "cluster_name", "group"):
        if cand in df.columns:
            cluster_col = cand
            break
    if cluster_col:
        seen: dict[str, list[int]] = {}
        for idx, val in enumerate(df[cluster_col].tolist()):
            if idx in used:
                continue
            label = str(val).strip() if val is not None else ""
            if not label or label.lower() in {"nan", "none", "-"}:
                continue
            seen.setdefault(label, []).append(idx)
        for label, idxs in seen.items():
            if len(idxs) >= 2:
                groups.append(sorted(idxs))
                used.update(idxs)

    # ---------- চিহ্ন ৩: খালি প্রাপ্যতা + একটি সারিতে মান ----------
    qty_vals = df[qty_col].tolist() if qty_col in df.columns else []
    if qty_vals:
        pending: list[int] = []
        for idx in range(n):
            if idx in used:
                pending = []
                continue
            v = qty_vals[idx]
            has_value = v is not None and not (
                isinstance(v, float) and np.isnan(v)
            ) and float(v or 0) > 0

            if has_value:
                if pending:                       # খালি সারিগুলো + এই সারি = গোষ্ঠী
                    member = pending + [idx]
                    if len(member) >= 2:
                        groups.append(sorted(member))
                        used.update(member)
                pending = []
            else:
                # নাম বা এইচ.এস কোড আছে এমন খালি-পরিমাণ সারি
                has_item = False
                for c in ("hs_code", "item_name"):
                    if c in df.columns:
                        cv = df[c].iloc[idx]
                        if cv is not None and str(cv).strip() and str(cv).lower() != "nan":
                            has_item = True
                            break
                if has_item:
                    pending.append(idx)
                else:
                    pending = []

    return sorted(groups, key=lambda g: g[0])


def find_period_column(df: pd.DataFrame, profile_columns: dict) -> Optional[str]:
    """
    প্রাপ্যতার মেয়াদ উল্লিখিত কলাম খুঁজে বের করো।

    যেমন কলাম শিরোনাম:
      "০১.০১.২০২৫ থেকে ৩১.১২.২০২৫ পর্যন্ত সময়ের জন্য প্রদত্ত/প্রস্তাবিত আমদানি প্রাপ্যতা"
    """
    keywords = ["প্রাপ্যতা", "প্রদত্ত", "প্রস্তাবিত", "entitle", "entitlement", "approved"]
    best_col, best_score = None, 0

    for col in df.columns:
        col_str = str(col)
        score = 0
        # তারিখ পরিসর আছে?
        d1, d2, _ = parse_period(col_str)
        if d1 and d2:
            score += 5
        # কীওয়ার্ড আছে?
        low = col_str.lower()
        score += sum(2 for k in keywords if k in low or k in col_str)
        # সংখ্যাসূচক কলাম?
        try:
            numeric_ratio = pd.to_numeric(df[col], errors="coerce").notna().mean()
            if numeric_ratio > 0.6:
                score += 3
        except Exception:
            pass

        if score > best_score:
            best_score, best_col = score, col

    return best_col if best_score >= 5 else None


# ==========================================================
# লোডার
# ==========================================================

class DataLoader:
    """Excel ফাইল → বিশ্লেষণযোগ্য অবজেক্ট"""

    def __init__(self, verbose: bool = True):
        self.excel = ExcelEngine(verbose=verbose)
        self.notes: list[str] = []
        self.bonding_capacity: dict = {"value_bdt": 0.0, "value_usd": 0.0, "source_text": ""}
        self.period: PeriodInfo = PeriodInfo()

    # ------------------------------------------------------
    def load_entitlement(
        self,
        file_path: str | Path,
        sheet_name: str | None = None,
        period_column: str | None = None,
        quantity_column: str | None = None,
    ) -> list[EntitlementRow]:
        """প্রাপ্যতা শীট পড়ো"""
        res = self.excel.read(file_path)
        if res.errors:
            raise ValueError("; ".join(res.errors))

        # --- সঠিক শীট নির্বাচন ---
        sheet = sheet_name or res.best_sheet("entitlement")
        if not sheet:
            # entitlement টাইপ না পেলে — import নয় এমন শীট বেছে নাও
            others = [
                s for s in res.sheets
                if s.header_row is not None and s.likely_type != "import"
            ]
            if others:
                sheet = max(others, key=lambda s: (s.confidence, s.total_rows)).sheet_name
            else:
                sheet = res.best_sheet()
        if not sheet:
            raise ValueError("প্রাপ্যতা শীট খুঁজে পাওয়া যায়নি")

        df = self.excel.get_clean_data(res.get_sheet(sheet))
        profile = next(p for p in res.sheets if p.sheet_name == sheet)
        self.notes.append(f"প্রাপ্যতা শীট নির্বাচিত: '{sheet}'")

        # --- প্রাপ্যতার পরিমাণ কলাম নির্ধারণ ---
        qty_col = quantity_column
        original_header = None
        if not qty_col:
            for cand in ["entitled_quantity", "approved_quantity", "quantity"]:
                if cand in df.columns:
                    qty_col = cand
                    # মূল (অনূদিত নয়) শিরোনাম — মেয়াদ পার্স করার জন্য
                    original_header = profile.detected_columns.get(cand)
                    break
        if not qty_col:
            qty_col = find_period_column(df, profile.detected_columns)
            original_header = qty_col

        if not qty_col:
            raise ValueError(
                "প্রাপ্যতার পরিমাণ কলাম শনাক্ত করা যায়নি। "
                "অনুগ্রহ করে কলামটি নির্বাচন করুন।"
            )

        # --- ★ মেয়াদ নির্ধারণ (দুই ধরনের তারিখ আলাদা করে) ---
        period = PeriodInfo()

        # ১) সর্বোচ্চ অগ্রাধিকার: প্রাপ্যতা কলামের মূল শিরোনাম
        #    (যেমন "০১.০১.২০২৫ থেকে ৩১.১২.২০২৫ ... আমদানি প্রাপ্যতা")
        primary = period_column or original_header or qty_col
        kind, d1, d2, lbl = classify_period_text(primary)
        if d1 and kind in ("entitlement", "unknown"):
            period.entitlement_from, period.entitlement_to = d1, d2
            period.entitlement_label = lbl
            period.entitlement_source = "প্রাপ্যতা কলামের শিরোনাম"

        # ২) শীটের অন্যান্য লেখা স্ক্যান করে দুই ধরনের মেয়াদ সংগ্রহ
        search_texts = (
            self._top_rows_text(res, sheet, profile)
            + list(profile.detected_columns.values())
            + list(profile.unmapped_columns)
        )
        for text in search_texts:
            k, a, b, l = classify_period_text(text)
            if not a:
                continue
            if k == "entitlement" and not period.entitlement_from:
                period.entitlement_from, period.entitlement_to = a, b
                period.entitlement_label = l
                period.entitlement_source = str(text)[:120]
            elif k == "audit" and not period.prev_audit_from:
                period.prev_audit_from, period.prev_audit_to = a, b
                period.prev_audit_label = l

        # ৩) এখনও প্রাপ্যতার মেয়াদ না পেলে — পূর্ববর্তী নিরীক্ষা মেয়াদ থেকে অনুমান
        #    (নিরীক্ষা মেয়াদের পরবর্তী সমান দৈর্ঘ্যের সময় = প্রাপ্যতার মেয়াদ)
        if not period.entitlement_from and period.prev_audit_to:
            from datetime import timedelta
            span = (period.prev_audit_to - period.prev_audit_from).days
            period.entitlement_from = period.prev_audit_to + timedelta(days=1)
            period.entitlement_to = period.entitlement_from + timedelta(days=span)
            period.entitlement_label = (
                f"{period.entitlement_from.strftime('%d.%m.%Y')} — "
                f"{period.entitlement_to.strftime('%d.%m.%Y')}"
            )
            period.entitlement_source = "পূর্ববর্তী নিরীক্ষা মেয়াদ হতে অনুমিত"
            self.notes.append(
                "⚠ প্রাপ্যতার মেয়াদ সরাসরি পাওয়া যায়নি; পূর্ববর্তী নিরীক্ষা মেয়াদের "
                "পরবর্তী সমান সময়কে প্রাপ্যতার মেয়াদ ধরা হয়েছে — যাচাই করুন।"
            )

        # ৪) সময়ক্রম যাচাই
        for issue in period.validate():
            self.notes.append(issue)

        self.period = period
        p_from, p_to, p_label = (
            period.entitlement_from, period.entitlement_to, period.entitlement_label
        )

        if p_from:
            self.notes.append(
                f"প্রাপ্যতার মেয়াদ = নিরীক্ষার মেয়াদ: {p_label} "
                f"(উৎস: {period.entitlement_source})"
            )
        if period.prev_audit_from:
            self.notes.append(
                f"পূর্ববর্তী নিরীক্ষা মেয়াদ: {period.prev_audit_label} "
                f"— এই নিরীক্ষা শেষেই প্রাপ্যতা শীটটি জারি হয়েছে"
            )

        if p_from:
            self.notes.append(f"প্রাপ্যতার মেয়াদ শনাক্ত: {p_label}")
        else:
            self.notes.append("⚠ প্রাপ্যতার মেয়াদ শনাক্ত করা যায়নি — সব আমদানি গণনায় আসবে")

        # --- ★ এককালীন বন্ডিং ক্যাপাসিটি (শীটের লেখা থেকে) ---
        header_texts = (
            self._top_rows_text(res, sheet, profile)
            + list(profile.detected_columns.values())
            + list(profile.unmapped_columns)
        )
        cap = parse_bonding_capacity(header_texts)
        self.bonding_capacity = cap
        if cap["value_bdt"] or cap["value_usd"]:
            amt = (f"৳{cap['value_bdt']:,.0f}" if cap["value_bdt"]
                   else f"USD {cap['value_usd']:,.0f}")
            self.notes.append(f"এককালীন বন্ডিং ক্যাপাসিটি শনাক্ত: {amt}")
        else:
            self.notes.append("⚠ এককালীন বন্ডিং ক্যাপাসিটি শনাক্ত করা যায়নি")

        # --- ★ প্রাপ্যতা শীটে উল্লিখিত ক্লাস্টার শনাক্ত করো ---
        groups = detect_entitlement_groups(df, qty_col, profile)
        idx_to_group: dict[int, int] = {}
        for gi, members in enumerate(groups):
            for i in members:
                idx_to_group[i] = gi
        if groups:
            self.notes.append(
                f"প্রাপ্যতা শীটে {len(groups)}টি ক্লাস্টার শনাক্ত হয়েছে "
                f"(মোট {sum(len(g) for g in groups)}টি কাঁচামাল একত্রে প্রাপ্যতাপ্রাপ্ত)"
            )

        # --- সারি তৈরি ---
        rows: list[EntitlementRow] = []
        handled: set[int] = set()

        def _member(i: int) -> EntitlementMember:
            r = df.iloc[i]
            return EntitlementMember(
                hs_code=clean_hs_code(r.get("hs_code")),
                item_name=self._s(r.get("item_name")),
                commercial_name=self._s(r.get("commercial_name")),
                row_number=i + 1,
            )

        def _common(i: int) -> dict:
            """গোষ্ঠীর মান নেওয়া হয় যে সারিতে সংখ্যা আছে সেখান থেকে"""
            r = df.iloc[i]
            return {
                "unit": self._s(r.get("unit")).upper(),
                "unit_price": clean_number(r.get("unit_price")) or 0.0,
                "entitled_value_usd": clean_number(r.get("value_usd")) or 0.0,
                "opening_stock": float(
                    clean_number(r.get("closing_stock"))
                    or clean_number(r.get("opening_stock")) or 0.0
                ),
                "bonding_capacity_qty": float(
                    clean_number(r.get("bonding_capacity")) or 0.0
                ),
                "capacity_100": float(clean_number(r.get("capacity_100")) or 0.0),
                "capacity_80": float(clean_number(r.get("capacity_80")) or 0.0),
                "capacity_60": float(clean_number(r.get("capacity_60")) or 0.0),
                "warehouse_capacity": float(
                    clean_number(r.get("warehouse_capacity")) or 0.0
                ),
                "duty_rate": clean_number(r.get("duty_rate")) or 0.0,
                "vat_rate": clean_number(r.get("vat_rate")) or 15.0,
                "at_rate": clean_number(r.get("at_rate")) or 5.0,
                "rd_rate": clean_number(r.get("rd_rate")) or 0.0,
                "sd_rate": clean_number(r.get("sd_rate")) or 0.0,
                "ait_rate": clean_number(r.get("ait_rate")) or 5.0,
                "serial_no": self._s(r.get("serial_no")),
            }

        row_id = 0
        for idx in range(len(df)):
            if idx in handled:
                continue

            gi = idx_to_group.get(idx)

            # ================= ক্লাস্টার =================
            if gi is not None:
                member_idx = groups[gi]
                handled.update(member_idx)

                # প্রাপ্যতার পরিমাণ ও অন্যান্য মান — যে সারিতে সংখ্যা আছে
                qty, value_idx = 0.0, member_idx[0]
                for i in member_idx:
                    v = clean_number(df.iloc[i].get(qty_col))
                    if v and v > 0:
                        qty, value_idx = float(v), i
                        break

                members = [_member(i) for i in member_idx]
                members = [m for m in members if m.hs_code or m.item_name]
                if not members:
                    continue

                # গোষ্ঠীর মান — সংখ্যাযুক্ত সারি থেকে; খালি হলে অন্য সারি থেকে
                common = _common(value_idx)
                for key in ("unit", "opening_stock", "bonding_capacity_qty",
                            "capacity_100", "capacity_80", "capacity_60",
                            "warehouse_capacity"):
                    if not common.get(key):
                        for i in member_idx:
                            alt = _common(i).get(key)
                            if alt:
                                common[key] = alt
                                break

                first = next((m.item_name for m in members if m.item_name), "")
                label = first[:45]

                row_id += 1
                rows.append(EntitlementRow(
                    row_id=row_id,
                    hs_code=members[0].hs_code,
                    item_name=members[0].item_name,
                    commercial_name=members[0].commercial_name,
                    is_cluster=True,
                    cluster_label=label,
                    members=members,
                    entitled_quantity=qty,
                    period_from=p_from, period_to=p_to, period_label=p_label,
                    **common,
                ))
                continue

            # ================= একক কাঁচামাল =================
            r = df.iloc[idx]
            qty = clean_number(r.get(qty_col))
            name = self._s(r.get("item_name")) or self._s(r.get("commercial_name"))
            hs = clean_hs_code(r.get("hs_code"))
            if not name and not hs:
                continue

            row_id += 1
            rows.append(EntitlementRow(
                row_id=row_id,
                hs_code=hs,
                item_name=name or "",
                commercial_name=self._s(r.get("commercial_name")),
                is_cluster=False,
                entitled_quantity=float(qty or 0.0),
                period_from=p_from, period_to=p_to, period_label=p_label,
                **_common(idx),
            ))

        with_opening = sum(1 for r in rows if r.opening_stock > 0)
        if with_opening:
            self.notes.append(
                f"প্রারম্ভিক জের পাওয়া গেছে {with_opening}টি প্রাপ্যতা-এককে "
                f"(পূর্ববর্তী নিরীক্ষার সমাপনী মজুত)"
            )

        n_cluster = sum(1 for r in rows if r.is_cluster)
        logger.info(
            f"প্রাপ্যতা লোড হয়েছে: {len(rows)} একক "
            f"({n_cluster}টি ক্লাস্টার, {len(rows)-n_cluster}টি একক কাঁচামাল) "
            f"| পরিমাণ কলাম: '{qty_col}'"
        )
        return rows

    # ------------------------------------------------------
    def load_imports(
        self, file_path: str | Path, sheet_name: str | None = None
    ) -> list[ImportRow]:
        """AIS আমদানি শীট পড়ো"""
        res = self.excel.read(file_path)
        if res.errors:
            raise ValueError("; ".join(res.errors))

        sheet = sheet_name or res.best_sheet("import")
        if not sheet:
            raise ValueError("আমদানি শীট খুঁজে পাওয়া যায়নি")

        df = self.excel.get_clean_data(res.get_sheet(sheet))

        rows: list[ImportRow] = []
        for idx, r in df.iterrows():
            name = self._s(r.get("item_name")) or self._s(r.get("commercial_name"))
            hs = clean_hs_code(r.get("hs_code"))
            qty = clean_number(r.get("quantity"))

            if not name and not hs:
                continue

            bdate = r.get("bill_date")
            if isinstance(bdate, pd.Timestamp):
                bdate = bdate.date()
            elif not isinstance(bdate, date):
                bdate = None

            rows.append(ImportRow(
                row_id=int(idx) + 1,
                bill_number=self._s(r.get("bill_number")),
                bill_date=bdate,
                bill_type=self._s(r.get("bill_type")) or "IM-4",
                hs_code=hs,
                item_name=name or "",
                commercial_name=self._s(r.get("commercial_name")),
                quantity=float(qty or 0),
                unit=self._s(r.get("unit")).upper(),
                unit_price=clean_number(r.get("unit_price")) or 0.0,
                value_usd=clean_number(r.get("value_usd")) or 0.0,
                value_bdt=clean_number(r.get("value_bdt")) or 0.0,
                exchange_rate=clean_number(r.get("exchange_rate")) or 0.0,
                duty_rate=clean_number(r.get("duty_rate")) or 0.0,
                vat_rate=clean_number(r.get("vat_rate")) or 15.0,
                duty_paid=clean_number(r.get("duty_paid")) or 0.0,
                vat_paid=clean_number(r.get("vat_paid")) or 0.0,
                rd_paid=clean_number(r.get("rd_paid")) or 0.0,
                sd_paid=clean_number(r.get("sd_paid")) or 0.0,
                at_paid=clean_number(r.get("at_paid")) or 0.0,
                ait_paid=clean_number(r.get("ait_paid")) or 0.0,
                total_tax=clean_number(r.get("total_tax")) or 0.0,
                supplier=self._s(r.get("supplier")),
                country=self._s(r.get("country")),
            ))

        logger.info(f"আমদানি লোড হয়েছে: {len(rows)} সারি")
        return rows

    # ------------------------------------------------------
    @staticmethod
    def _top_rows_text(res, sheet: str, profile) -> list[str]:
        """হেডারের উপরের সারিগুলোর লেখা — শিরোনাম/মেয়াদ প্রায়ই সেখানে থাকে"""
        texts: list[str] = []
        try:
            import pandas as _pd
            raw = _pd.read_excel(res.file_path, sheet_name=sheet, header=None, nrows=15)
            limit = profile.header_row if profile.header_row else 10
            for i in range(min(limit, len(raw))):
                for v in raw.iloc[i]:
                    if v is not None and str(v).strip() and str(v).lower() != "nan":
                        texts.append(str(v))
        except Exception:
            pass
        return texts

    # ------------------------------------------------------
    @staticmethod
    def _s(v) -> str:
        """নিরাপদ string রূপান্তর"""
        if v is None:
            return ""
        if isinstance(v, float) and np.isnan(v):
            return ""
        s = str(v).strip()
        return "" if s.lower() in {"nan", "none", "nat"} else s


__all__ = [
    "DataLoader", "PeriodInfo", "parse_period", "classify_period_text",
    "find_period_column", "parse_bonding_capacity",
]
