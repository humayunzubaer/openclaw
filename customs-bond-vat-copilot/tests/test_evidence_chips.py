"""
Smart Evidence Chip extraction — behavior test (JS evidence.test.js হইতে পোর্ট)।
চালান:  python3 tests/test_evidence_chips.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.checks.evidence import extract_document, scan_documents
from knowledge.check_specs import NUMERIC_CHECKS as NC

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def doc(text, **over):
    return {"id": "doc_1", "filename": "be.pdf", "ocrStatus": "done", "ocrText": text, **over}


def chip_for(chips, v):
    return next((c for c in chips if c["value"] == v), None)


chips = extract_document(doc("Total imported quantity 1,200.50 units under B/E"), NC)["chips"]
c = chip_for(chips, 1200.5)
check("1,200.50 extracted (raw+page)", c and c["raw"] == "1,200.50" and c["page"] == 1)

chips = extract_document(doc("আমদানি পরিমাণ ১২৩৪ একক"), NC)["chips"]
check("Bengali ১২৩৪ → 1234", chip_for(chips, 1234) is not None)

chips = extract_document(doc("Bill of Entry আমদানি 1500 একক"), NC)["chips"]
c = chip_for(chips, 1500)
keys = [s["inputKey"] for s in c["suggestions"]]
check("আমদানি/B/E → imported or beQty suggested", ("imported" in keys or "beQty" in keys) and c["suggestions"][0]["score"] > 0)

chips = extract_document(doc("মেশিনারিজ রেজিস্টার লিপিবদ্ধ 4 একক"), NC)["chips"]
c = chip_for(chips, 4)
top = c["suggestions"][0]
check("machinery context → num-be-register-machinery/registerQty",
      top["checkId"] == "num-be-register-machinery" and top["inputKey"] == "registerQty")

strong = chip_for(extract_document(doc("অপচয় wastage declared ৳ 80 একক"), NC)["chips"], 80)
bare = chip_for(extract_document(doc("page 80"), NC)["chips"], 80)
check("labelled+unit confidence > bare number", strong["confidence"] > bare["confidence"])

chips = extract_document(doc("closing stock সমাপনী মজুদ 200 একক"), NC)["chips"]
c = chips[0]
check("chip carries full provenance",
      all(k in c for k in ["id", "docId", "docFilename", "page", "value", "raw", "offset", "sourceText", "suggestions", "confidence"])
      and c["docFilename"] == "be.pdf" and len(c["sourceText"]) > 0)

chips = extract_document(doc("opening 10 units\fclosing 20 units"), NC)["chips"]
check("page detection via form-feed", chip_for(chips, 10)["page"] == 1 and chip_for(chips, 20)["page"] == 2)

res = scan_documents([doc("imported 100 units", id="d1"),
                      {"id": "d2", "filename": "x.pdf", "ocrStatus": "none", "ocrText": ""}], NC)
check("scan skips docs without OCR", res["scannedDocs"] == 1 and res["totalChips"] >= 1)

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
sys.exit(0 if _all_ok else 1)
