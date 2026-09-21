"""
Engine 2 — Premium Bias Engine
Source: Transcript 1
Logic:
  - Compare ATM vs ITM premium of CE and PE
  - If PUTs are rich relative to CALLs => BEARISH
  - If CALLs are rich relative to PUTs => BULLISH
"""


def premium_bias(chain, spot, step):
    atm = round(spot / step) * step
    itm_ce = atm - step
    itm_pe = atm + step

    def px(strike, typ):
        for r in chain:
            if r["strike"] == strike and r["type"] == typ:
                return r["ltp"], r["oi"]
        return None, None

    atm_ce_ltp, _ = px(atm, "CE")
    itm_ce_ltp, _ = px(itm_ce, "CE")
    atm_pe_ltp, _ = px(atm, "PE")
    itm_pe_ltp, _ = px(itm_pe, "PE")

    # Fallbacks if a leg isn't present in the sliced chain
    atm_ce_ltp = atm_ce_ltp or 0
    itm_ce_ltp = itm_ce_ltp or 0
    atm_pe_ltp = atm_pe_ltp or 0
    itm_pe_ltp = itm_pe_ltp or 0

    # Extrinsic = premium - intrinsic (intrinsic for ITM ≈ step)
    ext_atm_ce = atm_ce_ltp
    ext_itm_ce = max(0, itm_ce_ltp - step)
    ext_atm_pe = atm_pe_ltp
    ext_itm_pe = max(0, itm_pe_ltp - step)

    # Richness = premium per unit delta (ATM Δ≈0.5, ITM Δ≈1)
    call_richness = (ext_atm_ce / 0.5) - (ext_itm_ce / 1.0)
    put_richness  = (ext_atm_pe / 0.5) - (ext_itm_pe / 1.0)

    bias = "NEUTRAL"
    if put_richness > call_richness * 1.2:
        bias = "BEARISH"
    elif call_richness > put_richness * 1.2:
        bias = "BULLISH"

    return {
        "atm_strike": int(atm),
        "atm_ce": atm_ce_ltp, "itm_ce": itm_ce_ltp,
        "atm_pe": atm_pe_ltp, "itm_pe": itm_pe_ltp,
        "call_richness": round(call_richness, 2),
        "put_richness": round(put_richness, 2),
        "bias": bias,
    }