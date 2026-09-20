"""
বন্ড (non-garments) মডিউলের সংখ্যাগত ও মেয়াদ-যাচাই স্পেক
(JS src/modules/bond-direct-non-garments.js হইতে পোর্ট)।

শুধু serializable spec — হিসাব services/checks/{numeric,validity}.py-তে check id দিয়ে keyed।
"""

# আইনি-রেফারেন্স ম্যাপ (JS knowledge/bond-legal.js)
BOND_LEGAL_REFS = {
    "customs-act-13": {
        "title": "Customs Act — Warehousing (Bonded Warehouse)",
        "citation": "The Customs Act, Ch. XI (Warehousing) — verify current Act/section",
    },
    "customs-act-21": {
        "title": "Customs Act — Utilization / Drawback",
        "citation": "The Customs Act (Utilization/Drawback) — verify current Act/section",
    },
    "customs-act-156": {
        "title": "Customs Act — Penalty / Recovery",
        "citation": "The Customs Act, Section 156 — verify current Act/section",
    },
    "bwl-rules": {
        "title": "Bonded Warehouse Licensing / বার্ষিক আমদানি-প্রাপ্যতা বিধিমালা",
        "citation": "প্রাসঙ্গিক SRO/বিধি — সর্বশেষ সংশোধনী যাচাই করুন",
    },
}


NUMERIC_CHECKS = [
    {
        "id": "num-entitlement",
        "title": "Entitlement অতিক্রম (আমদানি vs অনুমোদিত)",
        "area": "লাইসেন্স ও Entitlement", "legalRef": "bwl-rules",
        "formula": "অতিরিক্ত = আমদানি − অনুমোদিত entitlement; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
        "inputs": [
            {"key": "approvedEntitlement", "label": "অনুমোদিত annual entitlement / UP", "unit": "একক"},
            {"key": "imported", "label": "প্রকৃত আমদানি", "unit": "একক"},
            {"key": "dutyPerUnit", "label": "শুল্ক-কর / একক", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-be-register-raw",
        "title": "কাঁচামাল আমদানি B/E vs ইন-টু-বন্ড রেজিস্টার",
        "area": "আমদানি বনাম রেকর্ড", "legalRef": "bwl-rules",
        "formula": "পার্থক্য = B/E − রেজিস্টার; কম রেকর্ড × শুল্ক-কর/একক = রাজস্ব",
        "inputs": [
            {"key": "beQty", "label": "কাঁচামাল আমদানি B/E পরিমাণ", "unit": "একক"},
            {"key": "registerQty", "label": "ইন-টু-বন্ড (কাঁচামাল) রেজিস্টার পরিমাণ", "unit": "একক"},
            {"key": "dutyPerUnit", "label": "শুল্ক-কর / একক", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-be-register-machinery",
        "title": "মেশিনারিজ আমদানি B/E vs রেজিস্টার",
        "area": "আমদানি বনাম রেকর্ড", "legalRef": "bwl-rules",
        "formula": "পার্থক্য = B/E − মূলধনী/মেশিনারিজ রেজিস্টার; কম রেকর্ড × শুল্ক-কর/একক = রাজস্ব",
        "inputs": [
            {"key": "beQty", "label": "মেশিনারিজ আমদানি B/E পরিমাণ", "unit": "একক"},
            {"key": "registerQty", "label": "মূলধনী/মেশিনারিজ রেজিস্টার পরিমাণ", "unit": "একক"},
            {"key": "dutyPerUnit", "label": "শুল্ক-কর / একক", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-be-register-sample",
        "title": "Sample আমদানি B/E vs রেজিস্টার",
        "area": "আমদানি বনাম রেকর্ড", "legalRef": "bwl-rules",
        "formula": "পার্থক্য = B/E − Sample রেজিস্টার; কম রেকর্ড × শুল্ক-কর/একক = রাজস্ব",
        "inputs": [
            {"key": "beQty", "label": "Sample আমদানি B/E পরিমাণ", "unit": "একক"},
            {"key": "registerQty", "label": "Sample রেজিস্টার পরিমাণ", "unit": "একক"},
            {"key": "dutyPerUnit", "label": "শুল্ক-কর / একক", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-coefficient",
        "title": "Coefficient অনুযায়ী অতিরিক্ত ব্যবহার",
        "area": "ব্যবহার (Consumption)", "legalRef": "bwl-rules",
        "formula": "অনুমোদিত = উৎপাদন × coefficient; অতিরিক্ত = প্রকৃত − অনুমোদিত; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
        "inputs": [
            {"key": "finishedProduced", "label": "উৎপাদিত পণ্য (Finished)", "unit": "একক"},
            {"key": "coeffPerUnit", "label": "অনুমোদিত coefficient (কাঁচামাল/একক পণ্য)", "unit": ""},
            {"key": "actualConsumed", "label": "প্রকৃত কাঁচামাল ব্যবহার", "unit": "একক"},
            {"key": "dutyPerRawUnit", "label": "শুল্ক-কর / একক কাঁচামাল", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-ud-export",
        "title": "UD/EP দাবি vs প্রকৃত রপ্তানি (সমন্বয়)",
        "area": "রপ্তানি সমন্বয়", "legalRef": "customs-act-21",
        "formula": "অসমর্থিত = দাবিকৃত − রপ্তানি-সমর্থিত; × শুল্ক-কর/একক = রাজস্ব (ইপিজেড হলে EP/Sales Contract)",
        "inputs": [
            {"key": "udClaimedRaw", "label": "UD/EP/Sales Contract-এ দাবিকৃত ব্যবহার", "unit": "একক"},
            {"key": "exportBackedRaw", "label": "রপ্তানি-সমর্থিত ব্যবহার (Bill of Export)", "unit": "একক"},
            {"key": "dutyPerRawUnit", "label": "শুল্ক-কর / একক কাঁচামাল", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-material-balance",
        "title": "কাঁচামাল Reconciliation (অহিসাবকৃত)",
        "area": "স্টক ও উদ্বৃত্ত", "legalRef": "customs-act-156",
        "formula": "অহিসাবকৃত = (Opening+Import) − (রপ্তানি-ব্যবহার + অপচয় + Closing); ঘাটতি × শুল্ক-কর/একক = রাজস্ব",
        "inputs": [
            {"key": "openingStock", "label": "প্রারম্ভিক মজুদ (Opening)", "unit": "একক"},
            {"key": "imported", "label": "আমদানি (Import)", "unit": "একক"},
            {"key": "consumedForExport", "label": "রপ্তানিতে ব্যবহৃত কাঁচামাল", "unit": "একক"},
            {"key": "wastageAllowedQty", "label": "স্বীকৃত অপচয় পরিমাণ", "unit": "একক", "optional": True},
            {"key": "closingStock", "label": "সমাপনী মজুদ (Closing)", "unit": "একক"},
            {"key": "dutyPerRawUnit", "label": "শুল্ক-কর / একক কাঁচামাল", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-wastage",
        "title": "অপচয় (Wastage) অনুমোদিত হারের বেশি",
        "area": "অপচয় (Wastage)", "legalRef": "bwl-rules",
        "formula": "অনুমোদিত অপচয় = ব্যবহৃত × হার%; অতিরিক্ত = দাবিকৃত − অনুমোদিত; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
        "inputs": [
            {"key": "consumedRaw", "label": "ব্যবহৃত কাঁচামাল", "unit": "একক"},
            {"key": "allowedWastagePct", "label": "অনুমোদিত অপচয় হার", "unit": "%"},
            {"key": "declaredWastageQty", "label": "দাবিকৃত অপচয়", "unit": "একক"},
            {"key": "dutyPerRawUnit", "label": "শুল্ক-কর / একক কাঁচামাল", "unit": "BDT", "optional": True},
        ],
    },
    {
        "id": "num-overstay",
        "title": "মেয়াদোত্তীর্ণ কাঁচামাল (Overstay)",
        "area": "স্টক ও উদ্বৃত্ত", "legalRef": "bwl-rules",
        "formula": "রাজস্ব = মেয়াদোত্তীর্ণ পরিমাণ × শুল্ক-কর/একক (working default >২ বছর — gazette অপেক্ষমাণ)",
        "inputs": [
            {"key": "overstayQty", "label": "মেয়াদোত্তীর্ণ (>২ বছর) পরিমাণ", "unit": "একক"},
            {"key": "dutyPerRawUnit", "label": "শুল্ক-কর / একক কাঁচামাল", "unit": "BDT", "optional": True},
        ],
    },
]


VALIDITY_CHECKS = [
    {
        "id": "val-license-expiry",
        "title": "বন্ড লাইসেন্স মেয়াদ",
        "area": "লাইসেন্স ও Entitlement", "legalRef": "customs-act-13",
        "formula": "লাইসেন্স মেয়াদ vs নিরীক্ষা তারিখ — উত্তীর্ণ (high) বা ≤৯০ দিন (medium) হলে flag",
        "inputs": [
            {"key": "licenseExpiry", "label": "লাইসেন্স মেয়াদ শেষ", "type": "date"},
            {"key": "asOf", "label": "নিরীক্ষা তারিখ (as-of)", "type": "date", "optional": True},
        ],
    },
    {
        "id": "val-up-coverage",
        "title": "UP/UD মেয়াদে লেনদেন",
        "area": "লাইসেন্স ও Entitlement", "legalRef": "bwl-rules",
        "formula": "লেনদেন (B/E/রপ্তানি) তারিখ UP/UD/EP বৈধতার (from–to) মধ্যে কি",
        "inputs": [
            {"key": "upValidFrom", "label": "UP/UD/EP বৈধ শুরু", "type": "date"},
            {"key": "upValidTo", "label": "UP/UD/EP বৈধ শেষ", "type": "date"},
            {"key": "transactionDate", "label": "লেনদেন (B/E/রপ্তানি) তারিখ", "type": "date"},
        ],
    },
    {
        "id": "val-hs-entitlement",
        "title": "HS code entitlement",
        "area": "লাইসেন্স ও Entitlement", "legalRef": "customs-act-13",
        "formula": "আমদানিকৃত প্রতিটি HS code অনুমোদিত entitlement তালিকায় আছে কি",
        "inputs": [
            {"key": "entitledHs", "label": "অনুমোদিত HS code (কমা/স্পেস)", "type": "text"},
            {"key": "importedHs", "label": "আমদানিকৃত HS code (কমা/স্পেস)", "type": "text"},
        ],
    },
]

__all__ = ["NUMERIC_CHECKS", "VALIDITY_CHECKS", "BOND_LEGAL_REFS"]
