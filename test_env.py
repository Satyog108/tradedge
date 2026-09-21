import os
from dotenv import load_dotenv

load_dotenv()

for k in ["FYERS_CLIENT_ID", "FYERS_SECRET_KEY", "FYERS_ACCESS_TOKEN",
          "SUPABASE_URL", "SUPABASE_KEY"]:
    v = os.getenv(k)
    if v:
        print(f"OK  {k}: {v[:15]}... (len={len(v)})")
    else:
        print(f"ERR {k}: MISSING")