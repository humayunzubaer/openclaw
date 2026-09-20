"""
এজেন্ট পরীক্ষা — এলএলএম ছাড়াই কাজ করে কি না
=================================================
চালান:  PYTHONPATH=backend python3 tests/test_agent.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.agent_router import (        # noqa: E402
    AgentRouter, detect_documents, detect_entity_type,
)
from services.agent_service import get_session, reset_session  # noqa: E402

FAILS: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  {'✅' if ok else '❌'} {label}")
    if not ok:
        FAILS.append(label)


def ask(sess_id: str, q: str):
    return AgentRouter(get_session(sess_id)).route(q)


print("== ১. শ্রেণি শনাক্তকরণ ==")
check("পোশাক", detect_entity_type("পোশাক শিল্পের দলিল") == "rmg_direct")
check("প্রচ্ছন্ন", detect_entity_type("প্রচ্ছন্ন রপ্তানিকারক") == "deemed")
check("ইপিজেড", detect_entity_type("ইপিজেডস্থ প্রতিষ্ঠান") == "epz_direct")
check("সরাসরি (পূর্বনির্ধারিত)", detect_entity_type("একটি প্রতিষ্ঠান") == "direct")

print("== ২. দলিল শনাক্তকরণ ==")
check("রেজিস্টার", "bond_register" in detect_documents("রেজিস্টার দেয় নাই"))
check("ইউপি ও রপ্তানি একসাথে",
      {"up", "export_data"} <= set(detect_documents("ইউপি ও রপ্তানি তথ্য নাই")))
check("বিদ্যুৎ", "electricity" in detect_documents("বিদ্যুৎ বিল পাই নাই"))

print("== ৩. এলএলএম ছাড়াই উত্তর আসে ==")
reset_session("t")
for q, want in [
    ("হ্যালো", "greeting"),
    ("তুমি কী কী করতে পারো?", "capability"),
    ("সরাসরি রপ্তানিকারকের কী কী দলিল লাগবে?", "required_docs"),
    ("রেজিস্টার দেয় নাই, কী করব?", "missing_docs"),
    ("সম্পূর্ণ নিরীক্ষা কর", "full_audit"),
    ("চলমান নিরীক্ষার অবস্থা কী?", "state"),
]:
    rep = ask("t", q)
    check(f"[{want}] ← {q[:28]}", rep.intent == want and len(rep.render()) > 40)

print("== ৪. দলিল-তালিকা প্রকৃত সংখ্যা দেয় ==")
rep = ask("t2", "পোশাক শিল্পের দলিলের চেকলিস্ট দাও")
check("পোশাকে ৪০+ দলিল", rep.data.get("documents", 0) >= 40)
check("তফসিল-ছক আছে", rep.data.get("schedules", 0) > 0)

print("== ৫. ★ প্রমাণ নাই ⇒ দাবি নাই ==")
rep = ask("t3", "প্রতিষ্ঠান বন্ড রেজিস্টার সরবরাহ করে নাই")
blocked = rep.data.get("blocked_kinds", [])
check("নিষিদ্ধ দাবির তালিকা আসে", len(blocked) >= 3)
check("ক্যাপাসিটি-দাবি নিষিদ্ধ", "capacity_breach_demand" in blocked)
check("তলবের তালিকা আসে", len(rep.needs_documents) > 0)
check("সেশনে মনে রাখে",
      "bond_register" in get_session("t3").missing_docs)

print("== ৬. ছোট, নির্দিষ্ট যাচাই ==")
for q, code in [("শুধু বিদ্যুৎ যাচাই কর", "electricity"),
                ("বন্ডিং ক্যাপাসিটি চেক কর", "bonding_capacity"),
                ("ইউপি যাচাই কর", "up")]:
    rep = ask("t4", q)
    check(f"যাচাই [{code}]", rep.intent == f"check:{code}")

print("== ৭. তথ্য না থাকিলে দলিল চায় (দাবি করে না) ==")
rep = ask("t5", "শুধু বিদ্যুৎ যাচাই কর")
check("দলিল চাহিয়াছে", len(rep.needs_documents) > 0)
check("কোনো অঙ্ক দাবি করে নাই", not rep.data.get("amount"))

print("== ৮. অজানা প্রশ্নে বানাইয়া বলে না ==")
rep = ask("t6", "zzz qqq xxx")
check("handled=False অথবা পরামর্শ দেয়",
      (not rep.handled) or bool(rep.next_actions))

print("== ৯. প্রতিবেদন-পরিকল্পনা প্রাসঙ্গিকতা মানে ==")
s = get_session("t7")
s.profile["entity_type"] = "epz_direct"
rep = AgentRouter(s).route("প্রতিবেদনের অনুচ্ছেদক্রম দাও")
paras = rep.data.get("paragraphs", [])
check("অনুচ্ছেদ আসে", len(paras) > 5)
check("ইপিজেডে ইউপি-অনুচ্ছেদ বাদ",
      not any("ইউপি" in p for p in paras))

print()
if FAILS:
    print(f"RESULT: ❌ {len(FAILS)}টি ব্যর্থ")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("RESULT: ALL PASS ✅")
