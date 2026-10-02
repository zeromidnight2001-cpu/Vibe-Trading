"""Run 1-year multi-venue strategy study for AU equities + crypto."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine import BacktestResult, compute_metrics, run_symbol_trades
from strategies.defs import STRATEGIES, atr
from venues.fees import asx_venues, crypto_perp_venues, crypto_spot_venues

ASX_SYMBOLS = [
    "BHP.AX",
    "CBA.AX",
    "CSL.AX",
    "NAB.AX",
    "WBC.AX",
    "ANZ.AX",
    "WES.AX",
    "MQG.AX",
    "WOW.AX",
    "TCL.AX",
]
CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]

EVAL_START = "2025-10-01"
EVAL_END = "2026-10-02"
WARMUP_START = "2024-10-01"
INITIAL_CASH = 100_000.0
RISK_FRACTION = 0.10
TARGET_WR = 0.60
MIN_TRADES = 20
ARTIFACTS = ROOT / "artifacts"


def download(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        raw = yf.download(sym, start=WARMUP_START, end=EVAL_END, progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]
        raw = raw.dropna(subset=["Close"]).copy()
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        out[sym] = raw
    return out


def eval_slice(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[(df.index >= EVAL_START) & (df.index < EVAL_END)].copy()


def param_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid.keys())
    combos = []
    for values in itertools.product(*(grid[k] for k in keys)):
        combos.append(dict(zip(keys, values)))
    return combos


def run_portfolio(
    data: dict[str, pd.DataFrame],
    strategy_id: str,
    params: dict[str, Any],
    venue,
    *,
    allow_short: bool,
) -> BacktestResult:
    fn = STRATEGIES[strategy_id]["fn"]
    all_trades = []
    # Equal cash sleeves per symbol
    sleeve = INITIAL_CASH / max(len(data), 1)
    equity_parts = []
    for sym, full in data.items():
        df_full = full.copy()
        signal_full = fn(df_full, {**params, "allow_short": allow_short})
        a_full = atr(df_full, 14)
        # restrict evaluation window but keep signal alignment
        df = eval_slice(df_full)
        if df.empty:
            continue
        signal = signal_full.reindex(df.index).fillna(0).astype(int)
        a = a_full.reindex(df.index)
        trades, curve = run_symbol_trades(
            df,
            signal,
            venue,
            symbol=sym,
            initial_cash=sleeve,
            risk_fraction=RISK_FRACTION,
            tp_atr=float(params["tp_atr"]),
            sl_atr=float(params["sl_atr"]),
            atr=a,
            allow_short=allow_short,
            max_hold_bars=int(params.get("max_hold", 30)),
        )
        all_trades.extend(trades)
        equity_parts.append(curve.rename(sym))

    if not equity_parts:
        empty = pd.Series(dtype=float)
        return BacktestResult(strategy_id, venue.id, params, [], empty, compute_metrics([], empty, INITIAL_CASH))

    # Combine sleeve equities (each starts at sleeve cash)
    eq = pd.concat(equity_parts, axis=1).ffill().fillna(sleeve)
    total_eq = eq.sum(axis=1)
    metrics = compute_metrics(all_trades, total_eq, INITIAL_CASH)
    return BacktestResult(strategy_id, venue.id, params, all_trades, total_eq, metrics)


def score(metrics: dict[str, float]) -> tuple:
    """Higher is better.

    Order of preference:
    1. Enough trades
    2. Positive expectancy after fees
    3. Win rate ≥ 60% when expectancy is positive
    4. Higher net return / Sharpe, shallower drawdown
    """
    n = metrics["n_trades"]
    wr = metrics["win_rate"]
    exp = metrics["expectancy"]
    ret = metrics["net_return"]
    dd = metrics["max_drawdown"]
    sharpe = metrics["sharpe"]
    if n < MIN_TRADES:
        return (-3, n, wr, ret)
    if exp <= 0 or ret <= 0:
        return (-1, ret, wr, exp, -abs(dd))
    wr_bonus = 1 if wr >= TARGET_WR else 0
    return (wr_bonus, ret, wr, sharpe, -abs(dd))


def optimize_strategy(
    data: dict[str, pd.DataFrame],
    strategy_id: str,
    baseline_venue,
    *,
    allow_short: bool,
    max_combos: int = 180,
) -> tuple[dict[str, Any], BacktestResult]:
    grid = STRATEGIES[strategy_id]["grid"]
    combos = param_grid(grid)
    if len(combos) > max_combos:
        rng = np.random.default_rng(42)
        pick = rng.choice(len(combos), size=max_combos, replace=False)
        combos = [combos[i] for i in sorted(pick)]

    best_params = combos[0]
    best_result = run_portfolio(data, strategy_id, best_params, baseline_venue, allow_short=allow_short)
    best_score = score(best_result.metrics)

    for params in combos[1:]:
        result = run_portfolio(data, strategy_id, params, baseline_venue, allow_short=allow_short)
        sc = score(result.metrics)
        if sc > best_score:
            best_score = sc
            best_params = params
            best_result = result
    return best_params, best_result


def make_charts(summary: pd.DataFrame, equity_map: dict[str, pd.Series]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    # 1) Win rate heatmap-like bar: strategy x venue
    pivot_wr = summary.pivot_table(index="strategy", columns="venue", values="win_rate", aggfunc="first")
    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.imshow(pivot_wr.values, aspect="auto", cmap="RdYlGn", vmin=0.35, vmax=0.75)
    ax.set_xticks(range(len(pivot_wr.columns)))
    ax.set_xticklabels(pivot_wr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot_wr.index)))
    ax.set_yticklabels(pivot_wr.index)
    ax.set_title("Win rate by strategy × venue (fee-inclusive)")
    for i in range(pivot_wr.shape[0]):
        for j in range(pivot_wr.shape[1]):
            val = pivot_wr.values[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.0%}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "win_rate_matrix.png", dpi=140)
    plt.close(fig)

    # 2) Net return bars for top venue per strategy
    top = summary.sort_values("net_return", ascending=False).groupby("strategy", as_index=False).first()
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [f"{r.strategy}\n{r.venue}" for r in top.itertuples()]
    colors = ["#2a9d8f" if r.win_rate >= TARGET_WR else "#e9c46a" for r in top.itertuples()]
    ax.bar(labels, top["net_return"] * 100, color=colors)
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_ylabel("Net return %")
    ax.set_title("Best venue per strategy (net return after fees)")
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "best_venue_returns.png", dpi=140)
    plt.close(fig)

    # 3) Equity curves for overall top 5 runs
    top5 = summary.sort_values(["net_return", "win_rate"], ascending=False).head(5)
    fig, ax = plt.subplots(figsize=(11, 5))
    for row in top5.itertuples():
        key = f"{row.strategy}::{row.venue}"
        if key in equity_map:
            eq = equity_map[key]
            ax.plot(eq.index, eq.values / INITIAL_CASH, label=f"{row.strategy}/{row.venue} WR={row.win_rate:.0%}")
    ax.set_title("Equity curves — top 5 profitable venue×strategy combos")
    ax.set_ylabel("Growth of A$1")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "equity_top5.png", dpi=140)
    plt.close(fig)

    # 4) Fees paid vs net PnL scatter
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(summary["fees_paid"], summary["total_pnl"], c=summary["win_rate"], cmap="viridis", s=40)
    ax.set_xlabel("Fees + financing paid")
    ax.set_ylabel("Total trade PnL")
    ax.set_title("Cost drag vs PnL (colour = win rate)")
    fig.colorbar(ax.collections[0], ax=ax, label="win rate")
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "fees_vs_pnl.png", dpi=140)
    plt.close(fig)


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    print("Downloading ASX + crypto data…")
    asx_data = download(ASX_SYMBOLS)
    crypto_data = download(CRYPTO_SYMBOLS)

    rows = []
    equity_map: dict[str, pd.Series] = {}
    best_params_store: dict[str, dict] = {}

    # ---- ASX leg ----
    baseline_asx = next(v for v in asx_venues() if v.id == "pepperstone_cfd")
    for sid in STRATEGIES:
        print(f"[ASX] Optimizing {sid} on {baseline_asx.name}…")
        params, _ = optimize_strategy(asx_data, sid, baseline_asx, allow_short=False, max_combos=220)
        best_params_store[f"asx::{sid}"] = params
        print(f"  best params: {params}")
        for venue in asx_venues():
            result = run_portfolio(asx_data, sid, params, venue, allow_short=False)
            m = result.metrics
            rows.append(
                {
                    "market": "ASX",
                    "strategy": sid,
                    "strategy_name": STRATEGIES[sid]["name"],
                    "venue": venue.id,
                    "venue_name": venue.name,
                    **m,
                    "params_json": json.dumps(params),
                }
            )
            equity_map[f"{sid}::{venue.id}"] = result.equity_curve
            print(
                f"  {venue.id:16s} WR={m['win_rate']:.1%} n={m['n_trades']:.0f} "
                f"ret={m['net_return']:.2%} exp={m['expectancy']:.2f} fees={m['fees_paid']:.0f}"
            )

    # ---- Crypto spot leg ----
    baseline_crypto = next(v for v in crypto_spot_venues() if v.id == "binance_spot")
    for sid in STRATEGIES:
        print(f"[CRYPTO] Optimizing {sid} on {baseline_crypto.name}…")
        params, _ = optimize_strategy(crypto_data, sid, baseline_crypto, allow_short=True)
        best_params_store[f"crypto::{sid}"] = params
        print(f"  best params: {params}")
        for venue in crypto_spot_venues() + crypto_perp_venues():
            result = run_portfolio(crypto_data, sid, params, venue, allow_short=True)
            m = result.metrics
            rows.append(
                {
                    "market": "CRYPTO",
                    "strategy": sid,
                    "strategy_name": STRATEGIES[sid]["name"],
                    "venue": venue.id,
                    "venue_name": venue.name,
                    **m,
                    "params_json": json.dumps(params),
                }
            )
            equity_map[f"{sid}::{venue.id}"] = result.equity_curve
            print(
                f"  {venue.id:16s} WR={m['win_rate']:.1%} n={m['n_trades']:.0f} "
                f"ret={m['net_return']:.2%} exp={m['expectancy']:.2f} fees={m['fees_paid']:.0f}"
            )

    summary = pd.DataFrame(rows)
    summary.to_csv(ARTIFACTS / "summary.csv", index=False)
    (ARTIFACTS / "best_params.json").write_text(json.dumps(best_params_store, indent=2))

    make_charts(summary, equity_map)

    # Ranked leaders
    leaders = summary.sort_values(["net_return", "win_rate"], ascending=False)
    leaders.head(20).to_csv(ARTIFACTS / "top20.csv", index=False)

    wr_ok = summary[summary["win_rate"] >= TARGET_WR].sort_values("net_return", ascending=False)
    wr_ok.to_csv(ARTIFACTS / "winrate_ge_60.csv", index=False)

    report = []
    report.append("# Results — 1y fee-inclusive multi-venue study\n")
    report.append(f"Evaluation window: **{EVAL_START} → {EVAL_END}**  \n")
    report.append(f"Starting capital: **A${INITIAL_CASH:,.0f}**  \n")
    report.append(f"Win-rate target: **{TARGET_WR:.0%}** (with positive expectancy preferred)\n")
    report.append("\n## Top 10 by net return\n")
    report.append(
        leaders.head(10)[
            ["market", "strategy", "venue_name", "win_rate", "n_trades", "net_return", "fees_paid", "max_drawdown", "sharpe"]
        ].to_markdown(index=False)
    )
    report.append("\n\n## Combos with win rate ≥ 60%\n")
    if len(wr_ok):
        report.append(
            wr_ok.head(15)[
                ["market", "strategy", "venue_name", "win_rate", "n_trades", "net_return", "expectancy", "fees_paid"]
            ].to_markdown(index=False)
        )
    else:
        report.append("_None reached 60% with the trade-count floor; see nearest candidates in summary.csv._\n")
    report.append("\n\n## Best strategy per market (by net return)\n")
    for market in ["ASX", "CRYPTO"]:
        sub = leaders[leaders["market"] == market].iloc[0]
        report.append(
            f"- **{market}**: `{sub.strategy}` on **{sub.venue_name}** — "
            f"WR {sub.win_rate:.1%}, net return {sub.net_return:.2%}, "
            f"fees A${sub.fees_paid:,.0f}, max DD {sub.max_drawdown:.1%}\n"
        )
    report.append("\nCharts: `win_rate_matrix.png`, `best_venue_returns.png`, `equity_top5.png`, `fees_vs_pnl.png`\n")
    (ARTIFACTS / "REPORT.md").write_text("".join(report))
    print("\nWrote artifacts to", ARTIFACTS)
    print(leaders.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
