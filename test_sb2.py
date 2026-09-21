import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("URL:", url)
print("Key prefix:", key[:20] if key else "MISSING")
print("Key length:", len(key) if key else 0)
print()

client = create_client(url, key)

# Try inserting a test row
try:
    r = client.table("oi_snapshots").insert({
        "index_name": "TEST",
        "spot": 23346.4,
        "max_pain": 23350,
        "pcr": 1.0,
        "range_low": 23300,
        "range_high": 23500,
    }).execute()
    print("INSERT OK:", r.data)
except Exception as e:
    print("INSERT FAILED:", e)

# Try reading back
try:
    r = client.table("oi_snapshots").select("*").limit(3).execute()
    print("READ OK. Rows:", len(r.data))
    for row in r.data:
        print("  ", row.get("index_name"), row.get("ts"))
except Exception as e:
    print("READ FAILED:", e)