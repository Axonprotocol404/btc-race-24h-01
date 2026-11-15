"""Surge Rider strategy: selective momentum on one-minute cbBTC closes.

Design (all thresholds in basis points, all comparisons in integers):

  ENTRY -- only when both hold at a bar's close:
    * 30-minute return >= +60 bps (a real leg, not a one-minute wiggle)
    * 60-minute return > 0 (the leg agrees with the slower trend)
  The two together fire only a few times a day, so the bot sits in cash
  through chop and pays the round-trip cost only when a move is under way.

  EXIT -- the whole position, on the first of:
    * stop: value <= cost - 2%
    * take-profit: value >= cost + 4%
    * trailing stop: value <= peak value - 1.5%
    * fade: 30-minute return <= -40 bps (the leg has rolled over)
    * stale: held for 240 bars without an exit firing

  SIZING -- each entry spends 60% of cash. Full size would pay about 15 bps
  of pool impact a side at this pool's depth; 60% keeps the impact near
  9 bps while still letting a leg move the account.

  SAFETY -- no new entry once 1,380 bars of the window have been seen (a
  position opened in the last hour has no room to earn its round-trip
  cost), and no new entry once equity has fallen 5% under its peak.

The class keeps only the closes it has seen and a few counters. It never
reads the clock, the environment or any file, and it uses no randomness, so
the same bars always give the same decision.
"""

# Entry: 30-minute and 60-minute returns, in basis points.
MOMENTUM_WINDOW = 30
MOMENTUM_MIN_BPS = 60
TREND_WINDOW = 60

# Sizing: basis points of cash spent on one entry.
SIZE_BPS = 6000
# The harness refuses a buy under this many quote units (1 USDC).
MIN_NOTIONAL_QUOTE_UNITS = 1_000_000

# Exits, in basis points.
STOP_BPS = 200          # value this far under cost
TAKE_PROFIT_BPS = 400   # value this far over cost
TRAILING_BPS = 150      # value this far under its peak since entry
FADE_BPS = -40          # 30-minute return this low means the leg faded
MAX_HOLD_BARS = 240

# Safety: no new entry after this many bars seen, or once equity is this
# far (basis points) under its peak.
LATE_BAR_CUTOFF = 1380
HALT_DRAWDOWN_BPS = 500

_BPS = 10_000


class SurgeRider:
    """One-symbol, long-only, single-position momentum rider."""

    def __init__(self):
        self.closes = []        # closes seen, oldest first, as ints
        self.peak_value = 0     # peak value of the open position, quote units
        self.bars_held = 0      # bars since the current position opened
        self.peak_equity = 0    # peak equity seen, quote units
        self.halted = False     # drawdown guard tripped: entries off

    def decide(self, close, cash, qty, cost, value, equity):
        """Return ("buy", notional) / ("sell",) / None for this bar's close."""
        self.closes.append(close)
        if equity > self.peak_equity:
            self.peak_equity = equity
        if (
            not self.halted
            and self.peak_equity > 0
            and equity * _BPS < self.peak_equity * (_BPS - HALT_DRAWDOWN_BPS)
        ):
            self.halted = True

        if qty > 0:
            return self._exit(close, qty, cost, value)
        self.peak_value = 0
        self.bars_held = 0
        return self._entry(close, cash)

    def _exit(self, close, qty, cost, value):
        self.bars_held += 1
        if value > self.peak_value:
            self.peak_value = value
        if value * _BPS <= cost * (_BPS - STOP_BPS):
            return ("sell",)
        if value * _BPS >= cost * (_BPS + TAKE_PROFIT_BPS):
            return ("sell",)
        if value * _BPS <= self.peak_value * (_BPS - TRAILING_BPS):
            return ("sell",)
        if len(self.closes) > MOMENTUM_WINDOW:
            past = self.closes[-1 - MOMENTUM_WINDOW]
            if close * _BPS <= past * (_BPS + FADE_BPS):
                return ("sell",)
        if self.bars_held >= MAX_HOLD_BARS:
            return ("sell",)
        return None

    def _entry(self, close, cash):
        if self.halted:
            return None
        if len(self.closes) > LATE_BAR_CUTOFF:
            return None
        if len(self.closes) <= TREND_WINDOW:
            return None
        past_momentum = self.closes[-1 - MOMENTUM_WINDOW]
        past_trend = self.closes[-1 - TREND_WINDOW]
        if close * _BPS < past_momentum * (_BPS + MOMENTUM_MIN_BPS):
            return None
        if close <= past_trend:
            return None
        notional = cash * SIZE_BPS // _BPS
        if notional < MIN_NOTIONAL_QUOTE_UNITS:
            return None
        return ("buy", notional)
