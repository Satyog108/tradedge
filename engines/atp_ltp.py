"""
Engine 3 - ATP-LTP Bias + Martingale Detector + 3-Trigger System
Source: Transcript 2

Core formula:
    BIAS POSITIVE if (ATP - LTP of ITM) < (ATP - LTP of ATM)

Fyers does not expose true ATP in the option chain, so we use a
multi-tier fallback:
  Tier 1: row['atp'] if provided
  Tier 2: (prev_close_price + ltp) / 2 if prev_close available
  Tier 3: intrinsic + 0.5 * extrinsic
"""


def _intrinsic(strike, typ, spot):
    if typ == "CE":
        return max(0.0, spot - strike)
    return max(0.0, strike - spot)


def _atp_proxy(row, strike, typ, spot):
    if row is None:
        return None
    if row.get("atp") is not None:
        return float(row["atp"])
    prev = row.get("prev_close_price") or row.get("prev_close")
    if prev is not None:
        return (float(prev) + float(row["ltp"])) / 2.0
    ltp = float(row["ltp"])
    intrinsic = _intrinsic(strike, typ, spot)
    extrinsic = max(0.0, ltp - intrinsic)
    return intrinsic + 0.5 * extrinsic


def _find(chain, strike, typ):
    for r in chain:
        if r["strike"] == strike and r["type"] == typ:
            return r
    return None


def atp_ltp_bias(chain, spot, step, atm_side="CE"):
    atm = round(spot / step) * step
    itm = atm - step if atm_side == "CE" else atm + step

    atm_o = _find(chain, atm, atm_side)
    itm_o = _find(chain, itm, atm_side)
    if not atm_o or not itm_o:
        return None

    atm_ltp = float(atm_o["ltp"])
    itm_ltp = float(itm_o["ltp"])
    atm_atp = _atp_proxy(atm_o, atm, atm_side, spot)
    itm_atp = _atp_proxy(itm_o, itm, atm_side, spot)

    atm_atp_ltp = round(max(0.0, atm_atp - atm_ltp), 2)
    itm_atp_ltp = round(max(0.0, itm_atp - itm_ltp), 2)

    bias_positive = itm_atp_ltp < atm_atp_ltp

    if bias_positive:
        signal = "REVERSAL (BUY)"
        reason = f"ITM ATP-LTP ({itm_atp_ltp}) < ATM ATP-LTP ({atm_atp_ltp})"
    else:
        signal = "NO SIGNAL"
        reason = f"ITM ATP-LTP ({itm_atp_ltp}) >= ATM ATP-LTP ({atm_atp_ltp})"

    return {
        "atm_strike": int(atm), "itm_strike": int(itm),
        "atm_ltp": atm_ltp, "itm_ltp": itm_ltp,
        "atm_atp": round(atm_atp, 2), "itm_atp": round(itm_atp, 2),
        "atm_atp_ltp": atm_atp_ltp,
        "itm_atp_ltp": itm_atp_ltp,
        "bias_positive": bias_positive,
        "signal": signal,
        "reason": reason,
    }


def detect_martingale(chain, spot, step, side="CE", threshold=1.5):
    atm = round(spot / step) * step
    itm = atm - step if side == "CE" else atm + step

    atm_o = _find(chain, atm, side)
    itm_o = _find(chain, itm, side)
    a = atm_o["oi"] if atm_o else 0
    i = itm_o["oi"] if itm_o else 0

    ratio = round(i / a, 3) if a else 0.0
    flag = ratio > threshold

    return {
        "atm_oi": a, "itm_oi": i,
        "stack_ratio": ratio,
        "martingale_flag": flag,
        "threshold": threshold,
        "note": "Big player likely averaging down" if flag else "Normal stacking",
    }


def three_triggers(chain, spot, step, ema5=None, ema8=None,
                   prev_oi=None, curr_oi=None, atm_side="CE"):
    bias = atp_ltp_bias(chain, spot, step, atm_side)
    t1 = bool(bias and bias["bias_positive"])

    t2 = None
    if ema5 is not None and ema8 is not None:
        t2 = (ema5 > ema8) if atm_side == "CE" else (ema5 < ema8)

    t3 = None
    if prev_oi is not None and curr_oi is not None:
        t3 = curr_oi < prev_oi

    fired = sum(x for x in [t1, t2, t3] if x is True)

    if fired == 3:
        action = "ENTER"
    elif fired == 2:
        action = "WAIT - 1 trigger missing"
    else:
        action = "NO TRADE"

    return {
        "side": atm_side,
        "trigger1_bias": t1,
        "trigger2_ema_cross": t2,
        "trigger3_oi_drop": t3,
        "triggers_fired": fired,
        "action": action,
        "detail": bias,
    }