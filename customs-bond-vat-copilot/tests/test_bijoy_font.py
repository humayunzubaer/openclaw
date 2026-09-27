"""
ফন্ট-রূপান্তর পরীক্ষা — SutonnyMJ (বিজয়) ও Nikosh
=====================================================
চালান:  PYTHONPATH=backend python3 tests/test_bijoy_font.py

★ কেন এত কড়া পরীক্ষা
    বিজয় ASCII-ভিত্তিক। একটিমাত্র অক্ষর ভুল ক্রমে বসিলে সম্পূর্ণ শব্দ
    বিকৃত দেখায় — অথচ কোড কোনো ত্রুটি দেখায় না। তাই প্রতিটি কঠিন
    গঠন এখানে বাঁধিয়া রাখা হইল।
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.bijoy import (                       # noqa: E402
    compose_nukta, split_runs, to_bijoy_runs, unicode_to_bijoy,
)

FAILS: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  {'✅' if ok else '❌'} {label}")
    if not ok:
        FAILS.append(label)


def eq(label: str, got: str, want: str) -> None:
    ok = got == want
    print(f"  {'✅' if ok else '❌'} {label}"
          + ("" if ok else f"\n        পাইলাম : {got!r}\n        চাহি   : {want!r}"))
    if not ok:
        FAILS.append(label)


print("== ১. নুক্তা যুক্তরূপে আসে (NFC ইহা করে না) ==")
# ★ কোড-পয়েন্টে লিখি — উৎস-ফাইলের বাংলা লিটারাল নিজেই বিযুক্ত
#   রূপে সংরক্ষিত থাকিতে পারে, তখন তুলনা অর্থহীন হইয়া যায়।
YA, NUKTA, YA_FINAL = "\u09af", "\u09bc", "\u09df"
DDA, DDA_FINAL = "\u09a1", "\u09dc"
check("য + ় → য়", compose_nukta(YA + NUKTA) == YA_FINAL)
check("ড + ় → ড়", compose_nukta(DDA + NUKTA) == DDA_FINAL)
check("যুক্তরূপ অপরিবর্তিত", compose_nukta(YA_FINAL) == YA_FINAL)
check("রূপান্তরে দুই রূপ একই ফল দেয়",
      unicode_to_bijoy(YA + NUKTA) == unicode_to_bijoy(YA_FINAL) == "q")

print("== ২. মৌলিক অক্ষর ==")
eq("ক", unicode_to_bijoy("ক"), "K")
eq("বাংলা", unicode_to_bijoy("বাংলা"), "evsjv")
eq("বাংলা অঙ্ক", unicode_to_bijoy("২০২৪"), "2024")

print("== ৩. ★ আগে-বসা কার (ি ে ৈ) ব্যঞ্জনের পূর্বে যায় ==")
eq("নি", unicode_to_bijoy("নি"), "wb")
eq("দে", unicode_to_bijoy("দে"), "‡`")
eq("বৈ", unicode_to_bijoy("বৈ"), "‰e")
eq("নিরীক্ষা", unicode_to_bijoy("নিরীক্ষা"), "wbix¶v")
eq("কো (ে+া)", unicode_to_bijoy("কো"), "‡Kv")
eq("নৌ (ে+ৗ)", unicode_to_bijoy("নৌ"), "‡bŠ")

print("== ৪. ★ রেফ (র্) ব্যঞ্জনের পরে যায় ==")
eq("কর্ম", unicode_to_bijoy("কর্ম"), "Kg©")
eq("কর্তৃপক্ষ", unicode_to_bijoy("কর্তৃপক্ষ"), "KZ©…c¶")
eq("বার্ষিক", unicode_to_bijoy("বার্ষিক"), "evwl©K")

print("== ৫. ★ য় / ড় / ঢ় এর পরে কার (পূর্বে ভুল হইত) ==")
eq("সাময়িক", unicode_to_bijoy("সাময়িক"), "mvgwqK")
eq("রয়েছে", unicode_to_bijoy("রয়েছে"), "i‡q‡Q")
eq("ছাড়কৃত", unicode_to_bijoy("ছাড়কৃত"), "QvoK…Z")

print("== ৬. য-ফলা ও র-ফলা ==")
eq("ব্যবহৃত", unicode_to_bijoy("ব্যবহৃত"), "e¨eüZ")
eq("প্রাপ্যতা", unicode_to_bijoy("প্রাপ্যতা"), "c«vc¨Zv")
eq("ওয়্যারহাউস", unicode_to_bijoy("ওয়্যারহাউস"), "Iq¨vinvDm")

print("== ৭. কার-সমেত একক গ্লিফ ==")
eq("শুল্ক", unicode_to_bijoy("শুল্ক"), "ïé")
eq("গুরুত্বপূর্ণ", unicode_to_bijoy("গুরুত্বপূর্ণ"), "¸i“Z¡c~Y©")
eq("হৃদয়", unicode_to_bijoy("হৃদয়"), "ü`q")

print("== ৮. যুক্তাক্ষর ==")
eq("প্রতিষ্ঠান", unicode_to_bijoy("প্রতিষ্ঠান"), "c«wZôvb")
eq("দ্বারা", unicode_to_bijoy("দ্বারা"), "Øviv")
eq("জ্ঞান", unicode_to_bijoy("জ্ঞান"), "Ávb")
eq("সূক্ষ্ম", unicode_to_bijoy("সূক্ষ্ম"), "m~¶§")
eq("উৎপাদ", unicode_to_bijoy("উৎপাদ"), "Drcv`")

print("== ৯. দাঁড়ি ও উদ্ধৃতি-চিহ্ন ==")
eq("দাঁড়ি", unicode_to_bijoy("।"), "|")
eq("বাক্যশেষ", unicode_to_bijoy("হইল।"), "nBj|")

print("== ১০. ★★ ইংরেজি কখনো বিজয় রানে যায় না ==")
runs = split_runs("H.S. Code 5209.31.00 অনুযায়ী KG পরিমাণ")
bn_text = "".join(v for k, v in runs if k == "bn")
check("ইংরেজি অক্ষর বাংলা রানে নাই",
      not any(c.isascii() and c.isalpha() for c in bn_text))
check("ASCII অঙ্ক বাংলা রানে নাই",
      not any(c in "0123456789" for c in bn_text))
check("বাংলা অংশ ঠিক আছে", "অনুযায়ী" in bn_text and "পরিমাণ" in bn_text)

print("== ১১. বিপজ্জনক চিহ্ন ইংরেজি রানে থাকে ==")
for ch, why in [("—", "্ত"), ("…", "ৃ"), ("~", "ূ"), ("_", "থ")]:
    r = split_runs(f"মোট {ch} শেষ")
    inside = "".join(v for k, v in r if k == "bn")
    check(f"{ch!r} (বিজয়ে {why}) বাংলা রানে নাই", ch not in inside)

print("== ১২. দাঁড়ি ও বাংলা যতি বাংলা রানেই থাকে ==")
r = split_runs("এই মর্মে জানানো হইল। (বিধি ৯)")
check("একটিই বাংলা রান", len([k for k, _ in r if k == "bn"]) == 1)
check("দাঁড়ি ভিতরে", "।" in "".join(v for k, v in r if k == "bn"))

print("== ১৩. অকারণে রান ভাঙে না ==")
r = split_runs("এস.আর.ও নং-২১৪-আইন/২০২৪/৬৬/কাস্টমস, তারিখঃ ২৯/০৫/২০২৪")
check("পুরাটাই এক রান", len(r) == 1 and r[0][0] == "bn")

print("== ১৪. to_bijoy_runs — প্রতিবেদনে বসিবার রূপ ==")
rr = to_bijoy_runs("মোট 47 টি দলিল")
check("দুই শ্রেণির রান আসে", {k for k, _ in rr} == {"bn", "other"})
check("ইংরেজি অংশ অপরিবর্তিত", any(v.strip() == "47" for k, v in rr if k == "other"))

print("== ১৫. খালি ও অ-বাংলা লেখা ==")
eq("খালি", unicode_to_bijoy(""), "")
eq("শুধু ইংরেজি", unicode_to_bijoy("Report 2024"), "Report 2024")

print()
if FAILS:
    print(f"RESULT: ❌ {len(FAILS)}টি ব্যর্থ")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("RESULT: ALL PASS ✅")
