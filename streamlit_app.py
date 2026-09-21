"""
TradeEdge - Unified OI Analyzer
Streamlit app: 3 engines + Supabase persistence + charts
"""
import os
import time
import threading
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from fyers_apiv3 import fyersModel

from engines.oi_engine import analyse_oi
from engines.premium_bias import premium_bias
from engines.atp_ltp import atp_ltp_bias, detect_martingale, three_triggers

load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------- Config ----------------
INDEXES = {
    "NIFTY":     {"spot": "NSE:NIFTY50-INDEX",   "step": 50,  "lot": 50},
    "BANKNIFTY": {"spot": "NSE:NIFTYBANK-INDEX", "step": 100, "lot": 15},
    "FINNIFTY":  {"spot": "NSE:FINNIFTY-INDEX",  "step": 50,  "lot": 40},
}
SNAPSHOT_INTERVAL = 30


# ---------------- Secrets ----------------
def get_secret(key):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


# ---------------- Singletons ----------------
_fyers_client = None


def get_fyers():
    global _fyers_client
    if _fyers_client is None:
        _fyers_client = fyersModel.FyersModel(
            client_id=get_secret("FYERS_CLIENT_ID"),
            token=get_secret("FYERS_ACCESS_TOKEN"),
            is_async=False,
            log_path="",
        )
    return _fyers_client


_sb_client = None


def get_supabase():
    global _sb_client
    if _sb_client is None:
        _sb_client = create_client(
            get_secret("SUPABASE_URL"),
            get_secret("SUPABASE_KEY"),
        )
    return _sb_client


# ---------------- Fyers helpers ----------------
def get_spot(fyers, symbol):
    r = fyers.quotes({"symbols": symbol})
    if "d" not in r or not r["d"]:
        print(f"[get_spot] ERROR for {symbol}: {r}")
        raise RuntimeError(f"Fyers quote failed for {symbol}: {r}")
    return float(r["d"][0]["v"]["lp"])


def get_option_chain(fyers, symbol, strikes=50):
    payload = {
        "symbol": symbol,
        "strikecount": strikes,
        "timestamp": "",
        "greeks": False,
    }
    r = fyers.optionchain(data=payload)
    if r.get("s") != "ok":
        print(f"[get_option_chain] ERROR for {symbol}: {r}")
        raise RuntimeError(f"Option chain error: {r}")
    rows = []
    for it in r["data"]["optionsChain"]:
        if it["option_type"] == "":
            continue
        rows.append({
            "strike": it["strike_price"],
            "type": it["option_type"],
            "ltp": it.get("ltp", 0),
            "oi": it.get("oi", 0),
            "volume": it.get("volume", 0),
        })
    return rows


# ---------------- Snapshot writer ----------------
def start_writer():
    if st.session_state.get("writer_started"):
        return

    def worker():
        sb = get_supabase()
        fyers = get_fyers()
        while True:
            for idx, meta in INDEXES.items():
                try:
                    spot = get_spot(fyers, meta["spot"])
                    chain = get_option_chain(fyers, meta["spot"])
                    res = analyse_oi(chain, spot)
                    row = {
                        "index_name": idx,
                        "spot": spot,
                        "max_pain": res.max_pain,
                        "pcr": res.pcr,
                        "range_low": res.range_low,
                        "range_high": res.range_high,
                        "top_res_strike": res.resistances[0]["strike"] if res.resistances else None,
                        "top_res_oi": res.resistances[0]["oi"] if res.resistances else None,
                        "top_sup_strike": res.supports[0]["strike"] if res.supports else None,
                        "top_sup_oi": res.supports[0]["oi"] if res.supports else None,
                    }
                    sb.table("oi_snapshots").insert(row).execute()
                except Exception as e:
                    print(f"[writer] {idx} error: {e}")
            time.sleep(SNAPSHOT_INTERVAL)

    threading.Thread(target=worker, daemon=True).start()
    st.session_state.writer_started = True


# ---------------- Page ----------------
st.set_page_config(page_title="TradeEdge - OI Analyzer", layout="wide")
st.title("TradeEdge - Unified OI Analyzer")

with st.sidebar:
    st.header("Settings")
    index = st.selectbox("Index", list(INDEXES.keys()), index=0)
    refresh_sec = st.slider("Auto-refresh (seconds)", 15, 120, 30)
    st.markdown("---")
    st.caption(f"Last render: {datetime.now(IST):%H:%M:%S} IST")

start_writer()

# Fetch live data
try:
    fyers = get_fyers()
    meta = INDEXES[index]
    spot = get_spot(fyers, meta["spot"])
    chain = get_option_chain(fyers, meta["spot"])

    e1 = analyse_oi(chain, spot)
    e2 = premium_bias(chain, spot, meta["step"])
    e3_ce = atp_ltp_bias(chain, spot, meta["step"], "CE")
    e3_pe = atp_ltp_bias(chain, spot, meta["step"], "PE")
    mg_ce = detect_martingale(chain, spot, meta["step"], "CE")
    mg_pe = detect_martingale(chain, spot, meta["step"], "PE")
except Exception as e:
    st.error(f"Fetch error: {e}")
    st.stop()

# Top metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Spot", f"{spot:,.2f}")
c2.metric("Max Pain", e1.max_pain)
c3.metric("PCR", f"{e1.pcr:.3f}")
c4.metric("Expiry Zone", e1.expected_expiry_zone)

st.markdown("---")

# ---------------- Engine 1 ----------------
st.subheader("Engine 1 - Base OI (Support / Resistance / Max Pain)")
colL, colR = st.columns(2)
with colL:
    st.write("**Resistances (High CALL OI)**")
    for r in e1.resistances:
        st.write(f"- `{r['strike']}` - OI {r['oi']:,}")
with colR:
    st.write("**Supports (High PUT OI)**")
    for s in e1.supports:
        st.write(f"- `{s['strike']}` - OI {s['oi']:,}")

# Crowd trap: show top-2 walls per side
st.warning(e1.crowd_trap_warning["advice"])

colWC, colWP = st.columns(2)
with colWC:
    st.caption("Top CALL walls (avoid buying CALLs here)")
    for w in e1.crowd_trap_warning.get("top_call_walls", []):
        st.write(f"- `{w['strike']}` - OI {w['oi']:,}")
with colWP:
    st.caption("Top PUT walls (avoid buying PUTs here)")
    for w in e1.crowd_trap_warning.get("top_put_walls", []):
        st.write(f"- `{w['strike']}` - OI {w['oi']:,}")
# ---------------- Engine 2 ----------------
st.subheader("Engine 2 - Premium Bias (ATM vs ITM)")
if e2["bias"] == "BEARISH":
    bias_tag = "[BEARISH]"
elif e2["bias"] == "BULLISH":
    bias_tag = "[BULLISH]"
else:
    bias_tag = "[NEUTRAL]"

st.write(f"{bias_tag} Bias: {e2['bias']}")
st.write(f"ATM CE: {e2['atm_ce']} | ITM CE: {e2['itm_ce']}")
st.write(f"ATM PE: {e2['atm_pe']} | ITM PE: {e2['itm_pe']}")
st.write(f"Call richness: {e2['call_richness']} | Put richness: {e2['put_richness']}")

# ---------------- Engine 3 ----------------
st.subheader("Engine 3 - ATP-LTP Bias + Martingale + 3 Triggers")

# CE side
st.write("**CE side**")
if e3_ce:
    st.write(
        f"ATM {e3_ce['atm_ltp']} | ITM {e3_ce['itm_ltp']} | "
        f"ATM ATP-LTP: {e3_ce['atm_atp_ltp']} | ITM ATP-LTP: {e3_ce['itm_atp_ltp']}"
    )
    st.write(f"Signal: **{e3_ce['signal']}** — {e3_ce['reason']}")

# PE side
st.write("**PE side**")
if e3_pe:
    st.write(
        f"ATM {e3_pe['atm_ltp']} | ITM {e3_pe['itm_ltp']} | "
        f"ATM ATP-LTP: {e3_pe['atm_atp_ltp']} | ITM ATP-LTP: {e3_pe['itm_atp_ltp']}"
    )
    st.write(f"Signal: **{e3_pe['signal']}** — {e3_pe['reason']}")

# Martingale
st.write("**Martingale watch**")
st.write(f"CE stack ratio: {mg_ce['stack_ratio']} (threshold {mg_ce['threshold']}) "
         f"{'[MARTINGALE]' if mg_ce['martingale_flag'] else ''}")
st.write(f"PE stack ratio: {mg_pe['stack_ratio']} (threshold {mg_pe['threshold']}) "
         f"{'[MARTINGALE]' if mg_pe['martingale_flag'] else ''}")

# ---------------- Live OI Chart ----------------
st.subheader("Live OI Chain")
df = pd.DataFrame(chain)
chart_df = (
    df.pivot_table(index="strike", columns="type", values="oi", aggfunc="sum")
      .fillna(0)
)
# Ensure both columns exist
for col in ["CE", "PE"]:
    if col not in chart_df.columns:
        chart_df[col] = 0

chart_df = chart_df.rename(columns={"CE": "Call OI", "PE": "Put OI"})
st.bar_chart(chart_df, color=["#e74c3c", "#2ecc71"])  # red = calls, green = puts

# ---------------- History from Supabase ----------------
st.subheader("Max Pain Migration (IST, last 100 snapshots)")
try:
    sb = get_supabase()
    hist = sb.table("oi_snapshots") \
        .select("ts, max_pain, spot") \
        .eq("index_name", index) \
        .order("ts", desc=True) \
        .limit(100) \
        .execute()

    if hist.data:
        hdf = pd.DataFrame(hist.data).iloc[::-1]
        hdf["ts"] = pd.to_datetime(hdf["ts"], utc=True).dt.tz_convert("Asia/Kolkata")
        hdf["max_pain"] = pd.to_numeric(hdf["max_pain"], errors="coerce")
        hdf["spot"] = pd.to_numeric(hdf["spot"], errors="coerce")

        st.caption(
            f"{len(hdf)} snapshots | Latest spot: {hdf['spot'].iloc[-1]:.2f} "
            f"| Latest Max Pain: {int(hdf['max_pain'].iloc[-1])}"
        )

        # Raw values chart
        st.line_chart(
            hdf.set_index("ts")[["max_pain", "spot"]],
            color=["#e74c3c", "#3498db"],
        )

        # Delta chart: how far Max Pain is from Spot
        hdf["max_pain - spot"] = hdf["max_pain"] - hdf["spot"]
        st.caption("Max Pain - Spot (positive = max pain above spot)")
        st.line_chart(
            hdf.set_index("ts")[["max_pain - spot"]],
            color=["#9b59b6"],
        )
    else:
        st.caption("No history yet - first snapshot arriving soon.")
except Exception as e:
    st.caption(f"History fetch error: {e}")

# Auto-refresh
time.sleep(refresh_sec)
st.rerun()