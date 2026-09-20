#!/bin/bash
# Customs Bond Audit Intelligence Platform — Linux/macOS. চালান: ./start.sh
cd "$(dirname "$0")" || exit 1
set -u

say() { printf "  %s\n" "$1"; }
die() { printf "\n  [!] %s\n\n" "$1"; read -r -p "  Enter চাপুন..."; exit 1; }

echo ""
echo "  ============================================================"
echo "    Customs Bond Audit Intelligence Platform"
echo "  ============================================================"
echo ""

# ---------- ০) সঠিক ফোল্ডারে আছি তো? ----------
if [ ! -f backend/requirements.txt ] || [ ! -f backend/run_server.py ]; then
  die "এই ফোল্ডারে backend পাওয়া যায় নাই।

  সম্ভবত জিপ ফাইলটি না খুলিয়া ভিতর হইতে চালানো হইয়াছে।

  যাহা করিবেন —
    ১। জিপ ফাইলে ডান-ক্লিক করিয়া Extract করুন
    ২। যে নূতন ফোল্ডার তৈরি হইল সেটি খুলুন
    ৩। সেখান হইতে এই ফাইলটি চালান"
fi

# ---------- ১) Python ----------
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done
[ -z "$PY" ] && die "Python পাওয়া যায় নাই। ইনস্টল করুন: https://www.python.org/downloads/release/python-3130/"

# ---------- ২) সংস্করণ যাচাই ----------
PYVER=$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
PYMINOR=${PYVER#*.}
if [ "${PYVER%%.*}" != "3" ] || [ "$PYMINOR" -lt 10 ] || [ "$PYMINOR" -gt 13 ]; then
  die "Python $PYVER পাওয়া গেল — ইহা সমর্থিত নহে।

  এই সফটওয়্যারে Python 3.10 হইতে 3.13 লাগে।
  (৩.১৪ বা তদূর্ধ্বে pandas এখনো তৈরি হয় নাই।)

  এখান হইতে 3.13 নামান:
      https://www.python.org/downloads/release/python-3130/"
fi

# ---------- ৩) পরিবেশ ----------
if [ ! -x ".venv/bin/python" ]; then
  say "প্রথমবার — প্যাকেজ নামানো হইতেছে (১–৩ মিনিট)..."
  "$PY" -m venv .venv || die "পরিবেশ তৈরি হয় নাই।"
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/python -m pip install -r backend/requirements.txt \
    || die "প্যাকেজ ইনস্টল হয় নাই। ইন্টারনেট সংযোগ দেখুন।"
  say "পরিবেশ প্রস্তুত।"
fi

# ---------- ৪) চালু ----------
say "সার্ভার চালু হইতেছে..."
( sleep 2; (xdg-open http://localhost:4800 || open http://localhost:4800) >/dev/null 2>&1 ) &
./.venv/bin/python backend/run_server.py

echo ""
read -r -p "  সার্ভার বন্ধ হইয়াছে। Enter চাপুন..."
