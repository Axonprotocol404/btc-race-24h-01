[![make.fun](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/Axonprotocol404/btc-race-24h-01/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/Axonprotocol404/btc-race-24h-01/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)

# Surge Rider — a selective momentum bot for cbBTC

An entry for [Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261115-0828) on make.fun. The bot trades Coinbase Wrapped BTC (cbBTC) against USDC on one-minute on-chain bars, starting with $1,000 of paper money. Simulation only: nothing is traded for real.

## Strategy

One-minute bitcoin prices are mostly noise, and every round trip costs roughly 15–30 bps in fees, slippage and pool impact, so the bot sits in cash most of the time and trades only when the market shows a real leg:

- **Enter** when the 30-minute return is at least +0.6% *and* the 60-minute return is positive — a combination that fires only a few times a day.
- **Exit** the whole position on the first of: a −2% stop under cost, a +4% take-profit, a 1.5% trailing stop under the position's peak value, a momentum fade (30-minute return back under −0.4%), or 240 bars held.
- **Size** each entry at 60% of cash, keeping pool impact modest while letting a leg move the account.
- **Safety:** no new entry in the last hour of the window, and no new entry once equity has fallen 5% under its peak.

All decisions are integer basis-point comparisons on bar closes — no randomness, no wall clock, no network — so two runs on the same bars produce identical orders.

## Dev-window result (local, kit harness)

| Metric | Value |
| --- | --- |
| Net PnL | +$10.48 USDC |
| Trades | 6 |
| Max drawdown | 1.02% |

Verified end to end over the wire protocol (hello → 1,440 batches → done) with two runs producing byte-identical action logs.

## Run

The grader runs the bot as:

```sh
python3 -P -s main.py
```

Grade it locally against the kit's dev window with:

```sh
node cli/makefun.mjs grade-local --kit <kitdir> --bot . --driver docker
```

## Layout

- `main.py` — the entrypoint: speaks `agent-fun/bars-replay/v1` via the vendored SDK shim and turns the strategy's decisions into orders.
- `strategy.py` — the Surge Rider strategy (original code, standard library only).
- `vendor/makefun_bars.py` — a byte-for-byte copy of the kit's Python SDK shim.
- `.makefun/owner.json` — the payout wallet that owns this entry.
