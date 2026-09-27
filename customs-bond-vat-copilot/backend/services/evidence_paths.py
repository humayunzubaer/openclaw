"""
বিকল্প প্রমাণ-পথ — মৌলিক দলিল অনুপস্থিত হইলে করণীয়
======================================================

একজন অভিজ্ঞ নিরীক্ষক দলিল না পাইলে হাত গুটাইয়া বসেন না — তিনি বিকল্প
উৎস হইতে একই সত্য প্রতিষ্ঠা করেন। আবার যেখানে প্রমাণ নাই, সেখানে
**অনুমান করিয়া দাবি করেন না**। এই মডিউল সেই দুইটি সিদ্ধান্তই ধারণ করে —

    (ক) কোন বিকল্প উৎস হইতে কী নির্ণয় করা **যায়** (certainty-হ্রাসসহ)
    (খ) কোন নির্ণয় **যায় না** — সেখানে দাবি নিষিদ্ধ, কেবল দলিল তলব ও
        শর্তভঙ্গের প্রস্তাব

★ মূল নীতি: প্রমাণ নাই ⇒ দাবি নাই। অনুপস্থিত দলিলের কারণে যে যাচাই
  সম্পন্ন করা যায় নাই, তাহা "তথ্য অসম্পূর্ণ" হিসাবে প্রতিবেদনে যাইবে
  এবং প্রস্তাবনায় **দলিল তলব** হিসাবে উপস্থাপিত হইবে — রাজস্ব দাবি
  হিসাবে নহে।
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

from utils.logger import logger


# ==========================================================
# দলিলের সাংকেতিক নাম (ইঞ্জিন-অভ্যন্তরীণ)
# ==========================================================

DOC_REGISTER = "bond_register"          # বন্ড রেজিস্টার (তফসিল-১)
DOC_COEFFICIENT = "coefficient"         # ডিইডিও অনুমোদিত সহগ
DOC_MIS_IMPORT = "mis_import"           # এমআইএস আমদানি বিবরণী
DOC_ENTITLEMENT = "entitlement"         # প্রাপ্যতা শীট / পূর্ব নিরীক্ষা
DOC_UP = "up"                           # ইউটিলাইজেশন পারমিশন
DOC_EXPORT = "export_data"              # রপ্তানি তথ্য (বি/এক্স, এমআইএস)
DOC_CLOSING_STOCK = "closing_stock"     # সমাপনী মজুদ / সরেজমিন
DOC_MUSHAK_43 = "mushak_43"             # উপকরণ-উৎপাদ সহগ ঘোষণা
DOC_MUSHAK_91 = "mushak_91"             # মূসক দাখিলপত্র
DOC_PRC = "prc"                         # প্রত্যাবাসন সনদ
DOC_ELECTRICITY = "electricity"         # বিদ্যুৎ বিল
DOC_MACHINE_LIST = "machine_list"       # লাইসেন্স-সংযোজিত মেশিন তালিকা
DOC_LOCAL_PURCHASE = "local_purchase"   # স্থানীয় সংগ্রহ দলিল

DOC_LABELS: dict[str, str] = {
    DOC_REGISTER: "বন্ড রেজিস্টার (তফসিল-১)",
    DOC_COEFFICIENT: "ডিইডিও অনুমোদিত উপকরণ-উৎপাদ সহগ",
    DOC_MIS_IMPORT: "এমআইএস আমদানি বিবরণী",
    DOC_ENTITLEMENT: "প্রাপ্যতা শীট / পূর্ববর্তী নিরীক্ষা প্রতিবেদন",
    DOC_UP: "ইউটিলাইজেশন পারমিশন (ইউপি)",
    DOC_EXPORT: "রপ্তানি তথ্য (বিল অব এক্সপোর্ট / এমআইএস)",
    DOC_CLOSING_STOCK: "সমাপনী মজুদের হিসাব / সরেজমিন প্রতিবেদন",
    DOC_MUSHAK_43: "মূসক-৪.৩ (উপকরণ-উৎপাদ সহগ ঘোষণা)",
    DOC_MUSHAK_91: "মূসক-৯.১ দাখিলপত্র",
    DOC_PRC: "প্রত্যাবাসন সনদ (পি.আর.সি.) / এফডিডি",
    DOC_ELECTRICITY: "বিদ্যুৎ বিল (১২ মাস)",
    DOC_MACHINE_LIST: "লাইসেন্সে সংযোজিত মেশিনারিজের তালিকা",
    DOC_LOCAL_PURCHASE: "স্থানীয় সংগ্রহের দলিল (বিবিএলসি / মূসক-৬.৩)",
}


# ==========================================================
# একটি বিকল্প-পথের বর্ণনা
# ==========================================================

@dataclass
class EvidencePath:
    """একটি অনুপস্থিত দলিলের বিকল্প পথ ও সীমা"""
    missing: str                                   # সাংকেতিক নাম
    label: str                                     # বাংলা নাম
    normally_proves: str                           # সাধারণত কী প্রতিষ্ঠা করে
    alternatives: list[str] = field(default_factory=list)   # বিকল্প উৎস
    still_possible: list[str] = field(default_factory=list) # তবু যা নির্ণেয়
    blocked: list[str] = field(default_factory=list)        # যা নির্ণেয় নহে
    blocked_kinds: list[str] = field(default_factory=list)  # নিষিদ্ধ দাবি-ছাঁচ
    certainty: str = "E"                           # বিকল্প পথে নিশ্চয়তা
    requisition: str = ""                          # কী তলব করিতে হইবে
    proposal: str = ""                             # প্রস্তাবনায় কী যাইবে
    legal_ref: str = ""

    def render(self) -> str:
        return f"{self.label} — বিকল্প: {'; '.join(self.alternatives) or 'নাই'}"


# ==========================================================
# ★ বিকল্প প্রমাণ-পথের ছক
# ==========================================================

EVIDENCE_PATHS: dict[str, EvidencePath] = {

    DOC_REGISTER: EvidencePath(
        missing=DOC_REGISTER, label=DOC_LABELS[DOC_REGISTER],
        normally_proves="ইন্টু-বন্ড ও এক্স-বন্ডের তারিখ-পরিমাণ; মজুদের ধারাবাহিক স্থিতি",
        alternatives=[
            "বিল অব এন্ট্রি ও এক্সিট নোট — প্রবেশের তারিখ ও পরিমাণ",
            "ইউপি-ভিত্তিক এক্স-বন্ড অনুমোদন — উত্তোলনের পরিমাণ",
            "বন্ড কর্মকর্তার নিকট রক্ষিত দ্বিতীয় কপি [বিধি ৭]",
            "পাশবই (প্রযোজ্য ক্ষেত্রে)",
        ],
        still_possible=[
            "মোট আমদানি ও প্রাপ্যতার অতিরিক্ত (দাবি ২)",
            "অননুমোদিত এইচ.এস কোড (দাবি ১)",
            "মেয়াদোত্তর আমদানি (দাবি ৫)",
        ],
        blocked=[
            "এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন (দাবি ৩) — ঘটনাক্রম ছাড়া নির্ণেয় নহে",
            "মেয়াদোত্তীর্ণ কাঁচামাল / overstay (দাবি ৬)",
            "ছাড়করণ হইতে ইন্টু-বন্ডের বিলম্ব [বিধি ৮]",
        ],
        blocked_kinds=["capacity_breach_demand", "overstay_demand",
                       "into_bond_delay", "register_two_copy_mismatch",
                       "register_signature_missing"],
        certainty="E",
        requisition="তফসিল-১ ছকে রক্ষিত বন্ড রেজিস্টারের উভয় কপি",
        proposal=("বন্ড রেজিস্টার দাখিল না করায় এস.আর.ও নং ২১২-আইন/২০২৪/৬৪/"
                  "কাস্টমস এর বিধি ৭ এবং বন্ড লাইসেন্সের শর্ত লঙ্ঘিত হয়েছে; "
                  "রেজিস্টার দাখিলের নির্দেশ প্রদানপূর্বক কারণ দর্শানো নোটিশ "
                  "জারি করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ৭ ও ৮; কাস্টমস আইন ২০২৩ ধারা ১২৮",
    ),

    DOC_COEFFICIENT: EvidencePath(
        missing=DOC_COEFFICIENT, label=DOC_LABELS[DOC_COEFFICIENT],
        normally_proves="প্রতি একক পণ্যে অনুমোদিত কাঁচামালের পরিমাণ ও অপচয়ের হার",
        alternatives=[
            "সমজাতীয় পণ্যের অনুমোদিত সহগ [বিধি ৯ — সর্বোচ্চ ৩০ দিন]",
            "মূসক-৪.৩ এ প্রতিষ্ঠান-ঘোষিত সহগ",
            "ইউপির ক্রমিক ১২ (সহগ-ছক) — ইউপিতে লিপিবদ্ধ হার",
            "পূর্ববর্তী নিরীক্ষা প্রতিবেদনে গৃহীত সহগ",
        ],
        still_possible=[
            "তাত্ত্বিক ব্যবহারের আনুমানিক হিসাব (নিশ্চয়তা 【E】)",
            "উপকরণ-ভারসাম্যের দিকনির্দেশ",
        ],
        blocked=[
            "সহগের অতিরিক্ত ব্যবহারের রাজস্ব দাবি",
            "অপচয় সীমাতিরিক্ত হওয়ার দাবি",
        ],
        blocked_kinds=["coefficient_overuse", "wastage_excess"],
        certainty="E",
        requisition="ডিইডিও কর্তৃক অনুমোদিত সহগের পত্র (মেয়াদ উল্লেখসহ)",
        proposal=("অনুমোদিত সহগ দাখিল না করায় প্রকৃত ভোগ যাচাই করা সম্ভব "
                  "হয়নি; সহগের অনুমোদনপত্র দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ৯",
    ),

    DOC_MIS_IMPORT: EvidencePath(
        missing=DOC_MIS_IMPORT, label=DOC_LABELS[DOC_MIS_IMPORT],
        normally_proves="মেয়াদে মোট আমদানির পরিমাণ, মূল্য ও শুল্ক-করাদি",
        alternatives=[
            "বিল অব এন্ট্রির মূল/সত্যায়িত কপি ও সংযুক্ত ইনভয়েস-প্যাকিং লিস্ট",
            "লিয়েন ব্যাংকের এলসি-তালিকা ও পরিশোধ বিবরণী",
            "বন্ড রেজিস্টারের প্রবেশ-ভুক্তি",
            "প্রাপ্যতা-পত্রে শুল্কায়ন কর্মকর্তার বিয়োজন-চিহ্ন [বিধি ৬]",
        ],
        still_possible=[
            "আমদানির পরিমাণ ও শুল্কায়িত মূল্য (দলিল-ভিত্তিক)",
            "প্রাপ্যতার অতিরিক্ত আমদানি (দাবি ২)",
        ],
        blocked=[],
        blocked_kinds=[],
        certainty="V",
        requisition="এমআইএস আমদানি বিবরণী (সম্পূর্ণ শুল্ক-কর কলামসহ)",
        proposal="",
        legal_ref="এসআরও ২১২ বিধি ১৩(১)(খ)",
    ),

    DOC_ENTITLEMENT: EvidencePath(
        missing=DOC_ENTITLEMENT, label=DOC_LABELS[DOC_ENTITLEMENT],
        normally_proves="অনুমোদিত বার্ষিক আমদানি প্রাপ্যতা ও প্রারম্ভিক জের",
        alternatives=[
            "বন্ড লাইসেন্সে লিপিবদ্ধ প্রাপ্যতা [এসআরও ২১২ বিধি ৪]",
            "ইউপির ক্রমিক ৯ (কাঁচামাল-মজুদ ছক) — প্রাপ্যতা ও অবশিষ্ট",
            "কমিশনারেটের ওয়েবসাইটে প্রকাশিত প্রাপ্যতা [বিধি ১০(৬)]",
            "মেশিনের বার্ষিক উৎপাদন ক্ষমতা হইতে পুনর্নির্ধারণ",
        ],
        still_possible=[
            "লাইসেন্স-ভিত্তিক প্রাপ্যতা দিয়া অতিরিক্ত আমদানি নির্ণয়",
            "অননুমোদিত এইচ.এস কোড (দাবি ১)",
        ],
        blocked=[
            "প্রারম্ভিক জেরনির্ভর এককালীন ক্যাপাসিটি (দাবি ৩)",
            "নিট প্রাপ্যতাভিত্তিক সূক্ষ্ম গণনা",
        ],
        blocked_kinds=["capacity_breach_demand"],
        certainty="E",
        requisition="প্রাপ্যতা শীট ও পূর্ববর্তী মেয়াদের নিরীক্ষা প্রতিবেদন",
        proposal=("প্রাপ্যতা শীট দাখিল না করায় প্রারম্ভিক জের নিশ্চিত করা "
                  "যায়নি; উক্ত দলিল দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১৪ বিধি ৫; এসআরও ২১২ বিধি ৪",
    ),

    DOC_UP: EvidencePath(
        missing=DOC_UP, label=DOC_LABELS[DOC_UP],
        normally_proves="অনুমোদিত ছাড়, সহগ-প্রয়োগ, মূল্য সংযোজন ও রপ্তানি-সংযোগ",
        alternatives=[
            "কমিশনারেটের ওয়েবসাইটে প্রকাশিত ইউপি [বিধি ১০(৬) ও ১০(৯)]",
            "কাস্টম হাউস ও লিয়েন ব্যাংকে প্রেরিত অনুলিপি [বিধি ১০(৯)]",
            "বন্ড রেজিস্টারে ইউপি-সূত্রের ভুক্তি",
        ],
        still_possible=["আমদানি ও প্রাপ্যতার তুলনা"],
        blocked=[
            "ইউপির গাণিতিক যাচাই",
            "মূল্য সংযোজনের হার [বিধি ১০(৮)]",
            "ইউপি-বহির্ভূত রপ্তানি",
            "বিবিএলসি সংখ্যা ও আবেদন-সময়ের যাচাই",
        ],
        blocked_kinds=["up_arithmetic", "value_addition_short",
                       "export_without_up", "btb_lc_limit_exceeded",
                       "up_application_late", "up_value_addition_missing",
                       "exbond_without_up"],
        certainty="E",
        requisition="আলোচ্য মেয়াদে ইস্যুকৃত সকল ইউটিলাইজেশন পারমিশন",
        proposal=("ইউটিলাইজেশন পারমিশন দাখিল না করায় ছাড়কৃত কাঁচামালের "
                  "অনুমোদন-ভিত্তি যাচাই করা যায়নি; উক্ত দলিল দাখিলের নির্দেশ "
                  "প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ১০ ও ১৩(১)(খ)",
    ),

    DOC_EXPORT: EvidencePath(
        missing=DOC_EXPORT, label=DOC_LABELS[DOC_EXPORT],
        normally_proves="রপ্তানির পরিমাণ, মূল্য, গন্তব্য ও প্রত্যাবাসন",
        alternatives=[
            "ইউপিতে ঘোষিত রপ্তানিতব্য পণ্য (ক্রমিক ১১)",
            "বিবিএলসি ও মাস্টার এলসির বিপরীতে ব্যাংক-বিবরণী",
            "বাংলাদেশ ব্যাংকের অনলাইন মনিটরিং (এলসি ও ইএক্সপি) [বিধি ১০(৬)]",
            "মূসক-৯.১ এর শূন্যহার সরবরাহের নোট",
        ],
        still_possible=["ইউপি-স্তরে অনুমোদিত বনাম ছাড়কৃত কাঁচামালের ভারসাম্য"],
        blocked=[
            "ইউপি-বহির্ভূত রপ্তানি",
            "প্রত্যাবাসন-বিলম্ব (১২০ দিন)",
            "গন্তব্য-অসঙ্গতি",
            "স্টক রিকনসিলিয়েশনে ঘাটতি",
            "মূল্য সংযোজনের হার",
        ],
        blocked_kinds=["export_without_up", "repatriation_overdue",
                       "destination_mismatch", "unexplained_shortage",
                       "value_addition_short", "export_not_made",
                       "egm_bex_missing", "prc_not_submitted"],
        certainty="E",
        requisition="বিল অব এক্সপোর্ট, ইজিএম ও এমআইএস রপ্তানি বিবরণী",
        proposal=("রপ্তানি সংক্রান্ত দলিলাদি দাখিল না করায় রপ্তানি ও মূল্য "
                  "প্রত্যাবাসন যাচাই করা যায়নি; উক্ত দলিল দাখিলের নির্দেশ "
                  "প্রদানপূর্বক কারণ দর্শানো নোটিশ জারি করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ১১ ও ১৩(১)(খ)",
    ),

    DOC_CLOSING_STOCK: EvidencePath(
        missing=DOC_CLOSING_STOCK, label=DOC_LABELS[DOC_CLOSING_STOCK],
        normally_proves="মেয়াদান্তে অবশিষ্ট কাঁচামালের পরিমাণ",
        alternatives=[
            "সরেজমিন পরিদর্শনে গণনা (নিরীক্ষা দল কর্তৃক)",
            "বন্ড রেজিস্টারের কলাম ১৫ (সমাপনী মজুদ)",
            "ইউপির ক্রমিক ৯ এর 'অবশিষ্ট' ঘর",
        ],
        still_possible=["রেজিস্টার-ভিত্তিক স্থিতি (রেজিস্টার থাকিলে)"],
        blocked=["অব্যাখ্যাত ঘাটতির রাজস্ব দাবি"],
        blocked_kinds=["unexplained_shortage"],
        certainty="E",
        requisition="মেয়াদান্তের মজুদ বিবরণী ও সরেজমিন গণনার প্রতিবেদন",
        proposal=("সমাপনী মজুদের হিসাব না পাওয়ায় উপকরণ-ভারসাম্য সম্পন্ন করা "
                  "যায়নি; মজুদ বিবরণী দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ১৩(৩)",
    ),

    DOC_MUSHAK_43: EvidencePath(
        missing=DOC_MUSHAK_43, label=DOC_LABELS[DOC_MUSHAK_43],
        normally_proves="প্রতিষ্ঠান-ঘোষিত উপকরণ-উৎপাদ সহগ ও প্রতি এককে ব্যয়",
        alternatives=[
            "ডিইডিও অনুমোদিত সহগ",
            "ইউপির সহগ-ছক (ক্রমিক ১২)",
        ],
        still_possible=["সহগ-ভিত্তিক তুলনা (বিকল্প উৎস হইতে)"],
        blocked=["বিদ্যুৎ-উৎপাদন সামঞ্জস্য যাচাই (ঘোষিত হার ছাড়া অসম্ভব)"],
        blocked_kinds=["electricity_inconsistency", "mushak_43_mismatch"],
        certainty="E",
        requisition="হালনাগাদ মূসক-৪.৩ ঘোষণা",
        proposal=("মূসক-৪.৩ দাখিল না করায় ঘোষিত সহগ যাচাই করা যায়নি; উক্ত "
                  "ঘোষণা দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="মূসক বিধিমালা, ২০১৬",
    ),

    DOC_MUSHAK_91: EvidencePath(
        missing=DOC_MUSHAK_91, label=DOC_LABELS[DOC_MUSHAK_91],
        normally_proves="ঘোষিত টার্নওভার, রেয়াত, উৎসে মূসক ও পরিশোধ",
        alternatives=[
            "অনলাইন মূসক ব্যবস্থায় দাখিলকৃত রিটার্নের প্রিন্ট",
            "মূসক-৬.৩ চালান ও ক্রয়-বিক্রয় হিসাব বই",
            "নিরীক্ষিত আর্থিক বিবরণী",
        ],
        still_possible=["চালান-ভিত্তিক সরবরাহ যাচাই"],
        blocked=[
            "frozen note সনাক্তকরণ",
            "টার্নওভার সমন্বয়",
            "রেয়াত ও এটি সমন্বয় যাচাই",
        ],
        blocked_kinds=["frozen_note_anomaly", "turnover_mismatch_fs",
                       "input_credit_ineligible", "at_adjustment_mismatch",
                       "vat_return_late"],
        certainty="E",
        requisition="আলোচ্য মেয়াদের সকল মূসক-৯.১ দাখিলপত্র",
        proposal=("মূসক দাখিলপত্র দাখিল না করায় কর-পরিশোধের যথার্থতা যাচাই "
                  "করা যায়নি; উক্ত দলিল দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
    ),

    DOC_PRC: EvidencePath(
        missing=DOC_PRC, label=DOC_LABELS[DOC_PRC],
        normally_proves="রপ্তানি মূল্য দেশে প্রত্যাবাসিত হইয়াছে কি না",
        alternatives=[
            "লিয়েন ব্যাংকের প্রত্যাবাসন-বিবরণী",
            "বাংলাদেশ ব্যাংকের অনলাইন ইএক্সপি মনিটরিং",
            "তফসিল-৩ কলাম ১৬ (প্রত্যাবাসিত মূল্য)",
        ],
        still_possible=["ব্যাংক-বিবরণী হইতে প্রত্যাবাসনের প্রাথমিক চিত্র"],
        blocked=["প্রত্যাবাসন-বিলম্বের আনুষ্ঠানিক নির্ণয়"],
        blocked_kinds=["repatriation_overdue", "prc_not_submitted"],
        certainty="E",
        requisition="প্রত্যাবাসন সনদ (পি.আর.সি.) ও এফডিডির কপি",
        proposal=("প্রত্যাবাসন সনদ দাখিল না করায় রপ্তানি মূল্যের প্রত্যাবাসন "
                  "নিশ্চিত করা যায়নি; উক্ত সনদ দাখিলের নির্দেশ প্রদান করা "
                  "যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ১১ ও ১৩(১)(খ)",
    ),

    DOC_ELECTRICITY: EvidencePath(
        missing=DOC_ELECTRICITY, label=DOC_LABELS[DOC_ELECTRICITY],
        normally_proves="প্রকৃত উৎপাদন-কার্যক্রমের পরোক্ষ প্রমাণ",
        alternatives=[
            "বিদ্যুৎ বিতরণ সংস্থার নিকট হইতে সংগৃহীত বিবরণী",
            "গ্যাস বিল (প্রযোজ্য ক্ষেত্রে)",
            "জনবল ও বেতন বিবরণী — কার্যক্রমের বিকল্প সূচক",
        ],
        still_possible=["কার্যক্রমের গুণগত সূচক"],
        blocked=["বিদ্যুৎ-উৎপাদন সামঞ্জস্যের সংখ্যাগত যাচাই"],
        blocked_kinds=["electricity_inconsistency"],
        certainty="E",
        requisition="আলোচ্য মেয়াদের ১২ মাসের বিদ্যুৎ ও গ্যাস বিল",
        proposal=("বিদ্যুৎ বিল দাখিল না করায় উৎপাদনের সহিত সামঞ্জস্য যাচাই "
                  "করা যায়নি; উক্ত বিল দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ১৩(১)(গ)",
    ),

    DOC_MACHINE_LIST: EvidencePath(
        missing=DOC_MACHINE_LIST, label=DOC_LABELS[DOC_MACHINE_LIST],
        normally_proves="বার্ষিক উৎপাদন ক্ষমতা ও প্রাপ্যতার ভিত্তি",
        alternatives=[
            "বন্ড লাইসেন্সের সংযুক্তি (annexure)",
            "সরেজমিন পরিদর্শনে গণনা ও ক্যাটালগ",
            "মেশিন আমদানির বিল অব এন্ট্রি ও ইনভয়েস",
        ],
        still_possible=["সরেজমিন গণনার ভিত্তিতে ক্ষমতার আনুমানিক নির্ণয়"],
        blocked=["উৎপাদন ক্ষমতার ৮০% সীমা লঙ্ঘনের দাবি"],
        blocked_kinds=["condition_violation"],
        certainty="E",
        requisition="লাইসেন্সে সংযোজিত মেশিনারিজের তালিকা ও ক্ষমতা-সনদ",
        proposal=("মেশিনারিজের তালিকা দাখিল না করায় উৎপাদন ক্ষমতা যাচাই করা "
                  "যায়নি; উক্ত তালিকা দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২০৯ বিধি ৮; এসআরও ২১৪ বিধি ৩(৪)",
    ),

    DOC_LOCAL_PURCHASE: EvidencePath(
        missing=DOC_LOCAL_PURCHASE, label=DOC_LABELS[DOC_LOCAL_PURCHASE],
        normally_proves="স্থানীয় উৎস হইতে সংগৃহীত কাঁচামাল ও উৎসে মূসক",
        alternatives=[
            "বিবিএলসি ও ব্যাংক-বিবরণী",
            "মূসক-৬.৩ চালান ও মূসক-৬.৬ সনদ",
            "বন্ড রেজিস্টারে স্থানীয় সংগ্রহের ভুক্তি [বিধি ৮]",
        ],
        still_possible=["সংগ্রহের পরিমাণ ও মূল্য (চালান-ভিত্তিক)"],
        blocked=["উৎসে মূসক কর্তন ও জমার যাচাই"],
        blocked_kinds=["vds_not_deducted", "vds_not_deposited", "mushak_66_late"],
        certainty="E",
        requisition="স্থানীয় সংগ্রহের বিবিএলসি, মূসক-৬.৩ ও ৬.৬",
        proposal=("স্থানীয় সংগ্রহের দলিল দাখিল না করায় উৎসে মূসক কর্তন যাচাই "
                  "করা যায়নি; উক্ত দলিল দাখিলের নির্দেশ প্রদান করা যেতে পারে"),
        legal_ref="এসআরও ২১২ বিধি ৮ ও ১৩(১)(খ)",
    ),
}


# ==========================================================
# অনুসন্ধান ও সিদ্ধান্ত
# ==========================================================

def path_for(doc: str) -> Optional[EvidencePath]:
    """একটি অনুপস্থিত দলিলের বিকল্প-পথ"""
    return EVIDENCE_PATHS.get(doc)


def paths_for(missing: Iterable[str]) -> list[EvidencePath]:
    """অনুপস্থিত দলিলগুলির বিকল্প-পথ (অজানা নাম উপেক্ষিত)"""
    out: list[EvidencePath] = []
    for d in missing or []:
        p = EVIDENCE_PATHS.get(d)
        if p:
            out.append(p)
    return out


def blocked_demand_kinds(missing: Iterable[str]) -> set[str]:
    """
    ★ যে দাবি-ছাঁচগুলি প্রমাণাভাবে নিষিদ্ধ।

    ইহাই অহেতুক দাবিনামা রোধের প্রধান প্রহরী — প্রমাণ নাই ⇒ দাবি নাই।
    """
    out: set[str] = set()
    for p in paths_for(missing):
        out.update(p.blocked_kinds)
    return out


def audit_route(missing: Iterable[str]) -> dict:
    """
    ★ অনুপস্থিত দলিলের তালিকা হইতে নিরীক্ষার বিকল্প পরিকল্পনা।

    ফেরত দেয় —
      paths            : প্রতিটি অনুপস্থিত দলিলের বিকল্প পথ
      still_possible   : যে যাচাইগুলি তবু সম্পন্ন করা যাইবে
      blocked          : যাহা নির্ণয় করা যাইবে না
      blocked_kinds    : নিষিদ্ধ দাবি-ছাঁচ (দাবি তৈরি করা যাইবে না)
      requisitions     : কী কী তলব করিতে হইবে
      proposals        : প্রস্তাবনায় যে শর্তভঙ্গগুলি যাইবে (দাবি নহে)
    """
    paths = paths_for(missing)
    still, blocked, reqs, props = [], [], [], []
    for p in paths:
        still.extend(p.still_possible)
        blocked.extend(p.blocked)
        if p.requisition:
            reqs.append(p.requisition)
        if p.proposal:
            props.append(p.proposal)
    logger.info(
        f"বিকল্প প্রমাণ-পথ: {len(paths)}টি অনুপস্থিত দলিল, "
        f"{len(blocked)}টি যাচাই অবরুদ্ধ"
    )
    return {
        "paths": [asdict(p) for p in paths],
        "still_possible": still,
        "blocked": blocked,
        "blocked_kinds": sorted(blocked_demand_kinds(missing)),
        "requisitions": reqs,
        "proposals": props,
    }


def filter_findings(findings: list[dict], missing: Iterable[str]) -> dict:
    """
    ★ প্রমাণাভাবে নিষিদ্ধ দাবি ছাঁকিয়া ফেলে।

    ফেরত: {"kept": [...], "suppressed": [{"kind", "কারণ"}]}
    """
    blocked = blocked_demand_kinds(missing)
    kept, suppressed = [], []
    for f in findings or []:
        k = f.get("kind", "")
        if k in blocked:
            suppressed.append({
                "kind": k,
                "কারণ": "প্রয়োজনীয় দলিল অনুপস্থিত — প্রমাণ ব্যতিরেকে দাবি নহে",
            })
        else:
            kept.append(f)
    return {"kept": kept, "suppressed": suppressed}


__all__ = [
    "DOC_REGISTER", "DOC_COEFFICIENT", "DOC_MIS_IMPORT", "DOC_ENTITLEMENT",
    "DOC_UP", "DOC_EXPORT", "DOC_CLOSING_STOCK", "DOC_MUSHAK_43",
    "DOC_MUSHAK_91", "DOC_PRC", "DOC_ELECTRICITY", "DOC_MACHINE_LIST",
    "DOC_LOCAL_PURCHASE", "DOC_LABELS",
    "EvidencePath", "EVIDENCE_PATHS",
    "path_for", "paths_for", "blocked_demand_kinds", "audit_route",
    "filter_findings",
]
