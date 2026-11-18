# Strategy

## What the bot does

Long-only mean reversion on 1-minute cbBTC/USDC bars, one full-size
position at a time:

1. Maintain EMA(120) of closes.
2. Buy with all cash when the close is ≥ 60 bps below the EMA.
3. Sell half at +80 bps vs the entry close; sell the rest when the close
   is still ≥ +80 bps on a later bar.
4. Stop-loss: sell all at −250 bps vs entry.
5. No new entries in the last 60 bars (a position opened there has no
   time to recover and would only pay entry costs at the flatten).

## Why this shape

Analysis of the 1,440-bar dev window (2026-11-17 14:45Z → 2026-11-18 14:44Z,
BTC $65,083 → $63,261, −2.80% — a falling day, buy-and-hold −$28.00):

- **Dips revert fast, then fade.** Buying the next open after the close
  sits ≥ 50 bps below EMA(60) earned +35 bps on average over the next
  30 minutes (83% of signals positive), but only ~+1 bp over 60 minutes.
  At ≥ 60 bps the 30-minute figure is +48 bps (95% positive). That is the
  whole edge: buy a dip, bank the quick recovery, do not wait around.
- **The old parameters fail here.** The previous race's EMA(60) / dip 50 /
  +80 / +200 / −250 set loses −$6.03 on this window: the +200 second leg
  rides the recovery back down. Exiting the rest at +80 instead of +200
  is worth about +$6 on this window.
- **Costs dominate small moves.** A full-size round trip costs ~36 bps
  (4 bps fee + 2 bps slippage + ~12 bps impact each way at ~$844k median
  pool depth). A +80 bps target clears that with margin; a 30–40 bps
  target would not — shallow-dip variants (dip 30) lost $9–$19.
- **EMA(120) beats EMA(60) here.** Across spans 100–120 with dip 60 /
  +80 exits, net PnL is +$12.20 to +$13.04 with max drawdown under 1%;
  EMA(130+) turns negative. The chosen span sits in the middle of that
  plateau, not at a sharp peak.

## Dev-window result (exact integer replay of the harness fill model)

- Net PnL **+$12.20** on $1,000 starting capital (buy-and-hold: −$28.00).
- 6 filled orders (2 round trips), fees $1.61, max drawdown 0.76%.
- Deterministic: two full runs produce byte-identical action logs.
  Zero rejected fills; the bot exits 0.

## Honest limits

- The edge rests on **2 round trips** in one 24-hour window. That is a
  tiny sample: the second 12 hours of the dev window produced zero
  qualifying dips at all. A different day can easily give fewer dips,
  dips that keep falling (the −250 bps stop caps that case), or
  recoveries that stall below +80 bps.
- The race window is a different 24 hours. Nothing here predicts it; the
  bot only applies the same rule to whatever prices arrive.
- If no dip of ≥ 60 bps vs EMA(120) occurs, the bot trades nothing and
  scores $0. Small changes near the threshold flip the result: dip 55
  loses money on this window while dip 60 makes $12 — the signal is real
  but the margin is thin, and the dev gate (+$0) is passed with $12.20
  of headroom, not with a wide cushion.
