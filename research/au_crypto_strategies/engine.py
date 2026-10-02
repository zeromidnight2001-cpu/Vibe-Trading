"""Event-driven trade backtester with TP/SL, fees, financing, and metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from venues.fees import Venue


@dataclass
class Trade:
    symbol: str
    side: int  # +1 long, -1 short
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    qty: float = 0.0
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    financing: float = 0.0
    exit_reason: str = ""
    pnl: float = 0.0


@dataclass
class BacktestResult:
    strategy: str
    venue: str
    params: dict[str, Any]
    trades: list[Trade]
    equity_curve: pd.Series
    metrics: dict[str, float]


def _slip(price: float, side: int, is_entry: bool, slippage_bps: float) -> float:
    direction = side if is_entry else -side
    return price * (1.0 + direction * slippage_bps / 10000.0)


def _equity(cash: float, trade: Trade | None, mark: float) -> float:
    if trade is None:
        return cash
    # cash excludes open notional for longs (spent) and includes short proceeds
    if trade.side > 0:
        return cash + trade.qty * mark
    return cash - trade.qty * mark


def run_symbol_trades(
    df: pd.DataFrame,
    signal: pd.Series,
    venue: Venue,
    *,
    symbol: str,
    initial_cash: float,
    risk_fraction: float,
    tp_atr: float,
    sl_atr: float,
    atr: pd.Series,
    allow_short: bool,
    max_hold_bars: int = 40,
) -> tuple[list[Trade], pd.Series]:
    cash = float(initial_cash)
    equity_vals: list[float] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None
    hold_bars = 0

    idx = df.index
    closes = df["Close"].astype(float)
    highs = df["High"].astype(float)
    lows = df["Low"].astype(float)
    sig = signal.reindex(idx).fillna(0).astype(int)

    for i, ts in enumerate(idx):
        c = float(closes.iloc[i])
        h = float(highs.iloc[i])
        lo = float(lows.iloc[i])
        a = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else float("nan")
        s = int(sig.iloc[i])

        if open_trade is not None:
            notional = abs(open_trade.qty * c)
            rate = venue.long_financing_daily if open_trade.side > 0 else venue.short_financing_daily
            fin = notional * rate
            open_trade.financing += fin
            cash -= fin
            hold_bars += 1

            exit_px = None
            reason = ""
            if a == a and a > 0:  # not NaN
                if open_trade.side > 0:
                    tp = open_trade.entry_price + tp_atr * a
                    sl = open_trade.entry_price - sl_atr * a
                    hit_tp, hit_sl = h >= tp, lo <= sl
                else:
                    tp = open_trade.entry_price - tp_atr * a
                    sl = open_trade.entry_price + sl_atr * a
                    hit_tp, hit_sl = lo <= tp, h >= sl
                if hit_sl:
                    exit_px, reason = sl, "stop"
                elif hit_tp:
                    exit_px, reason = tp, "take_profit"
            if exit_px is None and (
                hold_bars >= max_hold_bars or s == 0 or (allow_short and s == -open_trade.side)
            ):
                exit_px, reason = c, "signal_or_time"

            if exit_px is not None:
                fill = _slip(exit_px, open_trade.side, False, venue.slippage_bps)
                fee = venue.commission_fn(abs(open_trade.qty * fill), False)
                if open_trade.side > 0:
                    cash += open_trade.qty * fill
                else:
                    cash -= open_trade.qty * fill
                cash -= fee
                gross = open_trade.side * open_trade.qty * (fill - open_trade.entry_price)
                open_trade.exit_time = ts
                open_trade.exit_price = fill
                open_trade.exit_fee = fee
                open_trade.exit_reason = reason
                open_trade.pnl = gross - open_trade.entry_fee - fee - open_trade.financing
                trades.append(open_trade)
                open_trade = None
                hold_bars = 0

        if open_trade is None and s != 0 and a == a and a > 0:
            side = 1 if s > 0 else -1
            if side < 0 and not allow_short:
                equity_vals.append(_equity(cash, open_trade, c))
                continue
            risk_cash = cash * risk_fraction
            if risk_cash < 50 or cash < 100:
                equity_vals.append(_equity(cash, open_trade, c))
                continue
            entry_px = _slip(c, side, True, venue.slippage_bps)
            qty = risk_cash / entry_px
            fee = venue.commission_fn(abs(qty * entry_px), True)
            if side > 0:
                need = qty * entry_px + fee
                if need > cash:
                    qty = max(cash - fee, 0) * 0.99 / entry_px
                    fee = venue.commission_fn(abs(qty * entry_px), True)
                if qty <= 0:
                    equity_vals.append(_equity(cash, open_trade, c))
                    continue
                cash -= qty * entry_px + fee
            else:
                cash += qty * entry_px
                cash -= fee
            open_trade = Trade(
                symbol=symbol,
                side=side,
                entry_time=ts,
                entry_price=entry_px,
                qty=qty,
                entry_fee=fee,
            )
            hold_bars = 0

        equity_vals.append(_equity(cash, open_trade, c))

    if open_trade is not None:
        ts = idx[-1]
        c = float(closes.iloc[-1])
        fill = _slip(c, open_trade.side, False, venue.slippage_bps)
        fee = venue.commission_fn(abs(open_trade.qty * fill), False)
        if open_trade.side > 0:
            cash += open_trade.qty * fill
        else:
            cash -= open_trade.qty * fill
        cash -= fee
        gross = open_trade.side * open_trade.qty * (fill - open_trade.entry_price)
        open_trade.exit_time = ts
        open_trade.exit_price = fill
        open_trade.exit_fee = fee
        open_trade.exit_reason = "eod"
        open_trade.pnl = gross - open_trade.entry_fee - fee - open_trade.financing
        trades.append(open_trade)
        equity_vals[-1] = cash

    return trades, pd.Series(equity_vals, index=idx, name="equity")


def compute_metrics(trades: list[Trade], equity: pd.Series, initial_cash: float) -> dict[str, float]:
    closed = [t for t in trades if t.exit_time is not None]
    n = len(closed)
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl <= 0]
    win_rate = (len(wins) / n) if n else 0.0
    avg_win = float(np.mean([t.pnl for t in wins])) if wins else 0.0
    avg_loss = float(np.mean([abs(t.pnl) for t in losses])) if losses else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if n else 0.0
    total_pnl = float(sum(t.pnl for t in closed))
    fees = float(sum(t.entry_fee + t.exit_fee + t.financing for t in closed))
    final = float(equity.iloc[-1]) if len(equity) else initial_cash
    net_return = (final / initial_cash) - 1.0
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0
    gp = float(sum(t.pnl for t in wins)) if wins else 0.0
    gl = float(sum(abs(t.pnl) for t in losses)) if losses else 0.0
    pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
    rets = equity.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if len(rets) > 2 and rets.std() > 0 else 0.0
    return {
        "n_trades": float(n),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
        "fees_paid": fees,
        "net_return": net_return,
        "final_equity": final,
        "max_drawdown": max_dd,
        "profit_factor": float(pf),
        "sharpe": sharpe,
    }
