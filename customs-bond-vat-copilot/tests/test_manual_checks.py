"""
সংখ্যাগত ও মেয়াদ-যাচাই ইঞ্জিনের behavior test — JS test (numeric.test.js /
validity.test.js) হইতে পোর্ট, একই সংখ্যা যাচাই।

চালান:  python3 tests/test_manual_checks.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.checks.numeric import run_numeric_checks, result_to_finding
from services.checks.validity import run_validity_checks, validity_result_to_finding
from knowledge.check_specs import NUMERIC_CHECKS, VALIDITY_CHECKS

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def num(inputs):
    return {r["id"]: r for r in run_numeric_checks(NUMERIC_CHECKS, inputs)["results"]}


def val(inputs):
    return {r["id"]: r for r in run_validity_checks(VALIDITY_CHECKS, inputs)["results"]}


print("NUMERIC")
r = num({"num-entitlement": {"approvedEntitlement": 1000, "imported": 1200, "dutyPerUnit": 50}})["num-entitlement"]
check("entitlement breach → flag/high/disc200/rev10000",
      r["status"] == "flag" and r["severity"] == "high" and r["discrepancy"] == 200 and r["revenue_implication"] == 10000)

r = num({"num-entitlement": {"approvedEntitlement": 1000, "imported": 900, "dutyPerUnit": 50}})["num-entitlement"]
check("entitlement within → ok/rev0", r["status"] == "ok" and r["revenue_implication"] == 0)

r = num({"num-be-register-raw": {"beQty": 1000, "registerQty": 850, "dutyPerUnit": 30}})["num-be-register-raw"]
check("be-register raw under → high/disc150/rev4500",
      r["status"] == "flag" and r["severity"] == "high" and r["discrepancy"] == 150 and r["revenue_implication"] == 4500)

r = num({"num-be-register-raw": {"beQty": 800, "registerQty": 900, "dutyPerUnit": 30}})["num-be-register-raw"]
check("be-register raw over → medium/rev0", r["status"] == "flag" and r["severity"] == "medium" and r["revenue_implication"] == 0)

r = num({"num-be-register-raw": {"beQty": 900, "registerQty": 900, "dutyPerUnit": 30}})["num-be-register-raw"]
check("be-register raw exact → ok", r["status"] == "ok")

rr = num({"num-be-register-machinery": {"beQty": 5, "registerQty": 4, "dutyPerUnit": 100000},
          "num-be-register-sample": {"beQty": 20, "registerQty": 20, "dutyPerUnit": 5}})
check("machinery flag rev100000", rr["num-be-register-machinery"]["status"] == "flag" and rr["num-be-register-machinery"]["revenue_implication"] == 100000)
check("sample ok", rr["num-be-register-sample"]["status"] == "ok")

r = num({"num-ud-export": {"udClaimedRaw": 500, "exportBackedRaw": 420, "dutyPerRawUnit": 15}})["num-ud-export"]
check("ud-export → disc80/rev1200", r["status"] == "flag" and r["discrepancy"] == 80 and r["revenue_implication"] == 1200)

r = num({"num-ud-export": {"udClaimedRaw": 400, "exportBackedRaw": 400, "dutyPerRawUnit": 15}})["num-ud-export"]
check("ud-export supported → ok", r["status"] == "ok")

r = num({"num-coefficient": {"finishedProduced": 100, "coeffPerUnit": 2, "actualConsumed": 250, "dutyPerRawUnit": 10}})["num-coefficient"]
check("coefficient → disc50/rev500", r["status"] == "flag" and r["discrepancy"] == 50 and r["revenue_implication"] == 500)

r = num({"num-material-balance": {"openingStock": 100, "imported": 1000, "consumedForExport": 700,
                                  "wastageAllowedQty": 50, "closingStock": 200, "dutyPerRawUnit": 20}})["num-material-balance"]
check("material-balance shortage → high/disc150/rev3000",
      r["status"] == "flag" and r["severity"] == "high" and r["discrepancy"] == 150 and r["revenue_implication"] == 3000)

r = num({"num-material-balance": {"openingStock": 0, "imported": 1000, "consumedForExport": 900,
                                  "wastageAllowedQty": 50, "closingStock": 50, "dutyPerRawUnit": 20}})["num-material-balance"]
check("material-balance exact → ok", r["status"] == "ok")

r = num({"num-material-balance": {"openingStock": 0, "imported": 1000, "consumedForExport": 1100,
                                  "closingStock": 0, "dutyPerRawUnit": 20}})["num-material-balance"]
check("material-balance over-accounting → medium/rev0", r["status"] == "flag" and r["severity"] == "medium" and r["revenue_implication"] == 0)

r = num({"num-wastage": {"consumedRaw": 1000, "allowedWastagePct": 5, "declaredWastageQty": 80, "dutyPerRawUnit": 10}})["num-wastage"]
check("wastage → disc30/rev300", r["discrepancy"] == 30 and r["revenue_implication"] == 300)

r = num({"num-overstay": {"overstayQty": 40, "dutyPerRawUnit": 25}})["num-overstay"]
check("overstay → medium/rev1000", r["status"] == "flag" and r["severity"] == "medium" and r["revenue_implication"] == 1000)

r = num({"num-entitlement": {"imported": 1200}})["num-entitlement"]
check("missing required → insufficient", r["status"] == "insufficient")

r = num({"num-entitlement": {"approvedEntitlement": 1000, "imported": 1200}})["num-entitlement"]
check("duty omitted → flag/disc200/rev0", r["status"] == "flag" and r["discrepancy"] == 200 and r["revenue_implication"] == 0)

summ = run_numeric_checks(NUMERIC_CHECKS, {
    "num-entitlement": {"approvedEntitlement": 1000, "imported": 1200, "dutyPerUnit": 50},
    "num-overstay": {"overstayQty": 40, "dutyPerRawUnit": 25},
    "num-coefficient": {"finishedProduced": 100, "coeffPerUnit": 2, "actualConsumed": 150, "dutyPerRawUnit": 10},
})["summary"]
check("summary flagged=2 totalRevenue=11000 (only flagged count)", summ["flagged"] == 2 and summ["totalRevenue"] == 11000)

f = result_to_finding(num({"num-overstay": {"overstayQty": 40, "dutyPerRawUnit": 25}})["num-overstay"])
check("result_to_finding → rev1000/bwl-rules/source numeric",
      f["revenueImplication"] == 1000 and f["legalRef"] == "bwl-rules" and f["source"] == "numeric")

print("VALIDITY")
r = val({"val-license-expiry": {"licenseExpiry": "2020-01-01", "asOf": "2024-01-01"}})["val-license-expiry"]
check("license expired → high", r["status"] == "flag" and r["severity"] == "high" and r["detail"]["daysOverdue"] > 0)

r = val({"val-license-expiry": {"licenseExpiry": "2024-03-01", "asOf": "2024-01-15"}})["val-license-expiry"]
check("license ≤90 days → medium", r["status"] == "flag" and r["severity"] == "medium")

r = val({"val-license-expiry": {"licenseExpiry": "2030-01-01", "asOf": "2024-01-01"}})["val-license-expiry"]
check("license valid → ok", r["status"] == "ok")

r = val({"val-license-expiry": {"asOf": "2024-01-01"}})["val-license-expiry"]
check("license missing date → insufficient", r["status"] == "insufficient")

r = val({"val-up-coverage": {"upValidFrom": "2024-01-01", "upValidTo": "2024-12-31", "transactionDate": "2025-02-01"}})["val-up-coverage"]
check("txn outside UP → high", r["status"] == "flag" and r["severity"] == "high")

r = val({"val-up-coverage": {"upValidFrom": "2024-01-01", "upValidTo": "2024-12-31", "transactionDate": "2024-06-15"}})["val-up-coverage"]
check("txn within UP → ok", r["status"] == "ok")

r = val({"val-hs-entitlement": {"entitledHs": "5208.11, 5208.12", "importedHs": "5208.11 6109.10"}})["val-hs-entitlement"]
check("HS outside → flag lists 6109.10", r["status"] == "flag" and r["detail"]["outside"] == ["6109.10"])

r = val({"val-hs-entitlement": {"entitledHs": "5208.11 5208.12 6109.10", "importedHs": "5208.11, 6109.10"}})["val-hs-entitlement"]
check("all HS entitled → ok", r["status"] == "ok")

f = validity_result_to_finding(val({"val-license-expiry": {"licenseExpiry": "2020-01-01", "asOf": "2024-01-01"}})["val-license-expiry"])
check("validity finding → rev0/source validity/lic-validity",
      f["revenueImplication"] == 0 and f["source"] == "validity" and f["checklistId"] == "lic-validity")

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
sys.exit(0 if _all_ok else 1)
