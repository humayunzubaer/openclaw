#!/bin/bash
# Linux — টার্মিনালে চালান:  ./start.sh
cd "$(dirname "$0")" || exit 1

echo ""
echo "  ============================================================"
echo "    Customs Bond Audit Intelligence Platform"
echo "  ============================================================"
echo ""

PY=""
for c in python3.12 python3.11 python3; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done

if [ -z "$PY" ]; then
  echo "  ⚠️  Python পাওয়া যায় নাই।  ইনস্টল করুন:"
  echo "      sudo apt install python3 python3-venv python3-pip"
  echo ""
  read -r -p "  Enter চাপুন..."; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "  প্রথমবার চালু হইতেছে — প্যাকেজ ইনস্টল হইতেছে (২–৫ মিনিট)..."
  echo ""
  "$PY" -m venv .venv || {
    echo "  ⚠️  venv তৈরি হয় নাই। চালান: sudo apt install python3-venv"
    read -r -p "  Enter চাপুন..."; exit 1; }
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/python -m pip install -r backend/requirements.txt || {
    echo "  ⚠️  প্যাকেজ ইনস্টলে সমস্যা। ইন্টারনেট দেখুন।"
    read -r -p "  Enter চাপুন..."; exit 1; }
  echo ""
  echo "  পরিবেশ প্রস্তুত।"
  echo ""
fi

echo "  সার্ভার চালু হইতেছে... বন্ধ করিতে CTRL+C।"
echo ""
( sleep 3; xdg-open "http://localhost:4800" >/dev/null 2>&1 ) &
./.venv/bin/python backend/run_server.py
