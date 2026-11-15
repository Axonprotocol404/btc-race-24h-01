"""Surge Rider: a selective momentum bot for cbBTC (CBBTC/USDC) on make.fun.

The bot speaks agent-fun/bars-replay/v1 through the vendored SDK shim
(vendor/makefun_bars.py, a byte-for-byte copy of the kit's shim) and trades one
idea, in plain words:

  * Sit in cash most of the time. One-minute bitcoin prices are mostly noise,
    and every round trip costs roughly 15-30 bps in fees, slippage and pool
    impact, so trading often just pays the pool.
  * Enter only when the market shows a real leg: the 30-minute return is at
    least +0.6% *and* the 60-minute return is positive. That combination is
    rare (a handful of times a day) and marks the start of a sustained move
    rather than a one-minute wiggle.
  * Once in, let the leg run but cap the damage: exit on a hard stop (-2% of
    cost), a take-profit (+4%), a trailing stop (1.5% under the peak value),
    a momentum fade (30-minute return back under -0.4%), or after 240 bars.
  * Size each entry at 60% of cash: big enough for a leg to matter, small
    enough that the pool impact stays modest and a stopped-out trade costs
    little. Never enter in the last hour of the window, and stop entering
    altogether if equity ever falls 5% under its peak.

Everything is integer arithmetic on the bar closes (basis-point comparisons),
so two runs on the same bars produce the same orders byte for byte. No
network, no wall clock, no randomness, no files outside this repository.

Run locally against the kit's dev window with:
  node cli/makefun.mjs grade-local --kit <kitdir> --bot . --driver process
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "vendor"))

import makefun_bars
from strategy import SurgeRider

SYMBOL = "CBBTC"
MAX_SLIPPAGE_BPS = 100

_rider = SurgeRider()


def on_batch(state, batch):
    """Decide the orders for one batch: one buy or one sell, at most."""
    if state.warming_up:
        return []
    # A batch with no fresh bar for our symbol carries no new price: deciding
    # on it would re-run the same close and could double-count a signal.
    if not any(bar.get("symbol") == SYMBOL for bar in batch.get("bars", [])):
        return []
    bar = state.latest.get(SYMBOL)
    if bar is None:
        return []
    close = int(bar["c"])
    held = state.positions.get(SYMBOL)
    qty = held.qty if held is not None else 0
    cost = held.cost if held is not None else 0
    value = state.value(SYMBOL, qty) if qty > 0 else 0

    order = _rider.decide(
        close=close,
        cash=state.cash,
        qty=qty,
        cost=cost,
        value=value,
        equity=state.equity,
    )
    if order is None:
        return []
    if order[0] == "buy":
        # The strategy sizes at 60% of cash; clamp anyway so the order can
        # never trip the weight cap or the cash check, whatever the account
        # holds when the reply is built.
        notional = min(order[1], state.cash, state.weight_room(SYMBOL))
        if notional < 1_000_000:
            return []
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": notional,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return [{
        "side": "sell",
        "symbol": SYMBOL,
        "qty": qty,
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }]


def on_done(state, done):
    sys.stderr.write(
        "surge-rider done: final cash %d quote units, equity %d\n"
        % (state.cash, state.equity)
    )


makefun_bars.run(on_batch, on_done=on_done)
