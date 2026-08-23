"""বিজয় (SutonnyMJ) → ইউনিকোড রূপান্তরক — লিগ্যাসি নথি পড়িবার জন্য"""
from __future__ import annotations
import re, sys
sys.path.insert(0, '/home/claude/customs-bond-audit/backend')
from utils.bijoy import SINGLE_MAP, CONJUNCT_MAP, RA_PHALA_SPECIAL

# উল্টো মানচিত্র
REV_CONJ = {v: k for k, v in CONJUNCT_MAP.items()}
REV_RAPH = {v: k for k, v in RA_PHALA_SPECIAL.items()}
REV_SINGLE = {v: k for k, v in SINGLE_MAP.items()}

# অতিরিক্ত সাধারণ বিজয় সংকেত
EXTRA = {
    "†": "ে", "‡": "ে", "w": "ি", "v": "া", "y": "ু", "~": "ূ",
    "…": "ৃ", "‰": "ৈ", "Š": "ৗ", "&": "্", "©": "\x01",
    "ª": "\x02", "¨": "\x03", "s": "ং", "t": "ঃ", "u": "ঁ",
    "|": "।", "ó": "ষ্ট", "ô": "ষ্ঠ", "ÿ": "ক্ষ", "¶": "ক্ষ",
    "×": "দ্ধ", "š": "ন", "Í": "্ত", "’": "্থ", "¯": "স",
    "�": "", "\x93": "চ্চ", "\x94": "চ্চ",
}


def bijoy_to_unicode(text: str) -> str:
    if not text:
        return ""
    s = text
    # ১) দীর্ঘতম যুক্তাক্ষর আগে
    for k in sorted(list(REV_CONJ) + list(REV_RAPH), key=len, reverse=True):
        if len(k) < 2:
            continue
        s = s.replace(k, REV_CONJ.get(k) or REV_RAPH.get(k))
    # ২) একক অক্ষর ও অতিরিক্ত সংকেত
    out = []
    for ch in s:
        if "\u0980" <= ch <= "\u09FF":
            out.append(ch); continue
        out.append(EXTRA.get(ch, REV_SINGLE.get(ch, ch)))
    s = "".join(out)
    # ৩) সম্মুখগামী কার পিছনে সরাও: "িক" → "কি"
    s = re.sub(r"([িেৈ])([\u0995-\u09B9\u09DC-\u09DF])", r"\2\1", s)
    s = re.sub(r"([\u0995-\u09B9])ে([\u0995-\u09B9])", r"\1\2ে", s)
    # ৪) ো / ৌ পুনর্গঠন
    s = s.replace("ো", "ো").replace("ৌ", "ৌ")
    # ৫) রেফ ও ফলা
    s = s.replace("\x01", "\u09B0\u09CD")   # অস্থায়ী
    s = re.sub(r"([\u0995-\u09B9])\u09B0\u09CD", r"র্\1", s)
    s = s.replace("\x02", "্র").replace("\x03", "্য")
    return s


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/conv/HAIJINDI_NOTE_SHEET-1.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/conv/report_unicode.txt"
    raw = open(src, encoding="utf-8").read()
    open(dst, "w", encoding="utf-8").write(bijoy_to_unicode(raw))
    print(f"রূপান্তরিত: {dst}")
