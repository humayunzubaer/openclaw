"""
Excel Report Writer — অডিট কার্যপত্র প্রস্তুতকারক
====================================================

বিশ্লেষণের ফলাফলকে একটি সাজানো Excel Workbook-এ রূপান্তর করে,
যা নিরীক্ষা কার্যপত্র (Working Paper) হিসেবে ব্যবহারযোগ্য।

শীটসমূহ:
  ০. প্রচ্ছদ ও সারসংক্ষেপ
  ১. অতিরিক্ত আমদানি
  ২. অননুমোদিত এইচ.এস কোড
  ৩. বন্ডিং ক্যাপাসিটি
  ৪. প্রাপ্যতা ব্যবহার
  ৫. মেশিনারিজ ও যন্ত্রাংশ
  ৬. যাচাই প্রয়োজন
  ৭. সতর্কতা ও টীকা
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, NamedStyle
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from utils.logger import logger


# ==========================================================
# নকশা ধ্রুবক
# ==========================================================

FONT_NAME = "Arial"          # পেশাদার ফন্ট
FONT_BN = "Nirmala UI"       # বাংলা রেন্ডারিংয়ের জন্য (Windows-এ থাকে)

C_HEADER_BG = "1F3864"       # গাঢ় নীল
C_HEADER_FG = "FFFFFF"
C_TITLE_BG = "2E5C8A"
C_SUBTOTAL_BG = "D9E2F3"
C_CRITICAL = "FFC7CE"        # লাল আভা
C_WARNING = "FFEB9C"         # হলুদ আভা
C_OK = "C6EFCE"              # সবুজ আভা
C_BORDER = "8EA9DB"

FMT_MONEY = '#,##0;(#,##0);-'
FMT_QTY = '#,##0.00;(#,##0.00);-'
FMT_PCT = '0.00"%"'
FMT_DATE = 'DD.MM.YYYY'

THIN = Side(style="thin", color=C_BORDER)
BORDER_ALL = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# ==========================================================
# কলাম সংজ্ঞা — বাংলা শিরোনাম ও বিন্যাস
# ==========================================================
# (field_name, বাংলা শিরোনাম, প্রস্থ, বিন্যাস)

COLS_EXCESS = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 22, None),
    ("entitlement_item", "প্রাপ্যতা শীটের বিবরণ", 40, None),
    ("period_label", "প্রাপ্যতার মেয়াদ", 22, None),
    ("unit", "একক", 8, None),
    ("entitled_quantity", "প্রদত্ত প্রাপ্যতা", 15, FMT_QTY),
    ("imported_quantity", "প্রকৃত আমদানি", 15, FMT_QTY),
    ("excess_quantity", "অতিরিক্ত পরিমাণ", 15, FMT_QTY),
    ("excess_pct", "অতিরিক্ত (%)", 12, FMT_PCT),
    ("bill_count", "বিল সংখ্যা", 10, None),
    ("excess_bills", "সীমা অতিক্রমকারী বিল", 32, None),
    ("excess_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("duty_involved", "সিডি (৳)", 15, FMT_MONEY),
    ("rd_involved", "আরডি (৳)", 14, FMT_MONEY),
    ("sd_involved", "এসডি (৳)", 14, FMT_MONEY),
    ("vat_involved", "মূসক (৳)", 15, FMT_MONEY),
    ("at_involved", "এটি (৳)", 14, FMT_MONEY),
    ("ait_involved", "এআইটি (৳)", 14, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("assessment_basis", "শুল্কায়নের ভিত্তি", 22, None),
    ("remarks", "মন্তব্য", 70, None),
    ("bank_guarantee_note", "★ ব্যাংক গ্যারান্টি সংক্রান্ত শর্ত", 75, None),
]

COLS_UNAUTH = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 16, None),
    ("item_name", "পণ্যের বিবরণ", 40, None),
    ("bill_count", "বিল সংখ্যা", 10, None),
    ("bill_numbers", "বিল অব এন্ট্রি নং", 28, None),
    ("total_quantity", "পরিমাণ", 15, FMT_QTY),
    ("unit", "একক", 8, None),
    ("total_value_usd", "মূল্য (USD)", 15, FMT_MONEY),
    ("assessable_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("cd_demanded", "সিডি (৳)", 15, FMT_MONEY),
    ("rd_demanded", "আরডি (৳)", 14, FMT_MONEY),
    ("sd_demanded", "এসডি (৳)", 14, FMT_MONEY),
    ("vat_demanded", "মূসক (৳)", 15, FMT_MONEY),
    ("at_demanded", "এটি (৳)", 14, FMT_MONEY),
    ("ait_demanded", "এআইটি (৳)", 14, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("assessment_basis", "শুল্কায়নের ভিত্তি", 24, None),
    ("nearest_match", "নিকটতম প্রাপ্যতা", 30, None),
    ("remarks", "মন্তব্য", 70, None),
]

# দাবি ৫ — মেয়াদোত্তর আমদানি
COLS_POST_PERIOD = [
    ("serial", "ক্রমিক", 7, None),
    ("source", "উৎস", 18, None),
    ("hs_code", "এইচ.এস কোড", 16, None),
    ("item_name", "পণ্যের বিবরণ", 38, None),
    ("bill_count", "বিল সংখ্যা", 10, None),
    ("bill_numbers", "বিল অব এন্ট্রি নং", 26, None),
    ("total_quantity", "পরিমাণ", 15, FMT_QTY),
    ("unit", "একক", 8, None),
    ("total_value_usd", "মূল্য (USD)", 15, FMT_MONEY),
    ("assessable_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("cd_demanded", "সিডি (৳)", 14, FMT_MONEY),
    ("rd_demanded", "আরডি (৳)", 13, FMT_MONEY),
    ("sd_demanded", "এসডি (৳)", 13, FMT_MONEY),
    ("vat_demanded", "মূসক (৳)", 15, FMT_MONEY),
    ("at_demanded", "এটি (৳)", 13, FMT_MONEY),
    ("ait_demanded", "এআইটি (৳)", 13, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("period_window", "সময়কাল", 26, None),
    ("legal_basis", "আইনি ভিত্তি", 34, None),
    ("remarks", "মন্তব্য", 70, None),
]

# দাবি ৬ — মেয়াদোত্তীর্ণ (overstay)
COLS_OVERSTAY = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 16, None),
    ("item_name", "পণ্যের বিবরণ", 36, None),
    ("bill_numbers", "বিল অব এন্ট্রি নং", 26, None),
    ("into_bond_dates", "ইন্টু-বন্ড তারিখ", 22, None),
    ("overstay_quantity_kg", "অবশিষ্ট (কেজি)", 15, FMT_QTY),
    ("cutoff_date", "কর্তন-তারিখ", 14, None),
    ("assessable_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("cd_demanded", "সিডি (৳)", 14, FMT_MONEY),
    ("rd_demanded", "আরডি (৳)", 13, FMT_MONEY),
    ("sd_demanded", "এসডি (৳)", 13, FMT_MONEY),
    ("vat_demanded", "মূসক (৳)", 15, FMT_MONEY),
    ("at_demanded", "এটি (৳)", 13, FMT_MONEY),
    ("ait_demanded", "এআইটি (৳)", 13, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("legal_basis", "আইনি ভিত্তি", 34, None),
    ("remarks", "মন্তব্য", 70, None),
]

COLS_PROVISIONAL = [
    ("serial", "ক্রমিক", 7, None),
    ("entitlement_item", "প্রাপ্যতা-একক", 42, None),
    ("unit", "একক", 8, None),
    ("next_period_probable", "আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা", 26, FMT_QTY),
    ("divisor_label", "প্রযোজ্য সীমা", 20, None),
    ("allowed_cap", "সর্বোচ্চ গ্রহণযোগ্য", 20, FMT_QTY),
    ("provisional_taken", "গৃহীত সাময়িক প্রাপ্যতা", 22, FMT_QTY),
    ("excess_quantity", "সীমার অতিরিক্ত", 16, FMT_QTY),
    ("excess_pct", "অতিরিক্ত (%)", 12, FMT_PCT),
    ("status", "অবস্থা", 34, None),
    ("reference_date", "সূত্র-তারিখ", 14, None),
    ("legal_basis", "আইনি ভিত্তি", 50, None),
    ("explanation", "গণনার ব্যাখ্যা", 76, None),
    ("demand_proposal", "★ দাবিনামা জারির প্রস্তাব", 90, None),
]

COLS_INTO_BOND_DELAY = [
    ("serial", "ক্রমিক", 7, None),
    ("row_number", "রেজিস্টার সারি", 13, None),
    ("reference", "বিল অব এন্ট্রি নং", 24, None),
    ("hs_code", "এইচ.এস কোড", 16, None),
    ("item_name", "পণ্যের বিবরণ", 34, None),
    ("release_date", "ছাড়করণ (এক্সিট নোট)", 20, None),
    ("into_bond_date", "ইন্টু বন্ডের তারিখ", 18, None),
    ("quantity_kg", "পরিমাণ (কেজি)", 15, FMT_QTY),
    ("delay_days", "ব্যবধান (দিন)", 14, None),
    ("allowed_days", "অনুমোদিত (দিন)", 15, None),
    ("excess_days", "বিলম্ব (দিন)", 13, None),
    ("status", "অবস্থা", 20, None),
    ("legal_basis", "আইনি ভিত্তি", 55, None),
    ("remarks", "মন্তব্য", 80, None),
]

COLS_BREACH = [
    ("serial", "লঙ্ঘন নং", 10, None),
    ("breach_date", "লঙ্ঘনের তারিখ", 15, None),
    ("trigger_bill", "সীমা অতিক্রমকারী বিল", 22, None),
    ("balance_kg", "ঐ মুহূর্তে মজুত (কেজি)", 19, FMT_QTY),
    ("capacity_kg", "এককালীন বন্ডিং ক্যাপাসিটি (কেজি)", 24, FMT_QTY),
    ("gross_excess_kg", "মোট অতিরিক্ত (কেজি)", 18, FMT_QTY),
    ("shielded_kg", "পূর্বে শুল্কায়িত (কেজি)", 20, FMT_QTY),
    ("assessable_kg", "★ শুল্কায়নযোগ্য (কেজি)", 21, FMT_QTY),
    ("allocation_detail", "বিলভিত্তিক দায়ারোপ", 55, None),
    ("assessable_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("cd_demanded", "সিডি (৳)", 15, FMT_MONEY),
    ("rd_demanded", "আরডি (৳)", 14, FMT_MONEY),
    ("sd_demanded", "এসডি (৳)", 14, FMT_MONEY),
    ("vat_demanded", "মূসক (৳)", 15, FMT_MONEY),
    ("at_demanded", "এটি (৳)", 14, FMT_MONEY),
    ("ait_demanded", "এআইটি (৳)", 14, FMT_MONEY),
    ("source_vat_demanded", "উৎসে মূসক (৳)", 16, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("assessment_basis", "শুল্কায়নের ভিত্তি", 22, None),
    ("capacity_formula", "ক্যাপাসিটি নির্ণয়ের সূত্র", 60, None),
    ("legal_basis", "আইনি ভিত্তি", 65, None),
    ("remarks", "মন্তব্য", 85, None),
    ("bank_guarantee_note", "★ ব্যাংক গ্যারান্টি সংক্রান্ত শর্ত", 75, None),
]

COLS_LEDGER = [
    ("তারিখ", "তারিখ", 14, None),
    ("সূত্র (বিল/চালান)", "সূত্র (বিল/চালান)", 20, None),
    ("ইন্টু-বন্ড (কেজি)", "ইন্টু-বন্ড (কেজি)", 17, FMT_QTY),
    ("এক্স-বন্ড (কেজি)", "এক্স-বন্ড (কেজি)", 17, FMT_QTY),
    ("স্থিতি (কেজি)", "স্থিতি (কেজি)", 16, FMT_QTY),
    ("ক্যাপাসিটি (কেজি)", "ক্যাপাসিটি (কেজি)", 18, FMT_QTY),
    ("অতিরিক্ত (কেজি)", "অতিরিক্ত (কেজি)", 16, FMT_QTY),
    ("অবস্থা", "অবস্থা", 16, None),
]

COLS_LIMIT = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 24, None),
    ("item_name", "কাঁচামাল/ক্লাস্টার", 40, None),
    ("unit", "একক", 8, None),
    ("capacity_100", "বার্ষিক উৎপাদন ক্ষমতা (১০০%)", 20, FMT_QTY),
    ("limit_80", "৮০% সীমা", 15, FMT_QTY),
    ("entitled_quantity", "প্রদত্ত প্রাপ্যতা", 16, FMT_QTY),
    ("opening_stock", "প্রারম্ভিক জের", 15, FMT_QTY),
    ("entitlement_plus_opening", "প্রাপ্যতা + জের", 16, FMT_QTY),
    ("excess_over_limit", "সীমার অতিরিক্ত", 15, FMT_QTY),
    ("excess_pct", "অতিরিক্ত (%)", 12, FMT_PCT),
    ("actual_entry", "প্রকৃত প্রবেশ", 15, FMT_QTY),
    ("actual_held", "প্রকৃত ধারণকৃত", 16, FMT_QTY),
    ("assessable_excess", "শুল্কায়নযোগ্য অতিরিক্ত", 20, FMT_QTY),
    ("excess_bills", "সংশ্লিষ্ট বিল অব এন্ট্রি", 32, None),
    ("assessable_value_bdt", "শুল্কায়িত মূল্য (৳)", 18, FMT_MONEY),
    ("cd_demanded", "সিডি (৳)", 15, FMT_MONEY),
    ("rd_demanded", "আরডি (৳)", 14, FMT_MONEY),
    ("sd_demanded", "এসডি (৳)", 14, FMT_MONEY),
    ("vat_demanded", "মূসক (৳)", 15, FMT_MONEY),
    ("at_demanded", "এটি (৳)", 14, FMT_MONEY),
    ("ait_demanded", "এআইটি (৳)", 14, FMT_MONEY),
    ("total_revenue_impact", "মোট দাবি (৳)", 18, FMT_MONEY),
    ("legal_basis", "আইনি ভিত্তি", 55, None),
    ("demand_proposal", "★ দাবিনামা জারির প্রস্তাব", 90, None),
]

COLS_UTIL = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 22, None),
    ("entitlement_item", "প্রাপ্যতা শীটের বিবরণ", 42, None),
    ("period_label", "মেয়াদ", 22, None),
    ("unit", "একক", 8, None),
    ("entitled_quantity", "প্রদত্ত প্রাপ্যতা", 16, FMT_QTY),
    ("imported_quantity", "প্রকৃত আমদানি", 16, FMT_QTY),
    ("balance_quantity", "অবশিষ্ট", 14, FMT_QTY),
    ("utilization_pct", "ব্যবহার (%)", 13, FMT_PCT),
    ("bill_count", "বিল সংখ্যা", 11, None),
    ("status", "অবস্থা", 16, None),
]

COLS_MACHINERY = [
    ("serial", "ক্রমিক", 7, None),
    ("hs_code", "এইচ.এস কোড", 16, None),
    ("item_name", "পণ্যের বিবরণ", 42, None),
    ("bill_count", "বিল সংখ্যা", 10, None),
    ("bill_numbers", "বিল অব এন্ট্রি নং", 26, None),
    ("total_quantity", "পরিমাণ", 14, FMT_QTY),
    ("unit", "একক", 8, None),
    ("total_value_usd", "মূল্য (USD)", 15, FMT_MONEY),
    ("total_value_bdt", "মূল্য (৳)", 17, FMT_MONEY),
    ("duty_paid", "পরিশোধিত সিডি (৳)", 17, FMT_MONEY),
    ("vat_paid", "পরিশোধিত মূসক (৳)", 17, FMT_MONEY),
    ("reason", "শ্রেণীকরণের কারণ", 38, None),
    ("remarks", "মন্তব্য", 65, None),
]


# ==========================================================
# সহায়ক ফাংশন
# ==========================================================

def _style_title(ws: Worksheet, row: int, text: str, ncols: int, sub: str = ""):
    """শীটের শিরোনাম বসাও"""
    ws.cell(row=row, column=1, value=text)
    c = ws.cell(row=row, column=1)
    c.font = Font(name=FONT_NAME, size=13, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_TITLE_BG)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(ncols, 1))
    ws.row_dimensions[row].height = 26

    if sub:
        ws.cell(row=row + 1, column=1, value=sub)
        s = ws.cell(row=row + 1, column=1)
        s.font = Font(name=FONT_NAME, size=9, italic=True, color="444444")
        s.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.merge_cells(
            start_row=row + 1, start_column=1, end_row=row + 1, end_column=max(ncols, 1)
        )
        ws.row_dimensions[row + 1].height = 30


def _write_table(
    ws: Worksheet,
    start_row: int,
    cols: list[tuple],
    records: list[Any],
    total_fields: list[str] = None,
    highlight_field: str = None,
) -> int:
    """
    একটি টেবিল লেখো — শিরোনাম, তথ্য, ও যোগফল সারি।
    ফেরত দেয় শেষ সারির নম্বর।
    """
    total_fields = total_fields or []

    # --- শিরোনাম সারি ---
    hr = start_row
    for i, (_, title, width, _) in enumerate(cols, start=1):
        c = ws.cell(row=hr, column=i, value=title)
        c.font = Font(name=FONT_NAME, size=9, bold=True, color=C_HEADER_FG)
        c.fill = PatternFill("solid", fgColor=C_HEADER_BG)
        c.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
        c.border = BORDER_ALL
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[hr].height = 38

    if not records:
        ws.cell(row=hr + 1, column=1, value="— কোনো তথ্য পাওয়া যায়নি —")
        ws.cell(row=hr + 1, column=1).font = Font(
            name=FONT_NAME, size=10, italic=True, color="888888"
        )
        ws.merge_cells(
            start_row=hr + 1, start_column=1, end_row=hr + 1, end_column=len(cols)
        )
        return hr + 1

    # --- তথ্য সারি ---
    r = hr + 1
    for rec in records:
        d = asdict(rec) if hasattr(rec, "__dataclass_fields__") else dict(rec)

        # গুরুত্বপূর্ণ সারি চিহ্নিত করো
        fill = None
        if highlight_field:
            v = d.get(highlight_field)
            if isinstance(v, (int, float)) and v > 0:
                fill = PatternFill("solid", fgColor=C_CRITICAL)
            elif isinstance(v, str) and v == "সীমা অতিক্রম":
                fill = PatternFill("solid", fgColor=C_CRITICAL)

        for i, (field, _, _, fmt) in enumerate(cols, start=1):
            val = d.get(field, "")
            if val is None:
                val = ""
            c = ws.cell(row=r, column=i, value=val)
            c.font = Font(name=FONT_NAME, size=9)
            c.border = BORDER_ALL
            if fmt:
                c.number_format = fmt
                c.alignment = Alignment(horizontal="right", vertical="top")
            elif isinstance(val, str) and len(val) > 45:
                c.alignment = Alignment(
                    horizontal="left", vertical="top", wrap_text=True
                )
            else:
                c.alignment = Alignment(horizontal="left", vertical="top")
            if fill:
                c.fill = fill
        r += 1

    # --- যোগফল সারি (সূত্রসহ) ---
    if total_fields:
        first_data, last_data = hr + 1, r - 1
        ws.cell(row=r, column=1, value="সর্বমোট")
        tc = ws.cell(row=r, column=1)
        tc.font = Font(name=FONT_NAME, size=10, bold=True)
        tc.fill = PatternFill("solid", fgColor=C_SUBTOTAL_BG)
        tc.border = BORDER_ALL

        for i, (field, _, _, fmt) in enumerate(cols, start=1):
            c = ws.cell(row=r, column=i)
            c.border = BORDER_ALL
            c.fill = PatternFill("solid", fgColor=C_SUBTOTAL_BG)
            c.font = Font(name=FONT_NAME, size=10, bold=True)
            if field in total_fields:
                col_letter = get_column_letter(i)
                c.value = f"=SUM({col_letter}{first_data}:{col_letter}{last_data})"
                if fmt:
                    c.number_format = fmt
                c.alignment = Alignment(horizontal="right")

    # --- ফ্রিজ প্যান ও অটোফিল্টার ---
    ws.freeze_panes = ws.cell(row=hr + 1, column=1)
    ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(cols))}{r - 1}"

    return r


# ==========================================================
# মূল Writer
# ==========================================================

class ExcelReportWriter:
    """
    বিশ্লেষণ ফলাফল → অডিট কার্যপত্র (Excel)

    ব্যবহার:
        writer = ExcelReportWriter(result, meta)
        path = writer.write("output.xlsx")
    """

    def __init__(self, result, meta: dict | None = None):
        self.result = result
        self.meta = meta or {}
        self.wb = openpyxl.Workbook()

    # ------------------------------------------------------
    def write(self, out_path: str | Path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self.wb.remove(self.wb.active)

        self._sheet_cover()
        self._sheet_excess()
        self._sheet_unauthorized()
        self._sheet_post_period()
        self._sheet_overstay()
        self._sheet_provisional()
        self._sheet_into_bond_delay()
        self._sheet_bonding()
        self._sheet_ledger()
        self._sheet_capacity_limit()
        self._sheet_utilization()
        self._sheet_machinery()
        self._sheet_review()
        self._sheet_notes()

        self.wb.save(out_path)
        logger.success(f"অডিট কার্যপত্র তৈরি হয়েছে: {out_path}")
        return out_path

    # ------------------------------------------------------
    def _sheet_cover(self):
        """০. প্রচ্ছদ ও সারসংক্ষেপ"""
        ws = self.wb.create_sheet("০. সারসংক্ষেপ")
        m = self.meta
        res = self.result

        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 48
        ws.column_dimensions["C"].width = 26
        ws.column_dimensions["D"].width = 22

        # --- শিরোনাম ---
        ws["B2"] = "কাস্টমস বন্ড নিরীক্ষা — আমদানি বিশ্লেষণ কার্যপত্র"
        ws["B2"].font = Font(name=FONT_NAME, size=15, bold=True, color="FFFFFF")
        ws["B2"].fill = PatternFill("solid", fgColor=C_TITLE_BG)
        ws["B2"].alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells("B2:D2")
        ws.row_dimensions[2].height = 32

        # --- প্রতিষ্ঠানের তথ্য ---
        info = [
            ("প্রতিষ্ঠানের নাম", m.get("company_name", "—")),
            ("বন্ড লাইসেন্স নং", m.get("bond_number", "—")),
            ("নিরীক্ষার মেয়াদ", m.get("audit_period", "—")),
            ("প্রাপ্যতার মেয়াদ", m.get("entitlement_period", "—")),
            ("পূর্ববর্তী নিরীক্ষা মেয়াদ", m.get("prev_audit_period", "—")),
            ("এককালীন বন্ডিং ক্যাপাসিটি", m.get("bonding_capacity", "—")),
            ("প্রতিবেদন প্রস্তুতের তারিখ",
             datetime.now().strftime("%d.%m.%Y %H:%M")),
        ]
        r = 4
        for label, val in info:
            ws.cell(row=r, column=2, value=label).font = Font(
                name=FONT_NAME, size=10, bold=True
            )
            c = ws.cell(row=r, column=3, value=val)
            c.font = Font(name=FONT_NAME, size=10)
            c.alignment = Alignment(horizontal="left")
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
            r += 1

        # --- রাজস্ব দাবি ---
        r += 1
        ws.cell(row=r, column=2, value="রাজস্ব দাবির সারসংক্ষেপ")
        ws.cell(row=r, column=2).font = Font(
            name=FONT_NAME, size=12, bold=True, color="FFFFFF"
        )
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=C_HEADER_BG)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        ws.row_dimensions[r].height = 22
        r += 1

        s = res.summary
        claim_start = r
        claims = [
            ("দাবি ১ — অননুমোদিত এইচ.এস কোড",
             s.get("দাবি ১ — অননুমোদিত এইচএস কোড (BDT)", 0),
             f"{len(res.unauthorized_records)}টি পণ্য"),
            ("দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি",
             s.get("দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)", 0),
             f"{len(res.excess_records)}টি প্রাপ্যতা-একক"),
            ("দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত",
             s.get("দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত (BDT)", 0),
             f"{s.get('ক্যাপাসিটি লঙ্ঘনকারী আইটেম', 0)}টি আইটেম"),
            ("দাবি ৪ — উৎপাদন ক্ষমতার ৮০% সীমা [বিধি ১১(১)]",
             s.get("দাবি ৪ — উৎপাদন ক্ষমতার ৮০% সীমা লঙ্ঘন [বিধি ১১(১)] (BDT)", 0),
             f"{len(res.capacity_limit_records)}টি আইটেম"),
            ("দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি",
             s.get("দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি (BDT)", 0),
             f"{len(res.post_period_records)}টি রেকর্ড"),
            ("দাবি ৬ — মেয়াদোত্তীর্ণ (২ বছর+) কাঁচামাল",
             s.get("দাবি ৬ — মেয়াদোত্তীর্ণ (২ বছর+) কাঁচামাল (BDT)", 0),
             f"{len(getattr(res, 'overstay_records', []))}টি রেকর্ড"),
        ]
        for label, amount, detail in claims:
            ws.cell(row=r, column=2, value=label).font = Font(name=FONT_NAME, size=10)
            c = ws.cell(row=r, column=3, value=amount)
            c.number_format = FMT_MONEY
            c.font = Font(name=FONT_NAME, size=10)
            c.alignment = Alignment(horizontal="right")
            ws.cell(row=r, column=4, value=detail).font = Font(
                name=FONT_NAME, size=9, italic=True, color="666666"
            )
            for col in (2, 3, 4):
                ws.cell(row=r, column=col).border = BORDER_ALL
            r += 1

        # সর্বমোট — সূত্র দিয়ে
        ws.cell(row=r, column=2, value="সর্বমোট রাজস্ব দাবি")
        ws.cell(row=r, column=2).font = Font(name=FONT_NAME, size=11, bold=True)
        tc = ws.cell(row=r, column=3, value=f"=SUM(C{claim_start}:C{r-1})")
        tc.number_format = FMT_MONEY
        tc.font = Font(name=FONT_NAME, size=11, bold=True, color="C00000")
        tc.alignment = Alignment(horizontal="right")
        for col in (2, 3, 4):
            ws.cell(row=r, column=col).fill = PatternFill(
                "solid", fgColor=C_SUBTOTAL_BG
            )
            ws.cell(row=r, column=col).border = BORDER_ALL
        r += 2

        # --- বিশ্লেষণ পরিসংখ্যান ---
        ws.cell(row=r, column=2, value="বিশ্লেষণ পরিসংখ্যান")
        ws.cell(row=r, column=2).font = Font(
            name=FONT_NAME, size=12, bold=True, color="FFFFFF"
        )
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=C_HEADER_BG)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        r += 1

        skip = {"দাবি", "সর্বমোট রাজস্ব"}
        for k, v in s.items():
            if any(t in k for t in skip):
                continue
            ws.cell(row=r, column=2, value=k).font = Font(name=FONT_NAME, size=9)
            c = ws.cell(row=r, column=3, value=v)
            c.font = Font(name=FONT_NAME, size=9)
            if isinstance(v, (int, float)):
                c.number_format = FMT_MONEY if "BDT" in k or "USD" in k else "#,##0"
                c.alignment = Alignment(horizontal="right")
            r += 1

        ws.sheet_view.showGridLines = False

    # ------------------------------------------------------
    def _sheet_excess(self):
        ws = self.wb.create_sheet("১. অতিরিক্ত আমদানি")
        _style_title(
            ws, 1,
            "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি",
            len(COLS_EXCESS),
            "প্রাপ্যতা শীটে প্রদত্ত পরিমাণের অতিরিক্ত আমদানি। সহনসীমা শূন্য। "
            "তারিখক্রমে প্রাপ্যতা পূরণের পর যে বিলে সীমা অতিক্রম হয়, সেই বিল অব "
            "এন্ট্রিতে উল্লিখিত শুল্ক-কর আনুপাতিকভাবে দাবি করা হইয়াছে।"
        )
        _write_table(
            ws, 4, COLS_EXCESS, self.result.excess_records,
            total_fields=[
                "excess_value_bdt", "duty_involved", "rd_involved", "sd_involved",
                "vat_involved", "at_involved", "ait_involved", "total_revenue_impact",
            ],
        )

    # ------------------------------------------------------
    def _sheet_unauthorized(self):
        ws = self.wb.create_sheet("২. অননুমোদিত এইচএস")
        _style_title(
            ws, 1,
            "দাবি ১ — অননুমোদিত এইচ.এস কোড ব্যবহার করিয়া আমদানি",
            len(COLS_UNAUTH),
            "প্রাপ্যতা শীটে যে সকল কাঁচামালের নাম ও এইচ.এস কোড উল্লেখ আছে, "
            "তাহার বাইরের আমদানি (মেশিনারিজ ব্যতীত)। সম্পূর্ণ আমদানিতে বন্ড সুবিধা "
            "বাতিল করিয়া বিল অব এন্ট্রিতে উল্লিখিত সম্পূর্ণ শুল্ক-কর দাবি করা হইয়াছে। "
            "স্থানীয় ক্রয়ের ক্ষেত্রে ১৫% হারে উৎসে মূসক প্রযোজ্য।"
        )
        _write_table(
            ws, 4, COLS_UNAUTH, self.result.unauthorized_records,
            total_fields=[
                "total_value_usd", "assessable_value_bdt", "cd_demanded",
                "rd_demanded", "sd_demanded", "vat_demanded", "at_demanded",
                "ait_demanded", "total_revenue_impact",
            ],
        )

    # ------------------------------------------------------
    def _sheet_post_period(self):
        ws = self.wb.create_sheet("২ক. মেয়াদোত্তর আমদানি")
        _style_title(
            ws, 1,
            "দাবি ৫ — নিরীক্ষা মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি",
            len(COLS_POST_PERIOD),
            "নিরীক্ষা মেয়াদ (প্রাপ্যতার সমাপ্তি তারিখ) অতিক্রান্ত হইবার পর, নূতন "
            "প্রাপ্যতা/UP অনুমোদনের পূর্বে, কোনো বৈধ প্রাপ্যতা বা প্রত্যয়নপত্র ব্যতীত "
            "যে আমদানি ও স্থানীয় ক্রয় হইয়াছে। আমদানিতে সম্পূর্ণ শুল্ক-কর দাবিযোগ্য; "
            "স্থানীয় ক্রয়ে ১৫% হারে উৎসে মূসক। আইনি ভিত্তি: এসআরও ২১৪-আইন/২০২৪ — "
            "বিধি ৫, ৯ ও ১২।"
        )
        _write_table(
            ws, 4, COLS_POST_PERIOD, self.result.post_period_records,
            total_fields=[
                "total_value_usd", "assessable_value_bdt", "cd_demanded",
                "rd_demanded", "sd_demanded", "vat_demanded", "at_demanded",
                "ait_demanded", "total_revenue_impact",
            ],
        )

    # ------------------------------------------------------
    def _sheet_overstay(self):
        ws = self.wb.create_sheet("২খ. মেয়াদোত্তীর্ণ কাঁচামাল")
        _style_title(
            ws, 1, "দাবি ৬ — মেয়াদোত্তীর্ণ (নির্ধারিত মেয়াদের বেশি) বন্ডে থাকা কাঁচামাল",
            len(COLS_OVERSTAY),
            "বন্ড রেজিস্টার (তফসিল-১) হইতে auto-নির্ণীত — যে ইন্টু-বন্ড কাঁচামাল নির্ধারিত "
            "মেয়াদ (working default ২ বছর; gazette citation অপেক্ষমাণ) অতিক্রান্ত হইবার পরও "
            "বন্ডে অবশিষ্ট (ex-bond হয় নাই), তাহার শুল্ক-কর পরিশোধযোগ্য। শুল্ক MIS/বিল হইতে "
            "আনুপাতিকভাবে ধরা হইয়াছে।"
        )
        _write_table(
            ws, 4, COLS_OVERSTAY, getattr(self.result, "overstay_records", []),
            total_fields=[
                "overstay_quantity_kg", "assessable_value_bdt", "cd_demanded",
                "rd_demanded", "sd_demanded", "vat_demanded", "at_demanded",
                "ait_demanded", "total_revenue_impact",
            ],
        )

    # ------------------------------------------------------
    def _sheet_provisional(self):
        ws = self.wb.create_sheet("২গ. বিয়োজনের শর্তে প্রাপ্যতা")
        _style_title(
            ws, 1,
            "বিয়োজনের শর্তে গৃহীত সাময়িক আমদানি প্রাপ্যতার ঊর্ধ্বসীমা যাচাই",
            len(COLS_PROVISIONAL),
            "নিরীক্ষা চলাকালে প্রতিষ্ঠান আগামী মেয়াদের সম্ভাব্য প্রাপ্যতা হইতে বিয়োজনের "
            "শর্তে সাময়িক আমদানি প্রাপ্যতা গ্রহণ করিতে পারে। উক্ত পরিমাণ সম্ভাব্য "
            "প্রাপ্যতার এক-তৃতীয়াংশ (০১.০৭.২০২৬ এর পূর্বে) বা এক-চতুর্থাংশ (উক্ত তারিখ "
            "ও তৎপরবর্তী) অতিক্রম করিতে পারিবে না। সীমাতিরিক্ত অংশ বৈধ প্রাপ্যতা নহে "
            "বিধায় মোট অনুমোদিত প্রাপ্যতা হইতে বাদ দেওয়া হইয়াছে — উহার বিপরীতে "
            "আমদানিকৃত কাঁচামাল দাবি ২ (প্রাপ্যতার অতিরিক্ত আমদানি) হিসাবে শুল্কায়িত; "
            "কাস্টমস আইন, ২০২৩ এর ধারা ২৩৮ অনুযায়ী দাবিনামা জারির প্রস্তাব করা হইয়াছে।"
        )
        _write_table(
            ws, 4, COLS_PROVISIONAL,
            getattr(self.result, "provisional_records", []),
            highlight_field="excess_quantity",
        )

    # ------------------------------------------------------
    def _sheet_into_bond_delay(self):
        ws = self.wb.create_sheet("২ঘ. ইন্টু-বন্ড বিলম্ব")
        _style_title(
            ws, 1,
            "ছাড়করণ হইতে ইন্টু-বন্ডের বিলম্ব যাচাই [এসআরও ২১২/২০২৪, বিধি ৮]",
            len(COLS_INTO_BOND_DELAY),
            "পণ্যচালান কাস্টম হাউস হইতে ছাড়করণের (ASYCUDA এক্সিট নোট) তারিখ হইতে "
            "৫ (পাঁচ) দিনের মধ্যে ওয়্যারহাউসে ইন্টু-বন্ড করিতে হইবে; যুক্তিসংগত "
            "কারণে কমিশনার সর্বোচ্চ ৭ (সাত) দিন পর্যন্ত সময় বর্ধিত করিতে পারিবেন। "
            "তফসিল-১ এর কলাম ৩ ও কলাম ১১ হইতে auto-নির্ণীত। সীমা অতিক্রান্ত "
            "প্রবেশের ক্ষেত্রে বিলম্বের কারণ ও সময়-বর্ধিতকরণ আদেশ তলব করিতে হইবে।"
        )
        _write_table(
            ws, 4, COLS_INTO_BOND_DELAY,
            getattr(self.result, "into_bond_delay_records", []),
            highlight_field="excess_days",
        )

    # ------------------------------------------------------
    def _sheet_bonding(self):
        ws = self.wb.create_sheet("৩. বন্ডিং ক্যাপাসিটি")
        res = self.result
        cap = res.one_time_capacity

        sub = (
            "দাবি ৩ — এককালীন বন্ডিং ক্যাপাসিটির অতিরিক্ত মজুত। "
            "যাচাই সামগ্রিক (সকল কাঁচামাল একত্রে, কেজিতে) এবং নিরীক্ষাধীন "
            "মেয়াদের প্রতিটি মুহূর্তে প্রযোজ্য। বৎসরে যতবার সীমা অতিক্রান্ত "
            "হইয়াছে ততবারই শুল্কায়ন করা হইয়াছে; তবে যে পরিমাণের উপর একবার "
            "শুল্কায়ন হইয়াছে উহা ওয়্যারহাউসে বিদ্যমান থাকা পর্যন্ত পুনরায় "
            "শুল্কায়ন করা হয় নাই।"
        )
        if cap and getattr(cap, "formula", ""):
            sub += f"  ▸ {cap.formula}"

        _style_title(ws, 1, "দাবি ৩ — এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন",
                     len(COLS_BREACH), sub)

        # রেজিস্টার না থাকিলে বার্তা
        if not res.capacity_breach_records and res.bonding_value.status in (
            "যাচাই স্থগিত", "যাচাই সম্ভব হয় নাই", "প্রযোজ্য নয়"
        ):
            c = ws.cell(row=4, column=1, value=res.bonding_value.remarks)
            c.font = Font(name=FONT_NAME, size=10, italic=True)
            c.fill = PatternFill("solid", fgColor=C_WARNING)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=4, start_column=1, end_row=8, end_column=10)
            for i in range(1, 11):
                ws.column_dimensions[get_column_letter(i)].width = 18
            return

        _write_table(
            ws, 4, COLS_BREACH, res.capacity_breach_records,
            total_fields=[
                "assessable_kg", "assessable_value_bdt", "cd_demanded",
                "rd_demanded", "sd_demanded", "vat_demanded", "at_demanded",
                "ait_demanded", "source_vat_demanded", "total_revenue_impact",
            ],
            highlight_field="assessable_kg",
        )

    # ------------------------------------------------------
    def _sheet_ledger(self):
        """সময়ানুক্রমিক মজুত খতিয়ান — প্রমাণপত্র"""
        ws = self.wb.create_sheet("৩ক. মজুত খতিয়ান")
        lg = self.result.capacity_ledger
        _style_title(
            ws, 1, "সময়ানুক্রমিক মজুত খতিয়ান (তফসিল-১ ভিত্তিক)",
            len(COLS_LEDGER),
            "বন্ড রেজিস্টারের ইন্টু-বন্ড ও এক্স-বন্ড তথ্য হইতে প্রস্তুতকৃত। "
            "মজুত(t) = প্রারম্ভিক জের + ইন্টু-বন্ড(t পর্যন্ত) − এক্স-বন্ড(t পর্যন্ত)। "
            "লাল চিহ্নিত সারিসমূহে এককালীন বন্ডিং ক্যাপাসিটি অতিক্রান্ত হইয়াছে।"
        )
        if not lg or not getattr(lg, "points", None):
            c = ws.cell(row=4, column=1,
                        value="— বন্ড রেজিস্টার না পাওয়ায় খতিয়ান প্রস্তুত করা হয় নাই —")
            c.font = Font(name=FONT_NAME, size=10, italic=True, color="888888")
            ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=8)
            return

        rows = self.result._ledger_frame().to_dict("records")
        _write_table(ws, 4, COLS_LEDGER, rows,
                     total_fields=["ইন্টু-বন্ড (কেজি)", "এক্স-বন্ড (কেজি)"],
                     highlight_field="অতিরিক্ত (কেজি)")

        # সারসংক্ষেপ
        r = 6 + len(rows)
        info = [
            ("প্রারম্ভিক জের (কেজি)", lg.opening_kg),
            ("মোট ইন্টু-বন্ড (কেজি)", lg.total_into_bond_kg),
            ("মোট এক্স-বন্ড (কেজি)", lg.total_ex_bond_kg),
            ("সমাপনী মজুত (কেজি)", lg.closing_kg),
            ("সর্বোচ্চ মজুত (কেজি)", lg.peak_balance_kg),
            ("লঙ্ঘন সংখ্যা", lg.breach_count),
            ("মোট শুল্কায়নযোগ্য অতিরিক্ত (কেজি)", lg.total_assessable_kg),
        ]
        for label, val in info:
            ws.cell(row=r, column=1, value=label).font = Font(
                name=FONT_NAME, size=10, bold=True)
            c = ws.cell(row=r, column=3, value=val)
            c.number_format = FMT_QTY
            c.font = Font(name=FONT_NAME, size=10, bold=True)
            r += 1

    # ------------------------------------------------------
    def _sheet_capacity_limit(self):
        ws = self.wb.create_sheet("৪. উৎপাদন ক্ষমতা সীমা")
        _style_title(
            ws, 1,
            "দাবি ৪ — বার্ষিক উৎপাদন ক্ষমতার ৮০% সীমা লঙ্ঘন [বিধি ১১(১)]",
            len(COLS_LIMIT),
            "ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪ এর বিধি ১১(১) অনুযায়ী "
            "নির্ধারিত বার্ষিক আমদানি প্রাপ্যতা ও পূর্ববর্তী মেয়াদের মজুদ কাঁচামালের "
            "সমাপনী জেরসহ একত্রে প্রতিষ্ঠানের বার্ষিক উৎপাদন ক্ষমতার শতকরা ৮০ ভাগের "
            "অতিরিক্ত হইতে পারিবে না। অতিরিক্ত অংশের বন্ড সুবিধা বাতিলপূর্বক "
            "কাস্টমস আইন, ২০২৩ এর ধারা ২৩৮ অনুযায়ী দাবিনামা জারির প্রস্তাব করা হইয়াছে।"
        )
        _write_table(
            ws, 4, COLS_LIMIT, self.result.capacity_limit_records,
            total_fields=[
                "assessable_value_bdt", "cd_demanded", "rd_demanded", "sd_demanded",
                "vat_demanded", "at_demanded", "ait_demanded", "total_revenue_impact",
            ],
            highlight_field="excess_over_limit",
        )

    # ------------------------------------------------------
    def _sheet_utilization(self):
        ws = self.wb.create_sheet("৫. প্রাপ্যতা ব্যবহার")
        _style_title(
            ws, 1, "প্রাপ্যতা ব্যবহারের বিবরণী", len(COLS_UTIL),
            "প্রতিটি প্রাপ্যতা-এককের বিপরীতে প্রকৃত আমদানি ও অবশিষ্ট প্রাপ্যতা। "
            "ক্লাস্টারের ক্ষেত্রে অন্তর্ভুক্ত সকল কাঁচামালের সমষ্টি দেখানো হইয়াছে।"
        )
        _write_table(
            ws, 4, COLS_UTIL, self.result.utilization_records,
            total_fields=["entitled_quantity", "imported_quantity", "balance_quantity"],
        )

    # ------------------------------------------------------
    def _sheet_machinery(self):
        ws = self.wb.create_sheet("৬. মেশিনারিজ")
        _style_title(
            ws, 1, "মেশিনারিজ ও যন্ত্রাংশ (আপত্তির বাইরে)", len(COLS_MACHINERY),
            "প্রাপ্যতা শীটে অন্তর্ভুক্ত না থাকিলেও মূলধনী যন্ত্রপাতি ও যন্ত্রাংশ "
            "অননুমোদিত আমদানি হিসেবে গণ্য হয় নাই। তবে সংশ্লিষ্ট অনুমোদন ও "
            "এসআরও সুবিধার শর্ত পৃথকভাবে যাচাই করা প্রয়োজন।"
        )
        _write_table(
            ws, 4, COLS_MACHINERY, self.result.machinery_records,
            total_fields=["total_value_usd", "total_value_bdt", "duty_paid", "vat_paid"],
        )

    # ------------------------------------------------------
    def _sheet_review(self):
        """৬. যাচাই প্রয়োজন — কম আস্থার মিল ও মিলবিহীন সারি"""
        ws = self.wb.create_sheet("৭. যাচাই প্রয়োজন")
        rows = self.result.low_confidence_matches
        ncols = max(len(rows[0]) if rows else 0, 3)

        _style_title(
            ws, 1, "নিরীক্ষকের যাচাই প্রয়োজন", ncols,
            "যে সকল আমদানি সারি প্রাপ্যতার সহিত মিলাইতে গিয়া ইঞ্জিনের আস্থা "
            "৮০%-এর নিচে ছিল। নিরীক্ষক কর্তৃক হাতে যাচাই করা বাঞ্ছনীয়।"
        )

        if not rows:
            ws.cell(row=4, column=1, value="— সকল মিলকরণ উচ্চ আস্থাসম্পন্ন ছিল —")
            ws.cell(row=4, column=1).font = Font(
                name=FONT_NAME, size=10, italic=True, color="008000"
            )
            return

        headers = list(rows[0].keys())
        for i, h in enumerate(headers, start=1):
            c = ws.cell(row=4, column=i, value=h)
            c.font = Font(name=FONT_NAME, size=9, bold=True, color=C_HEADER_FG)
            c.fill = PatternFill("solid", fgColor=C_HEADER_BG)
            c.alignment = Alignment(horizontal="center", wrap_text=True)
            c.border = BORDER_ALL
            ws.column_dimensions[get_column_letter(i)].width = 26
        ws.row_dimensions[4].height = 32

        for r, row in enumerate(rows, start=5):
            for i, h in enumerate(headers, start=1):
                c = ws.cell(row=r, column=i, value=row.get(h, ""))
                c.font = Font(name=FONT_NAME, size=9)
                c.alignment = Alignment(vertical="top", wrap_text=True)
                c.border = BORDER_ALL
        ws.freeze_panes = "A5"

    # ------------------------------------------------------
    def _sheet_notes(self):
        """৮. সতর্কতা ও টীকা"""
        ws = self.wb.create_sheet("৮. সতর্কতা ও টীকা")
        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 130

        _style_title(ws, 1, "ইঞ্জিনের সতর্কতা, অনুমান ও টীকা", 2)

        r = 4
        sections = [
            ("ফাইল প্রক্রিয়াকরণ সংক্রান্ত টীকা", self.meta.get("loader_notes", [])),
            ("বিশ্লেষণকালীন সতর্কতা", self.result.warnings),
        ]
        for title, items in sections:
            if not items:
                continue
            ws.cell(row=r, column=2, value=title).font = Font(
                name=FONT_NAME, size=11, bold=True, color="1F3864"
            )
            r += 1
            for it in items:
                ws.cell(row=r, column=1, value="▸").font = Font(name=FONT_NAME, size=9)
                c = ws.cell(row=r, column=2, value=str(it))
                c.font = Font(name=FONT_NAME, size=9)
                c.alignment = Alignment(wrap_text=True, vertical="top")
                # রঙ দিয়ে গুরুত্ব বোঝাও
                txt = str(it)
                if txt.startswith("⛔"):
                    c.fill = PatternFill("solid", fgColor=C_CRITICAL)
                elif txt.startswith("⚠"):
                    c.fill = PatternFill("solid", fgColor=C_WARNING)
                elif txt.startswith("✓"):
                    c.fill = PatternFill("solid", fgColor=C_OK)
                r += 1
            r += 1

        # --- পদ্ধতিগত টীকা ---
        ws.cell(row=r, column=2, value="শুল্কায়ন পদ্ধতি").font = Font(
            name=FONT_NAME, size=11, bold=True, color="1F3864"
        )
        r += 1
        method_notes = [
            "অননুমোদিত এইচ.এস কোড: সংশ্লিষ্ট আমদানির সম্পূর্ণ অংশে বন্ড সুবিধা "
            "বাতিল করিয়া বিল অব এন্ট্রিতে উল্লিখিত সম্পূর্ণ শুল্ক-কর দাবি।",
            "প্রাপ্যতার অতিরিক্ত আমদানি: তারিখক্রমে (FIFO) প্রাপ্যতা পূরণের পর "
            "যে বিলসমূহে সীমা অতিক্রম হইয়াছে, সেই বিলের অতিরিক্ত অংশের অনুপাতে "
            "সংশ্লিষ্ট শুল্ক-কর দাবি।",
            "বন্ডিং ক্যাপাসিটি: প্রারম্ভিক জের বাদ দিয়া অবশিষ্ট ধারণক্ষমতার "
            "অতিরিক্ত প্রবেশের অনুপাতে শুল্ক-কর দাবি।",
            "স্থানীয় ক্রয়: উপরোক্ত যে কোনো একটি লঙ্ঘিত হইলে ক্রয়মূল্যের উপর "
            "১৫% হারে উৎসে মূসক দাবি।",
            "করহারের ক্যাসকেড: এসডি ভিত্তি = শুল্কায়িত মূল্য + সিডি + আরডি; "
            "মূসক ভিত্তি = শুল্কায়িত মূল্য + সিডি + আরডি + এসডি।",
            "যেখানে এমআইএস/বিল অব এন্ট্রিতে প্রকৃত শুল্ক-করের অঙ্ক পাওয়া গিয়াছে "
            "সেখানে তাহাই ব্যবহৃত; না পাওয়া গেলে করহার হইতে গণনা করা হইয়াছে "
            "(প্রতিটি সারির 'শুল্কায়নের ভিত্তি' কলামে উল্লেখ আছে)।",
        ]
        for note in method_notes:
            ws.cell(row=r, column=1, value="▸").font = Font(name=FONT_NAME, size=9)
            c = ws.cell(row=r, column=2, value=note)
            c.font = Font(name=FONT_NAME, size=9)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            r += 1

        ws.sheet_view.showGridLines = False


# ==========================================================
# সুবিধাজনক ফাংশন
# ==========================================================

def write_report(result, out_path: str | Path, meta: dict | None = None) -> Path:
    """দ্রুত প্রতিবেদন তৈরির শর্টকাট"""
    return ExcelReportWriter(result, meta).write(out_path)


__all__ = ["ExcelReportWriter", "write_report"]
