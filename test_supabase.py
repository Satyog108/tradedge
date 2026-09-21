import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"Connecting to: {url}")
print(f"Key length: {len(key)}")
print()

supabase = create_client(url, key)

# Insert one test row
test_row = {
    "index_name": "NIFTY",
    "spot": 23346.4,
    "max_pain": 23350,
    "pcr": 0.92,
    "range_low": 23300,
    "range_high": 23400,
    "top_res_strike": 23500,
    "top_res_oi": 9506000,
    "top_sup_strike": 23300,
    "top_sup_oi": 13081000,
}

print("Inserting test row...")
result = supabase.table("oi_snapshots").insert(test_row).execute()
print(f"Insert OK. Returned {len(result.data)} row(s).")

# Read it back
print("\nReading latest 3 rows:")
rows = supabase.table("oi_snapshots") \
    .select("*") \
    .order("ts", desc=True) \
    .limit(3) \
    .execute()

for r in rows.data:
    print(f"  {r['ts']} | {r['index_name']} | Spot={r['spot']} | MaxPain={r['max_pain']} | PCR={r['pcr']}")

print(f"\nTotal rows fetched: {len(rows.data)}")