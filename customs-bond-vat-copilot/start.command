#!/bin/bash
# macOS — এই ফাইলে ডাবল-ক্লিক করলেই অ্যাপ চালু হয়ে ব্রাউজার খোলে।
cd "$(dirname "$0")" || exit 1

if ! command -v node >/dev/null 2>&1; then
  echo ""
  echo "  ⚠️  Node.js পাওয়া যায়নি।"
  echo "  প্রথমে https://nodejs.org থেকে Node.js (LTS) ইনস্টল করুন,"
  echo "  তারপর আবার এই ফাইলে ডাবল-ক্লিক করুন।"
  echo ""
  read -r -p "  বন্ধ করতে Enter চাপুন..."
  exit 1
fi

echo "  Customs Bond & VAT Audit Copilot চালু হচ্ছে..."
( sleep 1.5; open "http://localhost:4700" ) &
node src/server.js
