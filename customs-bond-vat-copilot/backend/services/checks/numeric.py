"""
সংখ্যাগত auto-check ইঞ্জিন — বন্ড অডিটের reconciliation (JS src/checks/numeric.js হইতে পোর্ট)।

নীতি (নিরীক্ষক-নির্ধারিত):
  • প্রতিটি চেক দ্বিমুখী — ঘাটতি (রাজস্ব দাবি) ও over-recording (রেকর্ড অসঙ্গতি, রাজস্ব ০) আলাদা।
  • শুল্ক-ইনপুট ঐচ্ছিক — না দিলে শুধু পরিমাণ-ব্যত্যয়, রাজস্ব ০।
  • ★ দ্বৈত গণনা রোধ: এই উপমোট নিজে থেকে চূড়ান্ত রাজস্ব-মোটে যোগ হয় না; শুধু
    নিরীক্ষক-গৃহীত Finding যোগ হয় (result_to_finding → addFinding)।

প্রতিটি compute একটি values dict নেয় (missing → None), result দেয়:
  { status, severity, discrepancy, unit, revenue_implication, observation, breakdown }
  status: "ok" | "flag" | "insufficient"
"""
from __future__ import annotations

from typing import Any, Callable, Optional


def _r2(n: float) -> float:
    return round(float(n) + 0.0, 2)


def _isnum(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _bdt(n: float) -> str:
    return f"{float(n or 0):,.0f}"


def _q(n: float) -> str:
    return f"{_r2(n):,.2f}"


def _duty(v: dict, key: str) -> float:
    """duty ইনপুট ঐচ্ছিক; না দিলে ০ ধরে শুধু পরিমাণ-ব্যত্যয় দেখায়।"""
    return float(v[key]) if _isnum(v.get(key)) else 0.0


def _ok(severity: str, observation: str, breakdown=None) -> dict:
    return {"status": "ok", "severity": severity or "low", "observation": observation,
            "revenue_implication": 0.0, "breakdown": breakdown}


def _flag(severity: str, discrepancy: float, unit: str, revenue: float,
          observation: str, breakdown=None) -> dict:
    return {"status": "flag", "severity": severity, "discrepancy": _r2(discrepancy),
            "unit": unit, "revenue_implication": _r2(revenue),
            "observation": observation, "breakdown": breakdown}


# ---------------- per-check computers ----------------

def _c_entitlement(v: dict) -> dict:
    excess = v["imported"] - v["approvedEntitlement"]
    if excess <= 0:
        return _ok("low", f"আমদানি {_q(v['imported'])} একক অনুমোদিত entitlement "
                          f"{_q(v['approvedEntitlement'])} একক-এর মধ্যে; breach নেই।")
    rev = excess * _duty(v, "dutyPerUnit")
    return _flag("high", excess, "একক", rev,
                 f"অনুমোদিত entitlement/UP {_q(v['approvedEntitlement'])} একক-এর বিপরীতে "
                 f"আমদানি {_q(v['imported'])} একক — অতিরিক্ত {_q(excess)} একক (entitlement breach)। "
                 f"সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।",
                 [{"label": "অনুমোদিত entitlement", "value": _q(v['approvedEntitlement'])},
                  {"label": "আমদানি", "value": _q(v['imported'])},
                  {"label": "অতিরিক্ত", "value": _q(excess)}])


def _c_coefficient(v: dict) -> dict:
    allowed = v["finishedProduced"] * v["coeffPerUnit"]
    excess = v["actualConsumed"] - allowed
    if excess <= 0:
        return _ok("low", f"উৎপাদন {_q(v['finishedProduced'])} × coefficient {_q(v['coeffPerUnit'])} "
                          f"= অনুমোদিত ব্যবহার {_q(allowed)} একক; প্রকৃত {_q(v['actualConsumed'])} একক — সীমার মধ্যে।")
    rev = excess * _duty(v, "dutyPerRawUnit")
    return _flag("high", excess, "একক", rev,
                 f"উৎপাদন {_q(v['finishedProduced'])} × অনুমোদিত coefficient {_q(v['coeffPerUnit'])} "
                 f"= অনুমোদিত কাঁচামাল {_q(allowed)} একক; প্রকৃত ব্যবহার {_q(v['actualConsumed'])} একক — "
                 f"অতিরিক্ত {_q(excess)} একক। সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।",
                 [{"label": "অনুমোদিত ব্যবহার", "value": _q(allowed)},
                  {"label": "প্রকৃত ব্যবহার", "value": _q(v['actualConsumed'])},
                  {"label": "অতিরিক্ত", "value": _q(excess)}])


def _c_ud_export(v: dict) -> dict:
    unsupported = v["udClaimedRaw"] - v["exportBackedRaw"]
    if unsupported <= 0:
        return _ok("low", f"UD/EP-তে দাবিকৃত ব্যবহার {_q(v['udClaimedRaw'])} একক প্রকৃত রপ্তানি-সমর্থিত "
                          f"{_q(v['exportBackedRaw'])} একক দিয়ে সমর্থিত; ব্যত্যয় নেই।")
    rev = unsupported * _duty(v, "dutyPerRawUnit")
    return _flag("high", unsupported, "একক", rev,
                 f"UD/EP (ইপিজেড হলে EP/Sales Contract)-এ দাবিকৃত ব্যবহার {_q(v['udClaimedRaw'])} একক, "
                 f"কিন্তু রপ্তানি (Bill of Export) দিয়ে সমর্থিত মাত্র {_q(v['exportBackedRaw'])} একক — "
                 f"অসমর্থিত {_q(unsupported)} একক (রপ্তানি ছাড়াই শুল্কমুক্ত ব্যবহার)। "
                 f"সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।",
                 [{"label": "UD/EP দাবি", "value": _q(v['udClaimedRaw'])},
                  {"label": "রপ্তানি-সমর্থিত", "value": _q(v['exportBackedRaw'])},
                  {"label": "অসমর্থিত", "value": _q(unsupported)}])


def _c_material_balance(v: dict) -> dict:
    wastage = float(v["wastageAllowedQty"]) if _isnum(v.get("wastageAllowedQty")) else 0.0
    available = v["openingStock"] + v["imported"]
    accounted = v["consumedForExport"] + wastage + v["closingStock"]
    unaccounted = available - accounted
    bd = [{"label": "প্রাপ্যতা (Opening+Import)", "value": _q(available)},
          {"label": "হিসাবভুক্ত (Export+অপচয়+Closing)", "value": _q(accounted)},
          {"label": "পার্থক্য", "value": _q(unaccounted)}]
    if abs(unaccounted) < 1e-6:
        return _ok("low", f"কাঁচামাল ব্যালেন্স সঠিক: প্রাপ্যতা {_q(available)} = হিসাবভুক্ত "
                          f"{_q(accounted)} একক; ঘাটতি/উদ্বৃত্ত নেই।", bd)
    if unaccounted > 0:
        rev = unaccounted * _duty(v, "dutyPerRawUnit")
        return _flag("high", unaccounted, "একক", rev,
                     f"Opening {_q(v['openingStock'])} + Import {_q(v['imported'])} = {_q(available)} একক; "
                     f"হিসাবভুক্ত (রপ্তানি-ব্যবহার {_q(v['consumedForExport'])} + অপচয় {_q(wastage)} + "
                     f"Closing {_q(v['closingStock'])}) = {_q(accounted)} একক; অহিসাবকৃত ঘাটতি "
                     f"{_q(unaccounted)} একক — সম্ভাব্য শুল্কমুক্ত কাঁচামালের স্থানীয় অপসারণ/বিক্রয়। "
                     f"সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।", bd)
    return _flag("medium", -unaccounted, "একক", 0.0,
                 f"হিসাবভুক্ত পরিমাণ প্রাপ্যতার চেয়ে {_q(-unaccounted)} একক বেশি — রেকর্ডে অসঙ্গতি "
                 f"(over-accounting)। রেজিস্টার যাচাই করুন; স্বয়ংক্রিয় রাজস্ব ধরা হয়নি।", bd)


def _c_wastage(v: dict) -> dict:
    allowed_qty = v["consumedRaw"] * (v["allowedWastagePct"] / 100)
    excess = v["declaredWastageQty"] - allowed_qty
    if excess <= 0:
        return _ok("low", f"অনুমোদিত অপচয় {_q(v['allowedWastagePct'])}% × ব্যবহৃত {_q(v['consumedRaw'])} "
                          f"= {_q(allowed_qty)} একক; দাবিকৃত {_q(v['declaredWastageQty'])} একক — হারের মধ্যে।")
    rev = excess * _duty(v, "dutyPerRawUnit")
    return _flag("high", excess, "একক", rev,
                 f"অনুমোদিত অপচয় হার {_q(v['allowedWastagePct'])}% × ব্যবহৃত {_q(v['consumedRaw'])} "
                 f"= অনুমোদিত অপচয় {_q(allowed_qty)} একক; দাবিকৃত {_q(v['declaredWastageQty'])} একক — "
                 f"অতিরিক্ত {_q(excess)} একক (over-wastage)। সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।",
                 [{"label": "অনুমোদিত অপচয়", "value": _q(allowed_qty)},
                  {"label": "দাবিকৃত অপচয়", "value": _q(v['declaredWastageQty'])},
                  {"label": "অতিরিক্ত", "value": _q(excess)}])


def _c_overstay(v: dict) -> dict:
    if v["overstayQty"] <= 0:
        return _ok("low", "মেয়াদোত্তীর্ণ (২ বছরের বেশি) বন্ডে থাকা কাঁচামাল নেই।")
    rev = v["overstayQty"] * _duty(v, "dutyPerRawUnit")
    return _flag("medium", v["overstayQty"], "একক", rev,
                 f"নির্ধারিত মেয়াদ (working default ২ বছর — gazette citation অপেক্ষমাণ) অতিক্রান্ত বন্ডে "
                 f"থাকা কাঁচামাল {_q(v['overstayQty'])} একক — শুল্ক-কর পরিশোধযোগ্য। "
                 f"সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।",
                 [{"label": "মেয়াদোত্তীর্ণ পরিমাণ", "value": _q(v['overstayQty'])}])


def _be_vs_register(label: str) -> Callable[[dict], dict]:
    def _compute(v: dict) -> dict:
        diff = v["beQty"] - v["registerQty"]
        bd = [{"label": f"{label} B/E আমদানি", "value": _q(v['beQty'])},
              {"label": "রেজিস্টারে লিপিবদ্ধ", "value": _q(v['registerQty'])},
              {"label": "পার্থক্য", "value": _q(diff)}]
        if abs(diff) < 1e-6:
            return _ok("low", f"{label}: B/E {_q(v['beQty'])} একক = রেজিস্টারে লিপিবদ্ধ "
                              f"{_q(v['registerQty'])} একক; মিল আছে।", bd)
        if diff > 0:
            rev = diff * _duty(v, "dutyPerUnit")
            return _flag("high", diff, "একক", rev,
                         f"{label} আমদানি: Bill of Entry অনুযায়ী {_q(v['beQty'])} একক, কিন্তু রেজিস্টারে "
                         f"লিপিবদ্ধ {_q(v['registerQty'])} একক — {_q(diff)} একক রেজিস্টারভুক্ত হয়নি "
                         f"(unrecorded; সম্ভাব্য অপসারণ)। সম্ভাব্য রাজস্ব প্রভাব BDT {_bdt(rev)}।", bd)
        return _flag("medium", -diff, "একক", 0.0,
                     f"{label} আমদানি: রেজিস্টারে লিপিবদ্ধ {_q(v['registerQty'])} একক B/E {_q(v['beQty'])} "
                     f"একক-এর চেয়ে {_q(-diff)} একক বেশি — over-recording/রেকর্ড অসঙ্গতি; যাচাই করুন। "
                     f"স্বয়ংক্রিয় রাজস্ব ধরা হয়নি।", bd)
    return _compute


COMPUTERS: dict[str, Callable[[dict], dict]] = {
    "num-entitlement": _c_entitlement,
    "num-coefficient": _c_coefficient,
    "num-ud-export": _c_ud_export,
    "num-material-balance": _c_material_balance,
    "num-wastage": _c_wastage,
    "num-overstay": _c_overstay,
    "num-be-register-raw": _be_vs_register("কাঁচামাল"),
    "num-be-register-machinery": _be_vs_register("মেশিনারিজ"),
    "num-be-register-sample": _be_vs_register("Sample"),
}


# ---------------- runner ----------------

def _parse_values(spec: dict, raw: Optional[dict]) -> dict:
    raw = raw or {}
    out: dict[str, Any] = {}
    for inp in spec["inputs"]:
        val = raw.get(inp["key"])
        if val in ("", None):
            out[inp["key"]] = None
        else:
            try:
                out[inp["key"]] = float(val)
            except (TypeError, ValueError):
                out[inp["key"]] = None
    return out


def _guard(values: dict, spec: dict) -> Optional[dict]:
    keys = [i["key"] for i in spec["inputs"]]
    if not any(_isnum(values.get(k)) for k in keys):
        return {"status": "insufficient", "reason": "কোনো সংখ্যা দেওয়া হয়নি"}
    missing = [i["label"] for i in spec["inputs"]
               if not i.get("optional") and not _isnum(values.get(i["key"]))]
    if missing:
        return {"status": "insufficient", "reason": "প্রয়োজনীয় তথ্য অনুপস্থিত: " + ", ".join(missing)}
    return None


def run_numeric_checks(specs: list[dict], inputs_by_check: Optional[dict] = None) -> dict:
    """specs + auditor ইনপুট → সব check চালায়।"""
    inputs_by_check = inputs_by_check or {}
    results = []
    for spec in specs:
        base = {"id": spec["id"], "title": spec.get("title", ""), "area": spec.get("area", ""),
                "legalRef": spec.get("legalRef")}
        compute = COMPUTERS.get(spec["id"])
        if not compute:
            results.append({**base, "status": "insufficient", "severity": "low",
                            "observation": "এই check-এর হিসাব এখনো যুক্ত হয়নি।", "revenue_implication": 0.0})
            continue
        values = _parse_values(spec, inputs_by_check.get(spec["id"]))
        g = _guard(values, spec)
        if g:
            results.append({**base, "severity": "low", "revenue_implication": 0.0,
                            "observation": g["reason"], "status": "insufficient"})
            continue
        results.append({**base, **compute(values)})
    flagged = [r for r in results if r["status"] == "flag"]
    total = _r2(sum(float(r.get("revenue_implication") or 0) for r in flagged))
    return {"results": results, "summary": {"flagged": len(flagged), "totalRevenue": total}}


def result_to_finding(result: dict) -> dict:
    """flag হওয়া numeric result → finding payload (source=numeric)।"""
    return {
        "checklistId": None,
        "area": result.get("area", ""),
        "title": result.get("title", ""),
        "observation": result.get("observation", ""),
        "legalRef": result.get("legalRef"),
        "revenueImplication": float(result.get("revenue_implication") or 0),
        "severity": result.get("severity", "medium"),
        "source": "numeric",
    }


__all__ = ["run_numeric_checks", "result_to_finding", "COMPUTERS"]
