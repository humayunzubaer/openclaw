"""C5 — বিদ্যুৎ-উৎপাদন সামঞ্জস্য যাচাই টেস্ট (plain script)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.electricity_consistency import (
    check_electricity_consistency,
    detect_frozen_note,
    DEFAULT_THRESHOLD_PCT,
)

fails = []


def ok(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        fails.append(msg)


print("== C5: patch-notes নমুনা — ঘোষিত ৳৪.০০ বনাম প্রকৃত ৳৫.২০/কেজি = +৩০% ==")
# প্রকৃত হার ৳৫.২০/কেজি: মোট ৫২,০০০ ÷ ১০,০০০ একক
r = check_electricity_consistency(
    declared_rate_per_unit=4.00, total_electricity_cost=52000.0, produced_units=10000.0,
)
ok(abs(r.actual_rate_per_unit - 5.20) < 1e-6, f"প্রকৃত হার = ৳{r.actual_rate_per_unit}/কেজি (expect 5.20)")
ok(abs(r.deviation_pct - 30.0) < 1e-6, f"বিচ্যুতি = {r.deviation_pct}% (expect +30)")
ok(not r.within_tolerance, "±১৫% সীমা অতিক্রান্ত → flagged")
ok(r.direction == "স্ফীত", f"দিক = {r.direction} (expect স্ফীত)")
ok(r.certainty == "【E】", "certainty = 【E】 (আইনি দাবি নয়)")

print("== সীমার মধ্যে — ঘোষিত ৳৫.০০ বনাম প্রকৃত ৳৫.৩০ (+৬%) ==")
r2 = check_electricity_consistency(
    declared_rate_per_unit=5.00, total_electricity_cost=53000.0, produced_units=10000.0,
)
ok(r2.within_tolerance, f"বিচ্যুতি {r2.deviation_pct}% ±১৫%-এর মধ্যে")
ok(r2.direction == "সঙ্গতিপূর্ণ", f"দিক = {r2.direction}")

print("== হ্রাস দিক — প্রকৃত < ঘোষিত (−৪০%) ==")
r3 = check_electricity_consistency(
    declared_rate_per_unit=5.00, total_electricity_cost=30000.0, produced_units=10000.0,
)
ok(not r3.within_tolerance and r3.direction == "হ্রাস", f"দিক = {r3.direction}, বিচ্যুতি {r3.deviation_pct}%")

print("== নিরীক্ষক-নির্ধারিত থ্রেশহোল্ড পরিবর্তনযোগ্য (SRO নয়) ==")
r4 = check_electricity_consistency(4.00, 52000.0, 10000.0, threshold_pct=35.0)
ok(r4.within_tolerance, "৩৫% সহনসীমা দিলে +৩০% এখন সীমার মধ্যে (নিরীক্ষক-নিয়ন্ত্রিত)")
ok(DEFAULT_THRESHOLD_PCT == 15.0, "default সহনসীমা ১৫% (সূচনা-বিন্দু)")

print("== guard: উৎপাদন ০ / ঘোষিত হার ০ → warning, crash নয় ==")
r5 = check_electricity_consistency(4.00, 52000.0, 0.0)
ok(len(r5.warnings) >= 1, "produced_units=0 → warning")
r6 = check_electricity_consistency(0.0, 52000.0, 10000.0)
ok(len(r6.warnings) >= 1, "declared_rate=0 → warning")

print("== T-02 frozen-note detector ==")
f_susp = detect_frozen_note([12000, 12000, 12000, 12000, 9000, 12000])
ok(f_susp is not None and f_susp.suspected, "৬ মাসে ৫ বার একই ৳১২,০০০ → frozen সন্দেহ")
f_ok = detect_frozen_note([11000, 12500, 9800, 13200, 10100, 12900])
ok(f_ok is not None and not f_ok.suspected, "ভিন্ন ভিন্ন বিল → frozen সন্দেহ নয়")
f_na = detect_frozen_note([12000, 12000])
ok(f_na is None, "মাস < ৩ → যাচাই সম্ভব নয় (None)")

# frozen-note engine ফলাফলে যুক্ত হয়
r7 = check_electricity_consistency(
    5.00, 60000.0, 10000.0, monthly_costs=[5000, 5000, 5000, 5000, 5000, 5000],
)
ok(r7.frozen_note is not None and r7.frozen_note.suspected, "frozen-note engine result-এ flagged")
ok(any("frozen" in w for w in r7.warnings), "frozen warning summary-তে যুক্ত")

print()
print("RESULT:", "ALL PASS ✅" if not fails else f"❌ {len(fails)} FAIL")
sys.exit(1 if fails else 0)
