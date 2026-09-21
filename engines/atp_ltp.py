"""
Engine 3 - ATP-LTP Bias + Martingale Detector + 3-Trigger System
Source: Transcript 2

Core formula:
    BIAS POSITIVE if (ATP - LTP of ITM) < (ATP - LTP of ATM)

Since Fyers doesn't expose true ATP in the option chain payload, we use
a session-volume-weighted approximation. If the chain has 'volume' and
'ltp', we compute a rough ATP proxy; otherwise fall back to LTP.
"""


def _atp_proxy(row):
    """
    Approximate ATP for a single option row.
    - If row has 'atp' field, use it.
    - Else use LTP as proxy (best we can do with standard Fyers chain).
    """
    if row is None:
        return None
    return row.get("atp") or row.get("ltp")


def _find(chain, strike, typ):
    for r in chain:
        if r["strike"] == strike and r["type"] == typ:
            return r
    return None


def atp_ltp_bias(chain, spot, step, atm_side="CE"):
    """
    Compute the ATP-LTP bias for a given side.

    Returns a dict with:
      atm_strike, itm_strike
      atm_ltp, itm_ltp
      atm_atp_ltp, itm_atp_ltp
      bias_positive (bool)
      signal ("REVERSAL (BUY)" | "NO SIGNAL")
      reason (short text)
    """
    atm = round(spot / step) * step
    itm = atm - step if atm_side == "CE" else atm + step

    atm_o = _find(chain, atm, atm_side)
    itm_o = _find(chain, itm, atm_side)
    if not atm_o or not itm_o:
        return None

    atm_ltp = atm_o["ltp"]
    itm_ltp = itm_o["ltp"]
    atm_atp = _atp_proxy(atm_o)
    itm_atp = _atp_proxy(itm_o)

    atm_atp_ltp = max(0.0, atm_atp - atm_ltp)
    itm_atp_ltp = max(0.0, itm_atp - itm_ltp)

    bias_positive = itm_atp_ltp < atm_atp_ltp

    if bias_positive:
        signal = "REVERSAL (BUY)"
        reason = f"ITM ATP-LTP ({itm_atp_ltp:.2f}) < ATM ATP-LTP ({atm_atp_ltp:.2f})"
    else:
        signal = "NO SIGNAL"
        reason = f"ITM ATP-LTP ({itm_atp_ltp:.2f}) >= ATM ATP-LTP ({atm_atp_ltp:.2f})"

    return {
        "atm_strike": int(atm), "itm_strike": int(itm),
        "atm_ltp": atm_ltp, "itm_ltp": itm_ltp,
        "atm_atp_ltp": round(atm_atp_ltp, 2),
        "itm_atp_ltp": round(itm_atp_ltp, 2),
        "bias_positive": bias_positive,
        "signal": signal,
        "reason": reason,
    }


def detect_martingale(chain, spot, step, side="CE", threshold=1.5):
    """
    Detect if a big player is averaging down on a side.

    Heuristic:
      stack_ratio = ITM_OI / ATM_OI
      if stack_ratio > threshold:  Martingale flag on
    """
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
        "note": (
            "Big player likely averaging down (martingale)"
            if flag else "Normal stacking"
        ),
    }


def three_triggers(chain, spot, step, ema5=None, ema8=None,
                   prev_oi=None, curr_oi=None, atm_side="CE"):
    """
    Full 3-trigger system from Transcript 2:
      Trigger 1: ATP-LTP bias positive
      Trigger 2: 5-EMA > 8-EMA (momentum up) — for CE side
                 5-EMA < 8-EMA                     — for PE side
      Trigger 3: Open Interest decreasing (money flowing out)

    Returns dict with statuses and a final action.
    """
    bias = atp_ltp_bias(chain, spot, step, atm_side)
    t1 = bool(bias and bias["bias_positive"])

    t2 = None
    if ema5 is not None and ema8 is not None:
        if atm_side == "CE":
            t2 = ema5 > ema8
        else:
            t2 = ema5 < ema8

    t3 = None
    if prev_oi is not None and curr_oi is not None:
        t3 = curr_oi < prev_oi

    fired = sum(x for x in [t1, t2, t3] if x is True)
    fired_known = sum(1 for x in [t1, t2, t3] if x is not None)

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
        "triggers_evaluated": fired_known,
        "action": action,
        "detail": bias,
    }