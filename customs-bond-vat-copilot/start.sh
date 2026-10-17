#!/bin/bash
# Linux — টার্মিনালে চালান:  ./start.sh   (অথবা ডাবল-ক্লিক → Run)
cd "$(dirname "$0")" || exit 1

if ! command -v node >/dev/null 2>&1; then
  echo ""
  echo "  ⚠️  Node.js পাওয়া যায়নি। প্রথমে Node.js (LTS) ইনস্টল করুন:"
  echo "      https://nodejs.org  (অথবা: sudo apt install nodejs)"
  echo ""
  read -r -p "  বন্ধ করতে Enter চাপুন..."
  exit 1
fi

echo "  Customs Bond & VAT Audit Copilot চালু হচ্ছে..."
( sleep 1.5; xdg-open "http://localhost:4700" >/dev/null 2>&1 ) &
node src/server.js
