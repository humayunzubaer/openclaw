#!/bin/bash
# macOS — এই ফাইলে ডাবল-ক্লিক করলেই অ্যাপ চালু হয়।
cd "$(dirname "$0")" || exit 1

echo ""
echo "  ============================================================"
echo "    Customs Bond Audit Intelligence Platform"
echo "  ============================================================"
echo ""

# ---------- ১) Python খুঁজি ----------
PY=""
for c in python3.12 python3.11 python3; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done

if [ -z "$PY" ]; then
  echo "  ⚠️  Python পাওয়া যায় নাই।"
  echo ""
  echo "     এই লিংক হইতে Python ইনস্টল করুন:"
  echo "         https://www.python.org/downloads/"
  echo ""
  read -r -p "  বন্ধ করিতে Enter চাপুন..."
  exit 1
fi

# ---------- ২) প্রথমবার হইলে পরিবেশ তৈরি ----------
if [ ! -x ".venv/bin/python" ]; then
  echo "  প্রথমবার চালু হইতেছে — প্রয়োজনীয় প্যাকেজ ইনস্টল হইতেছে।"
  echo "  ইহাতে ২–৫ মিনিট লাগিতে পারে। অনুগ্রহ করিয়া অপেক্ষা করুন..."
  echo ""
  "$PY" -m venv .venv || {
    echo "  ⚠️  পরিবেশ তৈরি হয় নাই।"
    read -r -p "  Enter চাপুন..."; exit 1; }
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/python -m pip install -r backend/requirements.txt || {
    echo ""
    echo "  ⚠️  প্যাকেজ ইনস্টলে সমস্যা। ইন্টারনেট সংযোগ দেখুন।"
    read -r -p "  Enter চাপুন..."; exit 1; }
  echo ""
  echo "  পরিবেশ প্রস্তুত।"
  echo ""
fi

# ---------- ৩) চালু ----------
echo "  সার্ভার চালু হইতেছে... ব্রাউজার নিজেই খুলিয়া যাইবে।"
echo "  বন্ধ করিতে এই উইন্ডোতে CTRL+C চাপুন।"
echo ""
( sleep 3; open "http://localhost:4800" >/dev/null 2>&1 ) &
./.venv/bin/python backend/run_server.py

echo ""
read -r -p "  সার্ভার বন্ধ হইয়াছে। Enter চাপুন..."
