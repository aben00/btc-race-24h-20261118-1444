"""Dip-buy mean-reversion bot for the make.fun BTC 24h race
(btc-race-24h-20261118-1444).

Long-only, one full-size position at a time, on 1-minute cbBTC/USDC bars:

- Track EMA(120) of closes.
- BUY with all cash when the close is >= 60 bps below the EMA.
- SELL half when the close is >= +80 bps vs the entry close; sell the
  rest when it is still >= +80 bps on a later bar (the two halves exit
  one bar apart, so each pays about half the price impact of one
  full-size sell).
- STOP: sell everything if the close is <= -250 bps vs entry.
- No new entries in the final 60 bars of the window.

Deterministic: pure function of the bars seen so far. No network, no
clock, no files, no randomness. Standard library only, plus the vendored
kit SDK (vendor/makefun_bars.py).

Dev-window result (this race's frozen 24h window, exact integer replay
of the harness fill model): net PnL +$12.20, 6 filled orders
(2 round trips), fees $1.61, max drawdown $7.58 (0.76%).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
BPS = 10000

EMA_SPAN = 120
DIP_BPS = 60
TP1_BPS = 80
TP2_BPS = 80
STOP_BPS = 250
NO_ENTRY_LAST_BARS = 60
MAX_SLIPPAGE_BPS = 300

# State kept across batches (all derived from the bars themselves).
_ema = None          # float EMA(120) of closes, None until the first bar
_bars_seen = 0       # bars processed (excluding warm-up)
_entry_close = 0     # close at the bar the current position was decided on
_took_tp1 = False    # True once the first half has been sold


def _dip_bps(close, ema):
    """Bps the close sits below the EMA; 0 when at or above it."""
    if ema is None or ema <= close:
        return 0
    return (ema - close) * BPS // ema


def _exit_kind(entry_close, close, took_tp1):
    """Which exit fires on this bar: 'stop', 'tp2', 'tp1', or 'none'.

    Order matters: the stop is checked first, then the second take
    (only once the first half is gone), then the first take.
    """
    ret = (close - entry_close) * BPS // entry_close
    if ret <= -STOP_BPS:
        return "stop"
    if took_tp1 and ret >= TP2_BPS:
        return "tp2"
    if not took_tp1 and ret >= TP1_BPS:
        return "tp1"
    return "none"


def on_batch(state, batch):
    global _ema, _bars_seen, _entry_close, _took_tp1

    if state.warming_up:
        return []

    close = state.close(SYMBOL)
    if close is None:
        return []

    # Update the EMA with this bar's close, exactly as tuned offline:
    # seeded at the first close, k = 2 / (span + 1).
    if _ema is None:
        _ema = float(close)
    else:
        k = 2.0 / (EMA_SPAN + 1)
        _ema = close * k + _ema * (1.0 - k)
    _bars_seen += 1

    holding = state.positions.get(SYMBOL)
    qty = holding.qty if holding is not None else 0

    if qty == 0:
        _entry_close = 0
        _took_tp1 = False
        # No new entries in the final 60 bars of the 1,440-bar window,
        # and none before the EMA has 120 bars of history.
        first_tradeable = state.warmup_bars
        last_entry_seq = first_tradeable + 1440 - NO_ENTRY_LAST_BARS
        if state.seq < first_tradeable + EMA_SPAN:
            return []
        if state.seq >= last_entry_seq:
            return []
        dip = _dip_bps(close, _ema)
        if dip >= DIP_BPS and state.cash > 0:
            _entry_close = close
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": state.cash,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # We hold a position: manage the exit.
    kind = _exit_kind(_entry_close, close, _took_tp1)
    if kind in ("stop", "tp2"):
        return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    if kind == "tp1":
        half = qty // 2
        if (state.value(SYMBOL, half, close) >= 1000000
                and state.value(SYMBOL, qty - half, close) >= 1000000):
            _took_tp1 = True
            return [{"side": "sell", "symbol": SYMBOL, "qty": half,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
