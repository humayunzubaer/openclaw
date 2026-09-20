"""
C3 — বন্ড লাইসেন্স = তৃতীয় ক্যাপাসিটি উৎস regression test.

চালান:  python3 tests/test_bond_license_capacity_c3.py

যাচাই করে:
  • বন্ড লাইসেন্সের ধারণক্ষমতা দেওয়া থাকিলে তাহাই চূড়ান্ত (মাপ/প্রদত্ত থাকিলেও)
  • লাইসেন্স ও মাপ ভিন্ন হইলে সতর্কতা যুক্ত হয় (মান লাইসেন্সেরটিই থাকে)
  • লাইসেন্স নাই → পূর্বের আচরণ অক্ষত (measured / given / missing)
  • regime: পুরাতন → min(প্রাপ্যতা÷৩, লাইসেন্স); নূতন → লাইসেন্স
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.capacity_ledger import (
    compute_warehouse_capacity, compute_one_time_capacity, KG_PER_MT,
)

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


print("CASE 1 — bond license only")
wc = compute_warehouse_capacity(bond_license_capacity_mt=3400.0)
check("source == bond_license", wc.source == "bond_license")
check("capacity == 3400", abs(wc.capacity_mt - 3400.0) < 1e-6)
check("bond_license_mt recorded", abs(wc.bond_license_mt - 3400.0) < 1e-6)

print("CASE 2 — bond license wins over differing warehouse dims (+warning)")
# 100x100x100 = 1,000,000 cft → measured ≈ (900000/1360)*12 ≈ 7941 MT (≠ 3400)
wc = compute_warehouse_capacity(length_ft=100, width_ft=100, height_ft=100,
                                bond_license_capacity_mt=3400.0)
check("source == bond_license (license priority)", wc.source == "bond_license")
check("capacity == 3400 (not measured)", abs(wc.capacity_mt - 3400.0) < 1e-6)
check("warning about differing value present", "ভিন্ন মান" in wc.formula and "যাচাই" in wc.formula)

print("CASE 3 — bond license matches dims → no warning")
# choose dims so measured ≈ license. measured = (V*0.9/1360)*12. For 3400 MT:
# V*0.9/1360*12 = 3400 → V = 3400*1360/(0.9*12) = 428,148 cft
wc = compute_warehouse_capacity(volume_cft=428148.0, bond_license_capacity_mt=3400.0)
check("source == bond_license", wc.source == "bond_license")
check("no warning when values agree", "ভিন্ন মান" not in wc.formula)

print("CASE 4 — no license, dims only → measured (unchanged behavior)")
wc = compute_warehouse_capacity(length_ft=100, width_ft=100, height_ft=100)
check("source == measured", wc.source == "measured")
check("capacity > 0", wc.capacity_mt > 0)

print("CASE 5 — no license, given only → given (unchanged behavior)")
wc = compute_warehouse_capacity(given_capacity_mt=972.80)
check("source == given", wc.source == "given")
check("capacity == 972.80", abs(wc.capacity_mt - 972.80) < 1e-6)

print("CASE 6 — nothing provided → missing")
wc = compute_warehouse_capacity()
check("source == missing", wc.source == "missing")
check("capacity == 0", wc.capacity_mt == 0)

print("CASE 7 — regime integration with license-sourced capacity")
# entitlement 1,411,085 kg; /3 = 470,361.67 kg; license 3400 MT = 3,400,000 kg
ent_kg = 1_411_085.0
lic = compute_warehouse_capacity(bond_license_capacity_mt=3400.0)
old = compute_one_time_capacity(ent_kg, 0.0, lic.capacity_kg, regime="old")
check("old regime → min(ent/3, license) = ent/3",
      abs(old.capacity_kg - ent_kg / 3) < 1 and old.binding_constraint == "প্রাপ্যতার এক-তৃতীয়াংশ")
new = compute_one_time_capacity(ent_kg, 0.0, lic.capacity_kg, regime="new")
check("new regime → license capacity",
      abs(new.capacity_kg - 3400.0 * KG_PER_MT) < 1)

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
sys.exit(0 if _all_ok else 1)
