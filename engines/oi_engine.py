"""
Engine 1 - Base OI Engine
Source: Transcript 3 (Options1) + Transcript 1
Logic:
  - High CALL OI  => RESISTANCE
  - High PUT  OI  => SUPPORT
  - Max Pain = strike minimising total writer payout
  - Market avoids high-OI strikes (matka-king logic)

Key fix: resistances/supports use a small buffer around spot so ATM
strikes aren't mislabelled as walls.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict


@dataclass
class OIResult:
    spot: float
    atm_strike: int
    resistances: List[Dict]
    supports: List[Dict]
    max_pain: int
    pcr: float
    range_low: int
    range_high: int
    expected_expiry_zone: str
    crowd_trap_warning: Dict


def analyse_oi(chain: List[dict], spot: float, top_n: int = 3) -> OIResult:
    ce = {r["strike"]: r["oi"] for r in chain if r["type"] == "CE"}
    pe = {r["strike"]: r["oi"] for r in chain if r["type"] == "PE"}
    strikes = sorted(set(ce) | set(pe))
    if not strikes:
        raise ValueError("Empty option chain")

    atm = min(strikes, key=lambda k: abs(k - spot))

    # ------------- Resistances / Supports with ATM buffer -------------
    # Buffer = 0.15% of spot (~35 pts for Nifty 23,400)
    # Anything within the buffer is considered "ATM zone" and excluded
    buffer = max(spot * 0.0015, 25)

    # Resistances: top CALL OI strikes strictly ABOVE spot + buffer
    ce_above = sorted(
        [(k, v) for k, v in ce.items() if k > spot + buffer],
        key=lambda x: -x[1],
    )[:top_n]
    resistances = [{"strike": int(k), "oi": int(v)} for k, v in ce_above]

    # Supports: top PUT OI strikes strictly BELOW spot - buffer
    pe_below = sorted(
        [(k, v) for k, v in pe.items() if k < spot - buffer],
        key=lambda x: -x[1],
    )[:top_n]
    supports = [{"strike": int(k), "oi": int(v)} for k, v in pe_below]

    # ------------- Max Pain -------------
    pain = {}
    for s in strikes:
        call_pay = sum(max(0, s - k) * ce.get(k, 0) for k in strikes)
        put_pay  = sum(max(0, k - s) * pe.get(k, 0) for k in strikes)
        pain[s] = call_pay + put_pay
    max_pain = int(min(pain, key=pain.get))

    # ------------- PCR -------------
    total_ce = sum(ce.values()) or 1
    total_pe = sum(pe.values()) or 0
    pcr = round(total_pe / total_ce, 3)

    # ------------- Expected expiry range -------------
    # Use nearest resistance/support around max_pain (not the widest)
    range_high = resistances[0]["strike"] if resistances else max_pain
    range_low  = supports[0]["strike"]    if supports    else max_pain
    zone = f"{range_low} - {range_high}"

           # ------------- Crowd trap (top-2 walls per side) -------------
    top_ce_strikes = sorted(ce.items(), key=lambda x: -x[1])[:2]
    top_pe_strikes = sorted(pe.items(), key=lambda x: -x[1])[:2]

    call_wall = top_ce_strikes[0] if top_ce_strikes else (None, 0)
    put_wall  = top_pe_strikes[0] if top_pe_strikes else (None, 0)

    crowd = {
        "highest_call_oi_strike": int(call_wall[0]) if call_wall[0] else None,
        "highest_call_oi_value":  int(call_wall[1]),
        "highest_put_oi_strike":  int(put_wall[0]) if put_wall[0] else None,
        "highest_put_oi_value":   int(put_wall[1]),
        "top_call_walls": [
            {"strike": int(k), "oi": int(v)} for k, v in top_ce_strikes
        ],
        "top_put_walls": [
            {"strike": int(k), "oi": int(v)} for k, v in top_pe_strikes
        ],
        "advice": (
            f"Major CALL wall at {call_wall[0]} ({call_wall[1]:,} OI). "
            f"Major PUT wall at {put_wall[0]} ({put_wall[1]:,} OI). "
            "Market avoids paying the crowd at these strikes."
        ) if call_wall[0] and put_wall[0] else "n/a",
    }

    return OIResult(
        spot=spot, atm_strike=int(atm),
        resistances=resistances, supports=supports,
        max_pain=max_pain, pcr=pcr,
        range_low=int(range_low), range_high=int(range_high),
        expected_expiry_zone=zone,
        crowd_trap_warning=crowd,
    )


def to_dict(r: OIResult) -> dict:
    return asdict(r)