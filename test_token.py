from fyers_apiv3 import fyersModel

CLIENT_ID = "XXXXXXXXXX-100"   # ← paste your actual App ID
token = open("access_token.txt").read().strip()

fyers = fyersModel.FyersModel(
    client_id=CLIENT_ID,
    token=token,
    is_async=False,
    log_path=""
)

# Test 1: Get Nifty spot
r = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX"})
print("✅ Spot:", r["d"][0]["v"]["lp"])

# Test 2: Fetch option chain
payload = {
    "symbol": "NSE:NIFTY50-INDEX",
    "strikecount": 5,
    "timestamp": "",
    "greeks": False,
}
r2 = fyers.optionchain(data=payload)
if r2.get("s") == "ok":
    print("✅ Option chain rows:", len(r2["data"]["optionsChain"]))
else:
    print("❌ Chain error:", r2)