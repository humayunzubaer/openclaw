"""
বাস্তবসম্মত নোংরা অডিট ফাইল তৈরি করে Excel Engine পরীক্ষার জন্য।
"""
import openpyxl
from openpyxl.styles import Font, Alignment
from pathlib import Path

OUT = Path(__file__).parent / "sample_audit_file.xlsx"

wb = openpyxl.Workbook()

# ============ Sheet 1: Entitlement (নোংরা হেডার) ============
ws = wb.active
ws.title = "Entitlement Annexure-A"

ws["A1"] = "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার"
ws["A2"] = "কাস্টমস বন্ড কমিশনারেট, ঢাকা"
ws["A3"] = "ABC Garments Ltd. — Bond License No: DHK/BOND/1234"
ws["A4"] = "Annual Entitlement for the year 2023-24"
ws["A5"] = ""

headers = ["SL. No", "H.S. Code", "Description of Goods", "Commercial Description",
           "Approved Qty", "Unit", "Unit Price (USD)", "Total Value (USD)", "CD %", "VAT %"]
for i, h in enumerate(headers, start=1):
    c = ws.cell(row=6, column=i, value=h)
    c.font = Font(bold=True)

rows = [
    [1, "5208.11.00", "Woven Fabrics of Cotton, Unbleached", "Grey Cotton Fabric", 150000, "YDS", 1.85, 277500, 5, 15],
    [2, "5407.61.00", "Woven Fabrics of Polyester Filament", "PE Woven Fabric", 220000, "YDS", 1.20, 264000, 5, 15],
    [3, "5402.33.00", "Textured Yarn of Polyester", "Poly Textured Yarn", 45000, "KG", 2.40, 108000, 5, 15],
    [4, "5806.32.00", "Narrow Woven Fabrics of Man-made Fibre", "Elastic Tape", 80000, "MTR", 0.15, 12000, 10, 15],
    [5, "9606.21.00", "Buttons of Plastics", "Plastic Button", 2500000, "PCS", 0.012, 30000, 10, 15],
    [6, "4819.10.00", "Cartons, Boxes of Corrugated Paper", "Export Carton", 65000, "PCS", 0.45, 29250, 15, 15],
    [7, "3919.10.00", "Self-adhesive Plates of Plastics", "Adhesive Tape", 12000, "PCS", 0.85, 10200, 10, 15],
    [8, "5401.10.00", "Sewing Thread of Synthetic Filaments", "Poly Sewing Thread", 18000, "KG", 3.10, 55800, 5, 15],
]
r = 7
for row in rows:
    for i, v in enumerate(row, start=1):
        ws.cell(row=r, column=i, value=v)
    r += 1

ws.cell(row=r, column=3, value="Total").font = Font(bold=True)
ws.cell(row=r, column=8, value=786750).font = Font(bold=True)

ws.merge_cells("A1:J1")
ws.merge_cells("A2:J2")

# ============ Sheet 2: AIS Import Data ============
ws2 = wb.create_sheet("AIS Import IM-4")
ws2["A1"] = "AIS Import Statement — 01/07/2023 to 30/06/2024"

h2 = ["Sl", "B/E No", "B/E Date", "Type", "HS Code", "Item Description",
      "Qty", "UOM", "Unit Price", "CIF Value (USD)", "Exchange Rate",
      "Assessable Value BDT", "CD Paid", "VAT Paid", "Supplier", "Country of Origin"]
for i, h in enumerate(h2, start=1):
    ws2.cell(row=3, column=i, value=h).font = Font(bold=True)

imports = [
    [1, "C-102345", "12/07/2023", "IM-4", "5208.11.00", "Grey Cotton Fabric", 45000, "YDS", 1.85, 83250, 108.50, 9032625, 451631, 1422638, "Zhejiang Textile Co", "China"],
    [2, "C-102876", "28/07/2023", "IM-4", "5407.61.00", "PE Woven Fabric", 68000, "YDS", 1.22, 82960, 108.50, 9001160, 450058, 1417681, "Jiangsu Fabrics", "China"],
    [3, "C-103455", "15/08/2023", "IM-4", "5402.33.00", "Polyester Textured Yarn", 15000, "KG", 2.45, 36750, 109.00, 4005750, 200288, 630906, "Suzhou Yarn Ltd", "China"],
    [4, "C-104120", "03/09/2023", "IM-4", "9606.21.00", "Plastic Button Assorted", 850000, "PCS", 0.013, 11050, 109.20, 1206660, 120666, 199099, "Ningbo Button Mfg", "China"],
    [5, "C-104899", "22/09/2023", "IM-4", "5208.11.00", "Cotton Grey Fabric", 52000, "YDS", 1.90, 98800, 109.50, 10818600, 540930, 1703865, "Zhejiang Textile Co", "China"],
    # অননুমোদিত HS — Entitlement এ নেই
    [6, "C-105677", "11/10/2023", "IM-4", "6006.32.00", "Knitted Fabric Dyed", 30000, "KG", 3.50, 105000, 110.00, 11550000, 577500, 1819125, "Guangdong Knit", "China"],
    [7, "C-106234", "05/11/2023", "IM-4", "4819.10.00", "Corrugated Export Carton", 42000, "PCS", 0.46, 19320, 110.20, 2129064, 319360, 367264, "Local Pack BD", "Bangladesh"],
    [8, "C-107001", "19/12/2023", "IM-4", "5401.10.00", "Sewing Thread Polyester", 9500, "KG", 3.15, 29925, 110.50, 3306713, 165336, 520807, "Coats Thread", "India"],
    # অতিরিক্ত আমদানি — approved 150000, মোট হবে 165000
    [9, "C-108445", "14/02/2024", "IM-4", "5208.11.00", "Grey Cotton Fabric Unbleached", 68000, "YDS", 1.88, 127840, 111.00, 14190240, 709512, 2234813, "Zhejiang Textile Co", "China"],
    [10, "C-109233", "22/03/2024", "IM-7", "5806.32.00", "Elastic Tape Narrow", 35000, "MTR", 0.16, 5600, 111.50, 624400, 62440, 103026, "Foshan Elastic", "China"],
    [11, "C-110002", "18/04/2024", "IM-4", "3919.10.00", "Adhesive Tape Roll", 5500, "PCS", 0.88, 4840, 112.00, 542080, 54208, 89443, "Shanghai Tape", "China"],
    [12, "C-110877", "09/05/2024", "IM-4", "5407.61.00", "Polyester Woven Fabric", 91000, "YDS", 1.25, 113750, 112.30, 12774125, 638706, 2011700, "Jiangsu Fabrics", "China"],
]
r = 4
for row in imports:
    for i, v in enumerate(row, start=1):
        ws2.cell(row=r, column=i, value=v)
    r += 1

ws2.cell(row=r, column=6, value="Grand Total").font = Font(bold=True)
ws2.cell(row=r, column=10, value=719085).font = Font(bold=True)

# ============ Sheet 3: Hidden Sheet ============
ws3 = wb.create_sheet("Internal Notes")
ws3["A1"] = "Internal working sheet"
ws3["A2"] = "HS Code"
ws3["B2"] = "Remarks"
ws3["A3"] = "6006.32.00"
ws3["B3"] = "Not in entitlement - check"
ws3.sheet_state = "hidden"

wb.save(OUT)
print(f"✅ তৈরি হয়েছে: {OUT}")
