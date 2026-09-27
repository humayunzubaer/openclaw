"""
Customs Bond Audit Intelligence Platform — লোকাল সার্ভার চালু করে।

চালান (backend/ ফোল্ডার হইতে):
    python3 run_server.py

তারপর ব্রাউজারে খুলুন:  http://localhost:4800
একই Wi-Fi/LAN-এ ফোন হইতে:  http://<এই-কম্পিউটারের-IP>:4800

সব লোকাল — কোনো ডেটা ইন্টারনেটে যায় না।
"""
import os
import sys

# backend/ কে import-root বানাও (api.main → services.* absolute import)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4800"))
    print("\n  Customs Bond Audit Intelligence Platform")
    print(f"  এই কম্পিউটারে:  http://localhost:{port}")
    print(f"  LAN/মোবাইলে:    http://<IP>:{port}\n")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, log_level="info")
